# SPDX-License-Identifier: GPL-2.0-only
obj-m := g955n-haptic-identify.o

ifneq ($(filter y m,$(CONFIG_LEDS_CLASS)),)
obj-m += g955n-max77865-rgb.o
endif

ifeq ($(CONFIG_PWM),y)
obj-m += g955n-max77865-haptic.o
endif
