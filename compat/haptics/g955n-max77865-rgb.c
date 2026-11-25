// SPDX-License-Identifier: GPL-2.0-only
/* MAX77865 notification LEDs on the Korean SM-G955N. */
#include <linux/i2c.h>
#include <linux/leds.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/regmap.h>

#include "g955n-max77865-rgb.h"

#define MAX77865_PMIC_ID		0x00
#define MAX77865_LED_ENABLE	0x30
#define MAX77865_LED_CURRENT	0x31
#define MAX77865_LED_ON		1

struct g955n_rgb;

struct g955n_rgb_channel {
	struct led_classdev led;
	struct g955n_rgb *rgb;
	unsigned int index;
};

struct g955n_rgb {
	struct regmap *map;
	struct mutex lock;
	struct g955n_rgb_channel channels[3];
};

static enum led_brightness g955n_rgb_get(struct led_classdev *led)
{
	struct g955n_rgb_channel *channel = container_of(led, struct g955n_rgb_channel, led);
	struct g955n_rgb *rgb = channel->rgb;
	unsigned int mode, measured = 0;
	int ret;

	mutex_lock(&rgb->lock);
	ret = regmap_read(rgb->map, MAX77865_LED_ENABLE, &mode);
	if (!ret && ((mode >> (2 * channel->index)) & 3))
		ret = regmap_read(rgb->map, MAX77865_LED_CURRENT + channel->index, &measured);
	mutex_unlock(&rgb->lock);
	return ret ? ret : (int)min(measured, led->max_brightness);
}

static int g955n_rgb_set(struct led_classdev *led, enum led_brightness brightness)
{
	struct g955n_rgb_channel *channel = container_of(led, struct g955n_rgb_channel, led);
	struct g955n_rgb *rgb = channel->rgb;
	unsigned int shift = 2 * channel->index;
	unsigned int mask = 3 << shift;
	unsigned int wanted = brightness ? MAX77865_LED_ON << shift : 0;
	unsigned int reg = MAX77865_LED_CURRENT + channel->index;
	unsigned int previous_mode, previous_current, observed;
	int ret, rollback;

	mutex_lock(&rgb->lock);
	ret = regmap_read(rgb->map, MAX77865_LED_ENABLE, &previous_mode);
	if (ret)
		goto unlock;
	ret = regmap_read(rgb->map, reg, &previous_current);
	if (ret)
		goto unlock;
	if (brightness) {
		ret = regmap_write(rgb->map, reg, brightness);
		if (ret)
			goto unlock;
	}
	ret = regmap_update_bits(rgb->map, MAX77865_LED_ENABLE, mask, wanted);
	if (!ret)
		ret = regmap_read(rgb->map, MAX77865_LED_ENABLE, &observed);
	if (!ret && (observed & mask) != wanted)
		ret = -EIO;
	if (!ret && brightness) {
		ret = regmap_read(rgb->map, reg, &observed);
		if (!ret && observed != brightness)
			ret = -EIO;
	}
	if (!ret)
		goto unlock;

	rollback = regmap_write(rgb->map, reg, previous_current);
	if (regmap_update_bits(rgb->map, MAX77865_LED_ENABLE, mask, previous_mode & mask) ||
	    rollback)
		dev_err(led->dev, "failed to restore LED output %u\n", channel->index);
unlock:
	mutex_unlock(&rgb->lock);
	return ret;
}

int g955n_max77865_rgb_register(struct device *dev, struct regmap *map)
{
	static const char * const names[] = { "red:indicator", "green:indicator", "blue:indicator" };
	/* Samsung's normal current (10) multiplied by 820%, 70% and 150%. */
	static const unsigned int limits[] = { 82, 7, 15 };
	struct g955n_rgb *rgb;
	unsigned int i, mode, current_level;
	int ret;

	ret = regmap_read(map, MAX77865_LED_ENABLE, &mode);
	if (ret)
		return ret;

	rgb = devm_kzalloc(dev, sizeof(*rgb), GFP_KERNEL);
	if (!rgb)
		return -ENOMEM;
	rgb->map = map;
	mutex_init(&rgb->lock);
	for (i = 0; i < ARRAY_SIZE(rgb->channels); i++) {
		struct g955n_rgb_channel *channel = &rgb->channels[i];

		channel->rgb = rgb;
		channel->index = i + 1;
		channel->led.name = names[i];
		channel->led.max_brightness = limits[i];
		channel->led.brightness_set_blocking = g955n_rgb_set;
		channel->led.brightness_get = g955n_rgb_get;
		ret = regmap_read(map, MAX77865_LED_CURRENT + channel->index, &current_level);
		if (ret)
			return ret;
		if ((mode >> (2 * channel->index)) & 3)
			channel->led.brightness = min(current_level, limits[i]);

		ret = devm_led_classdev_register(dev, &channel->led);
		if (ret)
			return ret;
	}

	return 0;
}
EXPORT_SYMBOL_GPL(g955n_max77865_rgb_register);

static int g955n_rgb_probe(struct i2c_client *client)
{
	static const struct regmap_config config = {
		.reg_bits = 8,
		.val_bits = 8,
		.max_register = G955N_MAX77865_RGB_LAST_REG,
	};
	struct regmap *map;
	unsigned int id;
	int ret;

	if (!of_machine_is_compatible("samsung,dream2lteks") || client->addr != 0x66)
		return -ENODEV;
	map = devm_regmap_init_i2c(client, &config);
	if (IS_ERR(map))
		return PTR_ERR(map);
	ret = regmap_read(map, MAX77865_PMIC_ID, &id);
	if (ret)
		return ret;
	if (id != 0x65)
		return -ENODEV;
	return g955n_max77865_rgb_register(&client->dev, map);
}

/* A standalone LED-only binding for kernels without the PWM motor driver. */
static const struct i2c_device_id g955n_rgb_id[] = {
	{ "g955n-max77865-rgb" },
	{}
};
MODULE_DEVICE_TABLE(i2c, g955n_rgb_id);

static struct i2c_driver g955n_rgb_driver = {
	.driver.name = "g955n-max77865-rgb",
	.probe = g955n_rgb_probe,
	.id_table = g955n_rgb_id,
};
module_i2c_driver(g955n_rgb_driver);

MODULE_DESCRIPTION("SM-G955N MAX77865 notification LEDs");
MODULE_LICENSE("GPL");
