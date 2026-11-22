/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef G955N_PANEL_ROTATION_H
#define G955N_PANEL_ROTATION_H

#include <EGL/egl.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

enum { G955N_ROTATION_SLOTS = 3 };

/* Caller serializes access and keeps the slot out of scanout until KMS
 * retires it. The GPU pass returns with the producer's EGL binding restored. */
bool g955n_rotate_panel_buffer(EGLClientBuffer source, unsigned int degrees,
                              unsigned int slot, int *dma_buf,
                              EGLClientBuffer *destination);

#ifdef __cplusplus
}
#endif
#endif
