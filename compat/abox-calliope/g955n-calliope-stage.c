// SPDX-License-Identifier: GPL-2.0-only
/*
 * SM-G955N Calliope firmware staging test.
 * Firmware layout from Samsung Exynos8895 abox.c and exynos8895.dtsi.
 */
#include <linux/dma-mapping.h>
#include <linux/firmware.h>
#include <linux/iommu.h>
#include <linux/mm.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/pm_runtime.h>
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
#define CALLIOPE_IVA_IOVA		0x90000000UL
#define CALLIOPE_IVA_SIZE		SZ_512K
#define CALLIOPE_VSS_IOVA		0xa0000000UL
#define CALLIOPE_VSS_SIZE		(SZ_4M + SZ_2M)

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

static int __init g955n_calliope_stage(void)
{
	const struct firmware *sram = NULL;
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
	struct device *dev;
	bool chipid_mapped = false, keep_dma = false, runtime_active = false;
	int i, ret, cleanup;

	if (!of_machine_is_compatible("samsung,dream2lteks"))
		return -ENODEV;

	if ((try_resume && !try_boot) || (try_dsm_read && !try_resume) ||
	    (try_pcm && !try_dsm_read))
		return -EINVAL;

	dev = bus_find_device_by_name(&platform_bus_type, NULL, "soc@0:abox-speaker");
	if (!dev)
		return -ENODEV;

	device_lock(dev);
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
	if (!ret && try_pcm) {
		pcm.cpu = dma_alloc_coherent(dev, pcm.size, &pcm.dma, GFP_KERNEL);
		if (!pcm.cpu) {
			ret = -ENOMEM;
			goto release;
		}
		memset(pcm.cpu, 0, pcm.size);
		ret = calliope_map(dev, domain, &pcm);
	}
	if (!ret && try_boot) {
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
		ret = g955n_calliope_boot(dev, sram, dram.cpu, try_resume,
					 try_dsm_read, try_pcm, &keep_dma);
		if (keep_dma)
			goto out;
	}

release:
	if (chipid_mapped && iommu_unmap(domain, CALLIOPE_CHIPID, PAGE_SIZE) != PAGE_SIZE) {
		dev_err(dev, "Calliope CHIPID alias teardown incomplete\n");
		ret = -EIO;
	}
	cleanup = calliope_release(dev, domain, &pcm);
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
		ret = -ECANCELED;
	}
out:
	release_firmware(sram);
	if (runtime_active && !keep_dma)
		pm_runtime_put_sync(dev);
	device_unlock(dev);
	put_device(dev);
	return ret;
}

module_init(g955n_calliope_stage);
MODULE_DESCRIPTION("SM-G955N Calliope firmware and IOMMU staging test");
MODULE_LICENSE("GPL");
