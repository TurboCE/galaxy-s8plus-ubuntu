/* SPDX-License-Identifier: GPL-2.0-only */
#include "drm-output.h"
#include <stdio.h>
int main(void)
{
    struct g955n_kms *output = NULL;
    int error = g955n_kms_open(&output);
    if (error) {
        fprintf(stderr, "Native DRM/KMS PRIME panel unavailable: %d\n", -error);
        return 1;
    }
    g955n_kms_close(output);
    puts("g955n-decon KMS ABI 1.1: PRIME import, connected DSI 1440x2960");
    return 0;
}
