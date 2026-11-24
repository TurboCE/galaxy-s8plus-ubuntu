/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef G955N_CALLIOPE_H
#define G955N_CALLIOPE_H

#include <linux/types.h>

#define CALLIOPE_SRAM_IMAGE_LIMIT	0x30000
#define CALLIOPE_DRAM_IOVA		0x80000000UL
#define CALLIOPE_DRAM_SIZE		0xc00000
#define CALLIOPE_CHIPID			0x10000000UL
#define CALLIOPE_RDMA0_IOVA		0x81000000UL
#define CALLIOPE_PCM_PERIOD_BYTES	4096
#define CALLIOPE_PCM_PERIODS		4

struct device;
struct firmware;

int g955n_calliope_boot(struct device *dev, const struct firmware *fw,
		       const void *dram, bool try_resume, bool try_dsm_read,
		       bool try_pcm, bool try_feedback, bool *keep_dma);

#endif
