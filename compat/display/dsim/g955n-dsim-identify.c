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
#include <linux/slab.h>
#include <video/mipi_display.h>

#ifdef G955N_WITH_BACKLIGHT
#include <linux/backlight.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/suspend.h>
#endif

#ifdef G955N_WITH_AID
#include "g955n-panel-profile.h"
#endif

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
static int test_brightness = -1;
module_param(test_brightness, int, 0400);
MODULE_PARM_DESC(test_brightness, "Apply and restore a Samsung brightness level from 0 to 255");
#endif

#ifdef G955N_WITH_BACKLIGHT
static bool enable_backlight;
module_param(enable_backlight, bool, 0400);
MODULE_PARM_DESC(enable_backlight, "Register the OLED with Linux backlight");
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
		if (!received && len == 1 &&
		    (word & 0x3f) == MIPI_DSI_RX_DCS_SHORT_READ_RESPONSE_1BYTE) {
			data[0] = word >> 8;
			received = true;
			continue;
		}
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
static const struct {
	u8 address;
	size_t offset;
	size_t len;
} g955n_panel_registers[] = {
	{ 0xca, offsetof(struct g955n_panel_profile, gamma), sizeof_field(struct g955n_panel_profile, gamma) },
	{ 0xb1, offsetof(struct g955n_panel_profile, aor), sizeof_field(struct g955n_panel_profile, aor) },
	{ 0xb5, offsetof(struct g955n_panel_profile, elvss), sizeof_field(struct g955n_panel_profile, elvss) },
	{ 0xf4, offsetof(struct g955n_panel_profile, vint), sizeof_field(struct g955n_panel_profile, vint) },
	{ 0xb4, offsetof(struct g955n_panel_profile, acl), sizeof_field(struct g955n_panel_profile, acl) },
	{ 0x55, offsetof(struct g955n_panel_profile, acl_enable), sizeof_field(struct g955n_panel_profile, acl_enable) },
	{ 0xeb, offsetof(struct g955n_panel_profile, poc), sizeof_field(struct g955n_panel_profile, poc) },
	{ 0xb8, offsetof(struct g955n_panel_profile, irc), sizeof_field(struct g955n_panel_profile, irc) },
};

static int g955n_dsim_write_register(void __iomem *dsi, u8 address,
				     const u8 *data, size_t len)
{
	u32 word = address;
	size_t i;
	int ret;

	if (len == 1)
		return g955n_dsim_short_param(dsi, address, data[0]);

	ret = g955n_dsim_wait_tx(dsi);
	if (ret)
		return ret;
	for (i = 1; i <= len; i++) {
		word |= (u32)data[i - 1] << (8 * (i % 4));
		if (i % 4 == 3 || i == len) {
			writel(word, dsi + DSIM_PAYLOAD);
			word = 0;
		}
	}
	writel(MIPI_DSI_DCS_LONG_WRITE | ((len + 1) << 8), dsi + DSIM_PKTHDR);
	return g955n_dsim_wait_tx(dsi);
}

static int g955n_dsim_read_profile(void __iomem *dsi, struct g955n_panel_profile *profile)
{
	unsigned int i;
	int ret;

	for (i = 0; i < ARRAY_SIZE(g955n_panel_registers); i++) {
		const typeof(*g955n_panel_registers) *reg = &g955n_panel_registers[i];

		ret = g955n_dsim_read(dsi, reg->address, (u8 *)profile + reg->offset, reg->len);
		if (ret)
			return ret;
	}
	return 0;
}

static int g955n_dsim_write_profile(void __iomem *dsi, const struct g955n_panel_profile *profile)
{
	unsigned int i;
	int ret;

	/* Match the Dream2 A3 set-backlight command order before the latch. */
	for (i = 0; i < ARRAY_SIZE(g955n_panel_registers); i++) {
		const typeof(*g955n_panel_registers) *reg = &g955n_panel_registers[i];

		ret = g955n_dsim_write_register(dsi, reg->address,
					       (const u8 *)profile + reg->offset, reg->len);
		if (ret)
			return ret;
	}
	return g955n_dsim_short_param(dsi, 0xf7, 0x03);
}

static int g955n_dsim_check_profile(void __iomem *dsi,
				    const struct g955n_panel_profile *expected)
{
	struct g955n_panel_profile observed;
	unsigned int i;
	int ret;

	ret = g955n_dsim_read_profile(dsi, &observed);
	if (ret)
		return ret;
	for (i = 0; i < ARRAY_SIZE(g955n_panel_registers); i++) {
		const typeof(*g955n_panel_registers) *reg = &g955n_panel_registers[i];

		if (memcmp((const u8 *)expected + reg->offset,
			   (const u8 *)&observed + reg->offset, reg->len)) {
			pr_info("g955n-dsim: brightness register %02x readback differs\n",
				reg->address);
			return -EIO;
		}
	}
	return 0;
}

static int g955n_dsim_test_profile(void __iomem *dsi)
{
	struct g955n_panel_profile saved, trial;
	u8 mtp[S6E3HA6_MTP_LEN];
	struct g955n_gamma_table *table;
	int ret, restore;

	ret = g955n_dsim_read_profile(dsi, &saved);
	if (!ret)
		ret = g955n_dsim_check_profile(dsi, &saved);
	if (ret)
		return ret;

	trial = saved;
	table = kzalloc(sizeof(*table), GFP_KERNEL);
	if (!table)
		return -ENOMEM;
	ret = g955n_dsim_read(dsi, S6E3HA6_MTP, mtp, sizeof(mtp));
	if (!ret)
		ret = g955n_compile_gamma(mtp, table);
	memzero_explicit(mtp, sizeof(mtp));
	if (!ret)
		ret = g955n_build_panel_profile(table, test_brightness, &trial);
	kfree_sensitive(table);
	if (ret)
		return ret;
	if (!memcmp(&saved, &trial, sizeof(saved)))
		return -EALREADY;

	ret = g955n_dsim_write_profile(dsi, &trial);
	if (!ret)
		ret = g955n_dsim_check_profile(dsi, &trial);
	if (!ret)
		pr_info("g955n-dsim: brightness level %d read back after latch\n",
			test_brightness);
	restore = g955n_dsim_write_profile(dsi, &saved);
	if (!restore)
		restore = g955n_dsim_check_profile(dsi, &saved);
	if (restore)
		pr_err("g955n-dsim: brightness profile restoration not verified: %d\n",
		       restore);
	else
		pr_info("g955n-dsim: original brightness profile restored\n");
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
		ret = g955n_compile_gamma(first, NULL);
#endif
	memzero_explicit(first, sizeof(first));
	memzero_explicit(second, sizeof(second));
	return ret;
}

#ifdef G955N_WITH_BACKLIGHT
static struct {
	void __iomem *dsi;
	struct regmap *pmu;
	struct backlight_device *device;
	struct g955n_gamma_table gamma;
	struct g955n_panel_profile applied;
	int level;
	bool suspended;
} g955n_backlight;

static DEFINE_MUTEX(g955n_backlight_lock);

static int g955n_dsim_display_powered(struct regmap *pmu)
{
	unsigned int power;
	int ret = regmap_read(pmu, DISP_POWER_STATUS, &power);

	if (ret)
		return ret;
	return (power & DISP_POWER_MASK) == DISP_POWER_MASK ? 0 : -EHOSTDOWN;
}

static int g955n_capture_backlight(void __iomem *dsi)
{
	u8 mtp[S6E3HA6_MTP_LEN];
	int ret;

	ret = g955n_dsim_read_profile(dsi, &g955n_backlight.applied);
	if (!ret)
		ret = g955n_dsim_check_profile(dsi, &g955n_backlight.applied);
	if (!ret)
		ret = g955n_dsim_read(dsi, S6E3HA6_MTP, mtp, sizeof(mtp));
	if (!ret)
		ret = g955n_compile_gamma(mtp, &g955n_backlight.gamma);
	memzero_explicit(mtp, sizeof(mtp));
	if (!ret)
		g955n_backlight.level = g955n_estimate_panel_brightness(&g955n_backlight.applied);
	return ret;
}

static int g955n_backlight_apply(unsigned int level)
{
	void __iomem *dsi = g955n_backlight.dsi;
	struct g955n_panel_profile next = g955n_backlight.applied;
	u32 timeout;
	int ret, lock_error;

	ret = g955n_dsim_display_powered(g955n_backlight.pmu);
	if (!ret)
		ret = g955n_dsim_ready(dsi);
	if (ret)
		return ret;

	ret = g955n_build_panel_profile(&g955n_backlight.gamma, level, &next);
	if (ret)
		return ret;

	timeout = readl(dsi + DSIM_TIMEOUT);
	writel((timeout & ~DSIM_BTA_TIMEOUT) |
	       FIELD_PREP(DSIM_BTA_TIMEOUT, G955N_BTA_WAIT), dsi + DSIM_TIMEOUT);
	ret = g955n_dsim_long3(dsi, 0xf0, 0x5a, 0x5a);
	if (!ret) {
		ret = g955n_dsim_write_profile(dsi, &next);
		if (!ret)
			ret = g955n_dsim_check_profile(dsi, &next);
		if (ret && g955n_dsim_write_profile(dsi, &g955n_backlight.applied))
			pr_err("g955n-dsim: failed to roll back brightness\n");
	}
	lock_error = g955n_dsim_long3(dsi, 0xf0, 0xa5, 0xa5);
	writel(timeout, dsi + DSIM_TIMEOUT);

	if (lock_error) {
		pr_err("g955n-dsim: failed to send brightness lock key: %d\n",
		       lock_error);
		return lock_error;
	}
	if (ret)
		return ret;

	g955n_backlight.applied = next;
	WRITE_ONCE(g955n_backlight.level, level);
	pr_info("g955n-dsim: Linux backlight level %u verified at panel\n", level);
	return 0;
}

static int g955n_backlight_update(struct backlight_device *device)
{
	int ret = 0;

	mutex_lock(&g955n_backlight_lock);
	/* DECON owns display blanking. Avoid DSI transactions during sleep. */
	if (g955n_backlight.suspended)
		ret = -EAGAIN;
	else if (!backlight_is_blank(device) && device->props.brightness != g955n_backlight.level)
		ret = g955n_backlight_apply(device->props.brightness);
	mutex_unlock(&g955n_backlight_lock);
	return ret;
}

static int g955n_backlight_get(struct backlight_device *device)
{
	return READ_ONCE(g955n_backlight.level);
}

static const struct backlight_ops g955n_backlight_ops = {
	.update_status = g955n_backlight_update,
	.get_brightness = g955n_backlight_get,
};

static int g955n_backlight_pm(struct notifier_block *nb, unsigned long event, void *unused)
{
	mutex_lock(&g955n_backlight_lock);
	switch (event) {
	case PM_SUSPEND_PREPARE:
	case PM_HIBERNATION_PREPARE:
	case PM_RESTORE_PREPARE:
		g955n_backlight.suspended = true;
		break;
	case PM_POST_SUSPEND:
	case PM_POST_HIBERNATION:
	case PM_POST_RESTORE:
		g955n_backlight.suspended = false;
		break;
	}
	mutex_unlock(&g955n_backlight_lock);
	return NOTIFY_DONE;
}

static struct notifier_block g955n_backlight_pm_notifier = {
	.notifier_call = g955n_backlight_pm,
};

static int g955n_register_backlight(void __iomem *dsi, struct regmap *pmu)
{
	struct backlight_properties props = {
		.type = BACKLIGHT_RAW,
		.max_brightness = 255,
		.brightness = g955n_backlight.level,
		.scale = BACKLIGHT_SCALE_NON_LINEAR,
	};
	struct platform_device *decon;
	struct device_node *node;
	int ret;

	node = of_find_compatible_node(NULL, NULL, "samsung,sm-g955n-decon-handoff-test");
	if (!node)
		return -ENODEV;
	decon = of_find_device_by_node(node);
	of_node_put(node);
	if (!decon)
		return -ENODEV;

	g955n_backlight.dsi = dsi;
	g955n_backlight.pmu = pmu;
	ret = register_pm_notifier(&g955n_backlight_pm_notifier);
	if (!ret) {
		g955n_backlight.device = backlight_device_register("g955n-panel",
					&decon->dev, NULL, &g955n_backlight_ops, &props);
		if (IS_ERR(g955n_backlight.device)) {
			ret = PTR_ERR(g955n_backlight.device);
			unregister_pm_notifier(&g955n_backlight_pm_notifier);
		}
	}
	put_device(&decon->dev);
	if (!ret)
		pr_info("g955n-dsim: registered Linux backlight, initial estimated level %d\n",
			props.brightness);
	return ret;
}
#endif

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
	if (!ret && test_brightness >= 0)
		ret = g955n_dsim_test_profile(dsi);
#endif

#ifdef G955N_WITH_BACKLIGHT
	if (!ret && enable_backlight)
		ret = g955n_capture_backlight(dsi);
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
	if ((test_aor || test_brightness >= 0) && !read_calibration)
		return -EINVAL;
	if (test_brightness < -1 || test_brightness > 255)
		return -ERANGE;
#endif
#ifdef G955N_WITH_BACKLIGHT
	if (enable_backlight && (!read_calibration || test_aor || test_brightness >= 0))
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
#ifdef G955N_WITH_BACKLIGHT
	if (!ret && enable_backlight) {
		ret = g955n_register_backlight(dsi, pmu);
		if (!ret)
			return 0;
	}
	memzero_explicit(&g955n_backlight.gamma, sizeof(g955n_backlight.gamma));
#endif
	iounmap(dsi);

release:
	release_mem_region(DSIM_BASE, DSIM_SIZE);
	return ret;
}
module_init(g955n_dsim_identify);

#ifdef G955N_WITH_BACKLIGHT
static void __exit g955n_dsim_exit(void)
{
	if (!enable_backlight)
		return;

	backlight_device_unregister(g955n_backlight.device);
	unregister_pm_notifier(&g955n_backlight_pm_notifier);
	iounmap(g955n_backlight.dsi);
	release_mem_region(DSIM_BASE, DSIM_SIZE);
	memzero_explicit(&g955n_backlight.gamma, sizeof(g955n_backlight.gamma));
}
module_exit(g955n_dsim_exit);
#endif

MODULE_DESCRIPTION("SM-G955N inherited DSI status and panel identification");
MODULE_LICENSE("GPL");
