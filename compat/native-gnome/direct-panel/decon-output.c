/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * Wire layout and constants from Samsung's GPL Exynos8895 DECON driver,
 * drivers/video/fbdev/exynos/dpu/decon.h at 54feaea9870dd0e90ceced5623e0544d965b400b.
 * This ABI is for the pinned AArch64 kernel with DSU and without INDISPLAY.
 */
#include "decon-output.h"

#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <sys/ioctl.h>
#include <sys/types.h>
#include <unistd.h>

enum { PANEL_WIDTH = 1440, PANEL_HEIGHT = 2960 };

struct decon_rectangle {
    int32_t x, y;
    uint32_t width, height;
};

struct decon_frame {
    struct decon_rectangle crop;
    uint32_t full_width, full_height;
};

struct decon_dpp {
    uint64_t addresses[3];
    uint32_t flip, color_transform, compression_source;
};

struct decon_window {
    uint32_t state;
    int32_t dma_buf[3];
    int32_t fence, alpha;
    uint32_t blend, channel, format;
    struct decon_dpp dpp;
    struct decon_rectangle blocked, transparent, opaque;
    struct decon_frame source, destination;
    uint8_t protected_content, compressed;
};

struct decon_config {
    int32_t fence, writeback;
    struct decon_window windows[8];
};

#define DECON_WIN_CONFIG _IOW('F', 209, struct decon_config)

_Static_assert(sizeof(struct decon_window) == 184, "Exynos8895 window ABI");
_Static_assert(offsetof(struct decon_window, source) == 128, "Exynos8895 source offset");
_Static_assert(sizeof(struct decon_config) == 1480, "Exynos8895 ioctl ABI");

int g955n_decon_submit(int panel_fd, const struct g955n_panel_frame *frame,
                      int *completion_fence)
{
    if (!completion_fence)
        return -EINVAL;
    *completion_fence = -1;
    if (!frame || panel_fd < 0 || frame->dma_buf < 0 || frame->acquire_fence < -1 ||
        frame->stride_pixels < PANEL_WIDTH || frame->stride_pixels > 4096 ||
        frame->allocation_height < PANEL_HEIGHT || frame->allocation_height > 4096 ||
        (frame->format != G955N_DECON_RGBA8888 &&
         frame->format != G955N_DECON_BGRA8888 &&
         frame->format != G955N_DECON_RGBX8888))
        return -EINVAL;

    /* dma-buf SEEK_END returns its size, not a CPU mapping of its pixels. */
    const off_t size = lseek(frame->dma_buf, 0, SEEK_END);
    if (size < 0)
        return -errno;
    if ((uint64_t)size < (uint64_t)frame->stride_pixels * frame->allocation_height * 4)
        return -EINVAL;

    struct decon_config config = {.fence = -1, .writeback = -1};
    struct decon_window *window = &config.windows[0];
    window->state = 2;  /* DECON_WIN_STATE_BUFFER */
    window->dma_buf[0] = frame->dma_buf;
    window->dma_buf[1] = -1;
    window->dma_buf[2] = -1;
    window->fence = frame->acquire_fence;
    window->alpha = 255;
    window->channel = 1; /* IDMA_G1, G0 is reserved for WIN5 */
    window->format = frame->format;
    window->source = (struct decon_frame){
        .crop = {0, 0, PANEL_WIDTH, PANEL_HEIGHT},
        .full_width = frame->stride_pixels,
        .full_height = frame->allocation_height,
    };
    window->destination = (struct decon_frame){
        .crop = {0, 0, PANEL_WIDTH, PANEL_HEIGHT},
        .full_width = PANEL_WIDTH,
        .full_height = PANEL_HEIGHT,
    };

    if (ioctl(panel_fd, DECON_WIN_CONFIG, &config) < 0)
        return -errno;
    if (config.fence < 0)
        return -EIO;
    *completion_fence = config.fence;
    return 0;
}
