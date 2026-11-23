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

Apply patches 0007 and 0008 to Linux. Append `config/mainline618-ufs.fragment` to
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
uses `config/mainline618-ubuntu.fragment`. For a timed trial, also pass
`systemd.unit=multi-user.target g955n.ubuntu_return=1`. A timer in
`/run` checks for the target every 10 seconds. When it becomes active
or the boot reaches five minutes, the timer records the systemd state
and root mount, then requests a normal shutdown and recovery reboot.
On timeout it also records the pending systemd jobs. When testing an
installation that uses the downstream GNOME direct-output service, add
`systemd.mask=g955n-direct-panel-recover.service` to this trial's boot
arguments. This keeps the service from changing the working graphical
configuration for the older kernel.

To test an unattended diagnostic return, also pack the ARM64
`scripts/boot/reboot-recovery.c` helper at `/sbin/reboot-recovery` and
add `g955n.ufs_return=1` to the diagnostic boot arguments. The boot
probe requests recovery when it finishes. The board's syscon restart
sequence uses the Samsung PMU scratch and software-reset registers.
The storage probe has used this path to return to TWRP on the handset.

## USB diagnostic access

Apply patches 0009 through 0013 and append `config/mainline618-usb.fragment`
for the high-speed USB device build. Patch 0011 initializes the PHY before
the DWC3 device reset, matching the order in the Samsung kernel. If a control
endpoint command times out, the driver records its register state.
Patch 0012 matches the Samsung PHY calibration and initial EP0 speed.
Patch 0013 enables the MAX77865 MUIC on the board's I2C bus and routes
its USB2 data pins to the application processor. The switch driver
restores the inherited route when it shuts down.
The initramfs binds one CDC ACM serial
interface through configfs. Add `g955n.usb_diag=1` to the
boot arguments to enable the diagnostic commands. With the serial port
open from the host, send one command per line. `status` returns the
kernel release, `log` streams the kernel log, and `recovery` requests
a recovery reboot. The interface is available during the read-only
UFS test and exits before handing over to the installed system. The
timed Ubuntu trial records the early USB diagnostics in its journal.
Add `g955n.usb_handoff=1` to let the host send `continue` after reading
the early log. The normal Ubuntu boot proceeds after the bounded wait
if the host is absent. Initramfs logs include the monotonic time of
entry, root verification and handoff to systemd.
For a timed trial, add `g955n.usb_login=1` to start an Ubuntu login prompt
on ttyGS0 after initramfs exits. Authentication uses the installed
Ubuntu accounts. Add `g955n.netns_diag=1` to exercise a systemd unit
with `PrivateNetwork=yes` and check that the private network namespace
has a loopback interface.

## Storage command responses and touchscreen trial

Apply patch 0014 for the Exynos8895 UFS controller's command response
quirk. The controller has reported OCS 7 while supplying valid SCSI sense
data for a MODE SENSE request. The SCSI layer can then handle the
unsupported page with its normal fallback. The Ubuntu fragment enables
file locking, which systemd uses while creating private namespaces.

For a separate STMFTS trial, apply proposals 0059 and 0061 to Linux,
proposal 0060 to uniLoader, and append `config/mainline618-touch.fragment`.
The loader sets the two touchscreen rails to the levels observed on the
working SM-G955N. The FTS8CD56 variant uses the controller reset, chip ID
and FIFO protocol from the Samsung driver, with the standard STMFTS
input path on HSI2C23.
Boot with `g955n.hardware_diag=1` to record input, DRM, Wi-Fi, ALSA and
sleep interfaces in the timed trial journal. Treat driver enumeration
and actual input, scanout, audio and resume as separate checks.

Proposals 0062, 0064 and 0065 test the Exynos8895 UniPro Hibern8 result
and the host clock state when shutting down. Apply them in that order
for the combined trial. Keep using the timed recovery return while
testing.

Proposal 0068 adds the experimental Exynos8895 two-lane HS-B gear 1
tuning. Use a read-only trial when applying it. For diagnosis, build
`CONFIG_SCSI_UFS_EXYNOS=m` and place `ufs-exynos.ko` at
`/bin/ufs-exynos.ko` in the initramfs. Boot with `g955n.ufs_module_hs_trial=1`,
`g955n.usb_diag=1` and `g955n.usb_handoff=1`. The initramfs loads the
experimental driver after the host acknowledges receipt of the early
USB log. Add `g955n.ufs_read_diag=1` to time an 8 MiB direct read from
USERDATA without changing the contents.

For the G3D power snapshot, also apply proposal 0063 to uniLoader and
reserve five cells under `/chosen` in the embedded DTB. Use
`samsung,g955n-g3d-power-snapshot` with each cell initialized to
`0xffffffff`. The loader collects BUCK6 control and two voltage
selectors, LDO9 control and G3D power state for the USB boot log.
For the clock snapshot, also apply proposal 0066 and reserve seven more
cells under `/chosen` as `samsung,g955n-g3d-clock-snapshot`, all
initialized to `0xffffffff`. The loader reads the G3D clock registers
only when the PMU reports that the domain is fully on.

Apply proposal 0067 to register the G3D clocks and Mali device. A
diagnostic DTB enables both nodes. The driver checks inherited power
before accessing the CMU. This trial uses the firmware voltage and
frequency pending native regulator and power-domain support.

For the Mesa rendering check, build
`scripts/boot/panfrost-render-probe.c` for AArch64 against the EGL, GLES,
GBM and exported DRM UAPI headers, and link with `-ldl`. Include the executable in the
initramfs at `/bin/g955n-panfrost-render` and add
`g955n.panfrost_diag=1` to the boot arguments. The test uses the installed
Mesa libraries from the read-only Ubuntu mount. It verifies shader
rendering and pixel readback through Panfrost without exercising DECON.
An optional Ubuntu AArch64 `strace` executable at `/bin/g955n-strace`
enables a bounded syscall trace. The initramfs logs the last entries if
the rendering probe fails.

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
