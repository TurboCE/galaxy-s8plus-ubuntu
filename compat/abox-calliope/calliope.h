/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef G955N_CALLIOPE_H
#define G955N_CALLIOPE_H

#include <linux/types.h>

#define CALLIOPE_SRAM_IMAGE_LIMIT	0x30000
#define CALLIOPE_DRAM_IOVA		0x80000000UL
#define CALLIOPE_DRAM_SIZE		0xc00000
#define CALLIOPE_CHIPID			0x10000000UL

struct device;
struct firmware;

int g955n_calliope_boot(struct device *dev, const struct firmware *fw,
		       const void *dram, bool *keep_dma);

#endif
