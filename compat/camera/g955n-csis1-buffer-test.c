// SPDX-License-Identifier: GPL-2.0-only
/* Verify the CAM0 IOMMU buffer path without enabling camera DMA. */
#include <linux/dma-mapping.h>
#include <linux/iommu.h>
#include <linux/mm.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/sizes.h>

#define CSIS_TEST_SIZE	SZ_4M

static int g955n_csis1_buffer_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct iommu_domain *domain;
	struct page *pages;
	dma_addr_t iova;
	phys_addr_t phys;
	unsigned long offset;
	int ret;

	if (!of_machine_is_compatible("samsung,dream2lteks"))
		return -ENODEV;
	domain = iommu_get_domain_for_dev(dev);
	if (!domain || !iommu_is_dma_domain(domain))
		return dev_err_probe(dev, -ENODEV, "camera requires a translated DMA domain\n");
	ret = dma_set_mask_and_coherent(dev, DMA_BIT_MASK(32));
	if (ret)
		return ret;
	pages = alloc_pages(GFP_KERNEL | __GFP_NOWARN | __GFP_ZERO, get_order(CSIS_TEST_SIZE));
	if (!pages)
		return -ENOMEM;
	iova = dma_map_page(dev, pages, 0, CSIS_TEST_SIZE, DMA_FROM_DEVICE);
	if (dma_mapping_error(dev, iova)) {
		ret = -EIO;
		goto free_pages;
	}
	if (!IS_ALIGNED(iova, 16) || iova > U32_MAX - (CSIS_TEST_SIZE - 1)) {
		ret = -ERANGE;
		goto unmap;
	}
	phys = page_to_phys(pages);
	for (offset = 0; offset < CSIS_TEST_SIZE; offset += PAGE_SIZE) {
		if (iommu_iova_to_phys(domain, iova + offset) != phys + offset) {
			ret = -EIO;
			goto unmap;
		}
	}
unmap:
	dma_unmap_page(dev, iova, CSIS_TEST_SIZE, DMA_FROM_DEVICE);
	if (!ret && (iommu_iova_to_phys(domain, iova) ||
		     iommu_iova_to_phys(domain, iova + CSIS_TEST_SIZE - PAGE_SIZE)))
		ret = -EIO;
	if (!ret)
		dev_info(dev, "CAM0 translated all %lu pages of the 4 MiB camera buffer and unmapped it\n",
			 CSIS_TEST_SIZE / PAGE_SIZE);
free_pages:
	__free_pages(pages, get_order(CSIS_TEST_SIZE));
	return ret;
}

static const struct of_device_id g955n_csis1_buffer_of_match[] = {
	{ .compatible = "samsung,sm-g955n-csis1-buffer-test" },
	{ }
};
MODULE_DEVICE_TABLE(of, g955n_csis1_buffer_of_match);

static struct platform_driver g955n_csis1_buffer_driver = {
	.probe = g955n_csis1_buffer_probe,
	.driver = {
		.name = "g955n-csis1-buffer-test",
		.of_match_table = g955n_csis1_buffer_of_match,
	},
};
module_platform_driver(g955n_csis1_buffer_driver);

MODULE_DESCRIPTION("SM-G955N CAM0 translated camera buffer verification");
MODULE_LICENSE("GPL");
