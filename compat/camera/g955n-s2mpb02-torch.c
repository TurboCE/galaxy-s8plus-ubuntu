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

#define S2MPB02_FLED_CTRL1	0x12
#define S2MPB02_FLED_CUR1	0x14
#define S2MPB02_BST_CTRL2	0x1d
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
	.max_register = S2MPB02_BST_CTRL2,
};

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
