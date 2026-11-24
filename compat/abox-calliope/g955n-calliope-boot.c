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
#define IPC_SYSTEM		1
#define IPC_RESUME		2
#define IPC_BOOT_DONE		3
#define IPC_CHANGE_GEAR		4
#define IPC_CHANGED_GEAR	9
#define ABOX_BOOT_GEAR_ID	0xb00d
#define ABOX_BOOT_GEAR		3
#define ABOX_GEAR_RELEASE	12
#define ABOX_48K_PLL_RATE	1179648000UL
#define IPC_REPORT_COMPONENT	0xc0
#define IPC_REPORT_FAULT	0xfa
#define IPC_ERAP		5
#define IPC_REALTIME_EXTRA	0xea
#define DSM_PARAMETER_WORDS	185
#define DSM_ENABLE_WORD		1
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

static int calliope_send(void __iomem *sram, u32 ipc, u32 message,
			 u32 param1, u32 param2, u32 param3)
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
	writel(1, sram + IPC_TX_ACK);
	writel(ABOX_GIC_CA7 | ipc, gicd + ABOX_GICD_SGIR);
	ret = readl_poll_timeout(sram + IPC_TX_ACK, ack, !ack, 100, 20000);

	iounmap(gicd);
	return ret;
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
				      const void *dram, u32 addr)
{
	struct calliope_component component;
	size_t remaining;
	u32 offset, count;

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
	return 0;
}

static int calliope_wait_boot(struct device *dev, void __iomem *sram,
			      const void *dram)
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

			ret = calliope_component_report(dev, sram, dram, addr);
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

static int calliope_read_dsm(struct device *dev, void __iomem *sram,
			     const void *dram, unsigned long ca7_rate)
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
			return 0;
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

int g955n_calliope_boot(struct device *dev, const struct firmware *fw,
		       const void *dram, bool try_resume, bool try_dsm_read,
		       bool *keep_dma)
{
	void __iomem *sysreg = NULL, *sram = NULL, *cmu = NULL, *sfr = NULL;
	struct resource cmu_res, sfr_res;
	struct device_node *node;
	struct clk *pll = NULL;
	struct regmap *pmu;
	void *saved_sram = NULL;
	u32 saved_l2, saved_misc, saved_syspower, state, option, power;
	unsigned long ca7_rate = 0;
	int ret, stop;

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
	of_node_put(node);
	if (ret)
		return ret;
	if (IS_ERR(pmu))
		return PTR_ERR(pmu);
	if (IS_ERR(pll))
		return PTR_ERR(pll);

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
	if ((readl(sfr + 0x500) | readl(sfr + 0x540)) & 3 ||
	    (readl(sfr + 0x1000) | readl(sfr + 0x2100)) & 1) {
		ret = -EBUSY;
		goto out;
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
		ret = calliope_wait_boot(dev, sram, dram);
		if (!ret && try_resume) {
			dev_info(dev, "Calliope sending system RESUME\n");
			ret = calliope_send(sram, IPC_SYSTEM, IPC_RESUME, 0, 0, 0);
			if (!ret)
				dev_info(dev, "Calliope acknowledged system RESUME\n");
		}
		if (!ret && try_dsm_read)
			ret = calliope_read_dsm(dev, sram, dram, ca7_rate);
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
	if (stop) {
		*keep_dma = true;
		dev_crit(dev, "Calliope still active; DMA mappings retained until reboot\n");
		ret = stop;
		goto out;
	}

	memcpy_toio(sram, saved_sram, ABOX_SRAM_SIZE);
	writel(saved_l2, sysreg + ABOX_SYSREG_L2);
	writel(saved_misc, sysreg + ABOX_SYSREG_MISC);
	writel(saved_syspower, sfr + ABOX_SYSPOWER_CTRL);
	dev_info(dev, "Calliope powered off; SRAM and system registers restored\n");
out:
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
