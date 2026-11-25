// SPDX-License-Identifier: GPL-2.0-only
/* Inspect the SM-G955N Exynos8895 DSI controller inherited from the loader. */
#include <linux/bitfield.h>
#include <linux/delay.h>
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
#define DSIM_PAYLOAD		0x5c
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

static bool read_calibration;
module_param(read_calibration, bool, 0400);
MODULE_PARM_DESC(read_calibration, "Validate reads of S6E3HA6 brightness calibration");

#ifdef G955N_WITH_AID
static bool test_aor;
module_param(test_aor, bool, 0400);
MODULE_PARM_DESC(test_aor, "Temporarily dim via AOR and verify restoration");
#endif

#define S6E3HA6_MTP		0xc8
#define S6E3HA6_MTP_LEN		35
#define S6E3HA6_ELVSS		0xb5
#define S6E3HA6_ELVSS_LEN	24
#define S6E3HA6_HBM_GAMMA	0xb3
#define S6E3HA6_HBM_OFFSET	2
#define S6E3HA6_HBM_LEN		33
#define S6E3HA6_GPARA		0xb0
#define DSIM_TX_EMPTY		(DSIM_HDR_EMPTY | DSIM_PL_EMPTY)
#define DSIM_RX_EVENTS		(DSIM_RX_DONE | DSIM_RX_FAULTS)
#define DSIM_RX_WORD_LIMIT	64

static int g955n_dsim_ready(void __iomem *dsi)
{
	u32 fifo, phy, status;
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
	    status & DSIM_RX_EVENTS ||
	    !(readl(dsi + DSIM_LINK_STATUS3) & DSIM_LINK_LOCK)) {
		pr_info("g955n-dsim: command skipped: fifo=%08x irq=%08x phy=%08x\n",
			fifo, status, phy);
		return -EBUSY;
	}
	return 0;
}

static int g955n_dsim_wait_tx(void __iomem *dsi)
{
	u32 fifo;

	return readl_poll_timeout(dsi + DSIM_FIFOCTRL, fifo,
				 (fifo & DSIM_TX_EMPTY) == DSIM_TX_EMPTY, 100, 50000);
}

static int g955n_dsim_read(void __iomem *dsi, u8 address, u8 *data, size_t len)
{
	u32 status, word;
	unsigned int budget = DSIM_RX_WORD_LIMIT;
	size_t offset;
	bool received = false, malformed = false;
	int ret;

	ret = g955n_dsim_ready(dsi);
	if (ret)
		return ret;

	writel(MIPI_DSI_SET_MAXIMUM_RETURN_PACKET_SIZE | (len << 8),
	       dsi + DSIM_PKTHDR);
	ret = g955n_dsim_wait_tx(dsi);
	if (ret)
		return ret;

	writel(DSIM_BTA | MIPI_DSI_DCS_READ | (address << 8), dsi + DSIM_PKTHDR);
	ret = readl_poll_timeout(dsi + DSIM_INTSRC, status,
				 status & DSIM_RX_EVENTS, 200, 50000);
	if (ret)
		return ret;

	while (budget && !(readl(dsi + DSIM_FIFOCTRL) & DSIM_RX_EMPTY)) {
		word = readl(dsi + DSIM_RXFIFO);
		budget--;
		if ((word & 0x3f) == MIPI_DSI_RX_END_OF_TRANSMISSION)
			continue;
		if (!received && len == 2 &&
		    (word & 0x3f) == MIPI_DSI_RX_DCS_SHORT_READ_RESPONSE_2BYTE) {
			data[0] = word >> 8;
			data[1] = word >> 16;
			received = true;
			continue;
		}
		if ((word & 0x3f) != MIPI_DSI_RX_DCS_LONG_READ_RESPONSE ||
		    FIELD_GET(GENMASK(23, 8), word) != len || received) {
			malformed = true;
			break;
		}

		for (offset = 0; offset < len; offset++) {
			if (!(offset % 4)) {
				if (!budget || readl(dsi + DSIM_FIFOCTRL) & DSIM_RX_EMPTY)
					break;
				word = readl(dsi + DSIM_RXFIFO);
				budget--;
			}
			data[offset] = word;
			word >>= 8;
		}
		received = offset == len;
	}

	while (budget && !(readl(dsi + DSIM_FIFOCTRL) & DSIM_RX_EMPTY)) {
		readl(dsi + DSIM_RXFIFO);
		budget--;
	}
	writel(status & DSIM_RX_EVENTS, dsi + DSIM_INTSRC);
	if (status & DSIM_RX_FAULTS || !budget || malformed || !received) {
		pr_info("g955n-dsim: DCS %02x response rejected: irq=%08x\n",
			address, status);
		return -EPROTO;
	}

	return 0;
}

static int g955n_dsim_long3(void __iomem *dsi, u8 address, u8 first, u8 second)
{
	int ret = g955n_dsim_wait_tx(dsi);

	if (ret)
		return ret;
	writel(address | (first << 8) | (second << 16), dsi + DSIM_PAYLOAD);
	writel(MIPI_DSI_DCS_LONG_WRITE | (3 << 8), dsi + DSIM_PKTHDR);
	return g955n_dsim_wait_tx(dsi);
}

static int g955n_dsim_short_param(void __iomem *dsi, u8 address, u8 value)
{
	int ret = g955n_dsim_wait_tx(dsi);

	if (ret)
		return ret;
	writel(MIPI_DSI_DCS_SHORT_WRITE_PARAM | (address << 8) |
	       (value << 16), dsi + DSIM_PKTHDR);
	return g955n_dsim_wait_tx(dsi);
}

#ifdef G955N_WITH_AID
int g955n_aid_verify(const u8 *mtp);
int g955n_aor_trial_value(const u8 saved[2], u8 trial[2]);

static int g955n_dsim_latch_aor(void __iomem *dsi, const u8 value[2])
{
	int ret = g955n_dsim_long3(dsi, 0xb1, value[0], value[1]);

	if (ret)
		return ret;
	return g955n_dsim_short_param(dsi, 0xf7, 0x03);
}

static int g955n_dsim_check_aor(void __iomem *dsi)
{
	u8 saved[2], trial[2], observed[2];
	int ret, restore;

	ret = g955n_dsim_read(dsi, 0xb1, saved, sizeof(saved));
	if (!ret)
		ret = g955n_dsim_read(dsi, 0xb1, observed, sizeof(observed));
	if (ret)
		return ret;
	if (memcmp(saved, observed, sizeof(saved)))
		return -EAGAIN;

	ret = g955n_aor_trial_value(saved, trial);
	if (ret)
		return ret;

	ret = g955n_dsim_latch_aor(dsi, trial);
	if (!ret) {
		msleep(150);
		ret = g955n_dsim_read(dsi, 0xb1, observed, sizeof(observed));
		if (!ret && memcmp(trial, observed, sizeof(trial)))
			ret = -EIO;
		if (!ret)
			pr_info("g955n-dsim: AOR test value accepted: %*phN\n", 2, observed);
	}

	restore = g955n_dsim_latch_aor(dsi, saved);
	if (!restore)
		restore = g955n_dsim_read(dsi, 0xb1, observed, sizeof(observed));
	if (!restore && memcmp(saved, observed, sizeof(saved)))
		restore = -EIO;
	if (restore)
		pr_err("g955n-dsim: AOR restoration not verified: %d\n", restore);
	else
		pr_info("g955n-dsim: AOR original value restored: %*phN\n", 2, observed);
	return restore ?: ret;
}
#endif

static int g955n_dsim_check_resource(void __iomem *dsi, u8 address, u8 offset,
				     size_t len)
{
	u8 first[S6E3HA6_MTP_LEN], second[S6E3HA6_MTP_LEN];
	int ret = 0;

	if (offset)
		ret = g955n_dsim_short_param(dsi, S6E3HA6_GPARA, offset);
	if (!ret)
		ret = g955n_dsim_read(dsi, address, first, len);
	if (!ret && offset)
		ret = g955n_dsim_short_param(dsi, S6E3HA6_GPARA, offset);
	if (!ret)
		ret = g955n_dsim_read(dsi, address, second, len);
	if (offset && g955n_dsim_short_param(dsi, S6E3HA6_GPARA, 0)) {
		pr_err("g955n-dsim: failed to restore panel offset\n");
		ret = -EIO;
	}
	if (!ret && (!memchr_inv(first, 0, len) || !memchr_inv(first, 0xff, len) ||
		     memcmp(first, second, len)))
		ret = -ENODATA;
	if (!ret)
		pr_info("g955n-dsim: DCS %02x calibration: %zu stable nonblank bytes\n",
			address, len);
#ifdef G955N_WITH_AID
	if (!ret && address == S6E3HA6_MTP)
		ret = g955n_aid_verify(first);
#endif
	memzero_explicit(first, sizeof(first));
	memzero_explicit(second, sizeof(second));
	return ret;
}

static int g955n_dsim_check_calibration(void __iomem *dsi)
{
	static const u8 keys[] = { 0x9f, 0xf0, 0xfc };
	static const u8 unlock[] = { 0xa5, 0x5a, 0x5a };
	unsigned int opened = 0;
	int ret = 0, lock_error = 0;

	/* Match the S6E3HA6 Dream2 A3 resource-init key order. */
	while (opened < ARRAY_SIZE(keys)) {
		ret = g955n_dsim_long3(dsi, keys[opened], unlock[opened], unlock[opened]);
		opened++;
		if (ret)
			break;
	}
	if (!ret)
		ret = g955n_dsim_check_resource(dsi, S6E3HA6_MTP, 0, S6E3HA6_MTP_LEN);
	if (!ret)
		ret = g955n_dsim_check_resource(dsi, S6E3HA6_ELVSS, 0, S6E3HA6_ELVSS_LEN);
	if (!ret)
		ret = g955n_dsim_check_resource(dsi, S6E3HA6_HBM_GAMMA, S6E3HA6_HBM_OFFSET,
					       S6E3HA6_HBM_LEN);

#ifdef G955N_WITH_AID
	if (!ret && test_aor)
		ret = g955n_dsim_check_aor(dsi);
#endif

	while (opened) {
		int err;

		opened--;
		err = g955n_dsim_long3(dsi, keys[opened], ~unlock[opened], ~unlock[opened]);
		if (err)
			lock_error = err;
	}
	if (lock_error)
		pr_err("g955n-dsim: failed to send panel lock keys: %d\n", lock_error);
	else
		pr_info("g955n-dsim: panel lock keys sent\n");
	return lock_error ?: ret;
}

static int g955n_dsim_identify_panel(void __iomem *dsi)
{
	static const u8 dream2_a3_id[] = { 0xd1, 0x10, 0x10 };
	u8 id[G955N_PANEL_ID_LEN];
	u32 timeout;
	int ret;

	/* The loader's 0xff-cycle turnaround expires before the panel replies. */
	timeout = readl(dsi + DSIM_TIMEOUT);
	writel((timeout & ~DSIM_BTA_TIMEOUT) |
	       FIELD_PREP(DSIM_BTA_TIMEOUT, G955N_BTA_WAIT), dsi + DSIM_TIMEOUT);

	ret = g955n_dsim_read(dsi, MIPI_DCS_GET_DISPLAY_ID, id, sizeof(id));
	if (!ret) {
		pr_info("g955n-dsim: panel family ID %*phN\n", G955N_PANEL_ID_LEN, id);
		if (read_calibration)
			ret = memcmp(id, dream2_a3_id, sizeof(id)) ? -ENODEV :
				g955n_dsim_check_calibration(dsi);
	}

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

#ifdef G955N_WITH_AID
	if (test_aor && !read_calibration)
		return -EINVAL;
#endif
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
	if (read_id || read_calibration)
		ret = g955n_dsim_identify_panel(dsi);
	iounmap(dsi);

release:
	release_mem_region(DSIM_BASE, DSIM_SIZE);
	return ret;
}
module_init(g955n_dsim_identify);

MODULE_DESCRIPTION("SM-G955N inherited DSI status and panel identification");
MODULE_LICENSE("GPL");
