// SPDX-License-Identifier: GPL-2.0-only
/* Identify the Dream2 optical controller without enabling its emitters. */
#include <linux/bits.h>
#include <linux/delay.h>
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/unaligned.h>

#define S2DOS03_ENABLE		0x03
#define S2DOS03_LDO2_CFG		0x11
#define S2DOS03_LDO4_CFG		0x13
#define S2DOS03_VSEL_MASK	GENMASK_U32(6, 0)
#define ADPD_CHIP_ID		0x08
#define S2DOS03_LDO2_EN		BIT(1)
#define S2DOS03_LDO4_EN		BIT(3)
#define S2DOS03_LDO2_1V8	48

static DEFINE_MUTEX(optical_supply_lock);

static ssize_t rail_state_show(struct device *dev, struct device_attribute *attr,
			       char *buf)
{
	struct i2c_client *client = to_i2c_client(dev);
	int enable, ldo2, ldo4;

	enable = i2c_smbus_read_byte_data(client, S2DOS03_ENABLE);
	if (enable < 0)
		return enable;
	ldo2 = i2c_smbus_read_byte_data(client, S2DOS03_LDO2_CFG);
	if (ldo2 < 0)
		return ldo2;
	ldo4 = i2c_smbus_read_byte_data(client, S2DOS03_LDO4_CFG);
	if (ldo4 < 0)
		return ldo4;

	return sysfs_emit(buf, "enable=0x%02x LDO2=%u LDO4=%u\n", enable,
			  600000 + 25000 * (ldo2 & S2DOS03_VSEL_MASK),
			  600000 + 25000 * (ldo4 & S2DOS03_VSEL_MASK));
}
static DEVICE_ATTR_ADMIN_RO(rail_state);

static ssize_t chip_id_show(struct device *dev, struct device_attribute *attr,
			     char *buf)
{
	struct i2c_client *client = to_i2c_client(dev);
	u8 reg = ADPD_CHIP_ID, value[2];
	struct i2c_msg transfer[] = {
		{ .addr = client->addr, .len = sizeof(reg), .buf = &reg },
		{ .addr = client->addr, .flags = I2C_M_RD, .len = sizeof(value), .buf = value },
	};
	int ret;

	ret = i2c_transfer(client->adapter, transfer, ARRAY_SIZE(transfer));
	if (ret < 0)
		return ret;
	if (ret != ARRAY_SIZE(transfer))
		return -EIO;

	return sysfs_emit(buf, "0x%04x\n", get_unaligned_be16(value));
}
static DEVICE_ATTR_ADMIN_RO(chip_id);

static ssize_t powered_chip_id_show(struct device *dev, struct device_attribute *attr,
				    char *buf)
{
	struct device_node *node;
	struct i2c_client *pmic;
	int old, voltage, ret, restore;
	ssize_t length;

	node = of_find_node_by_path("/soc@0/usi@10860000/i2c@10000/pmic@60");
	if (!node)
		return -ENODEV;
	pmic = of_find_i2c_device_by_node(node);
	of_node_put(node);
	if (!pmic)
		return -ENODEV;

	device_lock(&pmic->dev);
	if (!pmic->dev.driver ||
	    !of_device_is_compatible(pmic->dev.of_node, "samsung,sm-g955n-s2dos03-readback")) {
		length = -ENODEV;
		goto release;
	}

	mutex_lock(&optical_supply_lock);
	old = i2c_smbus_read_byte_data(pmic, S2DOS03_ENABLE);
	voltage = i2c_smbus_read_byte_data(pmic, S2DOS03_LDO2_CFG);
	if (old < 0 || voltage < 0) {
		length = old < 0 ? old : voltage;
		goto unlock;
	}
	if ((old & (S2DOS03_LDO2_EN | S2DOS03_LDO4_EN)) ||
	    (voltage & S2DOS03_VSEL_MASK) != S2DOS03_LDO2_1V8) {
		length = -EBUSY;
		goto unlock;
	}

	/* Power the digital rail only. Keep the LED and display bits as found. */
	ret = i2c_smbus_write_byte_data(pmic, S2DOS03_ENABLE, old | S2DOS03_LDO2_EN);
	if (ret < 0) {
		length = ret;
		goto restore_enable;
	}
	ret = i2c_smbus_read_byte_data(pmic, S2DOS03_ENABLE);
	if (ret != (old | S2DOS03_LDO2_EN)) {
		length = ret < 0 ? ret : -EIO;
		goto restore_enable;
	}

	usleep_range(3000, 4000);
	length = chip_id_show(dev, attr, buf);

restore_enable:
	ret = i2c_smbus_read_byte_data(pmic, S2DOS03_ENABLE);
	restore = ret < 0 ? ret : 0;
	if (ret >= 0 && (ret & S2DOS03_LDO2_EN)) {
		restore = i2c_smbus_write_byte_data(pmic, S2DOS03_ENABLE,
						    ret & ~S2DOS03_LDO2_EN);
		if (!restore) {
			ret = i2c_smbus_read_byte_data(pmic, S2DOS03_ENABLE);
			if (ret < 0 || (ret & S2DOS03_LDO2_EN))
				restore = ret < 0 ? ret : -EIO;
		}
	}
	if (restore) {
		dev_err(dev, "cannot restore optical supply state: %d\n", restore);
		length = restore;
	}
unlock:
	mutex_unlock(&optical_supply_lock);
release:
	device_unlock(&pmic->dev);
	put_device(&pmic->dev);
	return length;
}
static DEVICE_ATTR_ADMIN_RO(powered_chip_id);

static struct attribute *optical_id_attrs[] = {
	&dev_attr_chip_id.attr,
	&dev_attr_powered_chip_id.attr,
	NULL,
};
static const struct attribute_group optical_id_group = {
	.attrs = optical_id_attrs,
};

static int g955n_optical_probe(struct i2c_client *client)
{
	struct device *dev = &client->dev;

	if (!of_machine_is_compatible("samsung,dream2lteks"))
		return -ENODEV;
	if (client->addr == 0x60 &&
	    of_device_is_compatible(dev->of_node, "samsung,sm-g955n-s2dos03-readback")) {
		if (!i2c_check_functionality(client->adapter, I2C_FUNC_SMBUS_BYTE_DATA))
			return -EOPNOTSUPP;
		return device_create_file(dev, &dev_attr_rail_state);
	}
	if (client->addr == 0x64 &&
	    of_device_is_compatible(dev->of_node, "samsung,sm-g955n-adpd-id-test")) {
		if (!i2c_check_functionality(client->adapter, I2C_FUNC_I2C))
			return -EOPNOTSUPP;
		return devm_device_add_group(dev, &optical_id_group);
	}
	return -ENODEV;
}

static void g955n_optical_remove(struct i2c_client *client)
{
	struct device *dev = &client->dev;

	if (client->addr == 0x60)
		device_remove_file(dev, &dev_attr_rail_state);

}

static const struct of_device_id g955n_optical_of_match[] = {
	{ .compatible = "samsung,sm-g955n-s2dos03-readback" },
	{ .compatible = "samsung,sm-g955n-adpd-id-test" },
	{ }
};
MODULE_DEVICE_TABLE(of, g955n_optical_of_match);

static struct i2c_driver g955n_optical_driver = {
	.driver = {
		.name = "g955n-optical-readback",
		.of_match_table = g955n_optical_of_match,
	},
	.probe = g955n_optical_probe,
	.remove = g955n_optical_remove,
};
module_i2c_driver(g955n_optical_driver);

MODULE_DESCRIPTION("SM-G955N optical sensor and supply readback");
MODULE_LICENSE("GPL");
