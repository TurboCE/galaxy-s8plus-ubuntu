# SM-G955N DSIM inspection

This diagnostic targets the Exynos8895 DSIM0 inherited from the loader.
Build it with the exact ARM64 kernel tree and Module.symvers used for
the installed image.

```sh
make -C "$KERNEL_BUILD" M="$PWD/compat/display/dsim" \
    ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- W=1 modules
sudo insmod compat/display/dsim/g955n-dsim-identify.ko
sudo dmesg | grep g955n-dsim:
```

The default mode snapshots six controller registers plus the IRQ and
FIFO status. It requires the Korean dream2lte board, the active display
power domain, and an unclaimed DSIM0 range. Use it only on the
loader-configured DECON build. The module does not install a display or
backlight driver.

The optional developer-only `read_id=Y` issues a standard three-byte DCS
ID request. This mode writes to the DSIM header FIFO and acknowledges
the resulting receive events. Keep the screen active and test only
with exclusive access to the controller. The loader-inherited setup
returned a bus-turnaround timeout on the tested handset.

Older Samsung-kernel logs from this handset contain
`lcdtype=13701136` (hexadecimal `d11010`). Samsung's
`exynos8895-dream2lte_common.dtsi` matches it with
`0xd01010 / 0xf0ffff` to the S6E3HA6 Dream2 A3 SA panel variant.
The matching vendor table applies gamma, AOR, temperature and supply
compensation, ACL and a latch command. A backlight implementation needs
the calibrated tables and a managed DSIM command path before exposing
brightness to Ubuntu.
