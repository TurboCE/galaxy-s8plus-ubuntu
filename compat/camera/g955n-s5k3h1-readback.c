// SPDX-License-Identifier: GPL-2.0-only
/* Read the S5K3H1 chip directly after Samsung's standalone power sequence. */
#include <linux/cleanup.h>
#include <linux/clk.h>
#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/pinctrl/consumer.h>
#include <linux/regulator/consumer.h>
#include <linux/unaligned.h>

#define S5K3H1_MCLK_HZ	26000000
#define S5K3H1_CHIP_ID	0x3081

struct s5k3h1_reg16 {
	u16 reg;
	u16 value;
};

#include "s5k3h1-1632x918.h"

static const char *const supply_names[] = { "afvdd", "avdd", "iovdd", "dvdd" };
static const unsigned int supply_uv[] = { 2800000, 2800000, 1800000, 1050000 };

struct g955n_s5k3h1 {
	struct clk *xclk;
	struct gpio_desc *reset;
	struct pinctrl *pins;
	struct pinctrl_state *idle;
	struct pinctrl_state *mclk;
	struct regulator *supplies[ARRAY_SIZE(supply_names)];
	struct mutex lock;
};

static int g955n_s5k3h1_read(struct i2c_client *client, u16 reg, u8 *data, u16 length)
{
	u8 address[] = { reg >> 8, reg & 0xff };
	struct i2c_msg msgs[] = {
		{ .addr = client->addr, .len = sizeof(address), .buf = address },
		{ .addr = client->addr, .flags = I2C_M_RD, .len = length, .buf = data },
	};
	int ret;

	ret = i2c_transfer(client->adapter, msgs, ARRAY_SIZE(msgs));
	if (ret < 0)
		return ret;
	return ret == ARRAY_SIZE(msgs) ? 0 : -EIO;
}

static int g955n_s5k3h1_drop_supplies(struct g955n_s5k3h1 *sensor, unsigned int enabled)
{
	static const unsigned int off_order[] = { 0, 3, 1, 2 };
	unsigned int i;
	int ret = 0;

	for (i = 0; i < ARRAY_SIZE(off_order); i++) {
		unsigned int index = off_order[i];
		int error;

		if (index >= enabled)
			continue;
		error = regulator_disable(sensor->supplies[index]);
		if (error && !ret)
			ret = error;
	}
	return ret;
}

static int g955n_s5k3h1_power_off(struct g955n_s5k3h1 *sensor, unsigned int enabled,
				 bool clock_on)
{
	int pins, supplies;

	pins = pinctrl_select_state(sensor->pins, sensor->idle);
	gpiod_set_value_cansleep(sensor->reset, 1);
	if (clock_on)
		clk_disable_unprepare(sensor->xclk);
	supplies = g955n_s5k3h1_drop_supplies(sensor, enabled);
	return pins ?: supplies;
}

static int g955n_s5k3h1_power_on(struct device *dev, struct g955n_s5k3h1 *sensor)
{
	unsigned int enabled;
	bool clock_on = false;
	int ret, cleanup;

	if (clk_get_rate(sensor->xclk) != S5K3H1_MCLK_HZ)
		return -ERANGE;
	for (enabled = 0; enabled < ARRAY_SIZE(sensor->supplies); enabled++) {
		ret = regulator_enable(sensor->supplies[enabled]);
		if (ret)
			goto power_off;
	}
	usleep_range(1000, 1500);
	ret = clk_prepare_enable(sensor->xclk);
	if (ret)
		goto power_off;
	clock_on = true;
	gpiod_set_value_cansleep(sensor->reset, 0);
	ret = pinctrl_select_state(sensor->pins, sensor->mclk);
	if (ret)
		goto power_off;
	usleep_range(9000, 10000);
	return 0;

power_off:
	cleanup = g955n_s5k3h1_power_off(sensor, enabled, clock_on);
	if (cleanup)
		dev_err_ratelimited(dev, "power-up rollback failed: %d\n", cleanup);
	return ret;
}

static int g955n_s5k3h1_write(struct i2c_client *client, u16 reg, u16 value, bool word)
{
	u8 bytes[4];
	unsigned int length = word ? 4 : 3;
	int ret;

	put_unaligned_be16(reg, bytes);
	if (word)
		put_unaligned_be16(value, bytes + 2);
	else
		bytes[2] = value;
	ret = i2c_master_send(client, bytes, length);
	if (ret < 0)
		return ret;
	return ret == length ? 0 : -EIO;
}

static int g955n_s5k3h1_set_stream(struct i2c_client *client, bool on)
{
	int ret;

	ret = g955n_s5k3h1_write(client, 0x6028, 0x4000, true);
	if (ret)
		return ret;
	return g955n_s5k3h1_write(client, 0x0100, on, false);
}

static int g955n_s5k3h1_start(struct i2c_client *client)
{
	unsigned int i;
	int ret;

	for (i = 0; i < ARRAY_SIZE(s5k3h1_1632x918); i++) {
		ret = g955n_s5k3h1_write(client, s5k3h1_1632x918[i].reg,
					 s5k3h1_1632x918[i].value, true);
		if (ret)
			return ret;
	}
	msleep(8);
	return g955n_s5k3h1_set_stream(client, true);
}

static int g955n_s5k3h1_frame_test(struct i2c_client *client, u8 *first, u8 *last)
{
	u8 frame, mode, identity[2];
	unsigned int i, count = 0;
	int ret;

	ret = g955n_s5k3h1_read(client, 0x0000, identity, sizeof(identity));
	if (ret)
		return ret;
	if (get_unaligned_be16(identity) != S5K3H1_CHIP_ID)
		return -ENODEV;
	ret = g955n_s5k3h1_start(client);
	if (ret)
		return ret;

	for (i = 0; i < 24; i++) {
		usleep_range(15000, 18000);
		ret = g955n_s5k3h1_read(client, 0x0005, &frame, 1);
		if (ret)
			return ret;
		if (frame == 0xff || (count && frame == *last))
			continue;
		if (!count)
			*first = frame;
		*last = frame;
		if (++count == 4)
			break;
	}
	if (count != 4)
		return -ETIMEDOUT;
	ret = g955n_s5k3h1_read(client, 0x0100, &mode, 1);
	if (ret)
		return ret;
	return mode == 1 ? 0 : -EIO;
}

static int g955n_s5k3h1_wait_standby(struct i2c_client *client)
{
	unsigned int i;
	u8 frame, mode;
	int ret;

	ret = g955n_s5k3h1_set_stream(client, false);
	if (ret)
		return ret;
	for (i = 0; i < 8; i++) {
		usleep_range(10000, 12000);
		ret = g955n_s5k3h1_read(client, 0x0005, &frame, 1);
		if (ret)
			return ret;
		if (frame == 0xff)
			break;
	}
	if (frame != 0xff)
		return -ETIMEDOUT;
	ret = g955n_s5k3h1_read(client, 0x0100, &mode, 1);
	if (ret)
		return ret;
	return mode ? -EIO : 0;
}

static ssize_t stream_probe_store(struct device *dev, struct device_attribute *attr,
				  const char *buf, size_t count)
{
	struct i2c_client *client = to_i2c_client(dev);
	struct g955n_s5k3h1 *sensor = i2c_get_clientdata(client);
	u8 first = 0xff, last = 0xff;
	int ret, stop, shutdown;

	if (!sysfs_streq(buf, "1"))
		return -EINVAL;
	guard(mutex)(&sensor->lock);
	ret = g955n_s5k3h1_power_on(dev, sensor);
	if (ret)
		return ret;
	ret = g955n_s5k3h1_frame_test(client, &first, &last);
	stop = g955n_s5k3h1_wait_standby(client);
	shutdown = g955n_s5k3h1_power_off(sensor, ARRAY_SIZE(sensor->supplies), true);
	if (stop || shutdown)
		dev_err_ratelimited(dev, "stream probe cleanup: standby %d, power %d\n",
				    stop, shutdown);
	if (ret || stop || shutdown)
		return ret ?: (stop ?: shutdown);
	dev_info(dev, "1632x918 stream counters advanced %u to %u and returned to standby\n",
		 first, last);
	return count;
}
static struct device_attribute dev_attr_stream_probe = __ATTR(stream_probe, 0200, NULL,
							      stream_probe_store);

static ssize_t sensor_registers_show(struct device *dev, struct device_attribute *attr,
				     char *buf)
{
	struct i2c_client *client = to_i2c_client(dev);
	struct g955n_s5k3h1 *sensor = i2c_get_clientdata(client);
	u8 identity[3], mode;
	int ret, cleanup;

	guard(mutex)(&sensor->lock);
	ret = g955n_s5k3h1_power_on(dev, sensor);
	if (ret)
		return ret;
	ret = g955n_s5k3h1_read(client, 0x0000, identity, sizeof(identity));
	if (!ret)
		ret = g955n_s5k3h1_read(client, 0x0100, &mode, 1);
	cleanup = g955n_s5k3h1_power_off(sensor, ARRAY_SIZE(sensor->supplies), true);
	if (ret || cleanup)
		return ret ?: cleanup;
	if (get_unaligned_be16(identity) != S5K3H1_CHIP_ID)
		return -ENODEV;
	if (mode)
		return -EBUSY;

	return sysfs_emit(buf, "chip=0x%04x revision=0x%02x mode=standby mclk=%u\n",
			  get_unaligned_be16(identity), identity[2], S5K3H1_MCLK_HZ);
}
static DEVICE_ATTR_ADMIN_RO(sensor_registers);

static struct attribute *g955n_s5k3h1_attrs[] = {
	&dev_attr_sensor_registers.attr,
	&dev_attr_stream_probe.attr,
	NULL,
};
ATTRIBUTE_GROUPS(g955n_s5k3h1);

static int g955n_s5k3h1_probe(struct i2c_client *client)
{
	struct device *dev = &client->dev;
	struct g955n_s5k3h1 *sensor;
	unsigned int i;
	int voltage;

	if (!of_machine_is_compatible("samsung,dream2lteks") || client->addr != 0x35)
		return -ENODEV;
	sensor = devm_kzalloc(dev, sizeof(*sensor), GFP_KERNEL);
	if (!sensor)
		return -ENOMEM;

	for (i = 0; i < ARRAY_SIZE(supply_names); i++) {
		sensor->supplies[i] = devm_regulator_get(dev, supply_names[i]);
		if (IS_ERR(sensor->supplies[i]))
			return dev_err_probe(dev, PTR_ERR(sensor->supplies[i]),
					     "missing %s supply\n", supply_names[i]);
		voltage = regulator_get_voltage(sensor->supplies[i]);
		if (voltage != supply_uv[i])
			return dev_err_probe(dev, voltage < 0 ? voltage : -EINVAL,
					     "unexpected %s voltage\n", supply_names[i]);
	}

	sensor->xclk = devm_clk_get(dev, "xclk");
	if (IS_ERR(sensor->xclk))
		return dev_err_probe(dev, PTR_ERR(sensor->xclk), "missing camera clock\n");
	sensor->pins = devm_pinctrl_get(dev);
	if (IS_ERR(sensor->pins))
		return dev_err_probe(dev, PTR_ERR(sensor->pins), "missing camera pinctrl\n");
	sensor->idle = pinctrl_lookup_state(sensor->pins, PINCTRL_STATE_DEFAULT);
	if (IS_ERR(sensor->idle))
		return PTR_ERR(sensor->idle);
	sensor->mclk = pinctrl_lookup_state(sensor->pins, "mclk");
	if (IS_ERR(sensor->mclk))
		return PTR_ERR(sensor->mclk);
	sensor->reset = devm_gpiod_get(dev, "reset", GPIOD_OUT_HIGH);
	if (IS_ERR(sensor->reset))
		return dev_err_probe(dev, PTR_ERR(sensor->reset), "missing camera reset\n");

	mutex_init(&sensor->lock);
	i2c_set_clientdata(client, sensor);
	return 0;
}

static const struct of_device_id g955n_s5k3h1_ids[] = {
	{ .compatible = "samsung,sm-g955n-s5k3h1-readback" },
	{ }
};
MODULE_DEVICE_TABLE(of, g955n_s5k3h1_ids);

static struct i2c_driver g955n_s5k3h1_driver = {
	.driver = {
		.name = "g955n-s5k3h1-readback",
		.of_match_table = g955n_s5k3h1_ids,
		.dev_groups = g955n_s5k3h1_groups,
	},
	.probe = g955n_s5k3h1_probe,
};
module_i2c_driver(g955n_s5k3h1_driver);

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("SM-G955N S5K3H1 front camera chip identification");
