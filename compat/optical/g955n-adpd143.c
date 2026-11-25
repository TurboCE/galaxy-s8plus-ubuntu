// SPDX-License-Identifier: GPL-2.0-only
/*
 * ADPD143 optical acquisition on the SM-G955N.
 * Timing and FIFO format from the Samsung ADPD143 driver,
 * Copyright 2016 Analog Devices, Inc.
 */
#include <linux/delay.h>
#include <linux/i2c.h>
#include <linux/iio/buffer.h>
#include <linux/iio/iio.h>
#include <linux/iio/kfifo_buf.h>
#include <linux/interrupt.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/regmap.h>
#include <linux/regulator/consumer.h>
#include <linux/unaligned.h>

#define ADPD_STATUS		0x00
#define ADPD_IRQ_MASK		0x01
#define ADPD_ID			0x08
#define ADPD_MODE		0x10
#define ADPD_SLOTS		0x11
#define ADPD_LED_DISABLE	0x34
#define ADPD_FIFO_ACCESS	0x5f
#define ADPD_FIFO		0x60

#define ADPD_STANDBY		0
#define ADPD_PROGRAM		1
#define ADPD_SAMPLE		2
#define ADPD_LED_BOTH_OFF	0x0300
#define ADPD_SLOT_AB		0x9131
#define ADPD_IRQ_SLOT_B		0xc1bf
#define ADPD_FIFO_CLEAR		0x80ff
#define ADPD_FRAME_BYTES	16
#define ADPD_FIFO_BYTES		128

/* Board sampling profile. Emitters remain disabled until GO. */
static const struct reg_sequence adpd_profile[] = {
	{ 0x02, 0x0005 }, { 0x06, 0x0000 }, { 0x12, 0x000a }, { 0x13, 0x0320 },
	{ 0x14, 0x0449 }, { 0x15, 0x0330 }, { 0x16, 0x8080 }, { 0x17, 0x8080 },
	{ 0x18, 0x2100 }, { 0x19, 0x2100 }, { 0x1a, 0x2000 }, { 0x1b, 0x2000 },
	{ 0x1c, 0x8080 }, { 0x1d, 0x8080 }, { 0x1e, 0x2100 }, { 0x1f, 0x2100 },
	{ 0x20, 0x2000 }, { 0x21, 0x2000 }, { 0x22, 0x3030 },
	/* Both board LED paths at coarse code 1, below the stock 5 and 15. */
	{ 0x23, 0x3071 }, { 0x24, 0x3071 }, { 0x25, 0x030c },
	{ 0x30, 0x0330 }, { 0x31, 0x0813 }, { 0x35, 0x0330 }, { 0x36, 0x0b13 },
	{ 0x39, 0x24d4 }, { 0x3b, 0x24d4 }, { 0x3c, 0x0006 },
	{ 0x42, 0x1c37 }, { 0x43, 0xada5 }, { 0x44, 0x1c37 }, { 0x45, 0xada5 },
	{ 0x4b, 0x2694 }, { 0x4e, 0x0040 }, { 0x52, 0x0040 },
	{ 0x54, 0x0020 }, { 0x58, 0x0000 },
	{ ADPD_SLOTS, ADPD_SLOT_AB }, { ADPD_IRQ_MASK, ADPD_IRQ_SLOT_B },
	{ ADPD_STATUS, ADPD_FIFO_CLEAR },
};

struct g955n_adpd {
	struct i2c_client *client;
	struct regmap *map;
	struct regulator *vdd;
	struct regulator *vddio;
	struct regulator *vled;
	bool streaming;
};

struct adpd_sample {
	u32 red;
	u32 ir;
	aligned_s64 timestamp;
};

static int adpd_fifo_frame(struct g955n_adpd *adpd, struct adpd_sample *sample)
{
	u8 addr = ADPD_FIFO, data[ADPD_FRAME_BYTES];
	struct i2c_client *client = adpd->client;
	struct i2c_msg msgs[] = {
		{ .addr = client->addr, .len = 1, .buf = &addr },
		{ .addr = client->addr, .flags = I2C_M_RD, .len = sizeof(data), .buf = data },
	};
	int ret, channel;

	ret = i2c_transfer(client->adapter, msgs, ARRAY_SIZE(msgs));
	if (ret < 0)
		return ret;
	if (ret != ARRAY_SIZE(msgs))
		return -EIO;

	for (channel = 0; channel < 4; channel++) {
		sample->red += get_unaligned_be16(data + 2 * channel);
		sample->ir += get_unaligned_be16(data + 8 + 2 * channel);
	}
	return 0;
}

static irqreturn_t adpd_irq(int irq, void *private)
{
	struct iio_dev *indio = private;
	struct g955n_adpd *adpd = iio_priv(indio);
	unsigned int status, count;
	int ret;

	ret = regmap_read(adpd->map, ADPD_STATUS, &status);
	if (ret)
		goto failed;

	count = min(status >> 8, (unsigned int)ADPD_FIFO_BYTES) / ADPD_FRAME_BYTES;
	for (; count; count--) {
		struct adpd_sample sample = {};

		ret = adpd_fifo_frame(adpd, &sample);
		if (ret)
			goto failed;
		iio_push_to_buffers_with_timestamp(indio, &sample, iio_get_time_ns(indio));
	}

	ret = regmap_write(adpd->map, ADPD_STATUS, status & 0xff);
	if (!ret)
		return IRQ_HANDLED;

failed:
	dev_err_ratelimited(&adpd->client->dev, "optical FIFO read failed: %d\n", ret);
	return IRQ_HANDLED;
}

static int adpd_logic_power_off(struct g955n_adpd *adpd)
{
	int vdd, io;

	vdd = regulator_disable(adpd->vdd);
	io = adpd->vddio ? regulator_disable(adpd->vddio) : 0;
	return vdd ?: io;
}

static int adpd_logic_power_on(struct g955n_adpd *adpd)
{
	int ret, cleanup;

	if (adpd->vddio) {
		ret = regulator_enable(adpd->vddio);
		if (ret)
			return ret;
	}
	ret = regulator_enable(adpd->vdd);
	if (ret) {
		if (adpd->vddio) {
			cleanup = regulator_disable(adpd->vddio);
			if (cleanup)
				dev_err(&adpd->client->dev, "cannot release optical I/O supply: %d\n",
					cleanup);
		}
		return ret;
	}
	usleep_range(3000, 4000);
	return 0;
}

static int adpd_stop(struct iio_dev *indio)
{
	struct g955n_adpd *adpd = iio_priv(indio);
	int standby, led, vdd;

	if (!adpd->streaming)
		return 0;

	disable_irq(adpd->client->irq);
	standby = regmap_write(adpd->map, ADPD_MODE, ADPD_STANDBY);
	led = regulator_disable(adpd->vled);
	vdd = adpd_logic_power_off(adpd);
	adpd->streaming = false;

	return standby ? standby : led ? led : vdd;
}

static int adpd_start(struct iio_dev *indio)
{
	struct g955n_adpd *adpd = iio_priv(indio);
	int ret;

	ret = adpd_logic_power_on(adpd);
	if (ret)
		return ret;
	ret = regmap_write(adpd->map, ADPD_MODE, ADPD_PROGRAM);
	if (ret)
		goto disable_vdd;
	ret = regmap_write(adpd->map, ADPD_LED_DISABLE, ADPD_LED_BOTH_OFF);
	if (ret)
		goto standby;
	ret = regmap_multi_reg_write(adpd->map, adpd_profile, ARRAY_SIZE(adpd_profile));
	if (ret)
		goto standby;
	ret = regmap_update_bits(adpd->map, ADPD_FIFO_ACCESS, BIT(0), BIT(0));
	if (ret)
		goto standby;

	ret = regulator_enable(adpd->vled);
	if (ret)
		goto standby;
	usleep_range(1000, 1100);
	ret = regmap_write(adpd->map, ADPD_LED_DISABLE, 0);
	if (ret)
		goto disable_vled;

	enable_irq(adpd->client->irq);
	ret = regmap_write(adpd->map, ADPD_MODE, ADPD_SAMPLE);
	if (ret) {
		disable_irq(adpd->client->irq);
		goto disable_vled;
	}
	adpd->streaming = true;
	return 0;

disable_vled:
	regulator_disable(adpd->vled);
standby:
	regmap_write(adpd->map, ADPD_MODE, ADPD_STANDBY);
disable_vdd:
	adpd_logic_power_off(adpd);
	return ret;
}

static const struct iio_buffer_setup_ops adpd_buffer_ops = {
	.postenable = adpd_start,
	.predisable = adpd_stop,
};

#define ADPD_INTENSITY(index, color) { \
	.type = IIO_INTENSITY, .modified = 1, .channel2 = IIO_MOD_LIGHT_##color, \
	.scan_index = index, .scan_type = { .sign = 'u', .realbits = 18, \
	.storagebits = 32, .endianness = IIO_CPU }, \
}

static const struct iio_chan_spec adpd_channels[] = {
	ADPD_INTENSITY(0, RED),
	ADPD_INTENSITY(1, IR),
	IIO_CHAN_SOFT_TIMESTAMP(2),
};

static const unsigned long adpd_scan_masks[] = { BIT(0) | BIT(1), 0 };
static const struct iio_info adpd_info = {};

static const struct regmap_config adpd_regmap = {
	.reg_bits = 8,
	.val_bits = 16,
	.val_format_endian = REGMAP_ENDIAN_BIG,
	.max_register = ADPD_FIFO,
};

static int g955n_adpd_probe(struct i2c_client *client)
{
	struct device *dev = &client->dev;
	struct iio_dev *indio;
	struct g955n_adpd *adpd;
	unsigned int id;
	int ret, disable;

	if (!of_machine_is_compatible("samsung,dream2lteks") || client->addr != 0x64)
		return -ENODEV;
	if (!i2c_check_functionality(client->adapter, I2C_FUNC_I2C))
		return -EOPNOTSUPP;

	indio = devm_iio_device_alloc(dev, sizeof(*adpd));
	if (!indio)
		return -ENOMEM;
	adpd = iio_priv(indio);
	adpd->client = client;

	adpd->map = devm_regmap_init_i2c(client, &adpd_regmap);
	if (IS_ERR(adpd->map))
		return dev_err_probe(dev, PTR_ERR(adpd->map), "cannot access ADPD143\n");
	adpd->vdd = devm_regulator_get(dev, "vdd");
	if (IS_ERR(adpd->vdd))
		return dev_err_probe(dev, PTR_ERR(adpd->vdd), "cannot get VDD\n");
	adpd->vddio = devm_regulator_get_optional(dev, "vddio");
	if (IS_ERR(adpd->vddio)) {
		if (PTR_ERR(adpd->vddio) != -ENODEV)
			return dev_err_probe(dev, PTR_ERR(adpd->vddio), "cannot get VDDIO\n");
		adpd->vddio = NULL;
	}
	adpd->vled = devm_regulator_get(dev, "vled");
	if (IS_ERR(adpd->vled))
		return dev_err_probe(dev, PTR_ERR(adpd->vled), "cannot get VLED\n");

	ret = adpd_logic_power_on(adpd);
	if (ret)
		return ret;
	ret = regmap_read(adpd->map, ADPD_ID, &id);
	disable = adpd_logic_power_off(adpd);
	if (ret || disable)
		return dev_err_probe(dev, ret ? ret : disable, "could not verify ADPD143\n");
	if (id != 0x0316)
		return dev_err_probe(dev, -ENODEV, "unexpected ADPD143 ID 0x%04x\n", id);

	indio->name = "g955n-adpd143";
	indio->info = &adpd_info;
	indio->channels = adpd_channels;
	indio->num_channels = ARRAY_SIZE(adpd_channels);
	indio->available_scan_masks = adpd_scan_masks;

	ret = devm_request_threaded_irq(dev, client->irq, NULL, adpd_irq,
					IRQF_ONESHOT | IRQF_NO_AUTOEN, dev_name(dev), indio);
	if (ret)
		return dev_err_probe(dev, ret, "cannot request ADPD143 IRQ\n");

	ret = devm_iio_kfifo_buffer_setup(dev, indio, &adpd_buffer_ops);
	if (ret)
		return ret;
	i2c_set_clientdata(client, indio);
	return devm_iio_device_register(dev, indio);
}

static int g955n_adpd_suspend(struct device *dev)
{
	return adpd_stop(dev_get_drvdata(dev));
}

static int g955n_adpd_resume(struct device *dev)
{
	struct iio_dev *indio = dev_get_drvdata(dev);

	return iio_buffer_enabled(indio) ? adpd_start(indio) : 0;
}
static DEFINE_SIMPLE_DEV_PM_OPS(g955n_adpd_pm, g955n_adpd_suspend, g955n_adpd_resume);

static void g955n_adpd_shutdown(struct i2c_client *client)
{
	adpd_stop(i2c_get_clientdata(client));
}

static const struct of_device_id g955n_adpd_match[] = {
	{ .compatible = "samsung,sm-g955n-adpd143" },
	{ }
};
MODULE_DEVICE_TABLE(of, g955n_adpd_match);

static struct i2c_driver g955n_adpd_driver = {
	.driver = {
		.name = "g955n-adpd143",
		.of_match_table = g955n_adpd_match,
		.pm = pm_sleep_ptr(&g955n_adpd_pm),
	},
	.probe = g955n_adpd_probe,
	.shutdown = g955n_adpd_shutdown,
};
module_i2c_driver(g955n_adpd_driver);

MODULE_DESCRIPTION("SM-G955N ADPD143 optical IIO acquisition");
MODULE_LICENSE("GPL");
