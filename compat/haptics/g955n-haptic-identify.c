// SPDX-License-Identifier: GPL-2.0-only
/* Read-only MAX77865 haptic block identification on Korean Dream2 boards. */
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/of.h>

#define MAX77865_ADDRESS	0x66
#define MAX77865_PMIC_ID	0x00
#define MAX77865_PMIC_REV	0x01
#define MAX77865_MAINCTRL1	0x02
#define MAX77865_MOTOR_CONFIG	0x10

static int __init g955n_haptic_identify(void)
{
	struct device_node *switch_node, *bus;
	struct i2c_adapter *adapter;
	struct i2c_client *client;
	int id, rev, bias, motor;

	if (!of_machine_is_compatible("samsung,dream2lteks"))
		return -ENODEV;

	/* The fuel gauge and USB switch are functions of the same PMIC. */
	switch_node = of_find_compatible_node(NULL, NULL, "maxim,max77865-usb2-switch");
	if (!switch_node)
		return -ENODEV;
	bus = of_get_parent(switch_node);
	of_node_put(switch_node);
	if (!bus)
		return -ENODEV;
	adapter = of_find_i2c_adapter_by_node(bus);
	of_node_put(bus);
	if (!adapter)
		return -ENODEV;
	if (!i2c_check_functionality(adapter, I2C_FUNC_SMBUS_BYTE_DATA)) {
		i2c_put_adapter(adapter);
		return -EOPNOTSUPP;
	}
	client = i2c_new_dummy_device(adapter, MAX77865_ADDRESS);
	i2c_put_adapter(adapter);
	if (IS_ERR(client))
		return PTR_ERR(client);

	id = i2c_smbus_read_byte_data(client, MAX77865_PMIC_ID);
	rev = i2c_smbus_read_byte_data(client, MAX77865_PMIC_REV);
	bias = i2c_smbus_read_byte_data(client, MAX77865_MAINCTRL1);
	motor = i2c_smbus_read_byte_data(client, MAX77865_MOTOR_CONFIG);
	i2c_unregister_device(client);
	if (id < 0 || rev < 0 || bias < 0 || motor < 0) {
		pr_err("g955n-haptic: PMIC access failed: %d %d %d %d\n", id, rev, bias, motor);
		return -EIO;
	}
	pr_info("g955n-haptic: PMIC id=%02x rev=%02x bias=%d motor=%d config=%02x\n",
		id, rev, !!(bias & BIT(7)), !!(motor & BIT(6)), motor);
	return 0;
}
module_init(g955n_haptic_identify);

MODULE_DESCRIPTION("Read-only SM-G955N MAX77865 haptic block identification");
MODULE_LICENSE("GPL");
