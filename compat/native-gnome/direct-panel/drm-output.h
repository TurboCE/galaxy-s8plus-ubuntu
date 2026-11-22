/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef G955N_DRM_OUTPUT_H
#define G955N_DRM_OUTPUT_H
#include "decon-output.h"

struct g955n_kms;
/* Open verifies the driver, PRIME import and the connected native panel mode.
 * It does not modeset or map pixels. The caller must hold the display lease. */
int g955n_kms_open(struct g955n_kms **output);
enum { G955N_KMS_DEFERRED = 1 };
/* Resume an outstanding flip. A deferred result keeps both buffers held and
 * lets the event loop run while the screen is off. */
int g955n_kms_progress(struct g955n_kms *output);
/* Success means the replacement reached the panel; the old buffer may then be
 * reused. A submitted error is ambiguous and must never recycle that buffer.
 * On G955N_KMS_DEFERRED, keep the new buffer only if submitted is set. */
int g955n_kms_present(struct g955n_kms *output,
                      const struct g955n_panel_frame *frame, int *submitted);
void g955n_kms_close(struct g955n_kms *output);
#endif
