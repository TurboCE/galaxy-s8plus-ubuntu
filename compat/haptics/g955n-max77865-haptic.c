// SPDX-License-Identifier: GPL-2.0-only
/* MAX77865 external-PWM haptic motor on SM-G955N revision 10. */
#include <linux/i2c.h>
#include <linux/input.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/pwm.h>
#include <linux/regmap.h>
#include <linux/workqueue.h>

#define MAX77865_PMIC_ID	0x00
#define MAX77865_MAINCTRL1	0x02
#define MAX77865_MOTOR_CONFIG	0x10
#define MAX77865_BIAS_ENABLE	BIT(7)
#define MAX77865_MOTOR_LRA	BIT(7)
#define MAX77865_MOTOR_ENABLE	BIT(6)
#define MAX77865_MOTOR_INTERNAL	BIT(5)
#define MAX77865_MOTOR_DIV128	BIT(1)
#define MAX77865_MOTOR_MODE	(MAX77865_MOTOR_LRA | MAX77865_MOTOR_INTERNAL | GENMASK(1, 0))

/* Samsung's Dream2 alert waveform and maximum timed-output duration. */
#define G955N_MOTOR_PERIOD_NS	48828
#define G955N_MOTOR_FULL_NS	36621
#define G955N_MOTOR_LIMIT_MS	10000

struct g955n_haptic {
	struct device *dev;
	struct regmap *regmap;
	struct pwm_device *pwm;
	struct workqueue_struct *queue;
	struct work_struct play;
	struct delayed_work timeout;
	spinlock_t requests;
	u16 magnitude;
	unsigned int base_bias;
	unsigned int base_mode;
	bool quiesced;
	bool expired;
	bool powered;
	bool running;
};

static int g955n_haptic_pwm(struct g955n_haptic *haptic, u16 level)
{
	struct pwm_state state;
	const unsigned int midpoint = G955N_MOTOR_PERIOD_NS / 2;

	pwm_init_state(haptic->pwm, &state);
	state.period = G955N_MOTOR_PERIOD_NS;
	state.duty_cycle = midpoint + mult_frac(G955N_MOTOR_FULL_NS - midpoint, level, U16_MAX);
	state.enabled = level != 0;
	return pwm_apply_might_sleep(haptic->pwm, &state);
}

static void g955n_haptic_stop(struct g955n_haptic *haptic)
{
	int ret, pwm_error;

	cancel_delayed_work(&haptic->timeout);
	haptic->running = false;
	if (!haptic->powered)
		return;
	ret = regmap_update_bits(haptic->regmap, MAX77865_MOTOR_CONFIG,
				 MAX77865_MOTOR_ENABLE | MAX77865_MOTOR_MODE, haptic->base_mode);
	pwm_error = g955n_haptic_pwm(haptic, 0);
	if (!ret && !pwm_error)
		ret = regmap_update_bits(haptic->regmap, MAX77865_MAINCTRL1,
					 MAX77865_BIAS_ENABLE, haptic->base_bias);
	if (ret || pwm_error)
		dev_err(haptic->dev, "failed to stop haptic motor: pmic=%d pwm=%d\n",
			ret, pwm_error);
	else
		haptic->powered = false;
}

static int g955n_haptic_start(struct g955n_haptic *haptic, u16 level)
{
	int ret;

	ret = regmap_update_bits(haptic->regmap, MAX77865_MAINCTRL1,
				 MAX77865_BIAS_ENABLE, MAX77865_BIAS_ENABLE);
	if (ret)
		return ret;
	haptic->powered = true;
	ret = regmap_update_bits(haptic->regmap, MAX77865_MOTOR_CONFIG,
				 MAX77865_MOTOR_ENABLE | MAX77865_MOTOR_MODE,
				 MAX77865_MOTOR_LRA | MAX77865_MOTOR_DIV128);
	if (!ret)
		ret = g955n_haptic_pwm(haptic, level);
	if (!ret)
		ret = regmap_update_bits(haptic->regmap, MAX77865_MOTOR_CONFIG,
					 MAX77865_MOTOR_ENABLE, MAX77865_MOTOR_ENABLE);
	if (!ret) {
		haptic->running = true;
		queue_delayed_work(haptic->queue, &haptic->timeout,
				   msecs_to_jiffies(G955N_MOTOR_LIMIT_MS));
	}
	return ret;
}

static void g955n_haptic_timeout(struct work_struct *work)
{
	struct g955n_haptic *haptic = container_of(to_delayed_work(work),
						  struct g955n_haptic, timeout);
	unsigned long flags;

	spin_lock_irqsave(&haptic->requests, flags);
	haptic->expired = haptic->magnitude != 0;
	spin_unlock_irqrestore(&haptic->requests, flags);
	g955n_haptic_stop(haptic);
}

static void g955n_haptic_play(struct work_struct *work)
{
	struct g955n_haptic *haptic = container_of(work, struct g955n_haptic, play);
	unsigned long flags;
	u16 level;
	int ret;

	spin_lock_irqsave(&haptic->requests, flags);
	level = haptic->expired ? 0 : haptic->magnitude;
	spin_unlock_irqrestore(&haptic->requests, flags);
	if (!level) {
		g955n_haptic_stop(haptic);
		return;
	}

	if (haptic->powered && !haptic->running) {
		g955n_haptic_stop(haptic);
		if (haptic->powered)
			return;
	}
	ret = haptic->running ? g955n_haptic_pwm(haptic, level) :
			       g955n_haptic_start(haptic, level);
	if (ret) {
		dev_err(haptic->dev, "failed to play haptic effect: %d\n", ret);
		g955n_haptic_stop(haptic);
	}
}

static int g955n_haptic_effect(struct input_dev *input, void *data, struct ff_effect *effect)
{
	struct g955n_haptic *haptic = input_get_drvdata(input);
	unsigned long flags;
	u16 level = max(effect->u.rumble.strong_magnitude, effect->u.rumble.weak_magnitude);

	spin_lock_irqsave(&haptic->requests, flags);
	if (!haptic->quiesced) {
		haptic->magnitude = level;
		if (!level)
			haptic->expired = false;
		queue_work(haptic->queue, &haptic->play);
	}
	spin_unlock_irqrestore(&haptic->requests, flags);
	return 0;
}

static void g955n_haptic_quiesce(struct g955n_haptic *haptic)
{
	unsigned long flags;

	spin_lock_irqsave(&haptic->requests, flags);
	haptic->quiesced = true;
	haptic->magnitude = 0;
	haptic->expired = false;
	spin_unlock_irqrestore(&haptic->requests, flags);
	cancel_work_sync(&haptic->play);
	cancel_delayed_work_sync(&haptic->timeout);
	g955n_haptic_stop(haptic);
}

static int g955n_haptic_resume(struct device *dev)
{
	struct g955n_haptic *haptic = dev_get_drvdata(dev);
	unsigned long flags;

	spin_lock_irqsave(&haptic->requests, flags);
	haptic->quiesced = false;
	spin_unlock_irqrestore(&haptic->requests, flags);
	return 0;
}

static int g955n_haptic_suspend(struct device *dev)
{
	struct g955n_haptic *haptic = dev_get_drvdata(dev);

	g955n_haptic_quiesce(haptic);
	if (haptic->powered) {
		g955n_haptic_resume(dev);
		return -EIO;
	}
	return 0;
}
static DEFINE_SIMPLE_DEV_PM_OPS(g955n_haptic_pm, g955n_haptic_suspend, g955n_haptic_resume);

static void g955n_haptic_release(void *data)
{
	struct g955n_haptic *haptic = data;

	g955n_haptic_quiesce(haptic);
	destroy_workqueue(haptic->queue);
}

static int g955n_haptic_probe(struct i2c_client *client)
{
	static const struct regmap_config config = {
		.reg_bits = 8,
		.val_bits = 8,
		.max_register = MAX77865_MOTOR_CONFIG,
	};
	struct device *dev = &client->dev;
	struct g955n_haptic *haptic;
	struct input_dev *input;
	unsigned int id, motor, bias;
	int ret;

	if (!of_machine_is_compatible("samsung,dream2lteks"))
		return -ENODEV;
	haptic = devm_kzalloc(dev, sizeof(*haptic), GFP_KERNEL);
	if (!haptic)
		return -ENOMEM;
	haptic->dev = dev;
	haptic->regmap = devm_regmap_init_i2c(client, &config);
	if (IS_ERR(haptic->regmap))
		return PTR_ERR(haptic->regmap);
	ret = regmap_read(haptic->regmap, MAX77865_PMIC_ID, &id);
	if (ret)
		return ret;
	if (id != 0x65)
		return -ENODEV;

	haptic->pwm = devm_pwm_get(dev, NULL);
	if (IS_ERR(haptic->pwm))
		return dev_err_probe(dev, PTR_ERR(haptic->pwm), "PWM unavailable\n");
	ret = regmap_read(haptic->regmap, MAX77865_MOTOR_CONFIG, &motor);
	if (ret)
		return ret;
	if (motor & MAX77865_MOTOR_ENABLE)
		return -EBUSY;
	ret = regmap_read(haptic->regmap, MAX77865_MAINCTRL1, &bias);
	if (ret)
		return ret;
	haptic->base_mode = motor & MAX77865_MOTOR_MODE;
	haptic->base_bias = bias & MAX77865_BIAS_ENABLE;
	spin_lock_init(&haptic->requests);
	INIT_WORK(&haptic->play, g955n_haptic_play);
	INIT_DELAYED_WORK(&haptic->timeout, g955n_haptic_timeout);
	haptic->queue = alloc_ordered_workqueue("g955n-haptic", 0);
	if (!haptic->queue)
		return -ENOMEM;
	ret = devm_add_action_or_reset(dev, g955n_haptic_release, haptic);
	if (ret)
		return ret;

	input = devm_input_allocate_device(dev);
	if (!input)
		return -ENOMEM;
	input->name = "SM-G955N Haptics";
	input->id.bustype = BUS_I2C;
	input_set_drvdata(input, haptic);
	input_set_capability(input, EV_FF, FF_RUMBLE);
	ret = input_ff_create_memless(input, NULL, g955n_haptic_effect);
	if (ret)
		return ret;
	i2c_set_clientdata(client, haptic);
	return input_register_device(input);
}

static void g955n_haptic_shutdown(struct i2c_client *client)
{
	g955n_haptic_quiesce(i2c_get_clientdata(client));
}

static const struct of_device_id g955n_haptic_match[] = {
	{ .compatible = "samsung,sm-g955n-max77865-haptic" },
	{}
};
MODULE_DEVICE_TABLE(of, g955n_haptic_match);

static struct i2c_driver g955n_haptic_driver = {
	.driver = {
		.name = "g955n-max77865-haptic",
		.of_match_table = g955n_haptic_match,
		.pm = pm_sleep_ptr(&g955n_haptic_pm),
	},
	.probe = g955n_haptic_probe,
	.shutdown = g955n_haptic_shutdown,
};
module_i2c_driver(g955n_haptic_driver);

MODULE_DESCRIPTION("SM-G955N MAX77865 force-feedback haptics");
MODULE_LICENSE("GPL");
