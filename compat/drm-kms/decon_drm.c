// SPDX-License-Identifier: GPL-2.0-only
/*
 * Standard KMS/PRIME presentation for Samsung Exynos8895 DECON.
 * The existing DECON driver owns panel, DPP, IOMMU and power programming.
 */
#include <linux/dma-buf.h>
#include <linux/exynos_ion.h>
#include <linux/ion.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/reservation.h>
#include <linux/sizes.h>
#include <linux/workqueue.h>
#include <drm/drmP.h>
#include <drm/drm_crtc_helper.h>
#include <drm/drm_fourcc.h>
#include <drm/drm_gem.h>
#include <drm/drm_plane_helper.h>
#include "decon.h"
#include "decon_drm.h"

struct decon_drm_buffer {
	struct drm_gem_object base;
	struct dma_buf *buffer;
};

struct decon_drm_fb {
	struct drm_framebuffer base;
	struct drm_gem_object *object;
};

struct decon_drm {
	struct drm_device *drm;
	struct decon_device *decon;
	struct drm_crtc crtc;
	struct drm_plane primary;
	struct drm_connector connector;
	struct drm_encoder encoder;
	struct workqueue_struct *workqueue;
	struct work_struct flip_work;
	struct mutex commit_lock;
	spinlock_t pending_lock;
	struct drm_framebuffer *scanout_fb;
	struct drm_framebuffer *pending;
	struct drm_pending_vblank_event *event;
	bool stopping;
	bool deferred;
	int error;
};

#define to_decon_buffer(obj) container_of(obj, struct decon_drm_buffer, base)
#define to_decon_fb(fb) container_of(fb, struct decon_drm_fb, base)
#define to_decon_crtc(c) container_of(c, struct decon_drm, crtc)

static void decon_gem_free(struct drm_gem_object *object)
{
	struct decon_drm_buffer *buffer = to_decon_buffer(object);

	drm_gem_free_mmap_offset(object);
	dma_buf_put(buffer->buffer);
	drm_gem_object_release(object);
	kfree(buffer);
}

static struct drm_gem_object *decon_gem_import(struct drm_device *drm,
					      struct dma_buf *dma_buf)
{
	struct decon_drm_buffer *buffer;

	if (!dma_buf->size || dma_buf->size > SZ_64M)
		return ERR_PTR(-EINVAL);
	buffer = kzalloc(sizeof(*buffer), GFP_KERNEL);
	if (!buffer)
		return ERR_PTR(-ENOMEM);
	drm_gem_private_object_init(drm, &buffer->base, dma_buf->size);
	get_dma_buf(dma_buf);
	buffer->buffer = dma_buf;
	return &buffer->base;
}

static struct dma_buf *decon_gem_export(struct drm_device *drm,
					struct drm_gem_object *object, int flags)
{
	struct dma_buf *dma_buf = to_decon_buffer(object)->buffer;

	get_dma_buf(dma_buf);
	return dma_buf;
}

static int decon_dumb_create(struct drm_file *file, struct drm_device *drm,
			      struct drm_mode_create_dumb *args)
{
	struct decon_drm *display = drm->dev_private;
	struct drm_gem_object *object;
	struct ion_handle *handle;
	struct dma_buf *dma_buf;
	u64 pitch, size;
	int ret;

	if (args->bpp != 32 || !args->width || !args->height ||
	    args->width > 4096 || args->height > 4096)
		return -EINVAL;
	pitch = ALIGN((u64)args->width * 4, 64);
	size = PAGE_ALIGN(pitch * args->height);
	if (size > SZ_64M)
		return -EINVAL;
	handle = ion_alloc(display->decon->ion_client, size, 0,
			   EXYNOS_ION_HEAP_SYSTEM_MASK, 0);
	if (IS_ERR(handle))
		return PTR_ERR(handle);
	dma_buf = ion_share_dma_buf(display->decon->ion_client, handle);
	ion_free(display->decon->ion_client, handle);
	if (IS_ERR(dma_buf))
		return PTR_ERR(dma_buf);
	object = decon_gem_import(drm, dma_buf);
	dma_buf_put(dma_buf);
	if (IS_ERR(object))
		return PTR_ERR(object);
	ret = drm_gem_handle_create(file, object, &args->handle);
	drm_gem_object_unreference_unlocked(object);
	if (!ret) {
		args->pitch = pitch;
		args->size = size;
	}
	return ret;
}

static int decon_dumb_map(struct drm_file *file, struct drm_device *drm,
			   u32 handle, u64 *offset)
{
	struct drm_gem_object *object = drm_gem_object_lookup(drm, file, handle);
	int ret;

	if (!object)
		return -ENOENT;
	ret = drm_gem_create_mmap_offset(object);
	if (!ret)
		*offset = drm_vma_node_offset_addr(&object->vma_node);
	drm_gem_object_unreference_unlocked(object);
	return ret;
}

static const struct vm_operations_struct decon_gem_vm_ops = {
	.open = drm_gem_vm_open,
	.close = drm_gem_vm_close,
};

static int decon_gem_mmap(struct file *file, struct vm_area_struct *vma)
{
	struct drm_gem_object *object;
	struct dma_buf *dma_buf;
	unsigned long flags = vma->vm_flags;
	int ret;

	/* This verifies that the caller owns the object at the requested offset. */
	ret = drm_gem_mmap(file, vma);
	if (ret)
		return ret;
	object = vma->vm_private_data;
	dma_buf = to_decon_buffer(object)->buffer;
	get_dma_buf(dma_buf);
	drm_gem_vm_close(vma);
	vma->vm_private_data = NULL;
	vma->vm_ops = NULL;
	vma->vm_flags = flags;
	ret = dma_buf_mmap(dma_buf, vma, 0);
	dma_buf_put(dma_buf);
	return ret;
}

static void decon_fb_destroy(struct drm_framebuffer *fb)
{
	struct decon_drm_fb *framebuffer = to_decon_fb(fb);

	drm_framebuffer_cleanup(fb);
	drm_gem_object_unreference_unlocked(framebuffer->object);
	kfree(framebuffer);
}

static int decon_fb_handle(struct drm_framebuffer *fb,
			    struct drm_file *file, unsigned int *handle)
{
	return drm_gem_handle_create(file, to_decon_fb(fb)->object, handle);
}

static const struct drm_framebuffer_funcs decon_fb_funcs = {
	.destroy = decon_fb_destroy,
	.create_handle = decon_fb_handle,
};

static int decon_pixel_format(u32 format)
{
	switch (format) {
	case DRM_FORMAT_XBGR8888:
		return DECON_PIXEL_FORMAT_RGBX_8888;
	case DRM_FORMAT_ABGR8888:
		return DECON_PIXEL_FORMAT_RGBA_8888;
	case DRM_FORMAT_XRGB8888:
		return DECON_PIXEL_FORMAT_BGRX_8888;
	case DRM_FORMAT_ARGB8888:
		return DECON_PIXEL_FORMAT_BGRA_8888;
	default:
		return -EINVAL;
	}
}

static struct drm_framebuffer *decon_fb_create(struct drm_device *drm,
			struct drm_file *file, struct drm_mode_fb_cmd2 *mode)
{
	struct decon_drm *display = drm->dev_private;
	struct decon_lcd *lcd = display->decon->lcd_info;
	struct decon_drm_fb *fb;
	struct drm_gem_object *object;
	u64 required;
	int ret;

	if (mode->width != lcd->xres || mode->height != lcd->yres ||
	    mode->flags || mode->offsets[0] ||
	    mode->pitches[0] < (u64)mode->width * 4 ||
	    mode->pitches[0] > 4096 * 4 || mode->pitches[0] % 4 ||
	    decon_pixel_format(mode->pixel_format) < 0)
		return ERR_PTR(-EINVAL);
	if (mode->handles[1] || mode->handles[2] || mode->handles[3])
		return ERR_PTR(-EINVAL);
	object = drm_gem_object_lookup(drm, file, mode->handles[0]);
	if (!object)
		return ERR_PTR(-ENOENT);
	required = (u64)mode->pitches[0] * mode->height;
	if (required > object->size) {
		ret = -EINVAL;
		goto put_object;
	}
	fb = kzalloc(sizeof(*fb), GFP_KERNEL);
	if (!fb) {
		ret = -ENOMEM;
		goto put_object;
	}
	drm_helper_mode_fill_fb_struct(&fb->base, mode);
	fb->object = object;
	ret = drm_framebuffer_init(drm, &fb->base, &decon_fb_funcs);
	if (ret) {
		kfree(fb);
		goto put_object;
	}
	return &fb->base;

put_object:
	drm_gem_object_unreference_unlocked(object);
	return ERR_PTR(ret);
}

static const struct drm_mode_config_funcs decon_mode_funcs = {
	.fb_create = decon_fb_create,
};

static int decon_commit_frame(struct decon_drm *display,
			       struct drm_framebuffer *fb)
{
	struct decon_drm_buffer *buffer =
		to_decon_buffer(to_decon_fb(fb)->object);
	struct decon_drm_frame frame = {
		.buffer = buffer->buffer,
		.width = fb->width,
		.height = fb->height,
		.pitch = fb->pitches[0],
		.format = decon_pixel_format(fb->pixel_format),
	};
	long ready;

	/* Scanout reads the buffer, so wait for its exclusive render writer. */
	ready = reservation_object_wait_timeout_rcu(buffer->buffer->resv,
						     false, false, HZ);
	if (ready <= 0)
		return ready < 0 ? ready : -ETIMEDOUT;
	return decon_drm_present(display->decon, &frame);
}

static void decon_complete_event(struct decon_drm *display,
		struct drm_pending_vblank_event *event, int error)
{
	struct drm_device *drm = display->drm;
	unsigned long flags;

	spin_lock_irqsave(&drm->event_lock, flags);
	if (event) {
		if (!error)
			drm_send_vblank_event(drm, 0, event);
		else {
			event->base.file_priv->event_space += sizeof(event->event);
			wake_up_interruptible(&event->base.file_priv->event_wait);
			kfree(event);
		}
	}
	spin_unlock_irqrestore(&drm->event_lock, flags);
	drm_vblank_put(drm, 0);
}

static void decon_flip_work(struct work_struct *work)
{
	struct decon_drm *display =
		container_of(work, struct decon_drm, flip_work);
	struct drm_framebuffer *fb, *old = NULL;
	struct drm_pending_vblank_event *event;
	unsigned long flags;
	int ret;

	mutex_lock(&display->commit_lock);
	spin_lock_irqsave(&display->pending_lock, flags);
	fb = display->pending;
	event = display->event;
	spin_unlock_irqrestore(&display->pending_lock, flags);
	if (!fb) {
		mutex_unlock(&display->commit_lock);
		return;
	}
	ret = display->stopping ? -ENODEV : decon_commit_frame(display, fb);
	if (ret == -EAGAIN && !display->stopping &&
	    READ_ONCE(display->decon->drm_owned)) {
		/* fbcon/system suspend can blank after the ioctl was accepted.
		 * Retain the buffer and its event until a real post-unblank frame.
		 * Never acknowledge a flip that did not reach the panel. */
		spin_lock_irqsave(&display->pending_lock, flags);
		display->deferred = true;
		spin_unlock_irqrestore(&display->pending_lock, flags);
		/* Close the race with a concurrent unblank notification. */
		if (READ_ONCE(display->decon->state) != DECON_STATE_OFF)
			queue_work(display->workqueue, &display->flip_work);
		mutex_unlock(&display->commit_lock);
		return;
	}
	if (!ret) {
		old = display->scanout_fb;
		display->scanout_fb = fb;
	} else {
		WRITE_ONCE(display->error, ret);
		DRM_ERROR("DECON page flip failed: %d\n", ret);
	}
	spin_lock_irqsave(&display->pending_lock, flags);
	display->pending = NULL;
	display->event = NULL;
	display->deferred = false;
	spin_unlock_irqrestore(&display->pending_lock, flags);
	mutex_unlock(&display->commit_lock);

	/* New submissions may now requeue this ordered work item. */
	decon_complete_event(display, event, ret);
	if (old)
		drm_framebuffer_unreference(old);
	if (ret)
		drm_framebuffer_unreference(fb);
}

static void decon_cancel_pending(struct decon_drm *display,
				struct drm_file *file)
{
	struct drm_framebuffer *fb = NULL;
	struct drm_pending_vblank_event *event = NULL;
	unsigned long flags;

	mutex_lock(&display->commit_lock);
	spin_lock_irqsave(&display->pending_lock, flags);
	if (display->pending && (!file ||
	    (display->event && display->event->base.file_priv == file) ||
	    (!display->event && file->is_master))) {
		fb = display->pending;
		event = display->event;
		display->pending = NULL;
		display->event = NULL;
		display->deferred = false;
	}
	spin_unlock_irqrestore(&display->pending_lock, flags);
	mutex_unlock(&display->commit_lock);
	if (fb) {
		decon_complete_event(display, event, -ECANCELED);
		drm_framebuffer_unreference(fb);
	}
}

void decon_drm_power_state(struct decon_device *decon, bool active)
{
	struct decon_drm *display;
	unsigned long flags;

	rcu_read_lock();
	display = rcu_dereference(decon->native_drm);
	if (display) {
		drm_object_property_set_value(&display->connector.base,
			display->drm->mode_config.dpms_property,
			active ? DRM_MODE_DPMS_ON : DRM_MODE_DPMS_OFF);
		spin_lock_irqsave(&display->pending_lock, flags);
		if (active && display->deferred && !display->stopping)
			queue_work(display->workqueue, &display->flip_work);
		spin_unlock_irqrestore(&display->pending_lock, flags);
	}
	rcu_read_unlock();
}

static int decon_page_flip(struct drm_crtc *crtc, struct drm_framebuffer *fb,
			    struct drm_pending_vblank_event *event, u32 flags)
{
	struct decon_drm *display = to_decon_crtc(crtc);
	unsigned long irqflags;
	int ret;

	if (flags & DRM_MODE_PAGE_FLIP_ASYNC)
		return -EINVAL;
	ret = drm_vblank_get(crtc->dev, 0);
	if (ret)
		return ret;
	spin_lock_irqsave(&display->pending_lock, irqflags);
	if (display->pending || display->stopping || READ_ONCE(display->error)) {
		ret = READ_ONCE(display->error);
		if (!ret)
			ret = display->stopping ? -ENODEV : -EBUSY;
		spin_unlock_irqrestore(&display->pending_lock, irqflags);
		drm_vblank_put(crtc->dev, 0);
		return ret;
	}
	drm_framebuffer_reference(fb);
	display->pending = fb;
	display->event = event;
	queue_work(display->workqueue, &display->flip_work);
	spin_unlock_irqrestore(&display->pending_lock, irqflags);
	return 0;
}

static void decon_crtc_dpms(struct drm_crtc *crtc, int mode)
{
	struct decon_drm *display = to_decon_crtc(crtc);
	int ret;

	flush_workqueue(display->workqueue);
	mutex_lock(&display->commit_lock);
	if (display->stopping || !READ_ONCE(display->decon->drm_owned)) {
		mutex_unlock(&display->commit_lock);
		return;
	}
	ret = decon_drm_power(display->decon, mode == DRM_MODE_DPMS_ON);
	if (ret) {
		WRITE_ONCE(display->error, ret);
		DRM_ERROR("DECON display power transition failed: %d\n", ret);
	} else
		WRITE_ONCE(display->error, 0);
	mutex_unlock(&display->commit_lock);
}

static bool decon_mode_fixup(struct drm_crtc *crtc,
			      const struct drm_display_mode *mode,
			      struct drm_display_mode *adjusted)
{
	struct decon_drm *display = to_decon_crtc(crtc);

	return mode->hdisplay == display->decon->lcd_info->xres &&
	       mode->vdisplay == display->decon->lcd_info->yres &&
	       !(mode->flags & DRM_MODE_FLAG_INTERLACE);
}

static int decon_mode_base(struct drm_crtc *crtc, int x, int y,
			    struct drm_framebuffer *old_fb)
{
	struct decon_drm *display = to_decon_crtc(crtc);
	struct drm_framebuffer *fb = crtc->primary->fb;
	struct drm_framebuffer *old = NULL;
	int ret;

	if (x || y || !fb)
		return -EINVAL;
	flush_workqueue(display->workqueue);
	mutex_lock(&display->commit_lock);
	if (display->stopping) {
		mutex_unlock(&display->commit_lock);
		return -ENODEV;
	}
	ret = decon_drm_claim(display->decon);
	if (!ret)
		ret = decon_drm_power(display->decon, true);
	if (!ret)
		ret = decon_commit_frame(display, fb);
	if (!ret) {
		drm_framebuffer_reference(fb);
		old = display->scanout_fb;
		display->scanout_fb = fb;
		WRITE_ONCE(display->error, 0);
	}
	mutex_unlock(&display->commit_lock);
	if (old)
		drm_framebuffer_unreference(old);
	return ret;
}

static int decon_mode_set(struct drm_crtc *crtc,
			   struct drm_display_mode *mode,
			   struct drm_display_mode *adjusted,
			   int x, int y, struct drm_framebuffer *old_fb)
{
	return decon_mode_base(crtc, x, y, old_fb);
}

static void decon_crtc_prepare(struct drm_crtc *crtc)
{
}

static void decon_crtc_commit(struct drm_crtc *crtc)
{
}

static const struct drm_crtc_helper_funcs decon_crtc_helpers = {
	.dpms = decon_crtc_dpms,
	.mode_fixup = decon_mode_fixup,
	.mode_set = decon_mode_set,
	.mode_set_base = decon_mode_base,
	.prepare = decon_crtc_prepare,
	.commit = decon_crtc_commit,
};

static const struct drm_crtc_funcs decon_crtc_funcs = {
	.set_config = drm_crtc_helper_set_config,
	.page_flip = decon_page_flip,
	.destroy = drm_crtc_cleanup,
};

static int decon_connector_modes(struct drm_connector *connector)
{
	struct decon_drm *display =
		container_of(connector, struct decon_drm, connector);
	struct decon_lcd *lcd = display->decon->lcd_info;
	struct drm_display_mode *mode = drm_mode_create(connector->dev);

	if (!mode)
		return 0;
	mode->hdisplay = lcd->xres;
	mode->hsync_start = mode->hdisplay + lcd->hfp;
	mode->hsync_end = mode->hsync_start + lcd->hsa;
	mode->htotal = mode->hsync_end + lcd->hbp;
	mode->vdisplay = lcd->yres;
	mode->vsync_start = mode->vdisplay + lcd->vfp;
	mode->vsync_end = mode->vsync_start + lcd->vsa;
	mode->vtotal = mode->vsync_end + lcd->vbp;
	mode->clock = (u64)mode->htotal * mode->vtotal * lcd->fps / 1000;
	mode->type = DRM_MODE_TYPE_DRIVER | DRM_MODE_TYPE_PREFERRED;
	drm_mode_set_name(mode);
	drm_mode_probed_add(connector, mode);
	connector->display_info.width_mm = lcd->width;
	connector->display_info.height_mm = lcd->height;
	return 1;
}

static enum drm_connector_status
decon_connector_detect(struct drm_connector *connector, bool force)
{
	return connector_status_connected;
}

static struct drm_encoder *decon_best_encoder(struct drm_connector *connector)
{
	struct decon_drm *display =
		container_of(connector, struct decon_drm, connector);

	return &display->encoder;
}

static const struct drm_connector_helper_funcs decon_connector_helpers = {
	.get_modes = decon_connector_modes,
	.best_encoder = decon_best_encoder,
};

static const struct drm_connector_funcs decon_connector_funcs = {
	.dpms = drm_helper_connector_dpms,
	.detect = decon_connector_detect,
	.fill_modes = drm_helper_probe_single_connector_modes,
	.destroy = drm_connector_cleanup,
};

static const struct drm_encoder_funcs decon_encoder_funcs = {
	.destroy = drm_encoder_cleanup,
};

static void decon_encoder_dpms(struct drm_encoder *encoder, int mode)
{
}

static bool decon_encoder_fixup(struct drm_encoder *encoder,
				 const struct drm_display_mode *mode,
				 struct drm_display_mode *adjusted)
{
	return true;
}

static void decon_encoder_prepare(struct drm_encoder *encoder)
{
}

static void decon_encoder_commit(struct drm_encoder *encoder)
{
}

static void decon_encoder_mode(struct drm_encoder *encoder,
				struct drm_display_mode *mode,
				struct drm_display_mode *adjusted)
{
}

static const struct drm_encoder_helper_funcs decon_encoder_helpers = {
	.dpms = decon_encoder_dpms,
	.mode_fixup = decon_encoder_fixup,
	.prepare = decon_encoder_prepare,
	.commit = decon_encoder_commit,
	.mode_set = decon_encoder_mode,
};

static int decon_enable_vblank(struct drm_device *drm, unsigned int pipe)
{
	return pipe ? -EINVAL : 0;
}

static void decon_disable_vblank(struct drm_device *drm, unsigned int pipe)
{
}

void decon_drm_vblank(struct decon_device *decon)
{
	struct decon_drm *display;

	rcu_read_lock();
	display = rcu_dereference(decon->native_drm);
	if (display)
		drm_handle_vblank(display->drm, 0);
	rcu_read_unlock();
}

static void decon_preclose(struct drm_device *drm, struct drm_file *file)
{
	struct decon_drm *display = drm->dev_private;

	/* A deferred flip must not outlive the destination drm_file. */
	flush_workqueue(display->workqueue);
	decon_cancel_pending(display, file);
	flush_workqueue(display->workqueue);
}

static void decon_master_drop(struct drm_device *drm,
			       struct drm_file *file, bool from_release)
{
	struct decon_drm *display = drm->dev_private;

	flush_workqueue(display->workqueue);
	decon_cancel_pending(display, file);
	flush_workqueue(display->workqueue);
	mutex_lock(&display->commit_lock);
	if (!display->stopping)
		decon_drm_release(display->decon);
	if (display->scanout_fb) {
		drm_framebuffer_unreference(display->scanout_fb);
		display->scanout_fb = NULL;
	}
	display->error = 0;
	mutex_unlock(&display->commit_lock);
}

static unsigned int decon_drm_poll(struct file *file, poll_table *wait)
{
	struct drm_file *priv = file->private_data;
	struct decon_drm *display = priv->minor->dev->dev_private;
	unsigned int events = drm_poll(file, wait);

	if (READ_ONCE(display->error))
		events |= POLLERR;
	return events;
}

static const struct file_operations decon_drm_fops = {
	.owner = THIS_MODULE,
	.open = drm_open,
	.release = drm_release,
	.unlocked_ioctl = drm_ioctl,
#ifdef CONFIG_COMPAT
	.compat_ioctl = drm_compat_ioctl,
#endif
	.poll = decon_drm_poll,
	.read = drm_read,
	.mmap = decon_gem_mmap,
	.llseek = noop_llseek,
};

static int decon_drm_unload(struct drm_device *drm)
{
	struct decon_drm *display = drm->dev_private;

	drm_mode_config_cleanup(drm);
	destroy_workqueue(display->workqueue);
	kfree(display);
	return 0;
}

static struct drm_driver decon_drm_driver = {
	.driver_features = DRIVER_MODESET | DRIVER_GEM | DRIVER_PRIME,
	.unload = decon_drm_unload,
	.preclose = decon_preclose,
	.master_drop = decon_master_drop,
	.get_vblank_counter = drm_vblank_no_hw_counter,
	.enable_vblank = decon_enable_vblank,
	.disable_vblank = decon_disable_vblank,
	.gem_free_object = decon_gem_free,
	.gem_vm_ops = &decon_gem_vm_ops,
	.dumb_create = decon_dumb_create,
	.dumb_map_offset = decon_dumb_map,
	.dumb_destroy = drm_gem_dumb_destroy,
	.prime_fd_to_handle = drm_gem_prime_fd_to_handle,
	.prime_handle_to_fd = drm_gem_prime_handle_to_fd,
	.gem_prime_import = decon_gem_import,
	.gem_prime_export = decon_gem_export,
	.fops = &decon_drm_fops,
	.name = "g955n-decon",
	.desc = "Exynos8895 DECON DMA-BUF scanout",
	.date = "20261120",
	.major = 1,
	.minor = 1,
};

static const struct drm_plane_funcs decon_primary_funcs = {
	.update_plane = drm_primary_helper_update,
	.disable_plane = drm_primary_helper_disable,
	.destroy = drm_plane_cleanup,
};

static const u32 decon_formats[] = {
	DRM_FORMAT_XRGB8888,
	DRM_FORMAT_ARGB8888,
	DRM_FORMAT_XBGR8888,
	DRM_FORMAT_ABGR8888,
};

int decon_drm_register(struct decon_device *decon)
{
	struct decon_drm *display;
	struct drm_device *drm;
	int ret;

	if (decon->id || decon->dt.out_type != DECON_OUT_DSI ||
	    !of_property_read_bool(decon->dev->of_node, "samsung,drm-scanout"))
		return 0;
	display = kzalloc(sizeof(*display), GFP_KERNEL);
	if (!display)
		return -ENOMEM;
	drm = drm_dev_alloc(&decon_drm_driver, decon->dev);
	if (IS_ERR_OR_NULL(drm)) {
		ret = drm ? PTR_ERR(drm) : -ENOMEM;
		kfree(display);
		return ret;
	}
	display->stopping = true;
	display->drm = drm;
	display->decon = decon;
	drm->dev_private = display;
	ret = drm_dev_set_unique(drm, "g955n-decon:%s", dev_name(decon->dev));
	if (ret)
		goto unref_device;
	mutex_init(&display->commit_lock);
	spin_lock_init(&display->pending_lock);
	INIT_WORK(&display->flip_work, decon_flip_work);
	display->workqueue = alloc_ordered_workqueue("g955n-drm",
						    WQ_MEM_RECLAIM | WQ_FREEZABLE);
	if (!display->workqueue) {
		ret = -ENOMEM;
		goto unref_device;
	}
	drm_mode_config_init(drm);
	drm->mode_config.funcs = &decon_mode_funcs;
	drm->mode_config.min_width = decon->lcd_info->xres;
	drm->mode_config.max_width = decon->lcd_info->xres;
	drm->mode_config.min_height = decon->lcd_info->yres;
	drm->mode_config.max_height = decon->lcd_info->yres;
	ret = drm_universal_plane_init(drm, &display->primary, 1,
					&decon_primary_funcs, decon_formats,
					ARRAY_SIZE(decon_formats),
					DRM_PLANE_TYPE_PRIMARY);
	if (ret)
		goto cleanup_modes;
	ret = drm_crtc_init_with_planes(drm, &display->crtc, &display->primary,
					 NULL, &decon_crtc_funcs);
	if (ret)
		goto cleanup_modes;
	drm_crtc_helper_add(&display->crtc, &decon_crtc_helpers);
	ret = drm_encoder_init(drm, &display->encoder, &decon_encoder_funcs,
			       DRM_MODE_ENCODER_DSI);
	if (ret)
		goto cleanup_modes;
	drm_encoder_helper_add(&display->encoder, &decon_encoder_helpers);
	display->encoder.possible_crtcs = 1;
	ret = drm_connector_init(drm, &display->connector, &decon_connector_funcs,
				 DRM_MODE_CONNECTOR_DSI);
	if (ret)
		goto cleanup_modes;
	drm_connector_helper_add(&display->connector, &decon_connector_helpers);
	ret = drm_mode_connector_attach_encoder(&display->connector,
						 &display->encoder);
	if (ret)
		goto cleanup_modes;
	ret = drm_vblank_init(drm, 1);
	if (ret)
		goto cleanup_modes;
	drm_mode_config_reset(drm);
	ret = drm_dev_register(drm, 0);
	if (ret)
		goto cleanup_vblank;
	ret = drm_connector_register(&display->connector);
	if (ret)
		goto unregister_device;
	rcu_assign_pointer(decon->native_drm, display);
	WRITE_ONCE(display->stopping, false);
	dev_info(decon->dev, "DRM/KMS PRIME scanout registered\n");
	return 0;

unregister_device:
	/* Registration did not enable commits; no parent ownership exists. */
	drm_device_set_unplugged(drm);
	drm_unplug_dev(drm);
	return ret;
cleanup_vblank:
	drm_vblank_cleanup(drm);
cleanup_modes:
	drm_mode_config_cleanup(drm);
	destroy_workqueue(display->workqueue);
unref_device:
	drm->dev_private = NULL;
	drm_dev_unref(drm);
	kfree(display);
	return ret;
}

void decon_drm_unregister(struct decon_device *decon)
{
	struct decon_drm *display = decon->native_drm;

	if (!display)
		return;
	drm_device_set_unplugged(display->drm);
	drm_modeset_lock_all(display->drm);
	spin_lock_irq(&display->pending_lock);
	display->stopping = true;
	spin_unlock_irq(&display->pending_lock);
	RCU_INIT_POINTER(decon->native_drm, NULL);
	synchronize_rcu();
	flush_workqueue(display->workqueue);
	decon_cancel_pending(display, NULL);
	/* Finish hardware ownership before the parent DECON can disappear. */
	decon_drm_release(decon);
	if (display->scanout_fb) {
		drm_framebuffer_unreference(display->scanout_fb);
		display->scanout_fb = NULL;
	}
	drm_connector_unregister(&display->connector);
	drm_modeset_unlock_all(display->drm);
	/* The DRM core defers unload until the last open file closes. */
	drm_unplug_dev(display->drm);
}
