/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef G955N_CALLIOPE_H
#define G955N_CALLIOPE_H

#include <linux/completion.h>
#include <linux/spinlock_types.h>
#include <linux/types.h>

#define CALLIOPE_SRAM_IMAGE_LIMIT	0x30000
#define CALLIOPE_DRAM_IOVA		0x80000000UL
#define CALLIOPE_DRAM_SIZE		0xc00000
#define CALLIOPE_CHIPID			0x10000000UL
#define CALLIOPE_RDMA0_IOVA		0x81000000UL
#define CALLIOPE_PCM_PERIOD_BYTES	4096
#define CALLIOPE_PCM_PERIODS		4
#define CALLIOPE_K58_PERIOD_BYTES	8192
#define CALLIOPE_K58_PERIODS		8

struct device;
struct firmware;

struct calliope_stream {
	dma_addr_t dma;
	unsigned int periods;
	unsigned int period_bytes;
	int (*mute)(struct calliope_stream *stream);
	struct completion ready;
	struct completion start;
	struct completion running;
	struct completion done;
	spinlock_t *host_route_lock;
	bool stopping;
	bool retain_ring;
	int result;
};

bool g955n_calliope_kernel58_route(void);
int g955n_calliope_run(struct device *dev, struct calliope_stream *stream);
int g955n_calliope_boot(struct device *dev, const struct firmware *fw,
		       void *dram, bool try_resume, bool try_dsm_read,
		       bool try_pcm, bool try_feedback, bool *keep_dma,
		       struct calliope_stream *stream);

#endif
