/* SPDX-License-Identifier: GPL-2.0-only */
/* Standard KMS/PRIME presentation. No CPU mapping or pixel transfer. */
#define _GNU_SOURCE
#include "drm-output.h"
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <xf86drm.h>
#include <xf86drmMode.h>
#include <drm_fourcc.h>

enum {
    PANEL_WIDTH = 1440, PANEL_HEIGHT = 2960, CACHE_SIZE = 8,
    FLIP_TIMEOUT_MS = 1500, FLIP_POLL_SLICE_MS = 25,
};
struct frame_entry {
    uint32_t handle, fb, pitch, format;
    uint64_t used;
};
struct g955n_kms {
    int fd;
    uint32_t crtc, connector, dpms_property, current_fb, pending_fb;
    drmModeModeInfo mode;
    struct frame_entry cache[CACHE_SIZE];
    uint64_t age, completions;
};

static uint64_t clock_milliseconds(clockid_t clock)
{
    struct timespec now;
    clock_gettime(clock, &now);
    return (uint64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}

static uint64_t milliseconds(void)
{
    return clock_milliseconds(CLOCK_MONOTONIC);
}

static int wait_readable(int fd, uint64_t deadline)
{
    for (;;) {
        uint64_t now = milliseconds();
        struct pollfd pollfd = { .fd = fd, .events = POLLIN };
        int result = poll(&pollfd, 1, now < deadline ? (int)(deadline - now) : 0);
        if (result < 0 && errno == EINTR)
            continue;
        if (result < 0)
            return -errno;
        if (!result)
            return -ETIMEDOUT;
        if (pollfd.revents & (POLLERR | POLLHUP | POLLNVAL))
            return -EIO;
        if (pollfd.revents & POLLIN)
            return 0;
    }
}

static void close_handle(int fd, uint32_t handle)
{
    struct drm_gem_close args = { .handle = handle };
    drmIoctl(fd, DRM_IOCTL_GEM_CLOSE, &args);
}

void g955n_kms_close(struct g955n_kms *output)
{
    if (!output)
        return;
    /* Closing the DRM file removes its framebuffers before master_drop;
     * the driver then restores fbdev. Do not drop master before RmFB. */
    close(output->fd);
    free(output);
}

int g955n_kms_open(struct g955n_kms **result)
{
    if (!result)
        return -EINVAL;
    *result = NULL;
    for (unsigned card = 0; card < 16; ++card) {
        char path[64];
        snprintf(path, sizeof(path), "/dev/dri/card%u", card);
        int fd = open(path, O_RDWR | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK);
        if (fd < 0)
            continue;
        drmVersionPtr version = drmGetVersion(fd);
        bool matches = version && version->name &&
                       version->name_len == strlen("g955n-decon") &&
                       !memcmp(version->name, "g955n-decon", version->name_len) &&
                       version->version_major == 1 && version->version_minor >= 1;
        drmFreeVersion(version);
        uint64_t prime = 0;
        if (!matches || drmGetCap(fd, DRM_CAP_PRIME, &prime) ||
            !(prime & DRM_PRIME_CAP_IMPORT)) {
            close(fd);
            continue;
        }
        drmModeResPtr resources = drmModeGetResources(fd);
        if (!resources) {
            close(fd);
            continue;
        }
        struct g955n_kms *output = calloc(1, sizeof(*output));
        if (!output) {
            drmModeFreeResources(resources);
            close(fd);
            return -ENOMEM;
        }
        output->fd = fd;
        for (int i = 0; i < resources->count_connectors && !output->connector; ++i) {
            drmModeConnectorPtr connector = drmModeGetConnector(fd, resources->connectors[i]);
            if (!connector)
                continue;
            if (connector->connection == DRM_MODE_CONNECTED &&
                connector->connector_type == DRM_MODE_CONNECTOR_DSI) {
                for (int m = 0; m < connector->count_modes && !output->connector; ++m) {
                    drmModeModeInfo mode = connector->modes[m];
                    if (mode.hdisplay != PANEL_WIDTH || mode.vdisplay != PANEL_HEIGHT ||
                        mode.flags & DRM_MODE_FLAG_INTERLACE)
                        continue;
                    for (int e = 0; e < connector->count_encoders && !output->connector; ++e) {
                        drmModeEncoderPtr encoder = drmModeGetEncoder(fd, connector->encoders[e]);
                        if (!encoder)
                            continue;
                        for (int c = 0; c < resources->count_crtcs && c < 32; ++c) {
                            if (encoder->possible_crtcs & (1U << c)) {
                                output->crtc = resources->crtcs[c];
                                output->connector = connector->connector_id;
                                output->mode = mode;
                                break;
                            }
                        }
                        drmModeFreeEncoder(encoder);
                    }
                }
            }
            drmModeFreeConnector(connector);
        }
        drmModeFreeResources(resources);
        if (output->connector) {
            drmModeObjectPropertiesPtr properties = drmModeObjectGetProperties(
                fd, output->connector, DRM_MODE_OBJECT_CONNECTOR);
            if (properties) {
                for (uint32_t p = 0; p < properties->count_props; ++p) {
                    drmModePropertyPtr property = drmModeGetProperty(fd, properties->props[p]);
                    if (property && !strcmp(property->name, "DPMS"))
                        output->dpms_property = property->prop_id;
                    drmModeFreeProperty(property);
                }
                drmModeFreeObjectProperties(properties);
            }
        }
        if (!output->connector || !output->dpms_property) {
            close(fd);
            free(output);
            continue;
        }
        *result = output;
        return 0;
    }
    return -ENODEV;
}

int g955n_kms_fd(const struct g955n_kms *output)
{
    return output->fd;
}

static uint32_t pixel_format(enum g955n_decon_rgb format)
{
    switch (format) {
    case G955N_DECON_RGBX8888: return DRM_FORMAT_XBGR8888;
    case G955N_DECON_RGBA8888: return DRM_FORMAT_ABGR8888;
    case G955N_DECON_BGRA8888: return DRM_FORMAT_ARGB8888;
    default: return 0;
    }
}

static int framebuffer(struct g955n_kms *output,
                       const struct g955n_panel_frame *frame, uint32_t *id)
{
    const uint32_t format = pixel_format(frame->format);
    uint32_t handle;
    if (drmPrimeFDToHandle(output->fd, frame->dma_buf, &handle))
        return -errno;
    for (unsigned i = 0; i < CACHE_SIZE; ++i) {
        struct frame_entry *entry = &output->cache[i];
        if (entry->handle == handle) {
            if (entry->pitch != frame->stride_pixels * 4 || entry->format != format)
                return -EINVAL;
            entry->used = ++output->age;
            *id = entry->fb;
            return 0;
        }
    }
    struct frame_entry *slot = NULL;
    for (unsigned i = 0; i < CACHE_SIZE; ++i) {
        struct frame_entry *entry = &output->cache[i];
        if (entry->fb && entry->fb == output->current_fb)
            continue;
        if (!slot || entry->used < slot->used)
            slot = entry;
    }
    if (!slot) {
        close_handle(output->fd, handle);
        return -EBUSY;
    }
    uint32_t handles[4] = { handle }, pitches[4] = { frame->stride_pixels * 4 };
    uint32_t offsets[4] = { 0 }, fb;
    if (drmModeAddFB2(output->fd, PANEL_WIDTH, PANEL_HEIGHT, format,
                      handles, pitches, offsets, &fb, 0)) {
        int error = -errno;
        close_handle(output->fd, handle);
        return error;
    }
    if (slot->fb)
        drmModeRmFB(output->fd, slot->fb);
    if (slot->handle)
        close_handle(output->fd, slot->handle);
    *slot = (struct frame_entry){handle, fb, pitches[0], format, ++output->age};
    *id = fb;
    return 0;
}

static int panel_is_off(struct g955n_kms *output)
{
    drmModeObjectPropertiesPtr properties = drmModeObjectGetProperties(
        output->fd, output->connector, DRM_MODE_OBJECT_CONNECTOR);
    if (!properties)
        return -errno;
    int state = -ENOENT;
    for (uint32_t i = 0; i < properties->count_props; ++i) {
        if (properties->props[i] == output->dpms_property) {
            state = properties->prop_values[i] != DRM_MODE_DPMS_ON;
            break;
        }
    }
    drmModeFreeObjectProperties(properties);
    return state;
}

static void flipped(int fd, unsigned sequence, unsigned seconds,
                     unsigned microseconds, void *data)
{
    (void)fd; (void)sequence; (void)seconds; (void)microseconds;
    ++((struct g955n_kms *)data)->completions;
}

int g955n_kms_progress(struct g955n_kms *output)
{
    if (!output || !output->pending_fb)
        return -EINVAL;
    int off = panel_is_off(output);
    if (off)
        return off < 0 ? off : G955N_KMS_DEFERRED;

    uint64_t completion = output->completions + 1;
    uint64_t started = milliseconds();
    uint64_t started_boot = clock_milliseconds(CLOCK_BOOTTIME);
    uint64_t deadline = started + FLIP_TIMEOUT_MS;
    bool resume_grace = false;
    drmEventContext events = { .version = 2, .page_flip_handler = flipped };
    while (output->completions < completion) {
        uint64_t now = milliseconds();
        uint64_t slice = now + FLIP_POLL_SLICE_MS;
        int error = wait_readable(output->fd, slice < deadline ? slice : deadline);
        if (error == -ETIMEDOUT) {
            off = panel_is_off(output);
            if (off)
                return off < 0 ? off : G955N_KMS_DEFERRED;

            now = milliseconds();
            uint64_t elapsed = now - started;
            uint64_t elapsed_boot = clock_milliseconds(CLOCK_BOOTTIME) - started_boot;
            if (!resume_grace &&
                (now > deadline + 250 || elapsed_boot > elapsed + 250)) {
                resume_grace = true;
                deadline = now + FLIP_TIMEOUT_MS;
            }
            if (now >= deadline)
                return error;
            continue;
        }
        if (error)
            return error;
        if (drmHandleEvent(output->fd, &events))
            return -errno;
    }
    output->current_fb = output->pending_fb;
    output->pending_fb = 0;
    return 0;
}

int g955n_kms_present(struct g955n_kms *output,
                      const struct g955n_panel_frame *frame, int *submitted)
{
    if (!submitted)
        return -EINVAL;
    *submitted = 0;
    if (!output || !frame || frame->dma_buf < 0 || frame->acquire_fence < -1 ||
        frame->stride_pixels < PANEL_WIDTH || frame->stride_pixels > 4096 ||
        frame->allocation_height < PANEL_HEIGHT || frame->allocation_height > 4096 ||
        !pixel_format(frame->format))
        return -EINVAL;
    if (output->pending_fb)
        return -EBUSY;
    int off = panel_is_off(output);
    if (off)
        return off < 0 ? off : G955N_KMS_DEFERRED;

    off_t size = lseek(frame->dma_buf, 0, SEEK_END);
    if (size < 0)
        return -errno;
    if ((uint64_t)size < (uint64_t)frame->stride_pixels * frame->allocation_height * 4)
        return -EINVAL;
    if (frame->acquire_fence >= 0) {
        int ready = wait_readable(frame->acquire_fence, milliseconds() + 1000);
        if (ready)
            return ready;
    }
    uint32_t fb = 0;
    int error = framebuffer(output, frame, &fb);
    if (error)
        return error;
    if (!output->current_fb) {
        if (!drmIsMaster(output->fd) && drmSetMaster(output->fd))
            return -errno;
        *submitted = 1;
        if (drmModeSetCrtc(output->fd, output->crtc, fb, 0, 0,
                           &output->connector, 1, &output->mode))
            return -errno;
        output->current_fb = fb;
        return 0;
    }

    *submitted = 1;
    if (drmModePageFlip(output->fd, output->crtc, fb,
                        DRM_MODE_PAGE_FLIP_EVENT, output))
        return -errno;
    output->pending_fb = fb;
    return g955n_kms_progress(output);
}
