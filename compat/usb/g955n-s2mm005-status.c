// SPDX-License-Identifier: GPL-2.0-only
/* Read the Samsung S2MM005 Type-C firmware status on the Korean SM-G955N. */
#include <linux/bitfield.h>
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/unaligned.h>
#include <linux/usb/typec.h>
#include <linux/workqueue.h>

#define S2MM005_FUNC_STATE	0x0020
#define S2MM005_LP_STATE	0x0060
#define S2MM005_PD_STATE	GENMASK(7, 0)
#define S2MM005_ATTACH_DONE	BIT(24)
#define S2MM005_IS_SOURCE	BIT(25)
#define S2MM005_IS_DFP		BIT(26)
#define S2MM005_VBUS_CC_SHORT	BIT(29)
#define S2MM005_VBUS_SBU_SHORT	BIT(30)
#define S2MM005_WATER_DET	BIT(3)
#define S2MM005_RUN_DRY		BIT(5)

static int s2mm005_read_state(struct i2c_client *client, u16 reg, u32 *value)
{
	u8 address[2], data[sizeof(*value)];
	struct i2c_msg messages[] = {
		{ .addr = client->addr, .len = sizeof(address), .buf = address },
		{ .addr = client->addr, .flags = I2C_M_RD, .len = sizeof(data), .buf = data },
	};
	int ret;

	/* The register address is big-endian and the firmware word is little-endian. */
	put_unaligned_be16(reg, address);
	ret = i2c_transfer(client->adapter, messages, ARRAY_SIZE(messages));
	if (ret != ARRAY_SIZE(messages))
		return ret < 0 ? ret : -EIO;

	*value = get_unaligned_le32(data);
	return 0;
}

static ssize_t port_status_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct i2c_client *client = to_i2c_client(dev);
	u32 state, low_power;
	int ret;

	ret = s2mm005_read_state(client, S2MM005_FUNC_STATE, &state);
	if (ret)
		return ret;
	ret = s2mm005_read_state(client, S2MM005_LP_STATE, &low_power);
	if (ret)
		return ret;

	return sysfs_emit(buf,
			  "pd_state=%u attached=%u source=%u dfp=%u water=%u dry=%u vbus_cc_short=%u vbus_sbu_short=%u\n",
			  (unsigned int)FIELD_GET(S2MM005_PD_STATE, state),
			  !!(state & S2MM005_ATTACH_DONE), !!(state & S2MM005_IS_SOURCE),
			  !!(state & S2MM005_IS_DFP), !!(low_power & S2MM005_WATER_DET),
			  !!(low_power & S2MM005_RUN_DRY), !!(state & S2MM005_VBUS_CC_SHORT),
			  !!(state & S2MM005_VBUS_SBU_SHORT));
}
static DEVICE_ATTR_RO(port_status);

static struct attribute *s2mm005_status_attrs[] = {
	&dev_attr_port_status.attr,
	NULL,
};
ATTRIBUTE_GROUPS(s2mm005_status);

#if IS_REACHABLE(CONFIG_TYPEC)
struct s2mm005_typec {
	struct i2c_client *client;
	struct delayed_work refresh;
	struct typec_port *port;
	struct typec_partner *partner;
};

static void s2mm005_report_typec(struct s2mm005_typec *status, u32 state)
{
	struct typec_partner_desc desc = { .accessory = TYPEC_ACCESSORY_NONE };
	struct typec_partner *partner;

	if (!(state & S2MM005_ATTACH_DONE) || !(state & S2MM005_PD_STATE)) {
		typec_unregister_partner(status->partner);
		status->partner = NULL;
		return;
	}

	typec_set_data_role(status->port, state & S2MM005_IS_DFP ? TYPEC_HOST : TYPEC_DEVICE);
	typec_set_pwr_role(status->port, state & S2MM005_IS_SOURCE ? TYPEC_SOURCE : TYPEC_SINK);
	if (status->partner)
		return;

	partner = typec_register_partner(status->port, &desc);
	if (IS_ERR(partner))
		dev_warn_ratelimited(&status->client->dev, "cannot report Type-C partner: %pe\n",
				     partner);
	else
		status->partner = partner;
}

static void s2mm005_refresh_typec(struct work_struct *work)
{
	struct s2mm005_typec *status = container_of(to_delayed_work(work),
						   struct s2mm005_typec, refresh);
	u32 state;

	if (!s2mm005_read_state(status->client, S2MM005_FUNC_STATE, &state))
		s2mm005_report_typec(status, state);
	queue_delayed_work(system_freezable_wq, &status->refresh,
			   round_jiffies_relative(2 * HZ));
}

static void s2mm005_unregister_typec(void *data)
{
	struct s2mm005_typec *status = data;

	cancel_delayed_work_sync(&status->refresh);
	typec_unregister_partner(status->partner);
	typec_unregister_port(status->port);
}

static int s2mm005_register_typec(struct i2c_client *client, u32 state)
{
	const struct typec_capability cap = {
		.type = TYPEC_PORT_DRP,
		.data = TYPEC_PORT_DRD,
		.prefer_role = TYPEC_NO_PREFERRED_ROLE,
	};
	struct device *dev = &client->dev;
	struct s2mm005_typec *status;
	int ret;

	status = devm_kzalloc(dev, sizeof(*status), GFP_KERNEL);
	if (!status)
		return -ENOMEM;

	status->client = client;
	INIT_DELAYED_WORK(&status->refresh, s2mm005_refresh_typec);
	status->port = typec_register_port(dev, &cap);
	if (IS_ERR(status->port))
		return dev_err_probe(dev, PTR_ERR(status->port), "cannot register Type-C port\n");

	ret = devm_add_action_or_reset(dev, s2mm005_unregister_typec, status);
	if (ret)
		return ret;

	s2mm005_report_typec(status, state);
	queue_delayed_work(system_freezable_wq, &status->refresh,
			   round_jiffies_relative(2 * HZ));
	return 0;
}
#else
static int s2mm005_register_typec(struct i2c_client *client, u32 state)
{
	return 0;
}
#endif

static int s2mm005_status_probe(struct i2c_client *client)
{
	u32 state;
	int ret;

	if (!of_machine_is_compatible("samsung,dream2lteks") || client->addr != 0x33 ||
	    !i2c_check_functionality(client->adapter, I2C_FUNC_I2C))
		return -ENODEV;

	ret = s2mm005_read_state(client, S2MM005_FUNC_STATE, &state);
	if (ret)
		return dev_err_probe(&client->dev, ret, "cannot read Type-C firmware state\n");

	return s2mm005_register_typec(client, state);
}

static const struct of_device_id s2mm005_status_of_match[] = {
	{ .compatible = "samsung,sm-g955n-s2mm005-status" },
	{ }
};
MODULE_DEVICE_TABLE(of, s2mm005_status_of_match);

static struct i2c_driver s2mm005_status_driver = {
	.driver = {
		.name = "g955n-s2mm005-status",
		.of_match_table = s2mm005_status_of_match,
		.dev_groups = s2mm005_status_groups,
	},
	.probe = s2mm005_status_probe,
};
module_i2c_driver(s2mm005_status_driver);

MODULE_DESCRIPTION("SM-G955N S2MM005 read-only Type-C status");
MODULE_LICENSE("GPL");
