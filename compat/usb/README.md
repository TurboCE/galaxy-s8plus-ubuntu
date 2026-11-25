# SM-G955N USB-C controller

The Korean Dream2 board connects the Samsung S2MM005 at address 0x33
to the secondary I²C adapter of USI9. Its I²C registers use a
big-endian 16-bit address and little-endian status words. The
[board fragment](g955n-s2mm005-status.dtsi) enables only that adapter
and the read-only status client.

Build the module against the exact configured ARM64 kernel directory:

```sh
make -C /path/to/kernel-build M="$PWD" ARCH=arm64 \
  CROSS_COMPILE=aarch64-linux-gnu- W=1 modules
```

The module uses the stock firmware function-state and low-power status
registers. With [CONFIG_TYPEC](../../config/mainline618-typec.fragment)
enabled, it also reports the port, partner and current roles through
`/sys/class/typec/`. The driver refreshes the firmware state on a
freezable workqueue and provides no userspace role setters.

The bus driver's diagnostic attribute remains available with or without
the Type-C class:

```sh
cat /sys/bus/i2c/drivers/g955n-s2mm005-status/*-0033/port_status
```

## DWC3 dual-role controller

The [kernel fragment](../../config/mainline618-usb-dual-role.fragment)
adds DWC3 dual-role and the platform xHCI driver. The
[board fragment](g955n-dwc3-dual-role.dtsi) registers the DWC3 role
switch and defaults to peripheral mode so the boot-time serial and
Ethernet gadget can start. Keep the Exynos USB DRD PHY built in for
that initramfs path. The Type-C class can continue to use the matching
module from the existing installation.

USB host operation also requires connecting the S2MM005 role events
to the DWC3 role switch and coordinating the board's VBUS supply.
The Type-C status driver continues to report the firmware's roles.
