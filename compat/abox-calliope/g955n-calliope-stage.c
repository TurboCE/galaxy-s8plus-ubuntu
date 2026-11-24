// SPDX-License-Identifier: GPL-2.0-only
/*
 * SM-G955N Calliope firmware staging test.
 * Firmware layout from Samsung Exynos8895 abox.c and exynos8895.dtsi.
 */
#include <linux/dma-mapping.h>
#include <linux/firmware.h>
#include <linux/i2c.h>
#include <linux/iommu.h>
#include <linux/mm.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/pm_runtime.h>
#include <linux/regmap.h>
#include <linux/sizes.h>

#include "calliope.h"

static bool try_boot;
module_param(try_boot, bool, 0400);
MODULE_PARM_DESC(try_boot, "Attempt one bounded Calliope boot with idle ABOX audio");
static bool try_resume;
module_param(try_resume, bool, 0400);
MODULE_PARM_DESC(try_resume, "Send RESUME after BOOT_DONE; requires try_boot");
static bool try_dsm_read;
module_param(try_dsm_read, bool, 0400);
MODULE_PARM_DESC(try_dsm_read, "Read DSM parameters without playback; requires try_resume");
static bool try_pcm;
module_param(try_pcm, bool, 0400);
MODULE_PARM_DESC(try_pcm, "Run a silent RDMA0 firmware PCM trial; requires try_dsm_read");
static bool try_feedback;
module_param(try_feedback, bool, 0400);
MODULE_PARM_DESC(try_feedback, "Check muted MAX98506 monitor configuration; requires try_pcm");
#define CALLIOPE_IVA_IOVA		0x90000000UL
#define CALLIOPE_IVA_SIZE		SZ_512K
#define CALLIOPE_VSS_IOVA		0xa0000000UL
#define CALLIOPE_VSS_SIZE		(SZ_4M + SZ_2M)
#define MAX98506_GLOBAL_ENABLE		0x38
#define MAX98506_ENABLE			BIT(7)

/* Samsung dream2lte has VMON on slots 2–3 and IMON on slots 0–1. */
static const struct {
	unsigned int reg, mask, value;
} max98506_feedback[] = {
	{ 0x22, GENMASK(5, 0), 0x22 },
	{ 0x23, GENMASK(5, 0), 0x20 },
	{ 0x2a, GENMASK(7, 0), 0xf0 },
	{ 0x36, GENMASK(1, 0), 0x03 },
};

struct calliope_feedback {
	struct i2c_client *client;
	struct regmap *map;
	unsigned int saved[ARRAY_SIZE(max98506_feedback)];
	unsigned int changed;
};

static int calliope_feedback_restore(struct calliope_feedback *feedback)
{
	bool changed = feedback->changed;
	int ret = 0;

	while (feedback->changed) {
		unsigned int i = --feedback->changed;
		unsigned int reg = max98506_feedback[i].reg;
		unsigned int mask = max98506_feedback[i].mask;
		unsigned int actual;
		int err;

		err = regmap_update_bits(feedback->map, reg, mask, feedback->saved[i] & mask);
		if (!err) {
			err = regmap_read(feedback->map, reg, &actual);
			if (!err && (actual & mask) != (feedback->saved[i] & mask))
				err = -EIO;
		}
		if (err && !ret)
			ret = err;
	}

	if (feedback->client) {
		if (changed && !ret) {
			unsigned int enabled;

			ret = regmap_read(feedback->map, MAX98506_GLOBAL_ENABLE, &enabled);
			if (!ret && (enabled & MAX98506_ENABLE))
				ret = -EIO;
			if (!ret)
				dev_info(&feedback->client->dev,
					 "Calliope feedback registers restored, amplifier off\n");
		}
		if (ret)
			dev_err(&feedback->client->dev, "Calliope monitor restore failed: %d\n", ret);
		device_unlock(&feedback->client->dev);
		put_device(&feedback->client->dev);
	}
	return ret;
}

static int calliope_feedback_prepare(struct device *dev, struct calliope_feedback *feedback)
{
	struct device_node *codec;
	unsigned int actual, i;
	int ret;

	codec = of_parse_phandle(dev->of_node, "audio-codec", 0);
	if (!codec)
		return -ENODEV;
	if (of_device_is_compatible(codec, "maxim,max98506"))
		feedback->client = of_find_i2c_device_by_node(codec);
	of_node_put(codec);
	if (!feedback->client)
		return -ENODEV;

	device_lock(&feedback->client->dev);
	feedback->map = dev_get_regmap(&feedback->client->dev, NULL);
	if (!feedback->map)
		return -ENODEV;
	ret = regmap_read(feedback->map, MAX98506_GLOBAL_ENABLE, &actual);
	if (ret || (actual & MAX98506_ENABLE))
		return ret ?: -EBUSY;

	for (i = 0; i < ARRAY_SIZE(max98506_feedback); i++) {
		unsigned int reg = max98506_feedback[i].reg;
		unsigned int mask = max98506_feedback[i].mask;
		unsigned int value = max98506_feedback[i].value;

		ret = regmap_read(feedback->map, reg, &feedback->saved[i]);
		if (ret)
			return ret;
		feedback->changed++;
		ret = regmap_update_bits(feedback->map, reg, mask, value);
		if (ret)
			return ret;
		ret = regmap_read(feedback->map, reg, &actual);
		if (ret || (actual & mask) != value)
			return ret ?: -EIO;
		dev_info(dev, "Calliope muted MAX98506 feedback reg %#x: %#x -> %#x\n",
			 reg, feedback->saved[i], actual);
	}
	ret = regmap_read(feedback->map, MAX98506_GLOBAL_ENABLE, &actual);
	if (ret || (actual & MAX98506_ENABLE))
		return ret ?: -EIO;
	return 0;
}

struct calliope_file {
	const char *name;
	size_t start;
	size_t end;
};

struct calliope_region {
	unsigned long iova;
	size_t size;
	dma_addr_t dma;
	void *cpu;
	size_t mapped;
};

/* Sorted offsets delimit each image before the next image or window end. */
static const struct calliope_file dram_files[] = {
	{ "calliope_dram.bin",       0,        0x4fc000 },
	{ "SoundBoosterParam.bin",   0x4fc000, 0x502000 },
	{ "dsm.bin",                 0x502000, 0x601000 },
	{ "dsm_tune.bin",            0x601000, 0x7ec000 },
	{ "APBargeIn_AUDIO_SLSI.bin", 0x7ec000, 0x7ef000 },
	{ "APBiBF_AUDIO_SLSI.bin",    0x7ef000, 0x7f0000 },
	{ "AP_AUDIO_SLSI.bin",       0x7f0000, CALLIOPE_DRAM_SIZE },
};

static const struct calliope_file iva_file = {
	"calliope_iva.bin", 0, CALLIOPE_IVA_SIZE,
};

static int calliope_load(struct device *dev, const struct calliope_file *file,
			 void *buffer)
{
	const struct firmware *fw;
	int ret;

	ret = request_firmware(&fw, file->name, dev);
	if (ret)
		return dev_err_probe(dev, ret, "requesting %s\n", file->name);

	if (!fw->size || fw->size > file->end - file->start) {
		ret = dev_err_probe(dev, -EFBIG, "invalid size for %s\n", file->name);
	} else if (buffer) {
		memcpy(buffer + file->start, fw->data, fw->size);
	}

	release_firmware(fw);
	return ret;
}

static int calliope_map(struct device *dev, struct iommu_domain *domain,
			struct calliope_region *region)
{
	size_t offset;
	phys_addr_t phys;
	int ret;

	/* The owner's 31-bit DMA allocations cannot use the firmware aliases. */
	if (dma_get_mask(dev) != DMA_BIT_MASK(31) ||
	    region->dma > DMA_BIT_MASK(31) - region->size + 1)
		return -ERANGE;

	for (offset = 0; offset < region->size; offset += PAGE_SIZE) {
		if (iommu_iova_to_phys(domain, region->iova + offset))
			return -EBUSY;
		phys = iommu_iova_to_phys(domain, region->dma + offset);
		if (!phys)
			return -EFAULT;
		ret = iommu_map(domain, region->iova + offset, phys, PAGE_SIZE,
				IOMMU_READ | IOMMU_WRITE, GFP_KERNEL);
		if (ret)
			return ret;
		region->mapped += PAGE_SIZE;
		if (iommu_iova_to_phys(domain, region->iova + offset) != phys)
			return -EIO;
	}
	return 0;
}

static int calliope_release(struct device *dev, struct iommu_domain *domain,
			    struct calliope_region *region)
{
	if (region->mapped &&
	    iommu_unmap(domain, region->iova, region->mapped) != region->mapped) {
		dev_crit(dev, "Calliope alias teardown incomplete; retaining DMA backing until reboot\n");
		return -EIO;
	}
	if (region->cpu)
		dma_free_coherent(dev, region->size, region->cpu, region->dma);
	return 0;
}

int g955n_calliope_run(struct device *dev, struct calliope_stream *stream)
{
	const struct firmware *sram = NULL;
	struct calliope_feedback feedback = {};
	struct calliope_region dram = {
		.iova = CALLIOPE_DRAM_IOVA, .size = CALLIOPE_DRAM_SIZE,
	};
	struct calliope_region iva = {
		.iova = CALLIOPE_IVA_IOVA, .size = CALLIOPE_IVA_SIZE,
	};
	struct calliope_region vss = {
		.iova = CALLIOPE_VSS_IOVA, .size = CALLIOPE_VSS_SIZE,
	};
	struct calliope_region pcm = {
		.iova = CALLIOPE_RDMA0_IOVA,
		.size = CALLIOPE_PCM_PERIOD_BYTES * CALLIOPE_PCM_PERIODS,
	};
	struct iommu_domain *domain;
	bool chipid_mapped = false, keep_dma = false, runtime_active = false;
	bool boot = stream || try_boot;
	bool resume = stream || try_resume;
	bool dsm = stream || try_dsm_read;
	bool play = stream || try_pcm;
	bool monitor = stream || try_feedback;
	unsigned int period_bytes = stream && stream->period_bytes ?
				    stream->period_bytes : CALLIOPE_PCM_PERIOD_BYTES;
	unsigned int max_periods = CALLIOPE_PCM_PERIODS;
	int i, ret, cleanup;

	if ((resume && !boot) || (dsm && !resume) ||
	    (play && !dsm) || (monitor && !play))
		return -EINVAL;
	if (period_bytes == CALLIOPE_K58_PERIOD_BYTES && g955n_calliope_kernel58_route())
		max_periods = CALLIOPE_K58_PERIODS;
	else if (period_bytes != CALLIOPE_PCM_PERIOD_BYTES)
		return -EINVAL;
	if (stream && (!stream->mute || stream->periods < 2 || stream->periods > max_periods ||
		       !IS_ALIGNED(stream->dma, PAGE_SIZE)))
		return -EINVAL;

	domain = iommu_get_domain_for_dev(dev);
	if (!dev->driver || !domain || !iommu_is_dma_domain(domain) ||
	    dma_get_mask(dev) != DMA_BIT_MASK(31)) {
		ret = -ENODEV;
		goto out;
	}

	/*
	 * The device link keeps the audio IOMMU powered while the PCM
	 * device is active. Hold the same reference during firmware access.
	 */
	ret = pm_runtime_resume_and_get(dev);
	if (ret < 0)
		goto out;
	runtime_active = true;

	ret = request_firmware(&sram, "calliope_sram.bin", dev);
	if (ret)
		goto out;
	if (!sram->size || sram->size > CALLIOPE_SRAM_IMAGE_LIMIT) {
		ret = -EFBIG;
		goto out;
	}

	dram.cpu = dma_alloc_coherent(dev, dram.size, &dram.dma, GFP_KERNEL);
	iva.cpu = dma_alloc_coherent(dev, iva.size, &iva.dma, GFP_KERNEL);
	/* Reserve private scratch DRAM; do not expose modem shared memory. */
	vss.cpu = dma_alloc_coherent(dev, vss.size, &vss.dma, GFP_KERNEL);
	if (!dram.cpu || !iva.cpu || !vss.cpu) {
		ret = -ENOMEM;
		goto release;
	}

	for (i = 0; i < ARRAY_SIZE(dram_files); i++) {
		ret = calliope_load(dev, &dram_files[i], dram.cpu);
		if (ret)
			goto release;
	}
	ret = calliope_load(dev, &iva_file, iva.cpu);
	if (ret)
		goto release;

	ret = calliope_map(dev, domain, &dram);
	if (!ret)
		ret = calliope_map(dev, domain, &iva);
	if (!ret)
		ret = calliope_map(dev, domain, &vss);
	if (!ret && play) {
		if (stream) {
			pcm.dma = stream->dma;
			pcm.size = stream->periods * period_bytes;
		} else {
			pcm.cpu = dma_alloc_coherent(dev, pcm.size, &pcm.dma, GFP_KERNEL);
			if (!pcm.cpu) {
				ret = -ENOMEM;
				goto release;
			}
			memset(pcm.cpu, 0, pcm.size);
		}
		ret = calliope_map(dev, domain, &pcm);
	}
	if (!ret && boot) {
		if (iommu_iova_to_phys(domain, CALLIOPE_CHIPID)) {
			ret = -EBUSY;
			goto release;
		}
		/* The stock reset handler reads the revision at CHIPID + 0x10. */
		ret = iommu_map(domain, CALLIOPE_CHIPID, CALLIOPE_CHIPID, PAGE_SIZE,
				IOMMU_READ | IOMMU_MMIO, GFP_KERNEL);
		if (ret)
			goto release;
		chipid_mapped = true;
		if (monitor) {
			ret = calliope_feedback_prepare(dev, &feedback);
			if (ret)
				goto release;
		}
		ret = g955n_calliope_boot(dev, sram, dram.cpu, resume,
					 dsm, play, monitor, &keep_dma, stream);
		if (keep_dma)
			goto out;
	}

release:
	if (chipid_mapped && iommu_unmap(domain, CALLIOPE_CHIPID, PAGE_SIZE) != PAGE_SIZE) {
		dev_err(dev, "Calliope CHIPID alias teardown incomplete\n");
		ret = -EIO;
	}
	cleanup = calliope_release(dev, domain, &pcm);
	if (cleanup && stream)
		stream->retain_ring = true;
	if (calliope_release(dev, domain, &vss))
		cleanup = -EIO;
	if (calliope_release(dev, domain, &iva))
		cleanup = -EIO;
	if (calliope_release(dev, domain, &dram) || cleanup)
		ret = -EIO;
	if (!ret) {
		dev_info(dev, "Calliope: verified nine firmware files and %zu mapped pages; aliases released\n",
			 (dram.mapped + iva.mapped + vss.mapped + pcm.mapped) >> PAGE_SHIFT);
		/* A completed one-shot test leaves no module or mappings resident. */
		if (!stream)
			ret = -ECANCELED;
	}
out:
	cleanup = calliope_feedback_restore(&feedback);
	if (cleanup && (!ret || ret == -ECANCELED))
		ret = cleanup;
	release_firmware(sram);
	if (runtime_active && !keep_dma)
		pm_runtime_put_sync(dev);
	if (stream && keep_dma)
		stream->retain_ring = true;
	return ret;
}

#ifndef G955N_CALLIOPE_ALSA
static int __init g955n_calliope_stage(void)
{
	struct device *dev;
	int ret;

	if (!of_machine_is_compatible("samsung,dream2lteks"))
		return -ENODEV;
	dev = bus_find_device_by_name(&platform_bus_type, NULL, "soc@0:abox-speaker");
	if (!dev)
		return -ENODEV;
	device_lock(dev);
	ret = g955n_calliope_run(dev, NULL);
	device_unlock(dev);
	put_device(dev);
	return ret;
}

module_init(g955n_calliope_stage);
MODULE_DESCRIPTION("SM-G955N Calliope firmware and IOMMU staging test");
MODULE_LICENSE("GPL");
#endif
