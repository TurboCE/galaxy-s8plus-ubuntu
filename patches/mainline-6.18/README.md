# SM-G955N Linux 6.18 bring-up

Apply patch 0001 to Linux v6.18 and patch 0002 to uniLoader at
`0bd1dd1b55420bebf6ddf24a4e46b16372ae53fb`. Build Linux with the
`config/mainline618-bringup.fragment` Kconfig seed. The ARM64 build targets
are `Image` and `exynos/exynos8895-dream2lteks.dtb`. With an output directory
and the ARM64 toolchain selected, pass the absolute fragment path as
`KCONFIG_ALLCONFIG` when running `make allnoconfig`.

Cross-compile `scripts/boot/mainline618-probe-init.c` as a static ARM64
executable. Put it at `/init` in a gzip-compressed newc archive with
`/sys`, `/dev`, the console character device (5, 1), and `/dev/kmsg`
(1, 11). Copy the kernel, DTB and archive into uniLoader's `blob/Image`, `blob/dtb` and
`blob/ramdisk`. Build uniLoader with `ARCH=aarch64`,
`CROSS_COMPILE=aarch64-linux-gnu-` and `dream2lteks_defconfig`. For the
outer Samsung boot image, use the original SM-G955N boot header and a
verified Samsung DTBH for this board. The loader hands Linux the new
DTB embedded in its own payload.

On the handset, this probe stops in its initramfs and reports
`SM-G955N INITRAMFS OK` on the inherited splash framebuffer console.
Its configuration contains no internal-storage or USB peripheral driver.
The probe mounts sysfs only. Rollback uses the preserved TWRP and a
verified copy of the previous BOOT partition.

The probe establishes early Linux and initramfs execution.
Panfrost still needs the Exynos8895 G3D domain, clock and supply. The
panel path also needs native DECON, DPP, DSI and display IOMMU support.
The touch, audio and WLAN paths must be validated separately
once the normal Ubuntu boot and native Wayland path are available.

Patch 0003 adds the S2DOS03 regulator at I2C address 0x60 and maps its
Samsung panel and touch supplies. It builds with `CONFIG_I2C`,
`CONFIG_REGULATOR` and `CONFIG_REGULATOR_S2DOS03`. Both the PMIC and the
parent I2C controller remain disabled for the initramfs-only probe.

Apply patch 0006 to Linux for the pinctrl and firmware device-link fixes.
The initramfs records whether the PMU, ALIVE and VTS pin controllers,
and GPIO keys bind. The GPIO keys binding checks registration. Key events
and wake from suspend require separate tests.

## Embedded UFS trial

Apply patch 0007 to Linux. Append `config/mainline618-ufs.fragment` to
the bring-up fragment for this build. Pack the static ARM64 BusyBox at
`/bin/busybox` and `scripts/boot/mainline618-ufs-init.sh` at `/init`.
Include `/dev`, `/proc`, `/sys`, `/run`, and `/newroot` in the archive.
The diagnostic uses the embedded controller's own GPT labels to
identify USERDATA. It mounts USERDATA with ext4 `ro,noload` and checks the
installed Ubuntu hostname and init program. The success marker is
`SM-G955N UFS UBUNTU ROOT OK (read-only)`.

The first port constrains the link to PWM gear 1. Use the diagnostic
mode first and retain the matching working BOOT backup. An explicit
`g955n.ufs_boot=1` boot argument lets the initramfs hand off to the
verified Ubuntu systemd after mounting EFS read-only. That stage also
requires a kernel configuration suitable for the installed userspace.

To test an unattended diagnostic return, also pack the ARM64
`scripts/boot/reboot-recovery.c` helper at `/sbin/reboot-recovery` and
add `g955n.ufs_return=1` to the diagnostic boot arguments. The boot
probe requests recovery when it finishes. The board's syscon restart
sequence uses the Samsung PMU scratch and software-reset registers.
This restart path awaits a device test.

## Reading the warm boot trace

Apply patch 0004 to Linux and patch 0005 to uniLoader for the trace build.
The fragment enables the board-specific ARM64 entry marker and the pstore
console. The probe writes its driver checks and boot result to `/dev/kmsg`.

The Samsung recovery kernel reserves 32 KiB at `0x92000000` with no ECC
and exposes the second 16 KiB as pmsg. The loader writes fixed stage
markers to that ring and the 6.18 kernel uses it for its persistent
console. The first ARM64 marker runs only when the MMU is off. Once
the persistent console attaches, kernel messages can replace the early
markers. The reader therefore also recognizes the kernel and initramfs
messages.

After a warm return to TWRP, run `scripts/read_mainline_boot_trace.py`
with the exact device serial. The reader reports matched stages and
can save the raw pmsg record to a private file for diagnosis. A trace
requires the RAM contents to survive the reset. A missing record
does not establish that the bootloader rejected the image.
