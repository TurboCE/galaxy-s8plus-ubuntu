# SPDX-License-Identifier: GPL-2.0-only
ifeq ($(G955N_WITH_AID),1)
obj-m := g955n-dsim-aid-probe.o
g955n-dsim-aid-probe-y := g955n-dsim-identify.o g955n-aid.o aid-source/dimming.o
ccflags-y += -DG955N_WITH_AID -DCONFIG_PANEL_AID_DIMMING
CFLAGS_aid-source/dimming.o += -Wno-missing-prototypes -Wno-missing-declarations
else
obj-m := g955n-dsim-identify.o
endif

ifeq ($(G955N_WITH_BACKLIGHT),1)
ifneq ($(G955N_WITH_AID),1)
$(error G955N_WITH_BACKLIGHT requires G955N_WITH_AID=1)
endif
ccflags-y += -DG955N_WITH_BACKLIGHT
endif
