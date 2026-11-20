/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef G955N_DECON_DRM_H
#define G955N_DECON_DRM_H

#include <linux/types.h>

struct decon_device;
struct dma_buf;

struct decon_drm_frame {
	struct dma_buf *buffer;
	unsigned int width;
	unsigned int height;
	unsigned int pitch;
	unsigned int format;
};

#ifdef CONFIG_DRM_EXYNOS8895_NATIVE
int decon_drm_register(struct decon_device *decon);
void decon_drm_unregister(struct decon_device *decon);
void decon_drm_vblank(struct decon_device *decon);
void decon_drm_power_state(struct decon_device *decon, bool active);
int decon_drm_present(struct decon_device *decon,
		      const struct decon_drm_frame *frame);
int decon_drm_power(struct decon_device *decon, bool enabled);
int decon_drm_claim(struct decon_device *decon);
void decon_drm_release(struct decon_device *decon);
#else
static inline int decon_drm_register(struct decon_device *decon) { return 0; }
static inline void decon_drm_unregister(struct decon_device *decon) {}
static inline void decon_drm_vblank(struct decon_device *decon) {}
static inline void decon_drm_power_state(struct decon_device *decon, bool active) {}
#endif
#endif
