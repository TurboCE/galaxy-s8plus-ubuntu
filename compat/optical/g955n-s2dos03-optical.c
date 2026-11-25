// SPDX-License-Identifier: GPL-2.0-only
/*
 * Optical supply controls for the SM-G955N S2DOS03.
 * Register layout from Samsung's S2DOS03 driver, Copyright 2016 Samsung.
 */
#include <linux/bitops.h>
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/regmap.h>
#include <linux/regulator/driver.h>

#define S2DOS03_ENABLE	0x03
#define S2DOS03_LDO2	0x11
#define S2DOS03_LDO4	0x13

static const struct regulator_ops optical_rail_ops = {
	.enable = regulator_enable_regmap,
	.disable = regulator_disable_regmap,
	.is_enabled = regulator_is_enabled_regmap,
};

static const struct regulator_desc optical_rails[] = {
	{
		.name = "adpd143-vdd",
		.of_match = of_match_ptr("ldo2"),
		.regulators_node = of_match_ptr("regulators"),
		.type = REGULATOR_VOLTAGE,
		.ops = &optical_rail_ops,
		.owner = THIS_MODULE,
		.n_voltages = 1,
		.fixed_uV = 1800000,
		.vsel_reg = S2DOS03_LDO2,
		.enable_reg = S2DOS03_ENABLE,
		.enable_mask = BIT(1),
		.enable_time = 50,
	}, {
		.name = "adpd143-vled",
		.of_match = of_match_ptr("ldo4"),
		.regulators_node = of_match_ptr("regulators"),
		.type = REGULATOR_VOLTAGE,
		.ops = &optical_rail_ops,
		.owner = THIS_MODULE,
		.n_voltages = 1,
		.fixed_uV = 3300000,
		.vsel_reg = S2DOS03_LDO4,
		.enable_reg = S2DOS03_ENABLE,
		.enable_mask = BIT(3),
		.enable_time = 50,
	},
};

static const struct regmap_config s2dos03_regmap = {
	.reg_bits = 8,
	.val_bits = 8,
	.max_register = S2DOS03_LDO4,
};

static int g955n_optical_pmic_probe(struct i2c_client *client)
{
	struct device *dev = &client->dev;
	struct regulator_config config = { .dev = dev };
	struct regulator_dev *rdev;
	unsigned int value, i;
	int ret;

	if (!of_machine_is_compatible("samsung,dream2lteks") || client->addr != 0x60)
		return -ENODEV;

	config.regmap = devm_regmap_init_i2c(client, &s2dos03_regmap);
	if (IS_ERR(config.regmap))
		return dev_err_probe(dev, PTR_ERR(config.regmap), "cannot access S2DOS03\n");

	for (i = 0; i < ARRAY_SIZE(optical_rails); i++) {
		const struct regulator_desc *rail = &optical_rails[i];

		ret = regmap_read(config.regmap, rail->vsel_reg, &value);
		if (ret)
			return dev_err_probe(dev, ret, "cannot read %s selector\n", rail->name);
		if (600000 + 25000 * (value & GENMASK_U32(6, 0)) != rail->fixed_uV)
			return dev_err_probe(dev, -EINVAL, "unexpected %s voltage\n", rail->name);
	}

	/* The display rails remain under the existing board power path. */
	for (i = 0; i < ARRAY_SIZE(optical_rails); i++) {
		rdev = devm_regulator_register(dev, &optical_rails[i], &config);
		if (IS_ERR(rdev))
			return dev_err_probe(dev, PTR_ERR(rdev), "cannot register optical rail\n");
	}
	return 0;
}

static const struct of_device_id g955n_optical_pmic_match[] = {
	{ .compatible = "samsung,sm-g955n-s2dos03-optical" },
	{ }
};
MODULE_DEVICE_TABLE(of, g955n_optical_pmic_match);

static struct i2c_driver g955n_optical_pmic_driver = {
	.driver = {
		.name = "g955n-s2dos03-optical",
		.of_match_table = g955n_optical_pmic_match,
	},
	.probe = g955n_optical_pmic_probe,
};
module_i2c_driver(g955n_optical_pmic_driver);

MODULE_DESCRIPTION("SM-G955N S2DOS03 optical supplies");
MODULE_LICENSE("GPL");
