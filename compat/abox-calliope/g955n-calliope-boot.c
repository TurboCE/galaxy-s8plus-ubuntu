// SPDX-License-Identifier: GPL-2.0-only
/*
 * One-shot SM-G955N Calliope boot and system IPC test.
 * Register layout and power sequencing from the Samsung Exynos8895 ABOX driver.
 */
#include <dt-bindings/clock/samsung,exynos8895-abox.h>
#include <linux/clk.h>
#include <linux/device.h>
#include <linux/firmware.h>
#include <linux/io.h>
#include <linux/iopoll.h>
#include <linux/jiffies.h>
#include <linux/ktime.h>
#include <linux/math64.h>
#include <linux/mfd/syscon.h>
#include <linux/of_address.h>
#include <linux/regmap.h>
#include <linux/vmalloc.h>

#include "calliope.h"

#define ABOX_PMU_STATE		0x4004
#define CA7_CONFIG		0x2520
#define CA7_STATE		0x2524
#define CA7_OPTION		0x2528
#define CA7_PWR			BIT(0)
#define CA7_ENABLE		BIT(15)
#define CA7_RUNNING		BIT(0)
#define CA7_CMU_GATE		0x2040
#define CA7_CMU_GATE_ON		BIT(21)
#define CA7_CMU_DIV		0x1820
#define CA7_CMU_DIV_MASK		GENMASK(3, 0)
#define ABOX_IP_ID		0x41424f58
#define ABOX_SYSPOWER_CTRL	0x10
#define ABOX_SYSPOWER_STATUS	0x14
#define ABOX_DRAM_ON		BIT(0)
#define ABOX_CA7_PC		0x2c3c
#define ABOX_SYSREG_BASE	0x13e20000
#define ABOX_SYSREG_L2		0x328
#define ABOX_SYSREG_MISC	0x32c
#define ABOX_SRAM_BASE		0x13f00000
#define ABOX_SRAM_SIZE		0x31000
#define IPC_TX			0x30000
#define IPC_TX_ACK		0x302fc
#define IPC_RX			0x30300
#define IPC_RX_ACK		0x305fc
#define ABOX_GICD_BASE		0x13ef1000
#define ABOX_GICD_SGIR		0xf00
#define ABOX_GIC_CA7		BIT(16)
#define IPC_RECEIVED		0
#define IPC_SYSTEM		1
#define IPC_PCM_PLAYBACK	2
#define IPC_ABOX_CONFIG		0xa
#define IPC_MIXER_RATE		1
#define IPC_INMUX4_RATE		9
#define IPC_MIXER_FORMAT	0x10
#define IPC_OUT1_FORMAT		0x11
#define IPC_INMUX3_FORMAT	0x17
#define IPC_RESUME		2
#define IPC_BOOT_DONE		3
#define IPC_CHANGE_GEAR		4
#define IPC_CHANGED_GEAR	9
#define IPC_REPORT_LOG		0x10
#define IPC_FLUSH_LOG		0x11
#define IPC_REPORT_DUMP		0x20
#define IPC_FLUSH_DUMP		0x22
#define ABOX_BOOT_GEAR_ID	0xb00d
#define ABOX_BOOT_GEAR		3
#define ABOX_GEAR_RELEASE	12
#define ABOX_48K_PLL_RATE	1179648000UL
#define IPC_REPORT_COMPONENT	0xc0
#define IPC_UPDATE_COMPONENT	0xc1
#define IPC_READ_COMPONENT	0xc2
#define IPC_COMPONENT_VALUE	0xc3
#define IPC_REPORT_FAULT	0xfa
#define IPC_ERAP		5
#define IPC_REALTIME_EXTRA	0xea
#define DSM_PARAMETER_WORDS	185
#define DSM_ENABLE_WORD		1
#define IPC_PCM_OPEN		11
#define IPC_PCM_CLOSE		12
#define IPC_PCM_HW_PARAMS	14
#define IPC_PCM_HW_FREE		15
#define IPC_PCM_PREPARE		16
#define IPC_PCM_TRIGGER		17
#define IPC_PCM_POINTER		18
#define IPC_PCM_SET_BUFFER	20
#define ABOX_RDMA0_CTRL		0x1000
#define ABOX_RDMA0_STATUS	0x1020
#define ABOX_RDMA_ENABLE	BIT(0)
#define ABOX_RDMA_PROGRESS	BIT(31)
#define ABOX_RDMA_POSITION	(GENMASK(28, 16) | GENMASK(12, 0))
#define CALLIOPE_PCM_START_MS	160
#define ABOX_UAIF4_GATE		0x2034
#define ABOX_UAIF0_GATE		0x2024
#define ABOX_UAIF_GATE_MASK	(BIT(28) | BIT(21) | BIT(20))
#define ABOX_UAIF_GATE_ON	(BIT(21) | BIT(20))
#define ABOX_UAIF4_CTRL0		0x540
#define ABOX_UAIF4_CTRL1		0x544
#define ABOX_UAIF0_CTRL0		0x500
#define ABOX_UAIF0_CTRL1		0x504
#define ABOX_UAIF_ENABLES	GENMASK(1, 0)
#define ABOX_UAIF_TX		BIT(0)
#define ABOX_WDMA1_CTRL		0x2100
#define ABOX_UAIF0_CLOCK_PROVIDER BIT(2)
#define ABOX_UAIF0_FORMAT_MASK	GENMASK(28, 0)
#define ABOX_UAIF0_S16_STEREO	((9 << 24) | BIT(23) | (1 << 18) | (15 << 12))
#define ABOX_UAIF4_BCLK		1536000UL
#define ABOX_SPUS_BANK(n)	(0x220 + (n) * sizeof(u32))
#define ABOX_SPUS_BANK_MASK	(GENMASK(13, 7) | GENMASK(28, 23))
#define ABOX_SPUS_S16_STEREO	(4 << 23)
#define FAULT_GPRS_SIZE		(16 * sizeof(u32))

/* Samsung's IPC descriptor layout is shared with the 32-bit CA7. */
struct calliope_component {
	__le32 id;
	char name[16];
	__le32 control_count;
};

struct calliope_control {
	__le32 id;
	char name[16];
	__le32 count;
	__le32 min;
	__le32 max;
};

struct calliope_dsm_control {
	u32 component_id;
	u32 control_id;
	bool found;
};

struct calliope_log_ring {
	__le32 writer, reader, size;
};

/* Stock SIFS0 clock path and SPUS OUT7 -> SIFS1 -> UAIF4. */
static const struct {
	u32 reg, mask, value;
} calliope_speaker_route[] = {
	{ 0x040, GENMASK(19, 16) | GENMASK(3, 0), (2 << 16) | 1 },
	{ 0x044, GENMASK(15, 12), 12 << 12 },
	{ 0x200, GENMASK(30, 29) | GENMASK(2, 1), 1 << 1 },
	{ 0x204, GENMASK(18, 16), 7 << 16 },
	{ ABOX_SPUS_BANK(0), ABOX_SPUS_BANK_MASK, ABOX_SPUS_S16_STEREO },
	{ ABOX_SPUS_BANK(7), ABOX_SPUS_BANK_MASK, ABOX_SPUS_S16_STEREO },
	{ ABOX_UAIF0_CTRL1, ABOX_UAIF0_FORMAT_MASK, ABOX_UAIF0_S16_STEREO },
	{ ABOX_UAIF0_CTRL0, BIT(2) | BIT(0), BIT(2) | BIT(0) },
	{ ABOX_UAIF4_CTRL1, GENMASK(28, 0), (9 << 24) | BIT(23) | (1 << 18) | (15 << 12) },
	{ ABOX_UAIF4_CTRL0, GENMASK(4, 0), BIT(2) | BIT(0) },
};

static u32 calliope_route_mask(unsigned int index, bool host_uaif0)
{
	if (host_uaif0) {
		/* Capture already owns UAIF0 format and clocks. Add only TX. */
		if (calliope_speaker_route[index].reg == ABOX_UAIF0_CTRL0)
			return ABOX_UAIF_TX;
		if (calliope_speaker_route[index].reg == ABOX_UAIF0_CTRL1)
			return 0;
	}
	return calliope_speaker_route[index].mask;
}

/* This trial uses the nonsecure GIC path on nonzero Exynos8895 revisions. */
static int calliope_check_chip(void)
{
	void __iomem *chipid = ioremap(CALLIOPE_CHIPID, 0x20);
	int ret;

	if (!chipid)
		return -ENOMEM;
	ret = (readl(chipid) == 0xe8895000 && readl(chipid + 0x10)) ? 0 : -ENODEV;
	iounmap(chipid);
	return ret;
}

static int calliope_send_message(void __iomem *sram, u32 ipc, u32 message,
				 u32 param1, u32 param2, u32 param3, u32 param4)
{
	void __iomem *gicd;
	u32 ack;
	int ret;

	if (readl(sram + IPC_TX_ACK))
		return -EBUSY;
	gicd = ioremap(ABOX_GICD_BASE, SZ_4K);
	if (!gicd)
		return -ENOMEM;

	memset_io(sram + IPC_TX, 0, IPC_TX_ACK - IPC_TX);
	writel(ipc, sram + IPC_TX);
	writel(message, sram + IPC_TX + 8);
	writel(param1, sram + IPC_TX + 12);
	writel(param2, sram + IPC_TX + 16);
	writel(param3, sram + IPC_TX + 20);
	writel(param4, sram + IPC_TX + 24);
	writel(1, sram + IPC_TX_ACK);
	writel(ABOX_GIC_CA7 | ipc, gicd + ABOX_GICD_SGIR);
	ret = readl_poll_timeout(sram + IPC_TX_ACK, ack, !ack, 100, 20000);

	iounmap(gicd);
	return ret;
}

static int calliope_send(void __iomem *sram, u32 ipc, u32 message,
			 u32 param1, u32 param2, u32 param3)
{
	return calliope_send_message(sram, ipc, message, param1, param2, param3, 0);
}

static int calliope_report_fault(struct device *dev, void __iomem *sram,
				 const void *dram)
{
	u32 type = readl(sram + IPC_RX + 12);
	u32 addr = readl(sram + IPC_RX + 24);
	u32 regs[16];

	dev_err(dev, "Calliope fault: type=%u p2=%08x p3=%08x dump=%08x\n",
		type, readl(sram + IPC_RX + 16), readl(sram + IPC_RX + 20), addr);
	if ((type != 1 && type != 2) || !IS_ALIGNED(addr, sizeof(u32)))
		return -EREMOTEIO;
	if (addr <= CALLIOPE_SRAM_IMAGE_LIMIT - FAULT_GPRS_SIZE)
		memcpy_fromio(regs, sram + addr, sizeof(regs));
	else if (addr >= CALLIOPE_DRAM_IOVA &&
		 addr - CALLIOPE_DRAM_IOVA <= CALLIOPE_DRAM_SIZE - FAULT_GPRS_SIZE)
		memcpy(regs, dram + (addr - CALLIOPE_DRAM_IOVA), sizeof(regs));
	else
		return -EREMOTEIO;

	dev_err(dev, "Calliope fault registers: r0=%08x r1=%08x r2=%08x r3=%08x lr=%08x pc=%08x\n",
		regs[0], regs[1], regs[2], regs[3], regs[14], regs[15]);
	return -EREMOTEIO;
}

static int calliope_component_report(struct device *dev, void __iomem *sram,
				      const void *dram, u32 addr, struct calliope_dsm_control *dsm)
{
	struct calliope_component component;
	struct calliope_control control;
	size_t remaining;
	u32 offset, count, i;

	if (!IS_ALIGNED(addr, sizeof(u32)))
		return -EINVAL;

	if (addr <= CALLIOPE_SRAM_IMAGE_LIMIT - sizeof(component)) {
		remaining = CALLIOPE_SRAM_IMAGE_LIMIT - addr;
		memcpy_fromio(&component, sram + addr, sizeof(component));
	} else if (addr >= CALLIOPE_DRAM_IOVA &&
		   addr - CALLIOPE_DRAM_IOVA <= CALLIOPE_DRAM_SIZE - sizeof(component)) {
		offset = addr - CALLIOPE_DRAM_IOVA;
		remaining = CALLIOPE_DRAM_SIZE - offset;
		dma_rmb();
		memcpy(&component, dram + offset, sizeof(component));
	} else {
		return -ERANGE;
	}

	count = le32_to_cpu(component.control_count);
	if (count > (remaining - sizeof(component)) / sizeof(struct calliope_control))
		return -EINVAL;

	/* The trial records the announcement without creating ALSA controls. */
	dev_info(dev, "Calliope component id=%u name=%.16s controls=%u\n",
		 le32_to_cpu(component.id), component.name, count);
	if (!dsm || strncmp(component.name, "ERAP info", sizeof(component.name)))
		return 0;

	for (i = 0; i < count; i++) {
		offset = sizeof(component) + i * sizeof(control);
		if (addr < CALLIOPE_DRAM_IOVA)
			memcpy_fromio(&control, sram + addr + offset, sizeof(control));
		else
			memcpy(&control, dram + (addr - CALLIOPE_DRAM_IOVA) + offset, sizeof(control));
		if (strncmp(control.name, "DSM On", sizeof(control.name)))
			continue;
		if (dsm->found || le32_to_cpu(control.count) != 1 ||
		    le32_to_cpu(control.min) != 0 || le32_to_cpu(control.max) != 1)
			return -EPROTO;
		dsm->component_id = le32_to_cpu(component.id);
		dsm->control_id = le32_to_cpu(control.id);
		dsm->found = true;
	}
	return 0;
}

static int calliope_wait_boot(struct device *dev, void __iomem *sram,
			      const void *dram, struct calliope_dsm_control *dsm)
{
	unsigned int attempt;
	u32 ipc, message;
	int ret;

	for (attempt = 0; attempt < 1000; attempt++) {
		if (!readl(sram + IPC_RX_ACK)) {
			usleep_range(1000, 1500);
			continue;
		}
		ipc = readl(sram + IPC_RX);
		message = readl(sram + IPC_RX + 8);
		if (ipc == IPC_SYSTEM && message == IPC_BOOT_DONE) {
			dev_info(dev, "Calliope BOOT_DONE version=%08x\n",
				 readl(sram + IPC_RX + 20));
			writel(0, sram + IPC_RX_ACK);
			return 0;
		}
		if (ipc == IPC_SYSTEM && message == IPC_REPORT_FAULT)
			return calliope_report_fault(dev, sram, dram);
		if (ipc == IPC_SYSTEM && message == IPC_REPORT_COMPONENT) {
			u32 addr = readl(sram + IPC_RX + 12);

			ret = calliope_component_report(dev, sram, dram, addr, dsm);
			if (ret) {
				dev_warn(dev, "Calliope invalid component descriptor at %08x: %d\n",
					 addr, ret);
				return ret;
			}
			writel(0, sram + IPC_RX_ACK);
			usleep_range(1000, 1500);
			continue;
		}
		dev_warn(dev, "Calliope requires unsupported startup IPC %u:%#x\n",
			 ipc, message);
		return -EOPNOTSUPP;
	}
	return -ETIMEDOUT;
}

static bool calliope_diagnostic_report(u32 ipc, u32 message)
{
	return ipc == IPC_SYSTEM &&
	       (message == IPC_REPORT_LOG || message == IPC_FLUSH_LOG ||
		message == IPC_REPORT_DUMP || message == IPC_FLUSH_DUMP);
}

static int calliope_set_dsm(struct device *dev, void __iomem *sram,
			   const struct calliope_dsm_control *dsm, bool enable)
{
	unsigned long deadline;
	u32 ipc, message, current_value;
	int ret;

	if (!dsm->found)
		return -ENODEV;
	ret = calliope_send_message(sram, IPC_SYSTEM, IPC_UPDATE_COMPONENT,
				    dsm->component_id, dsm->control_id, 0, enable);
	if (ret)
		return ret;
	ret = calliope_send(sram, IPC_SYSTEM, IPC_READ_COMPONENT,
			    dsm->component_id, dsm->control_id, 0);
	if (ret)
		return ret;
	/* Diagnostic notifications can arrive ahead of the component reply. */
	deadline = jiffies + msecs_to_jiffies(130);
	do {
		if (!readl(sram + IPC_RX_ACK)) {
			usleep_range(100, 200);
			continue;
		}
		ipc = readl(sram + IPC_RX);
		message = readl(sram + IPC_RX + 8);
		if (!calliope_diagnostic_report(ipc, message))
			goto receive;
		writel(0, sram + IPC_RX_ACK);
	} while (time_before(jiffies, deadline));
	return -ETIMEDOUT;

receive:
	if (ipc != IPC_SYSTEM || message != IPC_COMPONENT_VALUE)
		return -EPROTO;
	if (readl(sram + IPC_RX + 12) != dsm->component_id ||
	    readl(sram + IPC_RX + 16) != dsm->control_id)
		return -EPROTO;
	current_value = readl(sram + IPC_RX + 24);
	writel(0, sram + IPC_RX_ACK);
	dev_info(dev, "Calliope ERAP DSM On=%u (requested %u)\n", current_value, enable);
	return current_value == enable ? 0 : -EIO;
}

static int calliope_read_dsm(struct device *dev, void __iomem *sram,
			     const void *dram, unsigned long ca7_rate,
			     bool require_enabled)
{
	unsigned long deadline = jiffies + msecs_to_jiffies(130);
	u32 ack, ipc, message, count, enable, gear, id, nsec;
	u64 sec;
	int ret;

	/* REALTIME_EXTRA parameters 0 and 1 are the read selector and offset. */
	ret = calliope_send(sram, IPC_ERAP, IPC_REALTIME_EXTRA, 0, 0,
			    DSM_PARAMETER_WORDS);
	if (ret)
		return ret;

	do {
		ack = readl(sram + IPC_RX_ACK);
		if (!ack) {
			usleep_range(100, 200);
			continue;
		}
		ipc = readl(sram + IPC_RX);
		message = readl(sram + IPC_RX + 8);
		if (ipc == IPC_ERAP && message == IPC_REALTIME_EXTRA) {
			count = readl(sram + IPC_RX + 12);
			if (count <= DSM_ENABLE_WORD || count > DSM_PARAMETER_WORDS) {
				dev_warn(dev, "Calliope invalid DSM word count: %u\n", count);
				return -EPROTO;
			}
			enable = readl(sram + IPC_RX + 12 + DSM_ENABLE_WORD * sizeof(u32));
			writel(0, sram + IPC_RX_ACK);
			dev_info(dev, "Calliope returned %u DSM parameter words (enable=%u)\n",
				 count, enable);
			return require_enabled && enable != 1 ? -EHOSTDOWN : 0;
		}
		if (ipc == IPC_SYSTEM && message == IPC_REPORT_FAULT)
			return calliope_report_fault(dev, sram, dram);
		if (ipc != IPC_SYSTEM || message != IPC_CHANGE_GEAR) {
			dev_warn(dev, "Calliope unexpected DSM reply %u:%#x\n", ipc, message);
			return -EPROTO;
		}

		gear = readl(sram + IPC_RX + 12);
		id = readl(sram + IPC_RX + 16);
		/* The diagnostic only owns the preconfigured boot gear. */
		if (id == ABOX_BOOT_GEAR_ID && gear == ABOX_BOOT_GEAR) {
			sec = ktime_get_ns();
			nsec = do_div(sec, NSEC_PER_SEC);
			writel(0, sram + IPC_RX_ACK);
			ret = calliope_send(sram, IPC_SYSTEM, IPC_CHANGED_GEAR,
					    ca7_rate, sec, nsec);
			if (ret)
				return ret;
		} else if (gear == ABOX_GEAR_RELEASE) {
			writel(0, sram + IPC_RX_ACK);
		} else {
			dev_warn(dev, "Calliope DSM needs gear %u (id=%#x)\n", gear, id);
			return -EOPNOTSUPP;
		}
	} while (time_before(jiffies, deadline));

	return -ETIMEDOUT;
}

static void calliope_drain_log(struct calliope_log_ring *log, size_t capacity)
{
	u32 size = le32_to_cpu(READ_ONCE(log->size));
	u32 writer;

	dma_rmb();
	writer = le32_to_cpu(READ_ONCE(log->writer));
	/* Firmware can announce the ring before initializing its header. */
	if (!size || size > capacity || writer >= size)
		return;

	WRITE_ONCE(log->reader, cpu_to_le32(writer));
	dma_wmb();
}

static int calliope_speaker_format(void __iomem *sram)
{
	static const u32 output_formats[] = {
		IPC_MIXER_FORMAT, IPC_OUT1_FORMAT, IPC_INMUX3_FORMAT,
	};
	unsigned int i;
	int ret;

	/* Restore the factory mix rates before applying the SIFS/VI PCM format. */
	for (i = IPC_MIXER_RATE; i <= IPC_INMUX4_RATE; i++) {
		ret = calliope_send(sram, IPC_ABOX_CONFIG, i, 48000, 0, 0);
		if (ret)
			return ret;
	}
	for (i = 0; i < ARRAY_SIZE(output_formats); i++) {
		ret = calliope_send(sram, IPC_ABOX_CONFIG, output_formats[i], 16, 2, 0);
		if (ret)
			return ret;
	}
	return 0;
}

static int calliope_pcm_trial(struct device *dev, void __iomem *sram,
			      void __iomem *sfr, void *dram,
			      struct calliope_stream *stream)
{
	const unsigned int periods = stream ? stream->periods : CALLIOPE_PCM_PERIODS;
	const struct {
		u32 message, arg1, arg2, arg3;
	} setup[] = {
		{ IPC_PCM_OPEN },
		{ IPC_PCM_SET_BUFFER, CALLIOPE_RDMA0_IOVA, CALLIOPE_PCM_PERIOD_BYTES,
		  periods },
		{ IPC_PCM_HW_PARAMS, 48000, 16, 2 },
		{ IPC_PCM_PREPARE },
		{ IPC_PCM_TRIGGER, 1 },
	};
	unsigned long deadline;
	struct calliope_log_ring *log = NULL;
	size_t log_capacity = 0;
	u32 first = 0, pointer, ipc, message, status, initial = 0, running_status = 0;
	bool ipc_advanced = false, dma_advanced = false;
	int i, ret = 0, stop, release, close;

	for (i = 0; i < ARRAY_SIZE(setup); i++) {
		if (setup[i].message == IPC_PCM_TRIGGER) {
			if (stream) {
				complete(&stream->ready);
				wait_for_completion(&stream->start);
				if (READ_ONCE(stream->stopping))
					goto cleanup;
			}
			initial = readl(sfr + ABOX_RDMA0_STATUS) & ABOX_RDMA_POSITION;
		}
		ret = calliope_send_message(sram, IPC_PCM_PLAYBACK, setup[i].message,
					    0, setup[i].arg1, setup[i].arg2, setup[i].arg3);
		if (ret) {
			dev_warn(dev, "Calliope PCM command %u failed: %d\n", setup[i].message, ret);
			goto cleanup;
		}
	}
	dev_info(dev, "Calliope PCM programmed RDMA0 ctrl=%08x start=%08x end=%08x\n",
		 readl(sfr + ABOX_RDMA0_CTRL), readl(sfr + ABOX_RDMA0_CTRL + 8),
		 readl(sfr + ABOX_RDMA0_CTRL + 12));

	deadline = jiffies + msecs_to_jiffies(CALLIOPE_PCM_START_MS);
	do {
		if (stream && READ_ONCE(stream->stopping))
			break;

		running_status = readl(sfr + ABOX_RDMA0_STATUS);
		if (!dma_advanced && (running_status & ABOX_RDMA_PROGRESS) &&
		    (running_status & ABOX_RDMA_POSITION) != initial) {
			dma_advanced = true;
			if (stream)
				complete(&stream->running);
		}
		if (stream && !dma_advanced && time_after_eq(jiffies, deadline)) {
			dev_err(dev, "Calliope RDMA0 did not advance after PCM trigger\n");
			ret = -ETIMEDOUT;
			break;
		}
		if (!readl(sram + IPC_RX_ACK)) {
			usleep_range(500, 1000);
			continue;
		}
		ipc = readl(sram + IPC_RX);
		message = readl(sram + IPC_RX + 8);
		if (ipc == IPC_SYSTEM && message == IPC_CHANGE_GEAR &&
		    readl(sram + IPC_RX + 12) == ABOX_GEAR_RELEASE &&
		    readl(sram + IPC_RX + 16) == ABOX_BOOT_GEAR_ID) {
			/* Keep the fixed CA7 clock while the PCM stream is active. */
			writel(0, sram + IPC_RX_ACK);
			dev_dbg(dev, "Calliope released the boot gear during PCM\n");
			continue;
		}
		if (ipc == IPC_SYSTEM && message == IPC_REPORT_FAULT) {
			ret = calliope_report_fault(dev, sram, dram);
			break;
		}
		if (ipc == IPC_SYSTEM && message == IPC_REPORT_LOG &&
		    !readl(sram + IPC_RX + 12)) {
			u32 addr = readl(sram + IPC_RX + 16);
			u32 offset = addr - CALLIOPE_DRAM_IOVA;

			log = NULL;
			if (IS_ALIGNED(addr, sizeof(u32)) &&
			    addr >= CALLIOPE_DRAM_IOVA &&
			    offset <= CALLIOPE_DRAM_SIZE - sizeof(*log)) {
				log = dram + offset;
				log_capacity = CALLIOPE_DRAM_SIZE - offset - sizeof(*log);
				calliope_drain_log(log, log_capacity);
			}
		}
		if (ipc == IPC_SYSTEM && message == IPC_FLUSH_LOG && log &&
		    !readl(sram + IPC_RX + 12))
			calliope_drain_log(log, log_capacity);

		if (ipc == IPC_RECEIVED || calliope_diagnostic_report(ipc, message)) {
			writel(0, sram + IPC_RX_ACK);
			continue;
		}
		if (ipc != IPC_PCM_PLAYBACK || message != IPC_PCM_POINTER ||
		    readl(sram + IPC_RX + 12)) {
			dev_warn(dev, "Calliope unexpected PCM IPC %u:%#x (%#x, %#x)\n",
				 ipc, message, readl(sram + IPC_RX + 12),
				 readl(sram + IPC_RX + 16));
			ret = -EPROTO;
			break;
		}
		pointer = readl(sram + IPC_RX + 16);
		if (pointer < CALLIOPE_RDMA0_IOVA ||
		    pointer - CALLIOPE_RDMA0_IOVA >= CALLIOPE_PCM_PERIOD_BYTES * periods) {
			ret = -ERANGE;
			break;
		}
		writel(0, sram + IPC_RX_ACK);
		if (!first)
			first = pointer;
		else if (pointer != first)
			ipc_advanced = true;
	} while (stream || ((!ipc_advanced || !dma_advanced) &&
			   time_before(jiffies, deadline)));
	if (!ret && !stream && !dma_advanced)
		ret = -ETIMEDOUT;

cleanup:
	if (stream) {
		int mute = stream->mute(stream);

		if (!ret)
			ret = mute;
	}
	stop = i >= ARRAY_SIZE(setup) - 1 ?
		calliope_send(sram, IPC_PCM_PLAYBACK, IPC_PCM_TRIGGER, 0, 0, 0) : 0;
	release = i >= 1 ? calliope_send(sram, IPC_PCM_PLAYBACK, IPC_PCM_HW_FREE, 0, 0, 0) : 0;
	close = calliope_send(sram, IPC_PCM_PLAYBACK, IPC_PCM_CLOSE, 0, 0, 0);
	status = readl(sfr + ABOX_RDMA0_STATUS);
	dev_info(dev, "Calliope %s PCM: hardware progress=%d IPC pointer=%d RDMA0=%08x->%08x stop=%d free=%d close=%d\n",
		 stream ? "ALSA" : "silent", dma_advanced, ipc_advanced, running_status,
		 status, stop, release, close);
	return ret ?: stop ?: release ?: close;
}

int g955n_calliope_boot(struct device *dev, const struct firmware *fw,
		       void *dram, bool try_resume, bool try_dsm_read,
		       bool try_pcm, bool try_feedback, bool *keep_dma,
		       struct calliope_stream *stream)
{
	void __iomem *sysreg = NULL, *sram = NULL, *cmu = NULL, *sfr = NULL;
	struct resource cmu_res, sfr_res;
	struct calliope_dsm_control dsm = {};
	struct device_node *node;
	struct clk *pll = NULL, *bclk = NULL, *sifs0_bclk = NULL;
	struct regmap *pmu;
	void *saved_sram = NULL;
	u32 saved_l2, saved_misc, saved_syspower, state, option, power;
	u32 saved_rdma[8];
	u32 saved_route[ARRAY_SIZE(calliope_speaker_route)], saved_gate = 0, saved_sifs0_gate = 0;
	unsigned long ca7_rate = 0, saved_bclk = 0, saved_sifs0_bclk = 0;
	bool route_set = false;
	spinlock_t *host_route_lock = stream ? stream->host_route_lock : NULL;
	unsigned long route_flags = 0;
	bool host_uaif0 = host_route_lock;
	int i, ret, stop;

	ret = calliope_check_chip();
	if (ret)
		return ret;

	node = of_parse_phandle(dev->of_node, "samsung,abox-cmu", 0);
	if (!node)
		return -ENODEV;
	ret = of_address_to_resource(node, 0, &cmu_res);
	if (!ret)
		ret = of_address_to_resource(node, 1, &sfr_res);
	pmu = syscon_regmap_lookup_by_phandle(node, "samsung,pmu");
	if (try_dsm_read && !ret && !IS_ERR(pmu)) {
		struct of_phandle_args clock = {
			.np = node, .args_count = 1, .args = { G955N_ABOX_CLK_PLL },
		};

		pll = of_clk_get_from_provider(&clock);
	}
	if (try_pcm && !ret && !IS_ERR(pmu) && !IS_ERR(pll))
		bclk = of_clk_get(dev->of_node, 0);
	if (bclk && !IS_ERR(bclk))
		sifs0_bclk = of_clk_get(dev->of_node, 1);
	of_node_put(node);
	if (ret)
		return ret;
	if (IS_ERR(pmu))
		return PTR_ERR(pmu);
	if (IS_ERR(pll))
		return PTR_ERR(pll);
	if (IS_ERR(bclk)) {
		ret = PTR_ERR(bclk);
		bclk = NULL;
		goto out;
	}
	if (IS_ERR(sifs0_bclk)) {
		ret = PTR_ERR(sifs0_bclk);
		sifs0_bclk = NULL;
		goto out;
	}

	ret = regmap_read(pmu, ABOX_PMU_STATE, &state);
	if (ret || (state & 15) != 15) {
		ret = ret ?: -EHOSTDOWN;
		goto out;
	}
	ret = regmap_read(pmu, CA7_OPTION, &option);
	if (ret)
		goto out;
	if (regmap_read(pmu, CA7_STATE, &state) || state & CA7_RUNNING ||
	    option & CA7_ENABLE) {
		ret = -EBUSY;
		goto out;
	}

	ret = -ENOMEM;
	cmu = ioremap(cmu_res.start, resource_size(&cmu_res));
	sfr = ioremap(sfr_res.start, resource_size(&sfr_res));
	sram = ioremap(ABOX_SRAM_BASE, ABOX_SRAM_SIZE);
	sysreg = ioremap(ABOX_SYSREG_BASE, SZ_4K);
	saved_sram = kvmalloc(ABOX_SRAM_SIZE, GFP_KERNEL);
	if (!cmu || !sfr || !sram || !sysreg || !saved_sram)
		goto out;

	if (!(readl(cmu + CA7_CMU_GATE) & CA7_CMU_GATE_ON) ||
	    readl(sfr) != ABOX_IP_ID) {
		ret = -EHOSTDOWN;
		goto out;
	}
	if (readl(sfr + ABOX_UAIF4_CTRL0) & ABOX_UAIF_ENABLES ||
	    readl(sfr + ABOX_RDMA0_CTRL) & ABOX_RDMA_ENABLE ||
	    readl(sfr + ABOX_UAIF0_CTRL0) & ABOX_UAIF_TX ||
	    (!host_uaif0 && ((readl(sfr + ABOX_UAIF0_CTRL0) & ABOX_UAIF_ENABLES) ||
			     (readl(sfr + ABOX_WDMA1_CTRL) & ABOX_RDMA_ENABLE)))) {
		ret = -EBUSY;
		goto out;
	}
	if (host_uaif0) {
		unsigned long rate = clk_get_rate(sifs0_bclk);
		u32 gate = readl(cmu + ABOX_UAIF0_GATE);
		u32 mode = readl(sfr + ABOX_UAIF0_CTRL0);
		u32 format = readl(sfr + ABOX_UAIF0_CTRL1);

		if (rate != ABOX_UAIF4_BCLK ||
		    (gate & ABOX_UAIF_GATE_MASK) != ABOX_UAIF_GATE_ON ||
		    !(mode & ABOX_UAIF0_CLOCK_PROVIDER) ||
		    (format & ABOX_UAIF0_FORMAT_MASK) != ABOX_UAIF0_S16_STEREO) {
			dev_err(dev, "Calliope incompatible host UAIF0: %lu Hz gate=%#x mode=%#x format=%#x\n",
				rate, gate, mode, format);
			ret = -EIO;
			goto out;
		}
	}
	if (try_dsm_read) {
		unsigned long rate = clk_get_rate(pll);
		u32 divider = (readl(cmu + CA7_CMU_DIV) & CA7_CMU_DIV_MASK) + 1;

		if (divider != ABOX_BOOT_GEAR ||
		    rate < ABOX_48K_PLL_RATE - 1000 || rate > ABOX_48K_PLL_RATE + 1000) {
			dev_warn(dev, "Calliope DSM: incompatible inherited clock %lu/%u\n",
				 rate, divider);
			ret = -EOPNOTSUPP;
			goto out;
		}
		ca7_rate = rate / divider;
	}
	if (try_pcm) {
		if (readl(sfr + ABOX_RDMA0_STATUS) & ABOX_RDMA_PROGRESS ||
		    readl(sfr + ABOX_RDMA0_CTRL) & ABOX_RDMA_ENABLE) {
			ret = -EBUSY;
			goto out;
		}
		for (i = 0; i < ARRAY_SIZE(saved_rdma); i++)
			saved_rdma[i] = readl(sfr + ABOX_RDMA0_CTRL + i * sizeof(u32));
		saved_bclk = clk_get_rate(bclk);
		if (!saved_bclk) {
			ret = -EIO;
			goto out;
		}
		ret = clk_set_rate(bclk, ABOX_UAIF4_BCLK);
		if (ret || clk_get_rate(bclk) != ABOX_UAIF4_BCLK) {
			ret = ret ?: -EIO;
			goto out;
		}
		if (!host_uaif0) {
			saved_sifs0_bclk = clk_get_rate(sifs0_bclk);
			if (!saved_sifs0_bclk) {
				ret = -EIO;
				goto out;
			}
			ret = clk_set_rate(sifs0_bclk, ABOX_UAIF4_BCLK);
			if (ret || clk_get_rate(sifs0_bclk) != ABOX_UAIF4_BCLK) {
				ret = ret ?: -EIO;
				goto out;
			}
			saved_sifs0_gate = readl(cmu + ABOX_UAIF0_GATE);
			writel((saved_sifs0_gate & ~ABOX_UAIF_GATE_MASK) | ABOX_UAIF_GATE_ON,
			       cmu + ABOX_UAIF0_GATE);
		}
		saved_gate = readl(cmu + ABOX_UAIF4_GATE);
		writel((saved_gate & ~ABOX_UAIF_GATE_MASK) | ABOX_UAIF_GATE_ON,
		       cmu + ABOX_UAIF4_GATE);
		if (host_route_lock)
			spin_lock_irqsave(host_route_lock, route_flags);
		for (i = 0; i < ARRAY_SIZE(calliope_speaker_route); i++) {
			void __iomem *reg = sfr + calliope_speaker_route[i].reg;
			u32 mask = calliope_route_mask(i, host_uaif0);

			if (!mask)
				continue;
			saved_route[i] = readl(reg);
			writel((saved_route[i] & ~mask) |
			       (calliope_speaker_route[i].value & mask), reg);
		}
		if (host_route_lock)
			spin_unlock_irqrestore(host_route_lock, route_flags);
		route_set = true;
		if (try_feedback) {
			u32 ctrl = readl(sfr + ABOX_UAIF4_CTRL0);

			writel(ctrl | BIT(1), sfr + ABOX_UAIF4_CTRL0);
			dev_info(dev, "Calliope UAIF4 feedback input enabled, CTRL0=%08x\n",
				 readl(sfr + ABOX_UAIF4_CTRL0));
		}
	}

	saved_misc = readl(sysreg + ABOX_SYSREG_MISC);
	saved_l2 = readl(sysreg + ABOX_SYSREG_L2);
	saved_syspower = readl(sfr + ABOX_SYSPOWER_CTRL);
	writel(saved_syspower | ABOX_DRAM_ON, sfr + ABOX_SYSPOWER_CTRL);
	ret = readl_poll_timeout(sfr + ABOX_SYSPOWER_STATUS, power,
				 power & ABOX_DRAM_ON, 10, 20000);
	if (ret) {
		writel(saved_syspower, sfr + ABOX_SYSPOWER_CTRL);
		goto out;
	}
	memcpy_fromio(saved_sram, sram, ABOX_SRAM_SIZE);
	memset_io(sram, 0, ABOX_SRAM_SIZE);
	memcpy_toio(sram, fw->data, fw->size);
	writel(1, sysreg + ABOX_SYSREG_MISC);
	writel(1, sysreg + ABOX_SYSREG_L2);
	dma_wmb();

	dev_info(dev, "Calliope start: CA7 divider=%08x AUDIF divider=%08x\n",
		 readl(cmu + 0x1820), readl(cmu + 0x1800));
	ret = regmap_set_bits(pmu, CA7_CONFIG, CA7_PWR);
	if (!ret)
		ret = regmap_set_bits(pmu, CA7_OPTION, CA7_ENABLE);
	if (!ret)
		ret = regmap_read_poll_timeout(pmu, CA7_STATE, state, state & CA7_RUNNING,
					       100, 100000);
	if (!ret) {
		ret = calliope_wait_boot(dev, sram, dram, try_pcm ? &dsm : NULL);
		if (!ret && try_resume) {
			dev_info(dev, "Calliope sending system RESUME\n");
			ret = calliope_send(sram, IPC_SYSTEM, IPC_RESUME, 0, 0, 0);
			if (!ret)
				dev_info(dev, "Calliope acknowledged system RESUME\n");
		}
		if (!ret && try_dsm_read)
			ret = calliope_read_dsm(dev, sram, dram, ca7_rate, try_pcm);
		if (!ret && stream)
			ret = calliope_speaker_format(sram);
		if (!ret && try_pcm) {
			ret = calliope_set_dsm(dev, sram, &dsm, true);
			if (!ret) {
				int reset;

				ret = calliope_pcm_trial(dev, sram, sfr, dram, stream);
				reset = calliope_set_dsm(dev, sram, &dsm, false);
				if (!ret)
					ret = reset;
			}
		}
	}
	if (ret)
		dev_warn(dev, "Calliope bootstrap stopped at %d, CA7=%08x PC=%08x RX=%08x:%08x ACK=%08x\n",
			 ret, state, readl(sfr + ABOX_CA7_PC), readl(sram + IPC_RX),
			 readl(sram + IPC_RX + 8), readl(sram + IPC_RX_ACK));

	stop = regmap_clear_bits(pmu, CA7_OPTION, CA7_ENABLE);
	if (!stop)
		stop = regmap_clear_bits(pmu, CA7_CONFIG, CA7_PWR);
	if (!stop)
		stop = regmap_read_poll_timeout(pmu, CA7_STATE, state, !(state & CA7_RUNNING),
						100, 100000);
	if (!stop && try_pcm) {
		void __iomem *ctrl = sfr + ABOX_RDMA0_CTRL;

		writel(readl(ctrl) & ~ABOX_RDMA_ENABLE, ctrl);
		stop = readl_poll_timeout(sfr + ABOX_RDMA0_STATUS, state,
					  !(state & ABOX_RDMA_PROGRESS), 10, 40000);
		if (!stop) {
			for (i = 1; i < ARRAY_SIZE(saved_rdma); i++)
				writel(saved_rdma[i], ctrl + i * sizeof(u32));
			writel(saved_rdma[0], ctrl);
		}
	}
	if (stop) {
		*keep_dma = true;
		dev_crit(dev, "Calliope or RDMA0 did not stop; DMA mappings retained until reboot\n");
		ret = stop;
		goto out;
	}

	memcpy_toio(sram, saved_sram, ABOX_SRAM_SIZE);
	writel(saved_l2, sysreg + ABOX_SYSREG_L2);
	writel(saved_misc, sysreg + ABOX_SYSREG_MISC);
	writel(saved_syspower, sfr + ABOX_SYSPOWER_CTRL);
	dev_info(dev, "Calliope powered off; SRAM and system registers restored\n");
out:
	if (!*keep_dma) {
		if (route_set) {
			if (try_feedback)
				writel(readl(sfr + ABOX_UAIF4_CTRL0) & ~BIT(1),
				       sfr + ABOX_UAIF4_CTRL0);
			if (host_route_lock)
				spin_lock_irqsave(host_route_lock, route_flags);
			for (i = ARRAY_SIZE(calliope_speaker_route) - 1; i >= 0; i--) {
				void __iomem *reg = sfr + calliope_speaker_route[i].reg;
				u32 mask = calliope_route_mask(i, host_uaif0);

				if (mask)
					writel((readl(reg) & ~mask) | (saved_route[i] & mask), reg);
			}
			if (host_route_lock)
				spin_unlock_irqrestore(host_route_lock, route_flags);
			writel(saved_gate, cmu + ABOX_UAIF4_GATE);
			if (!host_uaif0)
				writel(saved_sifs0_gate, cmu + ABOX_UAIF0_GATE);
		}
		if (saved_sifs0_bclk && clk_set_rate(sifs0_bclk, saved_sifs0_bclk) && !ret)
			ret = -EIO;
		if (saved_bclk && clk_set_rate(bclk, saved_bclk) && !ret)
			ret = -EIO;
	}
	clk_put(sifs0_bclk);
	clk_put(bclk);
	clk_put(pll);
	kvfree(saved_sram);
	if (sysreg)
		iounmap(sysreg);
	if (sram)
		iounmap(sram);
	if (sfr)
		iounmap(sfr);
	if (cmu)
		iounmap(cmu);
	return ret;
}
