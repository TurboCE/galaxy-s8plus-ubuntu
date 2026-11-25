// SPDX-License-Identifier: GPL-2.0-only
/*
 * Bounded Exynos8895 CSIS1 receiver and opt-in VC0 DMA tests.
 * Register offsets, D-PHY settings and mode from Samsung FIMC-IS sources.
 */
#include <dt-bindings/clock/samsung,exynos8895.h>
#include <linux/bitfield.h>
#include <linux/clk.h>
#include <linux/delay.h>
#include <linux/dma-mapping.h>
#include <linux/iommu.h>
#include <linux/io.h>
#include <linux/iopoll.h>
#include <linux/ioport.h>
#include <linux/mfd/syscon.h>
#include <linux/mm.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/regmap.h>
#include <linux/sizes.h>

#define CAM_CMU_BASE		0x12c00000
#define CAM_STATUS		0x4024
#define CAM_PWR_MASK		GENMASK(3, 0)
#define CAM_BUS_USER		0x0100
#define CAM_CSIS1_ACLK		0x2060
#define CAM_CSIS1_APB_ASYNCM	0x202c
#define CAM_CSIS1_APB_ASYNCS	0x210c
#define CAM_GATE_ON		BIT(21)
#define CAM_DMA_ACLK		0x2078
#define CAM_DMA_APB_ASYNCM	0x2038
#define CAM_DMA_APB_ASYNCS	0x2118
#define CAM_DMA_QCH		0x3028
#define CAM_DMA_QE_QCH		0x3038
#define CAM_GATE_MANUAL		BIT(20)
#define CAM_GATE_AUTO		BIT(28)
#define CAM_QCH_REQUESTED	(BIT(0) | BIT(1))
#define CAM_SYSREG_RESET	0x12c21050
#define CAM_CSIS1_RESET		BIT(2)
#define CAM_CSIS3_RESET		BIT(3)
#define CAM_PHY_ISOLATION	0x0730
#define CAM_PHY_BYPASS		BIT(0)

#define CSIS1_BASE		0x12cb0000
#define CSIS1_SIZE		0x1420
#define CSIS_VERSION		0x0000
#define CSIS_COMMON		0x0004
#define	CSIS_INTERRUPT_MASK	0x0010
#define	CSIS_INTERRUPT_SOURCE	0x0014
#define	CSIS_INTERRUPT_MASK1	0x0018
#define	CSIS_INTERRUPT_SOURCE1	0x001c
#define CSIS_ISP_CONFIG		0x0040
#define CSIS_ISP_RESOLUTION	0x0044
#define CSIS_FRAME_COUNTER	0x0100
#define CSIS_PHY_STATUS		0x0700
#define CSIS_PHY_COMMON		0x0704
#define CSIS_DMA_BASE		0x1000
#define CSIS_DMA_STRIDE		0x0100
#define CSIS_DMA_ACTIVE		0x0030
#define CSIS_VC_COUNT		4
#define CSIS_VER_SM_G955N	0x03070000
#define CSIS_CMN_ENABLE		BIT(0)
#define CSIS_CMN_LANES		GENMASK(9, 8)
#define CSIS_CMN_UPDATE		GENMASK(19, 16)
#define CSIS_CMN_INTERLEAVE	GENMASK(11, 10)
#define CSIS_CMN_PHY_SELECT	BIT(21)
#define CSIS_PHY_SETTLE		GENMASK(31, 24)
#define CSIS_PHY_CLK_SETTLE	GENMASK(23, 16)
#define CSIS_PHY_LANES		GENMASK(4, 1)
#define CSIS_PHY_CLOCK		BIT(0)
#define CSIS_ISP_PIXEL_MODE	GENMASK(13, 12)
#define CSIS_ISP_PARALLEL	BIT(11)
#define CSIS_ISP_FORMAT		GENMASK(7, 2)
#define CSIS_ISP_VC		GENMASK(1, 0)
#define CSIS_RAW10		0x2b
#define CSIS_VC0_START		BIT(24)
#define CSIS_VC0_END		BIT(20)
#define CSIS_RX_ERRORS		GENMASK(19, 0)
#define CSIS_DMA_DISABLE	BIT(0)
#define CSIS_DMA_UPDATE		BIT(1)
#define CSIS_DMA_COMMON_BASE	0x12ce0000
#define CSIS_DMA_COMMON_ARB	0x00
#define CSIS_DMA_COMMON_CTRL	0x08
#define CSIS_DMA_COMMON_SRAM	0x0c
#define CSIS_DMA_COMMON_MATRIX	0x10
#define CSIS_DMA_IP_PROCESSING	BIT(1)
#define CSIS_DMA_SW_RESET	BIT(0)
#define CSIS_DMA0_FMT		0x1004
#define CSIS_DMA0_SKIP		0x1008
#define CSIS_DMA0_ADDR		0x1010
#define CSIS_DMA0_ACT_FMT	0x1034
#define CSIS_DMA0_RESOL		0x1040
#define CSIS_DMA0_SEQ		0x1050
#define CSIS_DMA_DATA_CTRL	0x1400
#define CSIS_DMA_INT_MASK	0x1404
#define CSIS_DMA_INT_SOURCE	0x1408
#define CSIS_DMA_CTRL		0x1414
#define CSIS_DMA_ERROR_CODE	0x1418
#define CSIS_DMA_ABORT_DONE	BIT(16)
#define CSIS_DMA_VC0_END	BIT(8)
#define CSIS_DMA_ERRORS		(GENMASK(23, 20) | BIT(12))
#define CSIS_DMA_PACK12		BIT(3)
#define CSIS_DMA_ADDR_COUNT	8
#define CSIS_WIDTH		1632
#define CSIS_HEIGHT		918
#define CSIS_DMA_STRIDE_BYTES	ALIGN(CSIS_WIDTH * 5 / 4, 16)
#define CSIS_FRAME_BYTES	(CSIS_HEIGHT * CSIS_DMA_STRIDE_BYTES)
#define CSIS_BUFFER_BYTES	SZ_4M
#define CSIS_DMA_SENTINEL	0xa5

static bool clock_status;
module_param(clock_status, bool, 0400);
MODULE_PARM_DESC(clock_status, "Read the three CSIS1 gates with the camera bus enabled");
static uint clock_register;
module_param(clock_register, uint, 0400);
MODULE_PARM_DESC(clock_register, "Read one selected CAM CMU mux, DMA gate or Q-channel offset");
static bool dma_common_status;
module_param(dma_common_status, bool, 0400);
MODULE_PARM_DESC(dma_common_status, "Read the CSISx4 DMA common control with its clocks held");
static bool dma_common_setup;
module_param(dma_common_setup, bool, 0400);
MODULE_PARM_DESC(dma_common_setup, "Verify and restore the stock CSISx4 DMA common settings");
static bool capture;
module_param(capture, bool, 0400);
MODULE_PARM_DESC(capture, "Check VC0 writes to a translated buffer without exporting pixels");
static bool capture_unsafe;

static int g955n_csis1_read_register(resource_size_t addr, u32 *value)
{
	void __iomem *reg;
	int ret = 0;

	if (!request_mem_region(addr, sizeof(*value), KBUILD_MODNAME))
		return -EBUSY;
	reg = ioremap(addr, sizeof(*value));
	if (reg) {
		*value = readl(reg);
		iounmap(reg);
	} else {
		ret = -ENOMEM;
	}
	release_mem_region(addr, sizeof(*value));
	return ret;
}

static int g955n_csis1_check_clocks(const u32 *offsets, size_t count)
{
	unsigned int i;
	u32 value;
	int ret;

	for (i = 0; i < count; i++) {
		ret = g955n_csis1_read_register(CAM_CMU_BASE + offsets[i], &value);
		if (ret)
			return ret;
		if (!(value & CAM_GATE_ON) ||
		    (!(value & CAM_GATE_MANUAL) && (value & CAM_GATE_AUTO))) {
			pr_info(KBUILD_MODNAME ": camera clock gate %#x is off (%#x)\n",
				offsets[i], value);
			return -EACCES;
		}
	}
	return 0;
}

static int g955n_csis1_clock_status(void)
{
	static const struct {
		u32 offset;
		const char *name;
	} gates[] = {
		{ CAM_CSIS1_ACLK, "CSIS1 ACLK" },
		{ CAM_CSIS1_APB_ASYNCM, "CSIS1 async master" },
		{ CAM_CSIS1_APB_ASYNCS, "CSIS1 async peripheral" },
	};
	unsigned int i;
	u32 value;
	int ret;

	for (i = 0; i < ARRAY_SIZE(gates); i++) {
		ret = g955n_csis1_read_register(CAM_CMU_BASE + gates[i].offset, &value);
		if (ret)
			return ret;
		pr_info(KBUILD_MODNAME ": %s=%#08x manual=%u gate=%u auto=%u\n",
			gates[i].name, value, !!(value & CAM_GATE_MANUAL),
			!!(value & CAM_GATE_ON), !!(value & CAM_GATE_AUTO));
	}
	pr_info(KBUILD_MODNAME ": CSIS1 gate snapshot complete\n");
	return 0;
}

static bool g955n_csis1_has_clock_register(uint offset)
{
	switch (offset) {
	case CAM_BUS_USER:
	case CAM_DMA_ACLK:
	case CAM_DMA_APB_ASYNCM:
	case CAM_DMA_APB_ASYNCS:
	case CAM_DMA_QCH:
	case CAM_DMA_QE_QCH:
		return true;
	default:
		return false;
	}
}

static int g955n_csis1_read_selected_clock(void)
{
	u32 value;
	int ret;

	pr_notice(KBUILD_MODNAME ": before CAM CMU register %#x\n", clock_register);
	ret = g955n_csis1_read_register(CAM_CMU_BASE + clock_register, &value);
	if (ret)
		return ret;
	pr_notice(KBUILD_MODNAME ": after CAM CMU register %#x value %#010x\n",
		  clock_register, value);
	return 0;
}

static int g955n_csis1_test(struct regmap *pmu);

static int g955n_csis1_dma_common(struct regmap *pmu)
{
	static const u32 clocks[] = { CAM_DMA_ACLK, CAM_DMA_APB_ASYNCM, CAM_DMA_APB_ASYNCS };
	static const u32 qchannels[] = { CAM_DMA_QCH, CAM_DMA_QE_QCH };
	static const struct {
		u32 offset;
		u32 mask;
		u32 value;
	} stock[] = {
		{ CSIS_DMA_COMMON_ARB, GENMASK(3, 0), 0x6 },
		{ CSIS_DMA_COMMON_CTRL, CSIS_DMA_IP_PROCESSING, CSIS_DMA_IP_PROCESSING },
		{ CSIS_DMA_COMMON_SRAM, GENMASK(25, 16) | GENMASK(9, 0), 0x01400140 },
		{ CSIS_DMA_COMMON_MATRIX, GENMASK(4, 0), 0 },
	};
	const unsigned int size = CSIS_DMA_COMMON_MATRIX + sizeof(u32);
	u32 saved[ARRAY_SIZE(stock)];
	void __iomem *regs;
	u32 value;
	unsigned int i;
	int ret;

	ret = g955n_csis1_read_register(CAM_CMU_BASE + CAM_BUS_USER, &value);
	if (ret)
		return ret;
	if (!(value & BIT(4)))
		return -EACCES;
	ret = g955n_csis1_check_clocks(clocks, ARRAY_SIZE(clocks));
	if (ret)
		return ret;
	for (i = 0; i < ARRAY_SIZE(qchannels); i++) {
		ret = g955n_csis1_read_register(CAM_CMU_BASE + qchannels[i], &value);
		if (ret)
			return ret;
		if ((value & CAM_QCH_REQUESTED) != CAM_QCH_REQUESTED)
			return -EACCES;
	}

	pr_notice(KBUILD_MODNAME ": before CSISx4 DMA common control read\n");
	if (!request_mem_region(CSIS_DMA_COMMON_BASE, size, KBUILD_MODNAME))
		return -EBUSY;
	regs = ioremap(CSIS_DMA_COMMON_BASE, size);
	if (!regs) {
		ret = -ENOMEM;
		goto release;
	}
	value = readl(regs + CSIS_DMA_COMMON_CTRL);
	pr_notice(KBUILD_MODNAME ": CSISx4 DMA common control %#010x\n", value);
	if (!dma_common_setup && !capture)
		goto unmap;
	if (value & (CSIS_DMA_IP_PROCESSING | CSIS_DMA_SW_RESET)) {
		ret = -EBUSY;
		goto unmap;
	}

	for (i = 0; i < ARRAY_SIZE(stock); i++)
		saved[i] = readl(regs + stock[i].offset);
	for (i = 0; i < ARRAY_SIZE(stock); i++) {
		value = (saved[i] & ~stock[i].mask) | stock[i].value;
		writel(value, regs + stock[i].offset);
		if ((readl(regs + stock[i].offset) & stock[i].mask) != stock[i].value) {
			ret = -EIO;
			break;
		}
	}
	if (!ret)
		pr_info(KBUILD_MODNAME ": stock CSISx4 DMA common settings read back\n");
	if (!ret && capture)
		ret = g955n_csis1_test(pmu);
	if (capture_unsafe)
		goto unmap;

	for (i = ARRAY_SIZE(stock); i-- > 0;) {
		writel(saved[i], regs + stock[i].offset);
		if (readl(regs + stock[i].offset) != saved[i]) {
			pr_err(KBUILD_MODNAME ": CSISx4 DMA common restore failed at %#x\n",
			       stock[i].offset);
			ret = -EIO;
		}
	}
	if (!ret)
		pr_info(KBUILD_MODNAME ": CSISx4 DMA common settings restored\n");
unmap:
	iounmap(regs);
release:
	release_mem_region(CSIS_DMA_COMMON_BASE, size);
	return ret;
}

struct csis_phy_register {
	u32 offset;
	u32 value;
};

static const struct csis_phy_register csis1_phy[] = {
	{ 0x0708, 0x000001f4 }, { 0x070c, 0x00000800 },
	{ 0x0710, 0x10001249 }, { 0x0714, 0x00500002 },
	{ 0x0718, 0x9e003e00 }, { 0x071c, 0x00000046 },
	{ 0x0720, 0xc000002c }, { 0x0724, 0x0000c000 },
};

struct csis_snapshot {
	u32 common;
	u32 phy_common;
	u32 isp_config;
	u32 resolution;
	u32 dma[CSIS_VC_COUNT];
	u32 phy[ARRAY_SIZE(csis1_phy)];
};

static int g955n_csis1_arm(void __iomem *regs, struct csis_snapshot *saved)
{
	u32 value;
	unsigned int vc, i;

	if (readl(regs + CSIS_VERSION) != CSIS_VER_SM_G955N)
		return -ENODEV;
	saved->common = readl(regs + CSIS_COMMON);
	if ((saved->common & CSIS_CMN_ENABLE) ||
	    readl(regs + CSIS_INTERRUPT_MASK) || readl(regs + CSIS_INTERRUPT_MASK1) ||
	    readl(regs + CSIS_INTERRUPT_SOURCE) || readl(regs + CSIS_INTERRUPT_SOURCE1))
		return -EBUSY;
	for (vc = 0; vc < CSIS_VC_COUNT; vc++) {
		unsigned int dma = CSIS_DMA_BASE + vc * CSIS_DMA_STRIDE;

		if (readl(regs + dma + CSIS_DMA_ACTIVE) & BIT(0))
			return -EBUSY;
		saved->dma[vc] = readl(regs + dma);
	}
	saved->phy_common = readl(regs + CSIS_PHY_COMMON);
	saved->isp_config = readl(regs + CSIS_ISP_CONFIG);
	saved->resolution = readl(regs + CSIS_ISP_RESOLUTION);

	for (vc = 0; vc < CSIS_VC_COUNT; vc++) {
		unsigned int dma = CSIS_DMA_BASE + vc * CSIS_DMA_STRIDE;

		writel((saved->dma[vc] & ~CSIS_DMA_UPDATE) | CSIS_DMA_DISABLE, regs + dma);
	}
	for (vc = 0; vc < CSIS_VC_COUNT; vc++)
		if (!(readl(regs + CSIS_DMA_BASE + vc * CSIS_DMA_STRIDE) & CSIS_DMA_DISABLE))
			goto restore_dma;

	for (i = 0; i < ARRAY_SIZE(csis1_phy); i++) {
		saved->phy[i] = readl(regs + csis1_phy[i].offset);
		writel(csis1_phy[i].value, regs + csis1_phy[i].offset);
	}
	value = saved->phy_common & ~(CSIS_PHY_SETTLE | CSIS_PHY_CLK_SETTLE |
				      CSIS_PHY_LANES | CSIS_PHY_CLOCK);
	value |= FIELD_PREP(CSIS_PHY_SETTLE, 7) | FIELD_PREP(CSIS_PHY_CLK_SETTLE, 1) |
		 FIELD_PREP(CSIS_PHY_LANES, 3) | CSIS_PHY_CLOCK;
	writel(value, regs + CSIS_PHY_COMMON);
	value = saved->isp_config & ~(CSIS_ISP_FORMAT | CSIS_ISP_PIXEL_MODE |
				      CSIS_ISP_PARALLEL | CSIS_ISP_VC);
	value |= FIELD_PREP(CSIS_ISP_FORMAT, CSIS_RAW10) | FIELD_PREP(CSIS_ISP_PIXEL_MODE, 1);
	writel(value, regs + CSIS_ISP_CONFIG);
	writel((CSIS_HEIGHT << 16) | CSIS_WIDTH, regs + CSIS_ISP_RESOLUTION);
	value = saved->common & ~(CSIS_CMN_LANES | CSIS_CMN_INTERLEAVE | CSIS_CMN_PHY_SELECT);
	value |= FIELD_PREP(CSIS_CMN_LANES, 1) | FIELD_PREP(CSIS_CMN_UPDATE, 0xf);
	writel(value | CSIS_CMN_ENABLE, regs + CSIS_COMMON);
	return 0;

restore_dma:
	for (vc = 0; vc < CSIS_VC_COUNT; vc++)
		writel(saved->dma[vc], regs + CSIS_DMA_BASE + vc * CSIS_DMA_STRIDE);
	return -EIO;
}

static void g955n_csis1_disarm(void __iomem *regs, const struct csis_snapshot *saved)
{
	unsigned int i;

	writel(saved->common, regs + CSIS_COMMON);
	writel(saved->phy_common, regs + CSIS_PHY_COMMON);
	for (i = 0; i < ARRAY_SIZE(csis1_phy); i++)
		writel(saved->phy[i], regs + csis1_phy[i].offset);
	writel(saved->isp_config, regs + CSIS_ISP_CONFIG);
	writel(saved->resolution, regs + CSIS_ISP_RESOLUTION);
	for (i = 0; i < CSIS_VC_COUNT; i++)
		writel(saved->dma[i], regs + CSIS_DMA_BASE + i * CSIS_DMA_STRIDE);
	writel(readl(regs + CSIS_INTERRUPT_SOURCE), regs + CSIS_INTERRUPT_SOURCE);
	writel(readl(regs + CSIS_INTERRUPT_SOURCE1), regs + CSIS_INTERRUPT_SOURCE1);
}

static int g955n_csis1_observe(void __iomem *regs)
{
	u32 before = readl(regs + CSIS_FRAME_COUNTER), after = before, events = 0;
	unsigned int i, vc;

	pr_info("g955n-csis1-link-test: armed with all virtual-channel DMA disabled\n");
	for (i = 0; i < 180; i++) {
		msleep(10);
		for (vc = 0; vc < CSIS_VC_COUNT; vc++)
			if (readl(regs + CSIS_DMA_BASE + vc * CSIS_DMA_STRIDE +
				  CSIS_DMA_ACTIVE) & BIT(0))
				return -EIO;
		after = readl(regs + CSIS_FRAME_COUNTER);
		events |= readl(regs + CSIS_INTERRUPT_SOURCE);
		if (after - before >= 2 && (events & (CSIS_VC0_START | CSIS_VC0_END)) ==
					  (CSIS_VC0_START | CSIS_VC0_END))
			break;
	}
	pr_info("g955n-csis1-link-test: frames=%u start=%u end=%u errors=%08x phy=%08x\n",
		after - before, !!(events & CSIS_VC0_START), !!(events & CSIS_VC0_END),
		(u32)(events & CSIS_RX_ERRORS), readl(regs + CSIS_PHY_STATUS));
	if (events & CSIS_RX_ERRORS)
		return -EIO;
	return i == 180 ? -ETIMEDOUT : 0;
}

static int g955n_csis1_capture(void __iomem *regs)
{
	static const unsigned int offsets[] = {
		CSIS_DMA0_FMT, CSIS_DMA0_SKIP, CSIS_DMA0_RESOL, CSIS_DMA0_SEQ, CSIS_DMA_DATA_CTRL,
	};
	static const u32 settings[] = { CSIS_DMA_PACK12, 0, CSIS_WIDTH, 0xff, BIT(0) };
	u32 saved[ARRAY_SIZE(offsets)], addr[CSIS_DMA_ADDR_COUNT];
	struct platform_device *pdev;
	struct iommu_domain *domain;
	struct device_node *node;
	struct device *dev;
	struct page *pages;
	dma_addr_t iova;
	u8 *pixels;
	u32 events = 0, rx_source, status;
	unsigned int i;
	int ret, stopped;

	if (readl(regs + CSIS_DMA_INT_MASK) || readl(regs + CSIS_DMA_INT_SOURCE) ||
	    readl(regs + CSIS_DMA_CTRL))
		return -EBUSY;
	node = of_find_compatible_node(NULL, NULL, "samsung,sm-g955n-csis1-buffer-test");
	if (!node)
		return -ENODEV;
	pdev = of_find_device_by_node(node);
	of_node_put(node);
	if (!pdev)
		return -ENODEV;
	dev = &pdev->dev;
	domain = iommu_get_domain_for_dev(dev);
	ret = -ENODEV;
	if (!domain || !iommu_is_dma_domain(domain) ||
	    dev->coherent_dma_mask != DMA_BIT_MASK(32))
		goto put;
	ret = -ENOMEM;
	pages = alloc_pages(GFP_KERNEL | __GFP_NOWARN, get_order(CSIS_BUFFER_BYTES));
	if (!pages)
		goto put;
	pixels = page_address(pages);
	memset(pixels, CSIS_DMA_SENTINEL, CSIS_BUFFER_BYTES);
	iova = dma_map_page(dev, pages, 0, CSIS_BUFFER_BYTES, DMA_BIDIRECTIONAL);
	ret = -EIO;
	if (dma_mapping_error(dev, iova))
		goto free;
	ret = -ERANGE;
	if (!iova || !IS_ALIGNED(iova, 16) || iova > U32_MAX - (CSIS_BUFFER_BYTES - 1))
		goto unmap;
	for (i = 0; i < CSIS_BUFFER_BYTES; i += PAGE_SIZE)
		if (iommu_iova_to_phys(domain, iova + i) != page_to_phys(pages) + i)
			goto unmap;

	for (i = 0; i < ARRAY_SIZE(offsets); i++)
		saved[i] = readl(regs + offsets[i]);
	for (i = 0; i < CSIS_DMA_ADDR_COUNT; i++)
		addr[i] = readl(regs + CSIS_DMA0_ADDR + i * sizeof(u32));

	ret = -EIO;
	for (i = 0; i < ARRAY_SIZE(offsets); i++) {
		writel(settings[i], regs + offsets[i]);
		if (readl(regs + offsets[i]) != settings[i])
			goto restore;
	}
	for (i = 0; i < CSIS_DMA_ADDR_COUNT; i++) {
		writel(lower_32_bits(iova), regs + CSIS_DMA0_ADDR + i * sizeof(u32));
		if (readl(regs + CSIS_DMA0_ADDR + i * sizeof(u32)) != lower_32_bits(iova))
			goto restore;
	}

	/* Keep output disabled until the sensor has delivered a complete CSI frame. */
	pr_notice(KBUILD_MODNAME ": VC0 waiting for first CSI frame with DMA disabled\n");
	ret = readl_poll_timeout(regs + CSIS_INTERRUPT_SOURCE, status,
				 status & CSIS_VC0_END, 150, 2000000);
	if (ret)
		goto restore;
	pr_info(KBUILD_MODNAME ": first CSI frame source=%#08x before DMA enable\n", status);
	writel(status, regs + CSIS_INTERRUPT_SOURCE);
	writel(CSIS_DMA_UPDATE, regs + CSIS_DMA_BASE);
	pr_notice(KBUILD_MODNAME ": VC0 DMA armed with all eight slots mapped\n");
	for (i = 0; i < 2; i++) {
		ret = readl_poll_timeout(regs + CSIS_DMA_INT_SOURCE, status,
					 status & (CSIS_DMA_VC0_END | CSIS_DMA_ERRORS), 500, 500000);
		events |= status;
		if (ret || (status & CSIS_DMA_ERRORS))
			break;
		writel(status, regs + CSIS_DMA_INT_SOURCE);
	}
	rx_source = readl(regs + CSIS_INTERRUPT_SOURCE);
	pr_info(KBUILD_MODNAME ": VC0 DMA completed=%u events=%#08x rx=%#08x error=%#08x\n",
		i, events, rx_source, readl(regs + CSIS_DMA_ERROR_CODE));
	pr_info(KBUILD_MODNAME ": VC0 DMA active control=%#08x format=%#08x\n",
		readl(regs + CSIS_DMA_BASE + CSIS_DMA_ACTIVE), readl(regs + CSIS_DMA0_ACT_FMT));

	/* Block the next frame and wait for the DMA engine to acknowledge abort. */
	writel(CSIS_DMA_DISABLE, regs + CSIS_DMA_BASE);
	writel(BIT(0), regs + CSIS_DMA_CTRL);
	stopped = readl_poll_timeout(regs + CSIS_DMA_INT_SOURCE, status,
				     status & CSIS_DMA_ABORT_DONE, 1000, 120000);
	stopped = stopped ?: readl_poll_timeout(regs + CSIS_DMA_BASE + CSIS_DMA_ACTIVE,
						status, !(status & BIT(0)), 1000, 120000);
	if (stopped) {
		/* Keep the IOVA valid if completion of outstanding writes is unknown. */
		capture_unsafe = true;
		pr_err(KBUILD_MODNAME ": VC0 DMA stop not confirmed, retaining mapped buffer\n");
		return stopped;
	}
	writel(0, regs + CSIS_DMA_CTRL);
	writel(readl(regs + CSIS_DMA_INT_SOURCE), regs + CSIS_DMA_INT_SOURCE);
	pr_info(KBUILD_MODNAME ": VC0 DMA abort acknowledged and output inactive\n");
	if (events & CSIS_DMA_VC0_END) {
		unsigned int lines = 0;
		bool tail_changed;

		dma_sync_single_for_cpu(dev, iova, CSIS_BUFFER_BYTES, DMA_BIDIRECTIONAL);
		for (i = 0; i < CSIS_FRAME_BYTES; i += CSIS_DMA_STRIDE_BYTES)
			if (memchr_inv(pixels + i, CSIS_DMA_SENTINEL, CSIS_WIDTH * 5 / 4))
				lines++;
		tail_changed = memchr_inv(pixels + CSIS_FRAME_BYTES, CSIS_DMA_SENTINEL,
					 CSIS_BUFFER_BYTES - CSIS_FRAME_BYTES) != NULL;
		if (lines != CSIS_HEIGHT || tail_changed) {
			pr_err(KBUILD_MODNAME ": VC0 DMA extent failed: %u/%u lines, tail changed=%u\n",
			       lines, CSIS_HEIGHT, tail_changed);
			ret = -EIO;
		} else {
			pr_info(KBUILD_MODNAME ": VC0 RAW10 %u lines changed, tail intact\n", CSIS_HEIGHT);
		}
	}
	if ((events & CSIS_DMA_ERRORS) || (rx_source & CSIS_RX_ERRORS))
		ret = -EIO;
restore:
	for (i = 0; i < CSIS_DMA_ADDR_COUNT; i++)
		writel(addr[i], regs + CSIS_DMA0_ADDR + i * sizeof(u32));
	for (i = 0; i < ARRAY_SIZE(offsets); i++)
		writel(saved[i], regs + offsets[i]);
unmap:
	dma_unmap_page(dev, iova, CSIS_BUFFER_BYTES, DMA_BIDIRECTIONAL);
free:
	memzero_explicit(pixels, CSIS_BUFFER_BYTES);
	__free_pages(pages, get_order(CSIS_BUFFER_BYTES));
put:
	put_device(dev);
	return ret;
}

static int g955n_csis1_test(struct regmap *pmu)
{
	static const u32 clocks[] = {
		CAM_CSIS1_ACLK, CAM_CSIS1_APB_ASYNCM, CAM_CSIS1_APB_ASYNCS,
	};
	struct csis_snapshot saved;
	void __iomem *regs, *reset;
	unsigned int bus, isolation, reset_state;
	int ret;

	ret = g955n_csis1_read_register(CAM_CMU_BASE + CAM_BUS_USER, &bus);
	if (ret)
		return ret;
	if (!(bus & BIT(4)))
		return -EACCES;
	ret = g955n_csis1_check_clocks(clocks, ARRAY_SIZE(clocks));
	if (ret)
		return ret;

	ret = -EBUSY;
	if (!request_mem_region(CSIS1_BASE, CSIS1_SIZE, "g955n-csis1-link-test"))
		return ret;
	if (!request_mem_region(CAM_SYSREG_RESET, 4, "g955n-csis1-link-test"))
		goto release_csis;
	regs = ioremap(CSIS1_BASE, CSIS1_SIZE);
	reset = ioremap(CAM_SYSREG_RESET, 4);
	ret = -ENOMEM;
	if (!regs || !reset)
		goto unmap_test;

	ret = regmap_read(pmu, CAM_PHY_ISOLATION, &isolation);
	if (ret)
		goto unmap_test;
	reset_state = readl(reset);
	ret = -EBUSY;
	if ((reset_state & CAM_CSIS3_RESET) && (isolation & CAM_PHY_BYPASS))
		goto unmap_test;
	ret = regmap_update_bits(pmu, CAM_PHY_ISOLATION, CAM_PHY_BYPASS, CAM_PHY_BYPASS);
	if (ret)
		goto unmap_test;
	writel(reset_state & ~CAM_CSIS1_RESET, reset);
	udelay(10);
	writel(reset_state | CAM_CSIS1_RESET, reset);
	ret = g955n_csis1_arm(regs, &saved);
	if (!ret) {
		ret = capture ? g955n_csis1_capture(regs) : g955n_csis1_observe(regs);
		if (capture_unsafe) {
			writel(readl(reset) & ~CAM_CSIS1_RESET, reset);
			readl(reset);
			goto unmap_test;
		}
		g955n_csis1_disarm(regs, &saved);
	}
	writel((readl(reset) & ~CAM_CSIS1_RESET) | (reset_state & CAM_CSIS1_RESET), reset);
	if (regmap_update_bits(pmu, CAM_PHY_ISOLATION, CAM_PHY_BYPASS, isolation) && !ret)
		ret = -EIO;
	if (!ret)
		pr_info("g955n-csis1-link-test: receiver and shared PHY state restored\n");

unmap_test:
	if (reset)
		iounmap(reset);
	if (regs)
		iounmap(regs);
	release_mem_region(CAM_SYSREG_RESET, 4);
release_csis:
	release_mem_region(CSIS1_BASE, CSIS1_SIZE);
	return ret;
}

static int __init g955n_csis1_link_test(void)
{
	struct of_phandle_args spec = { .args_count = 1, .args = { CLK_DOUT_CMU_CAM_BUS } };
	struct regmap *pmu;
	struct clk *bus;
	unsigned int state;
	unsigned long initial_rate;
	int ret, restore;

	if (!of_machine_is_compatible("samsung,dream2lteks"))
		return -ENODEV;
	if (clock_status + dma_common_status + dma_common_setup + capture + !!clock_register > 1 ||
	    (clock_register && !g955n_csis1_has_clock_register(clock_register)))
		return -EINVAL;
	pmu = syscon_regmap_lookup_by_compatible("samsung,exynos8895-pmu");
	if (IS_ERR(pmu))
		return PTR_ERR(pmu);
	ret = regmap_read(pmu, CAM_STATUS, &state);
	if (ret)
		return ret;
	if ((state & CAM_PWR_MASK) != CAM_PWR_MASK)
		return -EACCES;
	spec.np = of_find_node_by_path("/soc@0/clock-controller@15a80000");
	if (!spec.np)
		return -ENODEV;
	bus = of_clk_get_from_provider(&spec);
	of_node_put(spec.np);
	if (IS_ERR(bus))
		return PTR_ERR(bus);
	initial_rate = clk_get_rate(bus);
	if (initial_rate != 33312500) {
		ret = -ERANGE;
		goto put;
	}
	ret = clk_set_rate_exclusive(bus, 133250000);
	if (ret)
		goto put;
	ret = clk_prepare_enable(bus);
	if (!ret) {
		pr_info("g955n-csis1-link-test: CAM clock %lu Hz in probe window\n",
			clk_get_rate(bus));
		if (clk_get_rate(bus) != 133250000)
			ret = -ERANGE;
		else if (clock_register)
			ret = g955n_csis1_read_selected_clock();
		else if (clock_status)
			ret = g955n_csis1_clock_status();
		else if (dma_common_status || dma_common_setup || capture)
			ret = g955n_csis1_dma_common(pmu);
		else
			ret = g955n_csis1_test(pmu);
		/* A failed stop requires reboot. Do not unload or release the buffer. */
		if (capture_unsafe)
			return 0;
		clk_disable_unprepare(bus);
	}
	clk_rate_exclusive_put(bus);
	restore = clk_set_rate(bus, initial_rate);
	if (restore || clk_get_rate(bus) != initial_rate)
		ret = ret ?: (restore ?: -EIO);
	else
		pr_info("g955n-csis1-link-test: CAM clock restored to %lu Hz\n", initial_rate);
put:
	clk_put(bus);
	/* Release the one-shot module so it can be used again without a reboot. */
	return ret ?: -EAGAIN;
}

module_init(g955n_csis1_link_test);
MODULE_DESCRIPTION("Exynos8895 CSIS1 short frame reception test");
MODULE_LICENSE("GPL");
