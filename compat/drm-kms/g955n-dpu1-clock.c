// SPDX-License-Identifier: GPL-2.0-only
/* Exynos8895 G0 System MMU bus clocks for the SM-G955N panel handoff. */
#include <linux/clk-provider.h>
#include <linux/io.h>
#include <linux/mfd/syscon.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/regmap.h>

#define DPU0_STATUS		0x4064
#define DPU0_POWER		GENMASK(3, 0)
#define GATE_MANUAL		BIT(20)
#define GATE_VALUE		BIT(21)
#define GATE_AUTO		BIT(28)
#define GATE_FIELDS		(GATE_MANUAL | GATE_VALUE | GATE_AUTO)
#define GATE_FORCED_ON		(GATE_MANUAL | GATE_VALUE)

struct g955n_dpu1_clock {
	struct clk_hw hw;
	struct regmap *pmu;
	void __iomem *aclk;
	void __iomem *pclk;
	u32 saved_aclk;
	u32 saved_pclk;
};

static bool g955n_dpu0_powered(struct regmap *pmu)
{
	unsigned int status;

	return !regmap_read(pmu, DPU0_STATUS, &status) &&
	       (status & DPU0_POWER) == DPU0_POWER;
}

static void g955n_dpu1_write_gate(void __iomem *reg, u32 value)
{
	writel((readl(reg) & ~GATE_FIELDS) | value, reg);
}

static void g955n_dpu1_unprepare(struct clk_hw *hw)
{
	struct g955n_dpu1_clock *clock =
		container_of(hw, struct g955n_dpu1_clock, hw);

	if (!g955n_dpu0_powered(clock->pmu))
		return;

	g955n_dpu1_write_gate(clock->pclk, clock->saved_pclk);
	g955n_dpu1_write_gate(clock->aclk, clock->saved_aclk);
}

static int g955n_dpu1_prepare(struct clk_hw *hw)
{
	struct g955n_dpu1_clock *clock =
		container_of(hw, struct g955n_dpu1_clock, hw);

	if (!g955n_dpu0_powered(clock->pmu))
		return -EHOSTDOWN;
	clock->saved_aclk = readl(clock->aclk) & GATE_FIELDS;
	clock->saved_pclk = readl(clock->pclk) & GATE_FIELDS;
	g955n_dpu1_write_gate(clock->aclk, GATE_FORCED_ON);
	g955n_dpu1_write_gate(clock->pclk, GATE_FORCED_ON);
	if ((readl(clock->aclk) & GATE_FIELDS) == GATE_FORCED_ON &&
	    (readl(clock->pclk) & GATE_FIELDS) == GATE_FORCED_ON)
		return 0;

	g955n_dpu1_unprepare(hw);
	return -EIO;
}

static const struct clk_ops g955n_dpu1_clk_ops = {
	.prepare = g955n_dpu1_prepare,
	.unprepare = g955n_dpu1_unprepare,
};

static int g955n_dpu1_clock_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct g955n_dpu1_clock *clock;
	struct clk_init_data init = {
		.name = "g955n-dpu1-sysmmu",
		.ops = &g955n_dpu1_clk_ops,
	};
	int ret;

	if (!of_machine_is_compatible("samsung,dream2lteks"))
		return -ENODEV;
	clock = devm_kzalloc(dev, sizeof(*clock), GFP_KERNEL);
	if (!clock)
		return -ENOMEM;
	clock->pmu = syscon_regmap_lookup_by_compatible("samsung,exynos8895-pmu");
	if (IS_ERR(clock->pmu))
		return dev_err_probe(dev, PTR_ERR(clock->pmu), "display PMU unavailable\n");
	clock->aclk = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(clock->aclk))
		return PTR_ERR(clock->aclk);
	clock->pclk = devm_platform_ioremap_resource(pdev, 1);
	if (IS_ERR(clock->pclk))
		return PTR_ERR(clock->pclk);
	clock->hw.init = &init;
	ret = devm_clk_hw_register(dev, &clock->hw);
	if (ret)
		return ret;
	return devm_of_clk_add_hw_provider(dev, of_clk_hw_simple_get, &clock->hw);
}

static const struct of_device_id g955n_dpu1_clock_of_match[] = {
	{ .compatible = "samsung,sm-g955n-dpu1-clock" },
	{ }
};
MODULE_DEVICE_TABLE(of, g955n_dpu1_clock_of_match);

static struct platform_driver g955n_dpu1_clock_driver = {
	.probe = g955n_dpu1_clock_probe,
	.driver = {
		.name = "g955n-dpu1-clock",
		.of_match_table = g955n_dpu1_clock_of_match,
	},
};
module_platform_driver(g955n_dpu1_clock_driver);

MODULE_DESCRIPTION("SM-G955N DPU1 System MMU bus clocks");
MODULE_LICENSE("GPL");
