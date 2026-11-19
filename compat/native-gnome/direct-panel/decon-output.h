/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef G955N_DECON_OUTPUT_H
#define G955N_DECON_OUTPUT_H

#include <stdint.h>

enum g955n_decon_rgb {
    G955N_DECON_RGBA8888 = 2,
    G955N_DECON_BGRA8888 = 3,
    G955N_DECON_RGBX8888 = 6,
};

struct g955n_panel_frame {
    int dma_buf;
    int acquire_fence;
    uint32_t stride_pixels;
    uint32_t allocation_height;
    enum g955n_decon_rgb format;
};

/* The caller owns the verified primary-panel fd and a linear single-plane
 * buffer with checked layout. The caller must exclusively own presentation
 * and retain submitted buffers. The returned fence is owned by the caller.
 * The returned fence belongs to this frame and is signalled after a later
 * replacement on the primary command-mode panel.
 * An ambiguous result never gives permission to reuse a submitted buffer.
 * submitted is set immediately before the ioctl, so preflight failures can
 * be distinguished from failures after entering the driver. */
int g955n_decon_submit(int panel_fd, const struct g955n_panel_frame *frame,
                      int *completion_fence, int *submitted);

#endif
