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
registers. Read the attachment, data-role, power-role and safety flags
through the bus driver's sysfs directory:

```sh
cat /sys/bus/i2c/drivers/g955n-s2mm005-status/*-0033/port_status
```

The current mainline image uses DWC3 in peripheral mode. USB host
support requires the DWC3 dual-role and xHCI drivers, a Linux role
switch driven by validated S2MM005 attach events, and the board's VBUS
supply control. The diagnostic leaves those controls to the existing
kernel and firmware.
