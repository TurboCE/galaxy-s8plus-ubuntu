# SPDX-License-Identifier: GPL-2.0-only
ifeq ($(G955N_WITH_AID),1)
ccflags-y += -DG955N_WITH_AID -DCONFIG_PANEL_AID_DIMMING
CFLAGS_aid-source/dimming.o += -Wno-missing-prototypes -Wno-missing-declarations
ifeq ($(G955N_WITH_BACKLIGHT),1)
ccflags-y += -DG955N_WITH_BACKLIGHT
obj-m := g955n-dsim-backlight.o
g955n-dsim-backlight-y := g955n-dsim-identify.o g955n-aid.o aid-source/dimming.o
else
obj-m := g955n-dsim-aid-probe.o
g955n-dsim-aid-probe-y := g955n-dsim-identify.o g955n-aid.o aid-source/dimming.o
endif
else
ifeq ($(G955N_WITH_BACKLIGHT),1)
$(error G955N_WITH_BACKLIGHT requires G955N_WITH_AID=1)
endif
obj-m := g955n-dsim-identify.o
endif
