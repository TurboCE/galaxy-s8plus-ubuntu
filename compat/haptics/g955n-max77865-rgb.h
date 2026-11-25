/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef G955N_MAX77865_RGB_H
#define G955N_MAX77865_RGB_H

#include <linux/types.h>

struct device;
struct regmap;

#define G955N_MAX77865_RGB_LAST_REG 0x34

int g955n_max77865_rgb_register(struct device *dev, struct regmap *map);

#endif
