// SPDX-License-Identifier: GPL-2.0-only
/* Samsung dream2lte JD1/JD2 clamp detection through the standard ALSA jack. */
#include <linux/bitfield.h>
#include <linux/completion.h>
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
#define G955N_MICD_TIMEOUT_MS	1000
#define CS47L93_MICBIAS_SOFT_START	BIT(3)
#define CS47L93_MICBIAS_BYPASS	BIT(1)
/* The stock table ends at ADC code 64 (30 kOhm). Lower codes are <= 1257 Ohm. */
#define G955N_MICD_HEADSET_CODE	64

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
	struct snd_soc_dapm_context *dapm;
	struct snd_soc_jack jack;
	struct snd_soc_jack mic_jack;
	struct delayed_work report_work;
	struct completion micd_done;
	unsigned int saved[ARRAY_SIZE(g955n_jack_regs)];
	bool active;
	bool mic_detect;
	bool measuring_mic;
	bool inserted;
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

static irqreturn_t g955n_wired_mic_irq(int irq, void *data)
{
	struct g955n_wired_jack *jack = data;

	if (READ_ONCE(jack->measuring_mic))
		complete(&jack->micd_done);
	return IRQ_HANDLED;
}

static int g955n_wired_mic_measure(struct g955n_wired_jack *jack)
{
	const unsigned int ctl0_mask = MADERA_MICD1_ADC_MODE_MASK |
				      MADERA_MICD1_SENSE_MASK | MADERA_MICD1_GND_MASK;
	const unsigned int ctl1_mask = MADERA_MICD_ENA | MADERA_MICD_BIAS_STARTTIME_MASK |
				      MADERA_MICD_RATE_MASK | MADERA_MICD_BIAS_SRC_MASK |
				      MADERA_MICD_DBTIME_MASK;
	const unsigned int ctl1_setup = FIELD_PREP(MADERA_MICD_BIAS_STARTTIME_MASK, 1) |
				       FIELD_PREP(MADERA_MICD_RATE_MASK, 7) |
				       FIELD_PREP(MADERA_MICD_BIAS_SRC_MASK, 4) |
				       MADERA_MICD_DBTIME_MASK;
	const unsigned int bias_mask = MADERA_MICB1_LVL_MASK | MADERA_MICB1_EXT_CAP |
				       CS47L93_MICBIAS_SOFT_START | CS47L93_MICBIAS_BYPASS;
	struct regmap *map = jack->madera->regmap;
	unsigned int ctl0, ctl1, bias, enabled, clamp, value;
	int pin, ret, restore;
	bool bias_forced = false;

	ret = regmap_read(map, MADERA_MIC_DETECT_1_CONTROL_0, &ctl0);
	ret = ret ?: regmap_read(map, MADERA_MIC_DETECT_1_CONTROL_1, &ctl1);
	ret = ret ?: regmap_read(map, MADERA_MIC_BIAS_CTRL_2, &bias);
	ret = ret ?: regmap_read(map, MADERA_MIC_BIAS_CTRL_6, &enabled);
	ret = ret ?: regmap_read(map, MADERA_MICD_CLAMP_CONTROL, &clamp);
	if (ret)
		return ret;
	if ((ctl1 & MADERA_MICD_ENA) || (enabled & MADERA_MICB2A_ENA))
		return -EBUSY;
	pin = snd_soc_dapm_get_pin_status(jack->dapm, "MICBIAS2A");
	if (pin < 0)
		return pin;

	/* Samsung uses MICDET1, ground selector 1 and MICBIAS2A on this board. */
	ret = regmap_update_bits(map, MADERA_MIC_BIAS_CTRL_2, bias_mask,
				 FIELD_PREP(MADERA_MICB1_LVL_MASK, 13) | CS47L93_MICBIAS_SOFT_START);
	ret = ret ?: regmap_update_bits(map, MADERA_MICD_CLAMP_CONTROL, MADERA_MICD_CLAMP_OVD, 0);
	ret = ret ?: regmap_update_bits(map, MADERA_MIC_DETECT_1_CONTROL_0, ctl0_mask,
					MADERA_MICD1_ADC_MODE_MASK |
					FIELD_PREP(MADERA_MICD1_GND_MASK, 1));
	if (ret)
		goto restore;
	ret = snd_soc_dapm_force_enable_pin(jack->dapm, "MICBIAS2A");
	if (ret)
		goto restore;
	bias_forced = true;
	ret = snd_soc_dapm_sync(jack->dapm);
	if (ret)
		goto restore;

	reinit_completion(&jack->micd_done);
	WRITE_ONCE(jack->measuring_mic, true);
	ret = regmap_update_bits(map, MADERA_MIC_DETECT_1_CONTROL_1, ctl1_mask,
				 ctl1_setup | MADERA_MICD_ENA);
	if (ret)
		goto restore;
	if (!wait_for_completion_timeout(&jack->micd_done,
					 msecs_to_jiffies(G955N_MICD_TIMEOUT_MS))) {
		ret = -ETIMEDOUT;
		goto restore;
	}
	/* The hardware latches ADCVAL only once MICD is disabled. */
	ret = regmap_update_bits(map, MADERA_MIC_DETECT_1_CONTROL_1, MADERA_MICD_ENA, 0);
	ret = ret ?: regmap_read(map, MADERA_MIC_DETECT_1_CONTROL_4, &value);
	if (!ret)
		ret = (value & MADERA_MICDET_ADCVAL_MASK) == G955N_MICD_HEADSET_CODE;

restore:
	WRITE_ONCE(jack->measuring_mic, false);
	restore = regmap_update_bits(map, MADERA_MIC_DETECT_1_CONTROL_1, ctl1_mask, ctl1);
	if (bias_forced) {
		restore |= snd_soc_dapm_disable_pin(jack->dapm, "MICBIAS2A");
		if (pin)
			restore |= snd_soc_dapm_enable_pin(jack->dapm, "MICBIAS2A");
		restore |= snd_soc_dapm_sync(jack->dapm);
	}
	restore |= regmap_update_bits(map, MADERA_MIC_BIAS_CTRL_2, bias_mask, bias);
	restore |= regmap_update_bits(map, MADERA_MIC_DETECT_1_CONTROL_0, ctl0_mask, ctl0);
	restore |= regmap_update_bits(map, MADERA_MICD_CLAMP_CONTROL, MADERA_MICD_CLAMP_OVD, clamp);
	if (restore) {
		dev_warn_ratelimited(jack->dev, "wired mic detection rollback failed\n");
		return -EIO;
	}
	return ret;
}

static void g955n_wired_jack_report(struct work_struct *work)
{
	struct g955n_wired_jack *jack = container_of(to_delayed_work(work),
						    struct g955n_wired_jack, report_work);
	struct madera *madera = jack->madera;
	const unsigned int clamp_status = MADERA_MICD_CLAMP_RISE_STS1 | MADERA_MICD_CLAMP_FALL_STS1;
	unsigned int raw;
	int ret, mic = 0;

	ret = pm_runtime_resume_and_get(madera->dev);
	if (ret < 0)
		return;
	ret = regmap_read(madera->regmap, MADERA_IRQ1_RAW_STATUS_7, &raw);
	if (ret) {
		dev_warn_ratelimited(jack->dev, "wired jack status read failed: %d\n", ret);
		goto put;
	}

	/* Use the stock active-low clamp polarity. Ignore ambiguous samples. */
	raw &= clamp_status;
	if (raw == MADERA_MICD_CLAMP_FALL_STS1 && !jack->inserted) {
		if (jack->mic_detect) {
			mic = g955n_wired_mic_measure(jack);
			if (mic < 0)
				dev_dbg(jack->dev, "wired mic detection did not complete: %d\n", mic);
			ret = regmap_read(madera->regmap, MADERA_IRQ1_RAW_STATUS_7, &raw);
			if (ret || (raw & clamp_status) != MADERA_MICD_CLAMP_FALL_STS1)
				goto put;
			snd_soc_jack_report(&jack->mic_jack, mic > 0 ? SND_JACK_MICROPHONE : 0,
					    SND_JACK_MICROPHONE);
		}
		jack->inserted = true;
		snd_soc_jack_report(&jack->jack, SND_JACK_HEADPHONE, SND_JACK_HEADPHONE);
	} else if (raw == MADERA_MICD_CLAMP_RISE_STS1 && jack->inserted) {
		jack->inserted = false;
		if (jack->mic_detect)
			snd_soc_jack_report(&jack->mic_jack, 0, SND_JACK_MICROPHONE);
		snd_soc_jack_report(&jack->jack, 0, SND_JACK_HEADPHONE);
	}
put:
	pm_runtime_put_autosuspend(madera->dev);
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
	jack->dapm = snd_soc_component_to_dapm(codec);
	INIT_DELAYED_WORK(&jack->report_work, g955n_wired_jack_report);
	init_completion(&jack->micd_done);

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
	if (device_property_read_bool(dev, "samsung,wired-mic-detect")) {
		ret = madera_request_irq(madera, MADERA_IRQ_MICDET1, "G955N wired microphone",
					 g955n_wired_mic_irq, jack);
		if (!ret) {
			ret = snd_soc_card_jack_new(rtd->card, "Headset Mic Jack",
						   SND_JACK_MICROPHONE, &jack->mic_jack);
			if (ret)
				madera_free_irq(madera, MADERA_IRQ_MICDET1, jack);
		}
		if (ret)
			dev_warn(dev, "wired mic detection unavailable: %d\n", ret);
		else
			jack->mic_detect = true;
	}
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
	if (jack->mic_detect)
		madera_free_irq(madera, MADERA_IRQ_MICDET1, jack);

	ret = pm_runtime_resume_and_get(madera->dev);
	if (ret < 0) {
		dev_warn(jack->dev, "wired jack restore: codec unavailable: %d\n", ret);
	} else {
		g955n_wired_jack_restore(jack, ARRAY_SIZE(g955n_jack_regs));
		pm_runtime_put_autosuspend(madera->dev);
	}
	devm_kfree(jack->dev, jack);
}
