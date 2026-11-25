// SPDX-License-Identifier: GPL-2.0-only
/* Report input presence from the MAX77865 charger without programming it. */
#include <linux/bitops.h>
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/power_supply.h>
#include <linux/slab.h>
#include <linux/workqueue.h>

#define MAX77865_INT_OK		0xb2
#define MAX77865_WCIN_OK	BIT(5)
#define MAX77865_CHGIN_OK	BIT(6)
#define MAX77865_POLL_INTERVAL	5000

struct g955n_charger_inputs {
	struct i2c_client *client;
	struct power_supply *wired;
	struct power_supply *wireless;
	struct delayed_work poll;
	int online;
};

static enum power_supply_property max77865_input_properties[] = {
	POWER_SUPPLY_PROP_ONLINE,
};

static int max77865_online(struct power_supply *psy,
			   enum power_supply_property prop,
			   union power_supply_propval *val)
{
	struct g955n_charger_inputs *inputs = power_supply_get_drvdata(psy);
	int state = READ_ONCE(inputs->online);

	if (prop != POWER_SUPPLY_PROP_ONLINE)
		return -EINVAL;
	if (state < 0)
		return state;

	val->intval = !!(state & (psy->desc->type == POWER_SUPPLY_TYPE_USB ?
				  MAX77865_CHGIN_OK : MAX77865_WCIN_OK));
	return 0;
}

static const struct power_supply_desc max77865_wired_desc = {
	.name = "max77865-wired",
	.type = POWER_SUPPLY_TYPE_USB,
	.properties = max77865_input_properties,
	.num_properties = ARRAY_SIZE(max77865_input_properties),
	.get_property = max77865_online,
};

static const struct power_supply_desc max77865_wireless_desc = {
	.name = "max77865-wireless",
	.type = POWER_SUPPLY_TYPE_WIRELESS,
	.properties = max77865_input_properties,
	.num_properties = ARRAY_SIZE(max77865_input_properties),
	.get_property = max77865_online,
};

static int max77865_read_inputs(struct i2c_client *client)
{
	int value = i2c_smbus_read_byte_data(client, MAX77865_INT_OK);

	return value < 0 ? value : value & (MAX77865_CHGIN_OK | MAX77865_WCIN_OK);
}

static void max77865_poll_inputs(struct work_struct *work)
{
	struct g955n_charger_inputs *inputs =
		container_of(to_delayed_work(work), struct g955n_charger_inputs, poll);
	int value = max77865_read_inputs(inputs->client);
	int old = READ_ONCE(inputs->online);

	if (old != value) {
		WRITE_ONCE(inputs->online, value);
		power_supply_changed(inputs->wired);
		power_supply_changed(inputs->wireless);
	}
	queue_delayed_work(system_freezable_wq, &inputs->poll,
			   msecs_to_jiffies(MAX77865_POLL_INTERVAL));
}

static void max77865_stop_input_poll(void *data)
{
	struct g955n_charger_inputs *inputs = data;

	cancel_delayed_work_sync(&inputs->poll);
}

static int max77865_charger_probe(struct i2c_client *client)
{
	struct power_supply_config config = {};
	struct g955n_charger_inputs *inputs;
	int ret;

	if (!of_machine_is_compatible("samsung,dream2lteks") || client->addr != 0x69)
		return -ENODEV;
	if (!i2c_check_functionality(client->adapter, I2C_FUNC_SMBUS_BYTE_DATA))
		return -EOPNOTSUPP;

	inputs = devm_kzalloc(&client->dev, sizeof(*inputs), GFP_KERNEL);
	if (!inputs)
		return -ENOMEM;

	inputs->client = client;
	ret = max77865_read_inputs(client);
	if (ret < 0)
		return dev_err_probe(&client->dev, ret, "cannot read charger inputs\n");
	inputs->online = ret;
	config.drv_data = inputs;

	inputs->wired = devm_power_supply_register(&client->dev, &max77865_wired_desc,
						   &config);
	if (IS_ERR(inputs->wired))
		return PTR_ERR(inputs->wired);

	inputs->wireless = devm_power_supply_register(&client->dev, &max77865_wireless_desc,
						      &config);
	if (IS_ERR(inputs->wireless))
		return PTR_ERR(inputs->wireless);

	INIT_DEFERRABLE_WORK(&inputs->poll, max77865_poll_inputs);
	ret = devm_add_action_or_reset(&client->dev, max77865_stop_input_poll, inputs);
	if (ret)
		return ret;
	queue_delayed_work(system_freezable_wq, &inputs->poll,
			   msecs_to_jiffies(MAX77865_POLL_INTERVAL));
	return 0;
}

static const struct of_device_id max77865_input_of_match[] = {
	{ .compatible = "maxim,max77865-charger-inputs" },
	{ }
};
MODULE_DEVICE_TABLE(of, max77865_input_of_match);

static const struct i2c_device_id max77865_input_ids[] = {
	{ "g955n-charger-input" },
	{ }
};
MODULE_DEVICE_TABLE(i2c, max77865_input_ids);

static struct i2c_driver max77865_input_driver = {
	.driver = {
		.name = "g955n-max77865-input",
		.of_match_table = max77865_input_of_match,
	},
	.probe = max77865_charger_probe,
	.id_table = max77865_input_ids,
};
module_i2c_driver(max77865_input_driver);

MODULE_DESCRIPTION("SM-G955N MAX77865 wired and wireless supply presence");
MODULE_LICENSE("GPL");
