// SPDX-License-Identifier: GPL-2.0-only
/* Read the Dream2 sub-PMIC's identity and idle flash settings. */
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/of.h>

#define S2MPB02_ADDRESS 0x59
#define S2MPB02_ID 0x00
#define S2MPB02_FLED_CTRL1 0x12
#define S2MPB02_FLED_CTRL2 0x13
#define S2MPB02_FLED_CUR1 0x14
#define S2MPB02_FLED_TIME1 0x15
#define S2MPB02_BST_CTRL2 0x1d

static int __init g955n_s2mpb02_readback(void)
{
	static const u8 registers[] = {
		S2MPB02_ID, S2MPB02_FLED_CTRL1, S2MPB02_FLED_CTRL2,
		S2MPB02_FLED_CUR1, S2MPB02_FLED_TIME1, S2MPB02_BST_CTRL2,
	};
	struct device_node *root, *node;
	struct i2c_adapter *adapter;
	struct i2c_client *client;
	int i, ret = 0;

	root = of_find_node_by_path("/");
	if (!of_device_is_compatible(root, "samsung,dream2lteks")) {
		of_node_put(root);
		return -ENODEV;
	}
	of_node_put(root);
	node = of_find_node_by_path("/soc@0/usi@10900000/i2c@0");
	if (!node)
		return -ENODEV;
	adapter = of_get_i2c_adapter_by_node(node);
	of_node_put(node);
	if (!adapter)
		return -ENODEV;

	client = i2c_new_dummy_device(adapter, S2MPB02_ADDRESS);
	if (IS_ERR(client)) {
		ret = PTR_ERR(client);
		goto release_adapter;
	}
	for (i = 0; i < ARRAY_SIZE(registers); i++) {
		int value = i2c_smbus_read_byte_data(client, registers[i]);

		if (value < 0) {
			ret = value;
			break;
		}
		pr_info("g955n-s2mpb02-readback: reg 0x%02x = 0x%02x\n",
			registers[i], value);
	}
	i2c_unregister_device(client);
release_adapter:
	i2c_put_adapter(adapter);
	return ret;
}

static void __exit g955n_s2mpb02_readback_exit(void)
{
}

module_init(g955n_s2mpb02_readback);
module_exit(g955n_s2mpb02_readback_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("SM-G955N read-only S2MPB02 identification");
