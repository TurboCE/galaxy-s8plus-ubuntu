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
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/pm_runtime.h>
#include <linux/property.h>
#include <linux/regmap.h>
#include <linux/sizes.h>

#if IS_ENABLED(CONFIG_MEDIA_CONTROLLER) && IS_REACHABLE(CONFIG_VIDEO_DEV) && \
	IS_REACHABLE(CONFIG_V4L2_FWNODE)
#define G955N_CSIS1_MEDIA
#include <linux/uaccess.h>
#include <linux/vmalloc.h>
#include <media/v4l2-async.h>
#include <media/v4l2-device.h>
#include <media/v4l2-fh.h>
#include <media/v4l2-ioctl.h>
#include <media/v4l2-subdev.h>
#endif

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
/* Both storage modes write four additional rows in this sensor mode. */
#define CSIS_DMA_HEIGHT		922
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
static bool raw10_pack12;
module_param(raw10_pack12, bool, 0400);
MODULE_PARM_DESC(raw10_pack12, "Use the stock PACK12 flag during the VC0 RAW10 test");
static bool capture_unsafe;

struct csis_capture {
	struct device *dev;
	void *pixels;
	int (*stream)(struct csis_capture *request, bool on);
	bool pack12;
};

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

static int g955n_csis1_test(struct regmap *pmu, struct csis_capture *request);

static int g955n_csis1_dma_common(struct regmap *pmu, struct csis_capture *request)
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
	if (!dma_common_setup && !request)
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
	if (!ret && request)
		ret = g955n_csis1_test(pmu, request);
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

static int g955n_csis1_capture(void __iomem *regs, struct csis_capture *request)
{
	static const unsigned int offsets[] = {
		CSIS_DMA0_FMT, CSIS_DMA0_SKIP, CSIS_DMA0_RESOL, CSIS_DMA0_SEQ, CSIS_DMA_DATA_CTRL,
	};
	const u32 settings[] = { request->pack12 ? CSIS_DMA_PACK12 : 0, 0, CSIS_WIDTH, 0xff, BIT(0) };
	const unsigned int stride = CSIS_WIDTH * (request->pack12 ? 3 : 4) / 2;
	const unsigned int frame_bytes = CSIS_DMA_HEIGHT * stride;
	u32 saved[ARRAY_SIZE(offsets)], addr[CSIS_DMA_ADDR_COUNT];
	struct platform_device *pdev, *cam0;
	struct iommu_domain *domain;
	struct device_node *node;
	struct device *dev;
	struct page *pages;
	dma_addr_t iova;
	u8 *pixels;
	u32 events = 0, rx_source, status;
	unsigned int i;
	int ret, stopped;
	bool streaming = false;

	if (readl(regs + CSIS_DMA_INT_MASK) || readl(regs + CSIS_DMA_INT_SOURCE) ||
	    readl(regs + CSIS_DMA_CTRL))
		return -EBUSY;
	if (request->dev) {
		dev = get_device(request->dev);
	} else {
		node = of_find_compatible_node(NULL, NULL, "samsung,sm-g955n-csis1-buffer-test");
		if (!node)
			return -ENODEV;
		pdev = of_find_device_by_node(node);
		of_node_put(node);
		if (!pdev)
			return -ENODEV;
		dev = &pdev->dev;
	}
	domain = iommu_get_domain_for_dev(dev);
	ret = -ENODEV;
	if (!domain || !iommu_is_dma_domain(domain) ||
	    dev->coherent_dma_mask != DMA_BIT_MASK(32))
		goto put;

	/* The buffer-only platform device does not take a runtime PM reference. */
	node = of_parse_phandle(dev->of_node, "iommus", 0);
	if (!node)
		goto put;
	cam0 = of_find_device_by_node(node);
	of_node_put(node);
	if (!cam0)
		goto put;
	ret = pm_runtime_resume_and_get(&cam0->dev);
	if (ret < 0)
		goto put_cam0;
	if (!pm_runtime_active(&cam0->dev)) {
		ret = -EIO;
		goto suspend_cam0;
	}
	pr_info(KBUILD_MODNAME ": CAM0 System MMU active for VC0 DMA\n");
	ret = -ENOMEM;
	pages = alloc_pages(GFP_KERNEL | __GFP_NOWARN, get_order(CSIS_BUFFER_BYTES));
	if (!pages)
		goto suspend_cam0;
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
	if (request->stream) {
		ret = request->stream(request, true);
		if (ret)
			goto restore;
		streaming = true;
	}
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
		if (request->dev)
			__module_get(THIS_MODULE);
		if (streaming)
			request->stream(request, false);
		return stopped;
	}
	writel(0, regs + CSIS_DMA_CTRL);
	writel(readl(regs + CSIS_DMA_INT_SOURCE), regs + CSIS_DMA_INT_SOURCE);
	pr_info(KBUILD_MODNAME ": VC0 DMA abort acknowledged and output inactive\n");
	if (events & CSIS_DMA_VC0_END) {
		unsigned int lines = 0;
		unsigned int extent = CSIS_BUFFER_BYTES;

		dma_sync_single_for_cpu(dev, iova, CSIS_BUFFER_BYTES, DMA_BIDIRECTIONAL);
		for (i = 0; i < frame_bytes; i += stride)
			if (memchr_inv(pixels + i, CSIS_DMA_SENTINEL, stride))
				lines++;
		while (extent && pixels[extent - 1] == CSIS_DMA_SENTINEL)
			extent--;
		if (lines != CSIS_DMA_HEIGHT || extent > frame_bytes) {
			pr_err(KBUILD_MODNAME ": VC0 DMA extent failed: %u/%u rows, %u bytes (expected at most %u)\n",
			       lines, CSIS_DMA_HEIGHT, extent, frame_bytes);
			ret = -EIO;
		} else {
			pr_info(KBUILD_MODNAME ": VC0 RAW10 %u rows at %u bytes per row, tail intact\n",
				lines, stride);
		}
		if (!ret && !request->pack12) {
			const __le16 *samples = (const __le16 *)pixels;
			unsigned int outside = 0;
			u16 minimum = U16_MAX, maximum = 0;

			for (i = 0; i < frame_bytes / sizeof(*samples); i++) {
				u16 value = le16_to_cpu(samples[i]);

				outside += value > GENMASK(9, 0);
				minimum = min(minimum, value);
				maximum = max(maximum, value);
			}
			pr_info(KBUILD_MODNAME ": VC0 little-endian samples outside 10-bit range=%u varied=%u\n",
				outside, minimum != maximum);
			if (outside || minimum == maximum)
				ret = -EIO;
		}
	}
	if ((events & CSIS_DMA_ERRORS) || (rx_source & CSIS_RX_ERRORS))
		ret = -EIO;
	if (!ret && request->pixels)
		memcpy(request->pixels, pixels, frame_bytes);
restore:
	if (streaming) {
		stopped = request->stream(request, false);
		ret = ret ?: stopped;
	}
	for (i = 0; i < CSIS_DMA_ADDR_COUNT; i++)
		writel(addr[i], regs + CSIS_DMA0_ADDR + i * sizeof(u32));
	for (i = 0; i < ARRAY_SIZE(offsets); i++)
		writel(saved[i], regs + offsets[i]);
unmap:
	dma_unmap_page(dev, iova, CSIS_BUFFER_BYTES, DMA_BIDIRECTIONAL);
free:
	memzero_explicit(pixels, CSIS_BUFFER_BYTES);
	__free_pages(pages, get_order(CSIS_BUFFER_BYTES));
suspend_cam0:
	pm_runtime_put_sync(&cam0->dev);
put_cam0:
	put_device(&cam0->dev);
put:
	put_device(dev);
	return ret;
}

static int g955n_csis1_test(struct regmap *pmu, struct csis_capture *request)
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
		ret = request ? g955n_csis1_capture(regs, request) : g955n_csis1_observe(regs);
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

static int g955n_csis1_run(struct csis_capture *request)
{
	struct of_phandle_args spec = { .args_count = 1, .args = { CLK_DOUT_CMU_CAM_BUS } };
	struct regmap *pmu;
	struct clk *bus;
	unsigned int state;
	unsigned long initial_rate;
	int ret, restore;

	if (!of_machine_is_compatible("samsung,dream2lteks"))
		return -ENODEV;
	if (capture_unsafe)
		return -EIO;
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
		else if (dma_common_status || dma_common_setup || request)
			ret = g955n_csis1_dma_common(pmu, request);
		else
			ret = g955n_csis1_test(pmu, NULL);
		/* A failed stop requires reboot. Do not unload or release the buffer. */
		if (capture_unsafe)
			return ret;
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
	return ret;
}

#ifdef G955N_CSIS1_MEDIA
struct csis_video {
	struct v4l2_device v4l2;
	struct v4l2_async_notifier notifier;
	struct mutex lock;
	struct video_device *video;
	struct v4l2_subdev *sensor;
	u32 sensor_pad;
};

struct csis_video_capture {
	struct csis_capture request;
	struct csis_video *camera;
};

static bool video;
module_param(video, bool, 0400);
MODULE_PARM_DESC(video, "Register the DT-connected V4L2 read capture device");

static int g955n_csis1_video_stream(struct csis_capture *request, bool on)
{
	struct csis_video_capture *capture = container_of(request, struct csis_video_capture, request);
	struct csis_video *camera = capture->camera;

	if (on)
		return v4l2_subdev_enable_streams(camera->sensor, camera->sensor_pad, BIT_ULL(0));
	return v4l2_subdev_disable_streams(camera->sensor, camera->sensor_pad, BIT_ULL(0));
}

static ssize_t g955n_csis1_video_read(struct file *file, char __user *buf,
				     size_t size, loff_t *pos)
{
	struct csis_video *camera = video_drvdata(file);
	const unsigned int bytes = CSIS_WIDTH * CSIS_DMA_HEIGHT * sizeof(u16);
	struct csis_video_capture frame = {
		.camera = camera,
		.request.stream = g955n_csis1_video_stream,
	};
	ssize_t ret;

	if (!size)
		return 0;
	if (size < bytes)
		return -EINVAL;
	if (file->f_flags & O_NONBLOCK)
		return -EAGAIN;
	if (mutex_lock_interruptible(&camera->lock))
		return -ERESTARTSYS;
	ret = -ENODEV;
	if (!camera->sensor || camera->video != video_devdata(file))
		goto unlock;
	frame.request.dev = camera->v4l2.dev;
	frame.request.pixels = kvzalloc(bytes, GFP_KERNEL);
	if (!frame.request.pixels) {
		ret = -ENOMEM;
		goto unlock;
	}
	ret = g955n_csis1_run(&frame.request);
	if (!ret) {
		if (copy_to_user(buf, frame.request.pixels, bytes))
			ret = -EFAULT;
		else
			ret = bytes;
	}
	kvfree_sensitive(frame.request.pixels, bytes);
unlock:
	mutex_unlock(&camera->lock);
	return ret;
}

static int g955n_csis1_querycap(struct file *file, void *fh, struct v4l2_capability *cap)
{
	strscpy(cap->driver, "g955n-csis1", sizeof(cap->driver));
	strscpy(cap->card, "SM-G955N Front Camera", sizeof(cap->card));
	strscpy(cap->bus_info, "platform:12cb0000.csis", sizeof(cap->bus_info));
	return 0;
}

static int g955n_csis1_enum_fmt(struct file *file, void *fh, struct v4l2_fmtdesc *fmt)
{
	if (fmt->index)
		return -EINVAL;
	fmt->pixelformat = V4L2_PIX_FMT_SBGGR10;
	return 0;
}

static int g955n_csis1_fmt(struct file *file, void *fh, struct v4l2_format *fmt)
{
	fmt->fmt.pix = (struct v4l2_pix_format) {
		.width = CSIS_WIDTH,
		.height = CSIS_DMA_HEIGHT,
		.pixelformat = V4L2_PIX_FMT_SBGGR10,
		.field = V4L2_FIELD_NONE,
		.bytesperline = CSIS_WIDTH * sizeof(u16),
		.sizeimage = CSIS_WIDTH * CSIS_DMA_HEIGHT * sizeof(u16),
		.colorspace = V4L2_COLORSPACE_RAW,
		.quantization = V4L2_QUANTIZATION_FULL_RANGE,
		.xfer_func = V4L2_XFER_FUNC_NONE,
	};
	return 0;
}

static int g955n_csis1_enum_framesizes(struct file *file, void *fh,
				       struct v4l2_frmsizeenum *size)
{
	if (size->index || size->pixel_format != V4L2_PIX_FMT_SBGGR10)
		return -EINVAL;
	size->type = V4L2_FRMSIZE_TYPE_DISCRETE;
	size->discrete.width = CSIS_WIDTH;
	size->discrete.height = CSIS_DMA_HEIGHT;
	return 0;
}

static const struct v4l2_ioctl_ops g955n_csis1_video_ioctls = {
	.vidioc_querycap = g955n_csis1_querycap,
	.vidioc_enum_fmt_vid_cap = g955n_csis1_enum_fmt,
	.vidioc_g_fmt_vid_cap = g955n_csis1_fmt,
	.vidioc_try_fmt_vid_cap = g955n_csis1_fmt,
	.vidioc_s_fmt_vid_cap = g955n_csis1_fmt,
	.vidioc_enum_framesizes = g955n_csis1_enum_framesizes,
};

static const struct v4l2_file_operations g955n_csis1_video_fops = {
	.owner = THIS_MODULE,
	.open = v4l2_fh_open,
	.release = v4l2_fh_release,
	.read = g955n_csis1_video_read,
	.unlocked_ioctl = video_ioctl2,
};

static int g955n_csis1_video_bound(struct v4l2_async_notifier *notifier,
				   struct v4l2_subdev *sd, struct v4l2_async_connection *asc)
{
	struct csis_video *camera = container_of(notifier, struct csis_video, notifier);
	struct v4l2_subdev_format format = { .which = V4L2_SUBDEV_FORMAT_ACTIVE };
	int pad, ret;

	pad = media_entity_get_fwnode_pad(&sd->entity, asc->match.fwnode, MEDIA_PAD_FL_SOURCE);
	if (pad < 0)
		return pad;
	format.pad = pad;
	ret = v4l2_subdev_call_state_active(sd, pad, get_fmt, &format);
	if (ret)
		return ret;
	if (format.format.width != CSIS_WIDTH || format.format.height != CSIS_HEIGHT ||
	    format.format.code != MEDIA_BUS_FMT_SBGGR10_1X10)
		return -EINVAL;
	mutex_lock(&camera->lock);
	camera->sensor = sd;
	camera->sensor_pad = pad;
	mutex_unlock(&camera->lock);
	return 0;
}

static int g955n_csis1_video_complete(struct v4l2_async_notifier *notifier)
{
	struct csis_video *camera = container_of(notifier, struct csis_video, notifier);
	struct video_device *vdev;
	int ret;

	vdev = video_device_alloc();
	if (!vdev)
		return -ENOMEM;
	strscpy(vdev->name, "SM-G955N CSIS1", sizeof(vdev->name));
	vdev->v4l2_dev = &camera->v4l2;
	vdev->fops = &g955n_csis1_video_fops;
	vdev->ioctl_ops = &g955n_csis1_video_ioctls;
	vdev->release = video_device_release;
	vdev->lock = &camera->lock;
	vdev->device_caps = V4L2_CAP_VIDEO_CAPTURE | V4L2_CAP_READWRITE;
	video_set_drvdata(vdev, camera);
	mutex_lock(&camera->lock);
	ret = video_register_device(vdev, VFL_TYPE_VIDEO, -1);
	if (!ret)
		camera->video = vdev;
	mutex_unlock(&camera->lock);
	if (ret)
		video_device_release(vdev);
	return ret;
}

static void g955n_csis1_video_unbind(struct v4l2_async_notifier *notifier,
				     struct v4l2_subdev *sd, struct v4l2_async_connection *asc)
{
	struct csis_video *camera = container_of(notifier, struct csis_video, notifier);
	struct video_device *vdev;

	mutex_lock(&camera->lock);
	vdev = camera->video;
	camera->video = NULL;
	camera->sensor = NULL;
	mutex_unlock(&camera->lock);
	video_unregister_device(vdev);
}

static const struct v4l2_async_notifier_operations g955n_csis1_video_notifier_ops = {
	.bound = g955n_csis1_video_bound,
	.complete = g955n_csis1_video_complete,
	.unbind = g955n_csis1_video_unbind,
};

static void g955n_csis1_video_release(struct v4l2_device *v4l2)
{
	struct csis_video *camera = container_of(v4l2, struct csis_video, v4l2);

	mutex_destroy(&camera->lock);
	kfree(camera);
}

static int g955n_csis1_video_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct v4l2_async_connection *asc;
	struct fwnode_handle *endpoint;
	struct csis_video *camera;
	int ret;

	if (!of_machine_is_compatible("samsung,dream2lteks"))
		return -ENODEV;
	ret = dma_set_mask_and_coherent(dev, DMA_BIT_MASK(32));
	if (ret)
		return ret;
	endpoint = fwnode_graph_get_next_endpoint(dev_fwnode(dev), NULL);
	if (!endpoint)
		return -ENODEV;
	camera = kzalloc(sizeof(*camera), GFP_KERNEL);
	if (!camera) {
		fwnode_handle_put(endpoint);
		return -ENOMEM;
	}
	mutex_init(&camera->lock);
	camera->v4l2.release = g955n_csis1_video_release;
	ret = v4l2_device_register(dev, &camera->v4l2);
	if (ret) {
		fwnode_handle_put(endpoint);
		g955n_csis1_video_release(&camera->v4l2);
		return ret;
	}

	v4l2_async_nf_init(&camera->notifier, &camera->v4l2);
	camera->notifier.ops = &g955n_csis1_video_notifier_ops;
	asc = v4l2_async_nf_add_fwnode_remote(&camera->notifier, endpoint,
					    struct v4l2_async_connection);
	fwnode_handle_put(endpoint);
	ret = IS_ERR(asc) ? PTR_ERR(asc) : v4l2_async_nf_register(&camera->notifier);
	if (ret) {
		v4l2_async_nf_cleanup(&camera->notifier);
		v4l2_device_unregister(&camera->v4l2);
		v4l2_device_put(&camera->v4l2);
	}
	return ret;
}

static void g955n_csis1_video_remove(struct platform_device *pdev)
{
	struct v4l2_device *v4l2 = platform_get_drvdata(pdev);
	struct csis_video *camera = container_of(v4l2, struct csis_video, v4l2);

	v4l2_async_nf_unregister(&camera->notifier);
	v4l2_async_nf_cleanup(&camera->notifier);
	v4l2_device_unregister(v4l2);
	v4l2_device_put(v4l2);
}

static const struct of_device_id g955n_csis1_video_match[] = {
	{ .compatible = "samsung,sm-g955n-csis1" },
	{ }
};

static struct platform_driver g955n_csis1_video_driver = {
	.probe = g955n_csis1_video_probe,
	.remove = g955n_csis1_video_remove,
	.driver = {
		.name = "g955n-csis1",
		.of_match_table = g955n_csis1_video_match,
	},
};
#endif

static int __init g955n_csis1_link_test(void)
{
	struct csis_capture request = { .pack12 = raw10_pack12 };
	int modes = clock_status + dma_common_status + dma_common_setup + capture + !!clock_register;
	int ret;

#ifdef G955N_CSIS1_MEDIA
	if (video) {
		if (modes)
			return -EINVAL;
		return platform_driver_register(&g955n_csis1_video_driver);
	}
#endif
	if (modes > 1 || (clock_register && !g955n_csis1_has_clock_register(clock_register)))
		return -EINVAL;
	ret = g955n_csis1_run(capture ? &request : NULL);
	/* Release the one-shot module after a stopped trial. */
	if (capture_unsafe) {
		__module_get(THIS_MODULE);
		return 0;
	}
	return ret ?: -EAGAIN;
}

#ifdef G955N_CSIS1_MEDIA
static void __exit g955n_csis1_exit(void)
{
	if (video)
		platform_driver_unregister(&g955n_csis1_video_driver);
}
module_exit(g955n_csis1_exit);
#endif

module_init(g955n_csis1_link_test);
MODULE_DESCRIPTION("SM-G955N CSIS1 front camera receiver");
MODULE_LICENSE("GPL");
