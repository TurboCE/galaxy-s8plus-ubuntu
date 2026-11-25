// SPDX-License-Identifier: GPL-2.0-only
/* Report MAX77865 input presence and charge state without programming it. */
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
#define MAX77865_DETAILS_01	0xb4
#define MAX77865_CHG_DETAILS	GENMASK(3, 0)
#define MAX77865_POLL_INTERVAL	5000

struct g955n_charger_inputs {
	struct i2c_client *client;
	struct power_supply *wired;
	struct power_supply *wireless;
	struct delayed_work poll;
	int online;
	int status;
};

static char *max77865_supplied_to[] = { "max77865-battery" };

static enum power_supply_property max77865_input_properties[] = {
	POWER_SUPPLY_PROP_ONLINE,
	POWER_SUPPLY_PROP_STATUS,
};

static int max77865_input_get_property(struct power_supply *psy,
				       enum power_supply_property prop,
				       union power_supply_propval *val)
{
	struct g955n_charger_inputs *inputs = power_supply_get_drvdata(psy);
	int state = READ_ONCE(inputs->online);
	int input = psy->desc->type == POWER_SUPPLY_TYPE_USB ?
		    MAX77865_CHGIN_OK : MAX77865_WCIN_OK;

	if (state < 0)
		return state;

	switch (prop) {
	case POWER_SUPPLY_PROP_ONLINE:
		val->intval = !!(state & input);
		return 0;
	case POWER_SUPPLY_PROP_STATUS:
		/* The wired and wireless inputs share one charge controller. */
		if (state && !(state & input))
			return -ENODATA;
		val->intval = READ_ONCE(inputs->status);
		return 0;
	default:
		return -EINVAL;
	}
}

static const struct power_supply_desc max77865_wired_desc = {
	.name = "max77865-wired",
	.type = POWER_SUPPLY_TYPE_USB,
	.properties = max77865_input_properties,
	.num_properties = ARRAY_SIZE(max77865_input_properties),
	.get_property = max77865_input_get_property,
};

static const struct power_supply_desc max77865_wireless_desc = {
	.name = "max77865-wireless",
	.type = POWER_SUPPLY_TYPE_WIRELESS,
	.properties = max77865_input_properties,
	.num_properties = ARRAY_SIZE(max77865_input_properties),
	.get_property = max77865_input_get_property,
};

static int max77865_read_inputs(struct i2c_client *client)
{
	int value = i2c_smbus_read_byte_data(client, MAX77865_INT_OK);

	return value < 0 ? value : value & (MAX77865_CHGIN_OK | MAX77865_WCIN_OK);
}

static int max77865_read_charge_status(struct i2c_client *client)
{
	int details = i2c_smbus_read_byte_data(client, MAX77865_DETAILS_01);

	if (details < 0)
		return POWER_SUPPLY_STATUS_UNKNOWN;
	switch (details & MAX77865_CHG_DETAILS) {
	case 0x0:
	case 0x1:
	case 0x2:
		return POWER_SUPPLY_STATUS_CHARGING;
	case 0x3:
	case 0x4:
		return POWER_SUPPLY_STATUS_FULL;
	case 0x5:
	case 0x6:
	case 0x7:
		return POWER_SUPPLY_STATUS_NOT_CHARGING;
	case 0x8:
	case 0xa:
	case 0xb:
		return POWER_SUPPLY_STATUS_DISCHARGING;
	default:
		return POWER_SUPPLY_STATUS_UNKNOWN;
	}
}

static void max77865_poll_inputs(struct work_struct *work)
{
	struct g955n_charger_inputs *inputs =
		container_of(to_delayed_work(work), struct g955n_charger_inputs, poll);
	int value = max77865_read_inputs(inputs->client);
	int old = READ_ONCE(inputs->online);
	int status = max77865_read_charge_status(inputs->client);

	if (old != value || READ_ONCE(inputs->status) != status) {
		WRITE_ONCE(inputs->online, value);
		WRITE_ONCE(inputs->status, status);
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
	struct power_supply_config config = {
		.supplied_to = max77865_supplied_to,
		.num_supplicants = ARRAY_SIZE(max77865_supplied_to),
	};
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
	inputs->status = max77865_read_charge_status(client);
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

MODULE_DESCRIPTION("SM-G955N MAX77865 wired and wireless charger telemetry");
MODULE_LICENSE("GPL");
