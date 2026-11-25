# SPDX-License-Identifier: GPL-2.0-only
obj-m := g955n-nfc-reset.o

ifneq ($(filter y m,$(CONFIG_NFC_NCI)),)
obj-m += g955n-nfc-nci.o
endif
