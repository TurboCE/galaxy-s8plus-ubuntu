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

The default mode snapshots controller configuration, IRQ, and FIFO status. It requires the Korean dream2lte board, the active display
power domain, and an unclaimed DSIM0 range. Use it only on the
loader-configured DECON build. The module does not install a display or
backlight driver.

The optional developer-only `read_id=Y` issues a standard three-byte DCS
ID request. This mode writes to the DSIM header FIFO and acknowledges
the resulting receive events. Keep the screen active and test only
with exclusive access to the controller. The read temporarily extends the controller’s bus-turnaround
window, then restores the loader configuration. It returned
`d11010` on the running 6.18 handset.

The optional `read_calibration=Y` mode checks the live panel ID before
selecting the S6E3HA6 Dream2 A3 SA resource keys. It reads the factory
MTP (35 bytes), ELVSS (24 bytes), and HBM gamma (33 bytes) twice and
checks for matching, nonblank contents. It resets the global offset
after the HBM reads and sends the lock keys in reverse order. The
probe prints only resource lengths and status, and clears its
temporary buffers. It does not apply gamma or change the brightness.

Older Samsung-kernel logs from this handset contain
`lcdtype=13701136` (hexadecimal `d11010`). Samsung's
`exynos8895-dream2lte_common.dtsi` matches it with
`0xd01010 / 0xf0ffff` to the S6E3HA6 Dream2 A3 SA panel variant.
The matching vendor table applies gamma, AOR, temperature and supply
compensation, ACL and a latch command. A backlight implementation needs
the calibrated tables and a managed DSIM command path before exposing
brightness to Ubuntu.

## Calculate the normal-brightness gamma rows

The optional AID build reuses Samsung's GPL calculator and Dream2 A3
tuning rows. Stage the sources from the SM-G955N Samsung kernel tree.
The staging script checks the exact source hashes and disables vendor
debug output before building.

```sh
python3 compat/display/dsim/prepare-aid.py \
    "$SAMSUNG_KERNEL/drivers/video/fbdev/exynos/panel" compat/display/dsim
make -C "$KERNEL_BUILD" M="$PWD/compat/display/dsim" \
    ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- G955N_WITH_AID=1 W=1 modules
sudo insmod compat/display/dsim/g955n-dsim-aid-probe.ko read_calibration=Y
```

The AID build calculates all 74 normal-brightness rows from live MTP
data. It checks every packed row for nonblank output and the endpoints
for different contents. Calibration and computed bytes stay in scratch
memory. HBM gamma is read in the resource diagnostic. No calculated
row is sent to the panel by this probe.
