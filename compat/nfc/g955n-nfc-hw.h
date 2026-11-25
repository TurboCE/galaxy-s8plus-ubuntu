/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef G955N_NFC_HW_H
#define G955N_NFC_HW_H

#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/i2c.h>
#include <linux/mfd/syscon.h>
#include <linux/mutex.h>
#include <linux/regmap.h>
#include <linux/regulator/consumer.h>

#define EXYNOS8895_CLKOUT1		0xa0c
#define EXYNOS8895_CLKOUT1_MUX		GENMASK(13, 8)
#define EXYNOS8895_CLKOUT1_DISABLE	BIT(0)
#define NFC_CLOCK_MASK (EXYNOS8895_CLKOUT1_MUX | EXYNOS8895_CLKOUT1_DISABLE)
#define NCI_HEADER_BYTES	3

struct g955n_nfc {
	struct i2c_client *client;
	struct gpio_desc *enable;
	struct gpio_desc *firmware;
	struct gpio_desc *ready;
	struct regmap *pmu;
	struct regulator *vddio;
	struct mutex lock;
	unsigned int saved_clock;
};

static int g955n_nfc_get_resources(struct i2c_client *client, struct g955n_nfc *nfc)
{
	struct device *dev = &client->dev;

	nfc->pmu = syscon_regmap_lookup_by_phandle(dev->of_node, "samsung,pmu");
	if (IS_ERR(nfc->pmu))
		return dev_err_probe(dev, PTR_ERR(nfc->pmu), "NFC clock unavailable\n");
	nfc->vddio = devm_regulator_get_optional(dev, "vddio");
	if (IS_ERR(nfc->vddio)) {
		if (PTR_ERR(nfc->vddio) != -ENODEV)
			return dev_err_probe(dev, PTR_ERR(nfc->vddio), "NFC I/O supply unavailable\n");
		nfc->vddio = NULL;
	}
	nfc->enable = devm_gpiod_get(dev, "enable", GPIOD_OUT_LOW);
	if (IS_ERR(nfc->enable))
		return dev_err_probe(dev, PTR_ERR(nfc->enable), "NFC enable GPIO unavailable\n");
	nfc->firmware = devm_gpiod_get(dev, "firmware", GPIOD_OUT_LOW);
	if (IS_ERR(nfc->firmware))
		return dev_err_probe(dev, PTR_ERR(nfc->firmware), "NFC firmware GPIO unavailable\n");
	nfc->ready = devm_gpiod_get(dev, "ready", GPIOD_IN);
	if (IS_ERR(nfc->ready))
		return dev_err_probe(dev, PTR_ERR(nfc->ready), "NFC ready GPIO unavailable\n");

	nfc->client = client;
	mutex_init(&nfc->lock);
	return 0;
}

static int g955n_nfc_power_off(struct g955n_nfc *nfc)
{
	int ret, supply;

	gpiod_set_value_cansleep(nfc->firmware, 0);
	gpiod_set_value_cansleep(nfc->enable, 0);
	ret = regmap_update_bits(nfc->pmu, EXYNOS8895_CLKOUT1, NFC_CLOCK_MASK,
				 nfc->saved_clock);
	if (ret)
		dev_err(&nfc->client->dev, "cannot restore NFC clock: %d\n", ret);
	supply = nfc->vddio ? regulator_disable(nfc->vddio) : 0;
	if (supply)
		dev_err(&nfc->client->dev, "cannot release NFC I/O supply: %d\n", supply);
	return ret ?: supply;
}

static int g955n_nfc_power_on(struct g955n_nfc *nfc, bool wake)
{
	unsigned int enabled;
	int ret;

	ret = regmap_read(nfc->pmu, EXYNOS8895_CLKOUT1, &nfc->saved_clock);
	if (ret)
		return ret;
	if (nfc->vddio) {
		ret = regulator_enable(nfc->vddio);
		if (ret)
			return ret;
	}
	ret = regmap_update_bits(nfc->pmu, EXYNOS8895_CLKOUT1, NFC_CLOCK_MASK, 0);
	if (ret)
		goto restore;
	ret = regmap_read(nfc->pmu, EXYNOS8895_CLKOUT1, &enabled);
	if (ret)
		goto restore;
	if (enabled & NFC_CLOCK_MASK) {
		ret = -EIO;
		goto restore;
	}

	gpiod_set_value_cansleep(nfc->firmware, 0);
	gpiod_set_value_cansleep(nfc->enable, 0);
	msleep(150);
	gpiod_set_value_cansleep(nfc->enable, 1);
	msleep(75);
	if (wake) {
		/* Assert firmware-mode WAKE only after VEN, as Samsung does. */
		gpiod_set_value_cansleep(nfc->firmware, 1);
		msleep(20);
	}
	return 0;

restore:
	g955n_nfc_power_off(nfc);
	return ret;
}

static int g955n_read_nci_frame(struct g955n_nfc *nfc, u8 *header, u8 *payload)
{
	int ret;

	ret = i2c_master_recv(nfc->client, header, NCI_HEADER_BYTES);
	if (ret < 0)
		return ret;
	if (ret != NCI_HEADER_BYTES)
		return -EIO;
	if (!header[2])
		return 0;

	ret = i2c_master_recv(nfc->client, payload, header[2]);
	if (ret < 0)
		return ret;
	return ret == header[2] ? 0 : -EIO;
}

#endif
