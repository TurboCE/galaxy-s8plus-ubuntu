# Galaxy S8+ SM-G955N Ubuntu port

Experimental Ubuntu bring-up for the Korean Samsung Galaxy S8+ (dream2lteks,
Exynos 8895). **No Ubuntu hardware feature is qualified yet. No installation
image is offered.** This is a separate project from the SM-G965N port.

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
was found in the shell path. Partitions have not been backed up.

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

See [validation](docs/VALIDATION.md), [engineering notes](docs/PORTING.md),
[change log](docs/CHANGELOG.md), [installation review](docs/INSTALLATION_REVIEW.md),
and [attribution](NOTICE).
