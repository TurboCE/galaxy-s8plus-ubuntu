// SPDX-License-Identifier: GPL-2.0-only
/* Inspect the SM-G955N Exynos8895 DSI controller inherited from the loader. */
#include <linux/bitfield.h>
#include <linux/io.h>
#include <linux/iopoll.h>
#include <linux/ioport.h>
#include <linux/mfd/syscon.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/regmap.h>
#include <video/mipi_display.h>

#define DSIM_BASE		0x12870000
#define DSIM_SIZE		0x100
#define DISP_POWER_STATUS	0x4064
#define DISP_POWER_MASK		GENMASK(3, 0)
#define DSIM_LINK_STATUS3	0x14
#define DSIM_DPHY_STATUS	0x1c
#define DSIM_CLK_CTRL		0x20
#define DSIM_TIMEOUT		0x28
#define DSIM_ESCMODE		0x2c
#define DSIM_RESOL		0x3c
#define DSIM_CONFIG		0x4c
#define DSIM_INTSRC		0x50
#define DSIM_INTMSK		0x54
#define DSIM_PKTHDR		0x58
#define DSIM_RXFIFO		0x60
#define DSIM_FIFOCTRL		0x68
#define DSIM_CMD_CONFIG		0x80
#define DSIM_BTA_TIMEOUT	GENMASK(31, 16)
#define G955N_BTA_WAIT		0xfff
#define DSIM_RX_EMPTY		BIT(12)
#define DSIM_HDR_EMPTY		BIT(10)
#define DSIM_PL_EMPTY		BIT(8)
#define DSIM_FIFO_IDLE		(DSIM_RX_EMPTY | DSIM_HDR_EMPTY | DSIM_PL_EMPTY)
#define DSIM_BTA		BIT(24)
#define DSIM_RX_DONE		BIT(18)
#define DSIM_RX_FAULTS		(BIT(21) | BIT(20) | BIT(15))
#define DSIM_LINK_LOCK		BIT(0)
#define DSIM_PHY_READY		BIT(10)
#define G955N_PANEL_ID_LEN	3

static bool read_id;
module_param(read_id, bool, 0400);
MODULE_PARM_DESC(read_id, "Read only the display family's three-byte DCS ID");

static int g955n_dsim_read_id(void __iomem *dsi)
{
	u32 fifo, phy, status, timeout, word;
	u8 id[G955N_PANEL_ID_LEN];
	bool valid = false;
	unsigned int i;
	int ret;

	/* Noncontinuous clocking leaves HS briefly between scanout bursts. */
	ret = readl_poll_timeout(dsi + DSIM_DPHY_STATUS, phy,
				 phy & DSIM_PHY_READY, 100, 50000);
	if (ret) {
		pr_info("g955n-dsim: no ready clock lane: phy=%08x\n", phy);
		return ret;
	}

	fifo = readl(dsi + DSIM_FIFOCTRL);
	status = readl(dsi + DSIM_INTSRC);
	if ((fifo & DSIM_FIFO_IDLE) != DSIM_FIFO_IDLE ||
	    status & (DSIM_RX_DONE | DSIM_RX_FAULTS) ||
	    !(readl(dsi + DSIM_LINK_STATUS3) & DSIM_LINK_LOCK)) {
		pr_info("g955n-dsim: read skipped: fifo=%08x irq=%08x phy=%08x\n",
			fifo, status, phy);
		return -EBUSY;
	}

	/* The loader's 0xff-cycle turnaround expires before the panel replies. */
	timeout = readl(dsi + DSIM_TIMEOUT);
	writel((timeout & ~DSIM_BTA_TIMEOUT) |
	       FIELD_PREP(DSIM_BTA_TIMEOUT, G955N_BTA_WAIT), dsi + DSIM_TIMEOUT);

	writel(MIPI_DSI_SET_MAXIMUM_RETURN_PACKET_SIZE | (G955N_PANEL_ID_LEN << 8),
	       dsi + DSIM_PKTHDR);
	ret = readl_poll_timeout(dsi + DSIM_FIFOCTRL, fifo,
				 fifo & DSIM_HDR_EMPTY, 200, 20000);
	if (ret) {
		pr_info("g955n-dsim: maximum return size timeout: fifo=%08x irq=%08x\n",
			fifo, readl(dsi + DSIM_INTSRC));
		goto restore_timeout;
	}

	writel(DSIM_BTA | MIPI_DSI_DCS_READ | (MIPI_DCS_GET_DISPLAY_ID << 8),
	       dsi + DSIM_PKTHDR);
	ret = readl_poll_timeout(dsi + DSIM_INTSRC, status,
				 status & (DSIM_RX_DONE | DSIM_RX_FAULTS), 200, 50000);
	if (ret) {
		pr_info("g955n-dsim: DCS response timeout: fifo=%08x irq=%08x\n",
			readl(dsi + DSIM_FIFOCTRL), status);
		goto restore_timeout;
	}

	for (i = 0; i < 64 && !(readl(dsi + DSIM_FIFOCTRL) & DSIM_RX_EMPTY); i++) {
		word = readl(dsi + DSIM_RXFIFO);
		if ((word & 0x3f) == MIPI_DSI_RX_DCS_LONG_READ_RESPONSE &&
		    FIELD_GET(GENMASK(23, 8), word) == G955N_PANEL_ID_LEN &&
		    !(readl(dsi + DSIM_FIFOCTRL) & DSIM_RX_EMPTY)) {
			word = readl(dsi + DSIM_RXFIFO);
			id[0] = word;
			id[1] = word >> 8;
			id[2] = word >> 16;
			valid = true;
		}
	}
	writel(status & (DSIM_RX_DONE | DSIM_RX_FAULTS), dsi + DSIM_INTSRC);
	if (status & DSIM_RX_FAULTS || i == 64 || !valid) {
		pr_info("g955n-dsim: DCS response rejected: irq=%08x entries=%u\n",
			status, i);
		ret = -EPROTO;
		goto restore_timeout;
	}

	pr_info("g955n-dsim: panel family ID %*phN\n", G955N_PANEL_ID_LEN, id);
	restore_timeout:
	writel(timeout, dsi + DSIM_TIMEOUT);
	pr_info("g955n-dsim: restored timeout=%08x\n", readl(dsi + DSIM_TIMEOUT));
	return ret;
}

static int __init g955n_dsim_identify(void)
{
	struct regmap *pmu;
	void __iomem *dsi;
	unsigned int power;
	int ret;

	if (!of_machine_is_compatible("samsung,dream2lteks"))
		return -ENODEV;

	pmu = syscon_regmap_lookup_by_compatible("samsung,exynos8895-pmu");
	if (IS_ERR(pmu))
		return PTR_ERR(pmu);
	ret = regmap_read(pmu, DISP_POWER_STATUS, &power);
	if (ret)
		return ret;
	if ((power & DISP_POWER_MASK) != DISP_POWER_MASK)
		return -EHOSTDOWN;
	if (!request_mem_region(DSIM_BASE, DSIM_SIZE, KBUILD_MODNAME))
		return -EBUSY;
	dsi = ioremap(DSIM_BASE, DSIM_SIZE);
	if (!dsi) {
		ret = -ENOMEM;
		goto release;
	}

	pr_info("g955n-dsim: link=%08x phy=%08x clock=%08x escape=%08x resolution=%08x config=%08x irq=%08x mask=%08x fifo=%08x\n",
		readl(dsi + DSIM_LINK_STATUS3), readl(dsi + DSIM_DPHY_STATUS),
		readl(dsi + DSIM_CLK_CTRL), readl(dsi + DSIM_ESCMODE),
		readl(dsi + DSIM_RESOL), readl(dsi + DSIM_CONFIG),
		readl(dsi + DSIM_INTSRC), readl(dsi + DSIM_INTMSK),
		readl(dsi + DSIM_FIFOCTRL));
	pr_info("g955n-dsim: timeout=%08x command=%08x\n",
		readl(dsi + DSIM_TIMEOUT), readl(dsi + DSIM_CMD_CONFIG));
	if (read_id)
		ret = g955n_dsim_read_id(dsi);
	iounmap(dsi);

release:
	release_mem_region(DSIM_BASE, DSIM_SIZE);
	return ret;
}
module_init(g955n_dsim_identify);

MODULE_DESCRIPTION("SM-G955N inherited DSI status and panel identification");
MODULE_LICENSE("GPL");
