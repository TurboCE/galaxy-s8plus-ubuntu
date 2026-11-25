// SPDX-License-Identifier: GPL-2.0-only
/* White torch output of the Samsung SM-G955N S2MPB02. */
#include <linux/bitops.h>
#include <linux/cleanup.h>
#include <linux/gpio/consumer.h>
#include <linux/i2c.h>
#include <linux/leds.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/regmap.h>
#include <linux/regulator/driver.h>

#define S2MPB02_FLED_CTRL1	0x12
#define S2MPB02_FLED_CUR1	0x14
#define S2MPB02_BST_CTRL2	0x1d
#define S2MPB02_LDO5_CTRL	0x22
#define S2MPB02_LDO6_CTRL	0x23
#define S2MPB02_LDO13_CTRL	0x2a
#define S2MPB02_LDO16_CTRL	0x2d
#define S2MPB02_LDO17_CTRL	0x2e
#define S2MPB02_LDO_VSEL_MASK	GENMASK(6, 0)
#define S2MPB02_LDO_ENABLE	BIT(7)
#define S2MPB02_REV1_BOOST	0x90
#define S2MPB02_GPIO_MODE_MASK	GENMASK(7, 6)
#define S2MPB02_TORCH_CUR_MASK	GENMASK(3, 0)
/* Samsung's ordinary flashlight setting uses 60 mA, code 3. */
#define S2MPB02_TORCH_MAX	3

struct s2mpb02_torch {
	struct regmap *regmap;
	struct mutex lock;
	struct gpio_desc *enable;
	unsigned int idle_current;
	struct led_classdev led;
};

static const struct regmap_config s2mpb02_torch_regmap = {
	.reg_bits = 8,
	.val_bits = 8,
	.max_register = S2MPB02_LDO17_CTRL,
};

struct s2mpb02_camera_rail {
	struct regulator_desc desc;
	unsigned int selector;
};

static int s2mpb02_camera_prepare_voltage(struct device *dev, struct regmap *map,
					  const struct s2mpb02_camera_rail *rail)
{
	unsigned int reg = rail->desc.enable_reg;
	unsigned int value, previous;
	int ret;

	ret = regmap_read(map, reg, &value);
	if (ret)
		return ret;
	if ((value & S2MPB02_LDO_VSEL_MASK) == rail->selector)
		return 0;
	if (value & S2MPB02_LDO_ENABLE)
		return dev_err_probe(dev, -EBUSY, "%s active at unexpected voltage\n",
				     rail->desc.name);
	previous = value & S2MPB02_LDO_VSEL_MASK;
	ret = regmap_update_bits(map, reg, S2MPB02_LDO_VSEL_MASK, rail->selector);
	if (ret)
		return ret;
	ret = regmap_read(map, reg, &value);
	if (ret)
		return ret;
	if ((value & (S2MPB02_LDO_VSEL_MASK | S2MPB02_LDO_ENABLE)) != rail->selector)
		return dev_err_probe(dev, -EIO, "%s voltage readback failed\n",
				     rail->desc.name);
	dev_info(dev, "%s disabled selector %#x -> %#x\n",
		 rail->desc.name, previous, rail->selector);
	return 0;
}

static int s2mpb02_camera_enable(struct regulator_dev *rdev)
{
	const struct s2mpb02_camera_rail *rail = rdev_get_drvdata(rdev);
	int ret;

	ret = s2mpb02_camera_prepare_voltage(rdev_get_dev(rdev), rdev_get_regmap(rdev), rail);
	return ret ?: regulator_enable_regmap(rdev);
}

static const struct regulator_ops s2mpb02_camera_ops = {
	.enable = s2mpb02_camera_enable,
	.disable = regulator_disable_regmap,
	.is_enabled = regulator_is_enabled_regmap,
};

#define S2MPB02_FIXED_LDO(_name, _node, _reg, _uv, _step)		\
	{							\
		.desc = {					\
			.name = _name,				\
			.of_match = _node,			\
			.regulators_node = "regulators",	\
			.type = REGULATOR_VOLTAGE,		\
			.ops = &s2mpb02_camera_ops,		\
			.owner = THIS_MODULE,			\
			.n_voltages = 1,			\
			.fixed_uV = _uv,				\
			.enable_reg = _reg,			\
			.enable_mask = S2MPB02_LDO_ENABLE,	\
			.enable_time = 180,			\
		},						\
		.selector = (_uv - 600000) / _step,		\
	}

static struct s2mpb02_camera_rail s2mpb02_camera_rails[] = {
	S2MPB02_FIXED_LDO("camera-front-dvdd-1v05", "ldo5", S2MPB02_LDO5_CTRL, 1050000, 12500),
	S2MPB02_FIXED_LDO("camera-front-rom-1v8", "ldo6", S2MPB02_LDO6_CTRL, 1800000, 25000),
	S2MPB02_FIXED_LDO("camera-front-avdd-2v8", "ldo13", S2MPB02_LDO13_CTRL, 2800000, 25000),
	S2MPB02_FIXED_LDO("camera-front-af-2v8", "ldo16", S2MPB02_LDO16_CTRL, 2800000, 25000),
	S2MPB02_FIXED_LDO("camera-rear-rom-1v8", "ldo17", S2MPB02_LDO17_CTRL, 1800000, 25000),
};

static int s2mpb02_register_camera_rails(struct device *dev, struct regmap *map)
{
	struct regulator_config config = { .dev = dev, .regmap = map };
	struct device_node *regulators __free(device_node) =
		of_get_child_by_name(dev->of_node, "regulators");
	unsigned int i;
	int ret;

	if (!regulators)
		return 0;
	for (i = 0; i < ARRAY_SIZE(s2mpb02_camera_rails); i++) {
		struct s2mpb02_camera_rail *rail = &s2mpb02_camera_rails[i];
		struct device_node *child __free(device_node) =
			of_get_child_by_name(regulators, rail->desc.of_match);
		struct regulator_dev *rdev;

		if (!child || !of_device_is_available(child))
			continue;
		ret = s2mpb02_camera_prepare_voltage(dev, map, rail);
		if (ret)
			return ret;
		config.driver_data = rail;
		rdev = devm_regulator_register(dev, &rail->desc, &config);
		if (IS_ERR(rdev))
			return PTR_ERR(rdev);
	}
	return 0;
}

static int s2mpb02_torch_set(struct led_classdev *led, enum led_brightness level)
{
	struct s2mpb02_torch *torch = container_of(led, struct s2mpb02_torch, led);
	int ret;

	guard(mutex)(&torch->lock);
	gpiod_set_value_cansleep(torch->enable, 0);
	if (!level)
		return regmap_update_bits(torch->regmap, S2MPB02_FLED_CUR1,
					  S2MPB02_TORCH_CUR_MASK, torch->idle_current);

	ret = regmap_update_bits(torch->regmap, S2MPB02_FLED_CTRL1,
				 S2MPB02_GPIO_MODE_MASK, 0);
	if (ret)
		return ret;
	ret = regmap_update_bits(torch->regmap, S2MPB02_FLED_CUR1,
				 S2MPB02_TORCH_CUR_MASK, level);
	if (ret)
		return ret;

	gpiod_set_value_cansleep(torch->enable, 1);
	return 0;
}

static enum led_brightness s2mpb02_torch_get(struct led_classdev *led)
{
	struct s2mpb02_torch *torch = container_of(led, struct s2mpb02_torch, led);
	unsigned int current_code;
	int ret;

	guard(mutex)(&torch->lock);
	ret = gpiod_get_value_cansleep(torch->enable);
	if (ret <= 0)
		return ret;
	ret = regmap_read(torch->regmap, S2MPB02_FLED_CUR1, &current_code);
	if (ret)
		return ret;

	current_code &= S2MPB02_TORCH_CUR_MASK;
	if (!current_code || current_code > S2MPB02_TORCH_MAX)
		return -EIO;
	return current_code;
}

static void s2mpb02_torch_shutdown(struct i2c_client *client)
{
	struct s2mpb02_torch *torch = i2c_get_clientdata(client);

	s2mpb02_torch_set(&torch->led, LED_OFF);
}

static int s2mpb02_torch_probe(struct i2c_client *client)
{
	struct device *dev = &client->dev;
	struct s2mpb02_torch *torch;
	struct gpio_desc *flash;
	unsigned int boost, mode;
	int ret;

	torch = devm_kzalloc(dev, sizeof(*torch), GFP_KERNEL);
	if (!torch)
		return -ENOMEM;

	torch->regmap = devm_regmap_init_i2c(client, &s2mpb02_torch_regmap);
	if (IS_ERR(torch->regmap))
		return PTR_ERR(torch->regmap);

	ret = regmap_read(torch->regmap, S2MPB02_BST_CTRL2, &boost);
	if (ret)
		return ret;
	if (boost != S2MPB02_REV1_BOOST)
		return dev_err_probe(dev, -ENODEV, "unexpected boost configuration\n");
	ret = regmap_read(torch->regmap, S2MPB02_FLED_CTRL1, &mode);
	if (ret)
		return ret;
	if (mode & S2MPB02_GPIO_MODE_MASK)
		return dev_err_probe(dev, -EBUSY, "flash controller already active\n");

	ret = regmap_read(torch->regmap, S2MPB02_FLED_CUR1, &torch->idle_current);
	if (ret)
		return ret;
	torch->idle_current &= S2MPB02_TORCH_CUR_MASK;

	flash = devm_gpiod_get(dev, "flash", GPIOD_OUT_LOW);
	if (IS_ERR(flash))
		return dev_err_probe(dev, PTR_ERR(flash), "cannot keep flash disabled\n");
	torch->enable = devm_gpiod_get(dev, "torch", GPIOD_OUT_LOW);
	if (IS_ERR(torch->enable))
		return dev_err_probe(dev, PTR_ERR(torch->enable), "cannot claim torch pin\n");

	ret = s2mpb02_register_camera_rails(dev, torch->regmap);
	if (ret)
		return ret;
	mutex_init(&torch->lock);
	torch->led.name = "white:torch";
	torch->led.max_brightness = S2MPB02_TORCH_MAX;
	torch->led.brightness_set_blocking = s2mpb02_torch_set;
	torch->led.brightness_get = s2mpb02_torch_get;
	torch->led.flags = LED_CORE_SUSPENDRESUME;
	i2c_set_clientdata(client, torch);
	return devm_led_classdev_register(dev, &torch->led);
}

static const struct of_device_id s2mpb02_torch_of_match[] = {
	{ .compatible = "samsung,sm-g955n-s2mpb02-torch" },
	{}
};
MODULE_DEVICE_TABLE(of, s2mpb02_torch_of_match);

static struct i2c_driver s2mpb02_torch_driver = {
	.driver = {
		.name = "g955n-s2mpb02-torch",
		.of_match_table = s2mpb02_torch_of_match,
	},
	.probe = s2mpb02_torch_probe,
	.shutdown = s2mpb02_torch_shutdown,
};
module_i2c_driver(s2mpb02_torch_driver);

MODULE_DESCRIPTION("SM-G955N S2MPB02 white torch");
MODULE_LICENSE("GPL");
