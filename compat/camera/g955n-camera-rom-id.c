// SPDX-License-Identifier: GPL-2.0-only
/*
 * Classify installed Korean Dream2 camera modules without reading calibration.
 * Header locations and module signatures follow Samsung's FIMC-IS source.
 */
#include <linux/cleanup.h>
#include <linux/delay.h>
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/regulator/consumer.h>
#include <linux/spi/spi.h>

#define CAMERA_HEADER_LENGTH 5

struct g955n_camera_rom {
	struct regulator *supply;
	struct mutex lock;
	int (*read)(struct device *dev, u8 *header);
};

static const char *g955n_camera_model(const u8 *header, bool front)
{
	if (front) {
		if (!memcmp(header, "V08LS", CAMERA_HEADER_LENGTH))
			return "IMX320";
		if (!memcmp(header, "V08LL", CAMERA_HEADER_LENGTH))
			return "S5K3H1";
		return "unknown";
	}

	if (!memcmp(header, "F12LS", CAMERA_HEADER_LENGTH) ||
	    !memcmp(header, "F12LY", CAMERA_HEADER_LENGTH))
		return "IMX333";
	if (!memcmp(header, "F12LL", CAMERA_HEADER_LENGTH) ||
	    !memcmp(header, "F12LX", CAMERA_HEADER_LENGTH) ||
	    !memcmp(header, "E12LL", CAMERA_HEADER_LENGTH))
		return "S5K2L2";
	return "unknown";
}

static int g955n_front_read(struct device *dev, u8 *header)
{
	struct i2c_client *client = to_i2c_client(dev);
	u8 offset[] = { 0x00, 0x30 };
	struct i2c_msg msgs[] = {
		{ .addr = client->addr, .len = sizeof(offset), .buf = offset },
		{ .addr = client->addr, .flags = I2C_M_RD,
		  .len = CAMERA_HEADER_LENGTH, .buf = header },
	};
	int ret;

	ret = i2c_transfer(client->adapter, msgs, ARRAY_SIZE(msgs));
	if (ret < 0)
		return ret;
	return ret == ARRAY_SIZE(msgs) ? 0 : -EIO;
}

static int g955n_rear_read(struct device *dev, u8 *header)
{
	const u8 read_header[] = { 0x03, 0x00, 0x00, 0x40 };

	return spi_write_then_read(to_spi_device(dev), read_header, sizeof(read_header),
				   header, CAMERA_HEADER_LENGTH);
}

static ssize_t sensor_model_show(struct device *dev, struct device_attribute *attr,
				 char *buf)
{
	struct g955n_camera_rom *rom = dev_get_drvdata(dev);
	u8 header[CAMERA_HEADER_LENGTH];
	int shutdown, ret;

	guard(mutex)(&rom->lock);
	ret = regulator_enable(rom->supply);
	if (ret)
		return ret;
	usleep_range(2000, 3000);
	ret = rom->read(dev, header);
	shutdown = regulator_disable(rom->supply);
	if (shutdown) {
		dev_err_ratelimited(dev, "cannot disable camera ROM supply: %d\n", shutdown);
		return shutdown;
	}
	if (ret)
		return ret;

	return sysfs_emit(buf, "%s\n", g955n_camera_model(header, rom->read == g955n_front_read));
}
static DEVICE_ATTR_ADMIN_RO(sensor_model);

static struct attribute *g955n_camera_rom_attrs[] = {
	&dev_attr_sensor_model.attr,
	NULL,
};
ATTRIBUTE_GROUPS(g955n_camera_rom);

static int g955n_camera_rom_probe(struct device *dev,
				int (*read)(struct device *dev, u8 *header))
{
	struct g955n_camera_rom *rom;
	int voltage;

	if (!of_machine_is_compatible("samsung,dream2lteks") ||
	    !of_property_present(dev->of_node, "vcc-supply"))
		return -ENODEV;
	rom = devm_kzalloc(dev, sizeof(*rom), GFP_KERNEL);
	if (!rom)
		return -ENOMEM;
	rom->supply = devm_regulator_get(dev, "vcc");
	if (IS_ERR(rom->supply))
		return dev_err_probe(dev, PTR_ERR(rom->supply), "camera ROM supply unavailable\n");
	voltage = regulator_get_voltage(rom->supply);
	if (voltage != 1800000)
		return dev_err_probe(dev, voltage < 0 ? voltage : -EINVAL,
				     "camera ROM requires the 1.8 V rail\n");
	mutex_init(&rom->lock);
	rom->read = read;
	dev_set_drvdata(dev, rom);
	return 0;
}

static int g955n_camera_front_probe(struct i2c_client *client)
{
	if (client->addr != 0x51)
		return -ENODEV;
	return g955n_camera_rom_probe(&client->dev, g955n_front_read);
}

static int g955n_camera_rear_probe(struct spi_device *spi)
{
	if (spi->max_speed_hz > 1000000 || (spi->mode & (SPI_CPOL | SPI_CPHA)))
		return -EINVAL;
	return g955n_camera_rom_probe(&spi->dev, g955n_rear_read);
}

static const struct of_device_id g955n_camera_front_ids[] = {
	{ .compatible = "samsung,sm-g955n-camera-front-rom" },
	{ }
};
MODULE_DEVICE_TABLE(of, g955n_camera_front_ids);

static const struct of_device_id g955n_camera_rear_ids[] = {
	{ .compatible = "samsung,sm-g955n-camera-rear-rom" },
	{ }
};
MODULE_DEVICE_TABLE(of, g955n_camera_rear_ids);

static const struct spi_device_id g955n_camera_rear_spi_ids[] = {
	{ "sm-g955n-camera-rear-rom" },
	{ }
};
MODULE_DEVICE_TABLE(spi, g955n_camera_rear_spi_ids);

static struct i2c_driver g955n_camera_front_driver = {
	.driver = {
		.name = "g955n-camera-front-rom",
		.of_match_table = g955n_camera_front_ids,
		.dev_groups = g955n_camera_rom_groups,
	},
	.probe = g955n_camera_front_probe,
};

static struct spi_driver g955n_camera_rear_driver = {
	.driver = {
		.name = "g955n-camera-rear-rom",
		.of_match_table = g955n_camera_rear_ids,
		.dev_groups = g955n_camera_rom_groups,
	},
	.id_table = g955n_camera_rear_spi_ids,
	.probe = g955n_camera_rear_probe,
};

static int __init g955n_camera_rom_init(void)
{
	int ret;

	ret = i2c_add_driver(&g955n_camera_front_driver);
	if (ret)
		return ret;
	ret = spi_register_driver(&g955n_camera_rear_driver);
	if (ret)
		i2c_del_driver(&g955n_camera_front_driver);
	return ret;
}

static void __exit g955n_camera_rom_exit(void)
{
	spi_unregister_driver(&g955n_camera_rear_driver);
	i2c_del_driver(&g955n_camera_front_driver);
}

module_init(g955n_camera_rom_init);
module_exit(g955n_camera_rom_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("SM-G955N read-only camera module identification");
