# Galaxy S8+ SM-G955N Ubuntu port

Experimental Ubuntu bring-up for the Korean Samsung Galaxy S8+ (dream2lteks,
Exynos 8895). **Native Ubuntu 24.04 boots; USB serial login, root filesystem
growth and Wi-Fi 2.4/5 GHz DNS/HTTPS traffic have been observed. Most hardware
acceptance remains incomplete. No installation image is offered.** This is a
separate project from the SM-G965N port.

The goal is parity with the phone's supported hardware: LTE data, calls/SMS and
VoLTE, Wi-Fi (2.4/5 GHz), Bluetooth, GNSS, sensors, accelerated graphics,
display/touch, cameras, audio, charging, suspend and peripheral interfaces.
5G NR is not supported by this phone's hardware. Full feature parity is a
development goal, not a guarantee; proprietary Android HALs and firmware are
significant dependencies.

## Verified starting point

Read-only Android inspection on 2026-11-18 confirmed SM-G955N, dream2lteks,
G955NKSU5DZE1, Android 9, hardware revision 10, kernel 4.4.111.
SurfaceFlinger reports ARM Mali-G71 / OpenGL ES 3.2 / r16p0-01rel0.
Sensorservice lists LSM6DSL accelerometer/gyroscope and LPS22H barometer.
These are Android observations, **not Ubuntu validation**. No root executable
was found in the shell path at that initial inspection checkpoint.

Subsequent live work: the owner authorized the irreversible Knox change and
Android app-data initialization. TWRP 3.7.0 root ADB is verified, Knox reports 1,
and seven core partition backups have matching device/host byte counts and
SHA256 hashes. The RECOVERY prefix matches the reviewed official image.
TWRP lacks compiled crypto support; encrypted app-private data is not backed up.
Native Ubuntu is now installed and has booted into systemd, with an authenticated
Ubuntu session and no failed systemd units in the first status capture. The root
filesystem grew to approximately 113 GiB. Wi-Fi traffic on both bands works after
fixing inherited build-container DNS configuration. Kernel logs still contain
findings, and GPU, audio, sensors, radios and the other acceptance items remain
under active bring-up. No SIM is present for cellular end-to-end tests.

Ubuntu Desktop is installed. On 2026-11-19 the owner manually authenticated
through GDM into the ordinary Ubuntu GNOME46 session with **Mali-G71 GLES/EGL
hardware rendering and composition**. The actual GNOME process loads the
private EGL bridge and Exynos gralloc, with no swrast driver. Three native
client/overlay pixel and stable-calendar trials passed. The X11 presentation
initially used CPU copies and a separate60Hz panel commit pump. The current
kernel55 normal GNOME login passes Mali DMA-BUFs through DRM/KMS/PRIME to
DECON for its final composition, with no CPU pixel copy. Compatible driver
capabilities and installed-file hashes preserve this route across kernel
updates. See the [KMS driver and integration](compat/drm-kms/README.md). Application-buffer transfers and actual
panel FPS require separate measurement. See the
[direct-output validation](docs/gnome-direct-panel-output.md).
Automatic login is disabled; credentials and device artifacts remain private.
The GDM account-row touch repair now passes owner-confirmed password/desktop entry;
injected touchscreen/OSK/PAM login also passed after the kernel55 reboot and
timed resume. Kernel55 quiesces USB before sleep; recent bounded tests retained
the boot, GNOME and taint0. Earlier GNOME failures and remaining qualification
are recorded in VALIDATION.md. Speaker/mic desktop routing and native
accelerometer/light integration are active, with microphone startup quality,
dynamic rotation, native LTE integration and physical sensor acceptance open.
Ubuntu Location Services receives real satellite fixes through GeoClue on
kernel55. A 275-second field trial also verified the network fallback and
A-GNSS delivery. See [GNSS setup and image staging](compat/gnss/README.md).
Physical cold-boot regression and other hardware acceptance remain open.

Historical failures: Kernel24 passed bounded graphics trials, but later unattended operation produced
repeated resets and is **not stability-qualified**. A header-only cpuidle option
was ignored by the bootloader. Kernel25 actually applies built-in
`cpuidle.off=1`, but also reset: deep idle is not necessary for the failure, and
this diagnostic is not a repair. A legacy panel-presentation comparison is in
progress. Proposal29 fixes reproduced DPP metadata-lifetime and native pan/power
races; kernel26 later hard-hung during repeated desktop DPMS. The source-level
primary-QoS repair and later lifetime fixes are included in the current tested
profile. These early failures remain evidence, not the current running build. Kernel22 remains
quarantined. Recovery/calibration partitions are preserved. See the
[kernel investigation](docs/kernel22-stability-investigation.md).

## Approach

1. Preserve Android evidence privately and pin candidate source revisions.
2. Audit the Korean dream2lte kernel/DT and prepare a build-only configuration.
3. Prioritize a Halium/libhybris-compatible graphics investigation, retaining
   the matching Android Mali kernel/user-space ABI and gralloc/HWC dependencies.
   Assess native switch_root separately; it does not automatically enable GPU
   acceleration. Panfrost is an alternative requiring kernel/SoC integration.
4. Prepare recovery materials and verified backups before any device writes.
5. Bring up boot/logging, then validate each item in docs/VALIDATION.md.

## Developer commands

```sh
python3 scripts/fetch_sources.py
python3 scripts/collect_device.py --adb /path/to/adb --serial DEVICE_SERIAL
python3 -m unittest discover -s tests -v
docker build -t g955n-ubuntu-builder:24.04 -f build/Dockerfile .
bash scripts/build_kernel.sh config
# Experimental compilation; not an installable boot image:
bash scripts/build_kernel.sh image
# Only after Ubuntu boots and the SSH host key/authentication are configured:
python3 scripts/collect_linux.py --host root@PHONE_IP
python3 scripts/kernel_log_audit.py inventory/TIMESTAMP/dmesg.raw
```

Collectors are read-only; outputs under inventory/ may contain personal data
and must remain private. Source references and exact commits are in sources.json.
Build scripts do not flash phones. Never flash G950N/G955F/G965N images here.

For SSH diagnostics when USB is intermittent, pass the USB destination as
`--host` and the current WLAN destination as `--wifi-host`. Supply
`--known-hosts` and `--host-key-alias` for the same pinned handset key on both
addresses. The collector tries WLAN if the initial USB SSH connection fails.
Check the current lease after reboot if a saved WLAN address stops responding.

See [validation](docs/VALIDATION.md), [engineering notes](docs/PORTING.md),
[change log](docs/CHANGELOG.md), [installation review](docs/INSTALLATION_REVIEW.md),
[Ubuntu 26.04 upgrade handoff](docs/ubuntu-26.04-upgrade.md), and [attribution](NOTICE).

## Root filesystem / installation tools

After read-only own-device firmware extraction into ignored inventory/vendor/:

```sh
python3 scripts/build_rootfs.py
python3 scripts/validate_rootfs.py artifacts/rootfs/g955n-rootfs.unqualified.img
python3 scripts/pack_boot.py --kernel-dir artifacts/build-TIMESTAMP-SUFFIX \
  --busybox artifacts/rootfs/busybox-arm64-static --output artifacts/boot-g955n-experimental.img
```

The Linux 6.18 image uses Ubuntu's stock PipeWire, WirePlumber and GeoClue
with the board's ALSA UCM configuration and Wi-Fi/Bluetooth firmware. It
stages the power key and manual suspend when the DECON boot enables
`g955n.desktop_suspend=1`. The same build can include the reviewed modules
for the matching SM-G955N BOOT image.

```sh
python3 scripts/build_rootfs.py --mainline618 \
  --mainline-modules /path/to/lib/modules/6.18.0-g955n-usb-r98
python3 scripts/validate_rootfs.py artifacts/rootfs/mainline618/g955n-rootfs.unqualified.img
```

Private output contains SSH keys, host-key pins, firmware and disk images; never
publish it. Native USB networking uses 192.168.55.2/24 with ECM and a serial port.
The initial image deliberately disables automatic suspend and automatic camera
QUERYCAP until those paths are tested; neither is a root-cause fix or a feature
qualification. Installing Mesa packages does not enable Mali acceleration by itself.

scripts/install_ubuntu.py is an explicit destructive installer, separate from
builders. It requires matching validated images, verified private backups and
the --initialize-userdata flag. It writes/verifies USERDATA before BOOT and
checks RECOVERY/EFS/CPEFS/RADIO/PARAM remain unchanged. It never repartitions,
flashes a bootloader or reboots. See the installation review before using it.
