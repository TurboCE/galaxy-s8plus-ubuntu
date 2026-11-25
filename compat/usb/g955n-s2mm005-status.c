// SPDX-License-Identifier: GPL-2.0-only
/* Read the Samsung S2MM005 Type-C firmware status on the Korean SM-G955N. */
#include <linux/bitfield.h>
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/property.h>
#include <linux/regulator/consumer.h>
#include <linux/unaligned.h>
#include <linux/usb/role.h>
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
	struct usb_role_switch *role_switch;
	struct regulator *vbus;
	enum usb_role applied_role;
	bool vbus_enabled;
};

static bool s2mm005_host_attached(u32 state, u32 low_power)
{
	const u32 host = S2MM005_ATTACH_DONE | S2MM005_IS_SOURCE | S2MM005_IS_DFP;

	return (state & host) == host && (state & S2MM005_PD_STATE) &&
	       !(state & (S2MM005_VBUS_CC_SHORT | S2MM005_VBUS_SBU_SHORT)) &&
	       (low_power & S2MM005_RUN_DRY) && !(low_power & S2MM005_WATER_DET);
}

static int s2mm005_set_controller_role(struct s2mm005_typec *status, enum usb_role role)
{
	u32 state, low_power;
	int ret;

	if (!status->role_switch)
		return 0;

	if (role != USB_ROLE_HOST && status->vbus_enabled) {
		ret = regulator_disable(status->vbus);
		if (ret)
			return ret;
		status->vbus_enabled = false;
	}

	if (role == USB_ROLE_HOST && !status->vbus_enabled) {
		ret = regulator_enable(status->vbus);
		if (ret)
			return ret;
		status->vbus_enabled = true;

		/* A partner can detach while the regulator is starting. */
		ret = s2mm005_read_state(status->client, S2MM005_FUNC_STATE, &state);
		ret = ret ?: s2mm005_read_state(status->client, S2MM005_LP_STATE, &low_power);
		if (ret || !s2mm005_host_attached(state, low_power)) {
			ret = ret ?: -ENOTCONN;
			goto disable_vbus;
		}
	}

	if (status->applied_role == role)
		return 0;

	ret = usb_role_switch_set_role(status->role_switch, role);
	if (ret)
		goto disable_vbus;

	status->applied_role = role;
	dev_dbg(&status->client->dev, "requested controller USB role %s\n", usb_role_string(role));
	return 0;

disable_vbus:
	if (status->vbus_enabled && !regulator_disable(status->vbus))
		status->vbus_enabled = false;
	return ret;
}

static void s2mm005_sync_controller(struct s2mm005_typec *status, u32 state)
{
	enum usb_role role = USB_ROLE_NONE;
	u32 low_power;
	int ret;

	if ((state & S2MM005_ATTACH_DONE) && (state & S2MM005_PD_STATE) &&
	    !(state & S2MM005_IS_DFP)) {
		role = USB_ROLE_DEVICE;
	} else if (status->vbus && (state & S2MM005_IS_DFP) &&
		   !s2mm005_read_state(status->client, S2MM005_LP_STATE, &low_power) &&
		   s2mm005_host_attached(state, low_power)) {
		role = USB_ROLE_HOST;
	}

	ret = s2mm005_set_controller_role(status, role);
	if (ret)
		dev_warn_ratelimited(&status->client->dev, "cannot update controller USB role: %d\n",
				     ret);
}

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

	if (!s2mm005_read_state(status->client, S2MM005_FUNC_STATE, &state)) {
		s2mm005_report_typec(status, state);
		s2mm005_sync_controller(status, state);
	} else if (status->vbus_enabled) {
		s2mm005_sync_controller(status, 0);
	}
	queue_delayed_work(system_freezable_wq, &status->refresh,
			   round_jiffies_relative(2 * HZ));
}

static void s2mm005_unregister_typec(void *data)
{
	struct s2mm005_typec *status = data;

	cancel_delayed_work_sync(&status->refresh);
	s2mm005_sync_controller(status, 0);
	usb_role_switch_put(status->role_switch);
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
	if (device_property_present(dev, "vbus-supply")) {
		status->vbus = devm_regulator_get_optional(dev, "vbus");
		if (IS_ERR(status->vbus))
			return dev_err_probe(dev, PTR_ERR(status->vbus), "cannot get VBUS supply\n");
	}

	status->role_switch = usb_role_switch_get(dev);
	if (IS_ERR(status->role_switch))
		return dev_err_probe(dev, PTR_ERR(status->role_switch), "cannot get USB role switch\n");

	INIT_DELAYED_WORK(&status->refresh, s2mm005_refresh_typec);
	status->port = typec_register_port(dev, &cap);
	if (IS_ERR(status->port)) {
		usb_role_switch_put(status->role_switch);
		return dev_err_probe(dev, PTR_ERR(status->port), "cannot register Type-C port\n");
	}

	ret = devm_add_action_or_reset(dev, s2mm005_unregister_typec, status);
	if (ret)
		return ret;

	s2mm005_report_typec(status, state);
	s2mm005_sync_controller(status, state);
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
