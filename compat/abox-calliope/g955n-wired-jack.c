// SPDX-License-Identifier: GPL-2.0-only
/* Samsung dream2lte JD1/JD2 clamp detection through the standard ALSA jack. */
#include <linux/interrupt.h>
#include <linux/mfd/madera/core.h>
#include <linux/irqchip/irq-madera.h>
#include <linux/mfd/madera/registers.h>
#include <linux/of.h>
#include <linux/pm_runtime.h>
#include <linux/property.h>
#include <linux/slab.h>
#include <linux/workqueue.h>
#include <sound/jack.h>
#include <sound/soc.h>

#include "g955n-wired-jack.h"

#define G955N_JD_CLAMP_MODE	0x8
#define G955N_JD_DEBOUNCE_MS	300

static const struct g955n_jack_reg {
	unsigned int reg;
	unsigned int mask;
	unsigned int enable;
} g955n_jack_regs[] = {
	{ MADERA_MICD_CLAMP_CONTROL, MADERA_MICD_CLAMP_MODE_MASK, G955N_JD_CLAMP_MODE },
	{ MADERA_INTERRUPT_DEBOUNCE_7, MADERA_MICD_CLAMP_DB | MADERA_JD1_DB | MADERA_JD2_DB,
	  MADERA_MICD_CLAMP_DB | MADERA_JD1_DB | MADERA_JD2_DB },
	{ MADERA_JACK_DETECT_ANALOGUE, MADERA_JD1_ENA | MADERA_JD2_ENA,
	  MADERA_JD1_ENA | MADERA_JD2_ENA },
};

struct g955n_wired_jack {
	struct device *dev;
	struct madera *madera;
	struct snd_soc_jack jack;
	struct delayed_work report_work;
	unsigned int saved[ARRAY_SIZE(g955n_jack_regs)];
	bool active;
};

static void g955n_wired_jack_schedule(struct g955n_wired_jack *jack)
{
	mod_delayed_work(system_freezable_wq, &jack->report_work,
			 msecs_to_jiffies(G955N_JD_DEBOUNCE_MS));
}

static irqreturn_t g955n_wired_jack_irq(int irq, void *data)
{
	struct g955n_wired_jack *jack = data;

	if (READ_ONCE(jack->active))
		g955n_wired_jack_schedule(jack);
	return IRQ_HANDLED;
}

static void g955n_wired_jack_report(struct work_struct *work)
{
	struct g955n_wired_jack *jack = container_of(to_delayed_work(work),
						    struct g955n_wired_jack, report_work);
	struct madera *madera = jack->madera;
	unsigned int raw;
	int ret;

	ret = pm_runtime_resume_and_get(madera->dev);
	if (ret < 0)
		return;
	ret = regmap_read(madera->regmap, MADERA_IRQ1_RAW_STATUS_7, &raw);
	pm_runtime_put_autosuspend(madera->dev);
	if (ret) {
		dev_warn_ratelimited(jack->dev, "wired jack status read failed: %d\n", ret);
		return;
	}

	/* Use the stock active-low clamp polarity. Ignore ambiguous samples. */
	raw &= MADERA_MICD_CLAMP_RISE_STS1 | MADERA_MICD_CLAMP_FALL_STS1;
	if (raw == MADERA_MICD_CLAMP_FALL_STS1)
		snd_soc_jack_report(&jack->jack, SND_JACK_HEADPHONE, SND_JACK_HEADPHONE);
	else if (raw == MADERA_MICD_CLAMP_RISE_STS1)
		snd_soc_jack_report(&jack->jack, 0, SND_JACK_HEADPHONE);
}

static void g955n_wired_jack_restore(struct g955n_wired_jack *jack, unsigned int count)
{
	int ret;

	while (count) {
		const struct g955n_jack_reg *setting = &g955n_jack_regs[--count];

		ret = regmap_update_bits(jack->madera->regmap, setting->reg,
					 setting->mask, jack->saved[count]);
		if (ret)
			dev_warn(jack->dev, "wired jack restore %#x: %d\n", setting->reg, ret);
	}
}

struct g955n_wired_jack *g955n_wired_jack_init(struct snd_soc_pcm_runtime *rtd)
{
	struct snd_soc_component *codec = snd_soc_rtd_to_codec(rtd, 0)->component;
	struct device *dev = rtd->card->dev;
	struct g955n_wired_jack *jack;
	struct madera *madera;
	unsigned int count = 0;
	int ret;

	if (!device_property_read_bool(dev, "samsung,wired-jack-detect"))
		return NULL;
	if (!of_machine_is_compatible("samsung,dream2lteks") || !codec->dev->parent ||
	    !of_device_is_compatible(codec->dev->parent->of_node, "cirrus,cs47l93"))
		return ERR_PTR(-ENODEV);
	madera = dev_get_drvdata(codec->dev->parent);
	if (!madera || madera->type != CS47L93 || !madera->irq_data)
		return ERR_PTR(-ENODEV);

	jack = devm_kzalloc(dev, sizeof(*jack), GFP_KERNEL);
	if (!jack)
		return ERR_PTR(-ENOMEM);
	jack->madera = madera;
	jack->dev = dev;
	INIT_DELAYED_WORK(&jack->report_work, g955n_wired_jack_report);

	ret = pm_runtime_resume_and_get(madera->dev);
	if (ret < 0)
		goto free;
	while (count < ARRAY_SIZE(g955n_jack_regs)) {
		const struct g955n_jack_reg *setting = &g955n_jack_regs[count];

		ret = regmap_read(madera->regmap, setting->reg, &jack->saved[count]);
		if (ret)
			goto restore;
		count++;
		ret = regmap_update_bits(madera->regmap, setting->reg,
					 setting->mask, setting->enable);
		if (ret)
			goto restore;
	}

	ret = madera_request_irq(madera, MADERA_IRQ_MICD_CLAMP_RISE, "G955N jack rise",
				 g955n_wired_jack_irq, jack);
	if (ret)
		goto restore;
	ret = madera_request_irq(madera, MADERA_IRQ_MICD_CLAMP_FALL, "G955N jack fall",
				 g955n_wired_jack_irq, jack);
	if (ret)
		goto free_rise;
	ret = snd_soc_card_jack_new(rtd->card, "Headphone Jack", SND_JACK_HEADPHONE, &jack->jack);
	if (ret)
		goto free_fall;
	WRITE_ONCE(jack->active, true);
	g955n_wired_jack_schedule(jack);
	pm_runtime_put_autosuspend(madera->dev);
	return jack;

free_fall:
	madera_free_irq(madera, MADERA_IRQ_MICD_CLAMP_FALL, jack);
free_rise:
	madera_free_irq(madera, MADERA_IRQ_MICD_CLAMP_RISE, jack);
restore:
	g955n_wired_jack_restore(jack, count);
	pm_runtime_put_autosuspend(madera->dev);
free:
	devm_kfree(dev, jack);
	return ERR_PTR(ret);
}

void g955n_wired_jack_exit(struct g955n_wired_jack *jack)
{
	struct madera *madera;
	int ret;

	if (!jack)
		return;
	madera = jack->madera;
	WRITE_ONCE(jack->active, false);
	madera_free_irq(madera, MADERA_IRQ_MICD_CLAMP_FALL, jack);
	madera_free_irq(madera, MADERA_IRQ_MICD_CLAMP_RISE, jack);
	cancel_delayed_work_sync(&jack->report_work);

	ret = pm_runtime_resume_and_get(madera->dev);
	if (ret < 0) {
		dev_warn(jack->dev, "wired jack restore: codec unavailable: %d\n", ret);
	} else {
		g955n_wired_jack_restore(jack, ARRAY_SIZE(g955n_jack_regs));
		pm_runtime_put_autosuspend(madera->dev);
	}
	devm_kfree(jack->dev, jack);
}
