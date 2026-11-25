// SPDX-License-Identifier: GPL-2.0-only
/* SM-G955N S3NRN82 bring-up using normal NCI mode. */
#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/i2c.h>
#include <linux/iopoll.h>
#include <linux/mfd/syscon.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/regmap.h>

#include "g955n-nfc-hw.h"

static int nfc_read_frame(struct g955n_nfc *nfc, u8 *header, u8 *payload)
{
	int ready, ret;

	ret = read_poll_timeout(gpiod_get_value_cansleep, ready, ready,
				1000, 300000, false, nfc->ready);
	if (ret)
		return ret;
	if (ready < 0)
		return ready;

	return g955n_read_nci_frame(nfc, header, payload);
}

static int nfc_core_reset(struct g955n_nfc *nfc)
{
	/* NCI CORE_RESET_CMD with Keep Configuration. */
	const u8 request[] = { 0x20, 0x00, 0x01, 0x00 };
	u8 header[NCI_HEADER_BYTES], payload[U8_MAX];
	struct device *dev = &nfc->client->dev;
	int ret;

	ret = i2c_master_send(nfc->client, request, sizeof(request));
	if (ret < 0)
		return dev_err_probe(dev, ret, "CORE_RESET write failed\n");
	if (ret != sizeof(request))
		return -EIO;

	ret = nfc_read_frame(nfc, header, payload);
	if (ret)
		return dev_err_probe(dev, ret, "CORE_RESET response unavailable\n");
	if (header[0] != 0x40 || header[1] != 0 || !header[2])
		return -EPROTO;

	dev_info(dev, "CORE_RESET response length=%u status=0x%02x\n",
		 header[2], payload[0]);
	if (payload[0])
		return -EPROTO;
	if (header[2] >= 3) {
		dev_info(dev, "NCI version byte=0x%02x\n", payload[1]);
		return 0;
	}

	/* NCI 2.x reports the version in CORE_RESET_NTF. */
	ret = nfc_read_frame(nfc, header, payload);
	if (ret)
		return ret;
	if (header[0] != 0x60 || header[1] != 0 || header[2] < 3)
		return -EPROTO;
	dev_info(dev, "CORE_RESET notification length=%u NCI version=0x%02x\n",
		 header[2], payload[2]);
	return 0;
}

static ssize_t core_reset_store(struct device *dev, struct device_attribute *attr,
				const char *buf, size_t count)
{
	struct g955n_nfc *nfc = dev_get_drvdata(dev);
	bool wake = sysfs_streq(buf, "wake");
	int ret, restore;

	if (!wake && !sysfs_streq(buf, "1"))
		return -EINVAL;

	mutex_lock(&nfc->lock);
	ret = g955n_nfc_power_on(nfc, wake);
	if (!ret) {
		dev_info(dev, "CORE_RESET ready=%d wake=%d\n",
			 gpiod_get_value_cansleep(nfc->ready), wake);
		ret = nfc_core_reset(nfc);
		restore = g955n_nfc_power_off(nfc);
		if (!ret)
			ret = restore;
	}
	mutex_unlock(&nfc->lock);
	return ret ? ret : count;
}
static DEVICE_ATTR_WO(core_reset);

static struct attribute *g955n_nfc_attrs[] = {
	&dev_attr_core_reset.attr,
	NULL,
};
ATTRIBUTE_GROUPS(g955n_nfc);

static int g955n_nfc_probe(struct i2c_client *client)
{
	struct device *dev = &client->dev;
	struct g955n_nfc *nfc;
	int ret;

	if (!of_machine_is_compatible("samsung,dream2lteks") || client->addr != 0x27)
		return -ENODEV;
	if (!i2c_check_functionality(client->adapter, I2C_FUNC_I2C))
		return -EOPNOTSUPP;

	nfc = devm_kzalloc(dev, sizeof(*nfc), GFP_KERNEL);
	if (!nfc)
		return -ENOMEM;
	ret = g955n_nfc_get_resources(client, nfc);
	if (ret)
		return ret;

	i2c_set_clientdata(client, nfc);
	return 0;
}

static const struct of_device_id g955n_nfc_match[] = {
	{ .compatible = "samsung,sm-g955n-nfc-reset-test" },
	{ }
};
MODULE_DEVICE_TABLE(of, g955n_nfc_match);

static struct i2c_driver g955n_nfc_driver = {
	.driver = {
		.name = "g955n-nfc-reset",
		.of_match_table = g955n_nfc_match,
		.dev_groups = g955n_nfc_groups,
	},
	.probe = g955n_nfc_probe,
};
module_i2c_driver(g955n_nfc_driver);

MODULE_DESCRIPTION("SM-G955N S3NRN82 normal-mode reset test");
MODULE_LICENSE("GPL");
