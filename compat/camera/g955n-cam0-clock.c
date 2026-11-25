// SPDX-License-Identifier: GPL-2.0-only
/* CAM0 System MMU clock gate in the Exynos8895 camera clock controller. */
#include <linux/clk-provider.h>
#include <linux/mfd/syscon.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/regmap.h>

#define EXYNOS8895_CAM_STATUS	0x4024
#define EXYNOS8895_CAM_ON	GENMASK(3, 0)
#define EXYNOS8895_CAM0_GATE	21

static int g955n_cam0_clock_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct clk_parent_data parent = { .index = 0 };
	struct clk_hw *hw;
	struct regmap *pmu;
	void __iomem *gate;
	unsigned int state;
	int ret;

	if (!of_machine_is_compatible("samsung,dream2lteks"))
		return -ENODEV;
	pmu = syscon_regmap_lookup_by_compatible("samsung,exynos8895-pmu");
	if (IS_ERR(pmu))
		return dev_err_probe(dev, PTR_ERR(pmu), "camera PMU unavailable\n");
	ret = regmap_read(pmu, EXYNOS8895_CAM_STATUS, &state);
	if (ret)
		return ret;
	if ((state & EXYNOS8895_CAM_ON) != EXYNOS8895_CAM_ON)
		return dev_err_probe(dev, -EACCES, "camera domain is off\n");

	gate = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(gate))
		return PTR_ERR(gate);
	hw = devm_clk_hw_register_gate_parent_data(dev, "g955n-cam0-sysmmu",
						  &parent, 0, gate,
						  EXYNOS8895_CAM0_GATE, 0, NULL);
	if (IS_ERR(hw))
		return PTR_ERR(hw);
	return devm_of_clk_add_hw_provider(dev, of_clk_hw_simple_get, hw);
}

static const struct of_device_id g955n_cam0_clock_of_match[] = {
	{ .compatible = "samsung,sm-g955n-cam0-clock" },
	{ }
};
MODULE_DEVICE_TABLE(of, g955n_cam0_clock_of_match);

static struct platform_driver g955n_cam0_clock_driver = {
	.probe = g955n_cam0_clock_probe,
	.driver = {
		.name = "g955n-cam0-clock",
		.of_match_table = g955n_cam0_clock_of_match,
	},
};
module_platform_driver(g955n_cam0_clock_driver);

MODULE_DESCRIPTION("SM-G955N camera CAM0 System MMU clock gate");
MODULE_LICENSE("GPL");
