# Samsung SSP native sensor work

This directory contains a **build-only, uninstalled prototype** backend for the
Ubuntu iio-sensor-proxy 3.5 API. It is not hardware acceptance or a completed
rotation/brightness solution. The phone must first recover from the separately
tracked kernel26 display-power hang.

The existing stock sensor proxy incorrectly identifies `hrm_sensor` input axes
as an accelerometer. The actual Samsung SSP IIO devices contain packed records
rather than the standard separate IIO axis attributes. The prototype udev rules
remove that HRM classification and identify the actual accelerometer/light nodes.
Do not install them without the matching tested backend and recovery plan.

Public protocol: pinned Samsung kernel commit
54feaea9870dd0e90ceced5623e0544d965b400b,
`drivers/sensorhub/brcm/{sensor_list.h,ssp.h,ssp_iio.c}` and the LSM6DSL factory
range of 4096 counts/g. Accelerometer records are14bytes, light records26bytes;
MCU-reported lux is the first u32 with LIGHT_REPORT_LUX enabled. No calibration
constant or service-ready value is invented. Firmware revision must genuinely
match before open/claim. The prototype retains upstream DBus/Polkit claims and
uses an exclusive controller lock; only its own enable bits are changed, and
normal release restores FIFO/polling attributes. GNOME policies are unchanged.

Build source is the official Ubuntu 3.5 original tarball, SHA256
8689425f2287626a95d95b1e1e5b62e497d09dd08cf411084ed22166d4a49da5.
The Ubuntu 3.5-1build2 .dsc checksum was checked; its Debian delta has no source
patches. Original source/license notices remain in the private extracted build.
The additional driver is GPL-3.0-or-later. The Dockerfile installs the ARM64
Polkit development package through authenticated Ubuntu package metadata.

Use `build.py --archive ARCHIVE --output FRESH_DIRECTORY` inside the image built
from this Dockerfile. It cross-compiles the real daemon and monitor, checks
AArch64 ELF headers and does not access a handset. The reviewed prototype builds
without compiler warnings. Binary output and device inputs remain ignored.

Before production deployment, complete at least:

* Actual claim/sample/release tests, preserving other sensors and original state.
* Abrupt process termination and a persistent recoverable ownership lease; the
  current driver restores on normal release/read failure but lacks SIGKILL
  recovery. Do not auto-enable this prototype at boot.
* Genuine LHD firmware startup and original read-only EFS calibration sequencing.
* Physical axis/mount-matrix and changing-light verification. The proposed
  identity matrix is a candidate, not measured calibration.
* GNOME rotation with a dynamic-rotation-capable display path. Stock fbdev's
  startup Rotate option disables RandR and does not implement dynamic rotation.
* Backlight interface/units and actual automatic-brightness/toggle acceptance.

The independent bounded `../sensor-iio-probe.py` now supports native magnetic
and step-counter capture, strict pinned layouts and decoded values. A step
record contains the kernel's accumulated u64 total (not the MCU's u32 delta).
Eight protocol fixtures pass. A single on-change light record is valid evidence
of a record; no step event while stationary is incomplete evidence (exit2), not
a fabricated pass. Physical response is always reported unverified by this
capture tool. Normal signal/error cleanup restores temporary settings; SIGKILL
is outside that guarantee. Logs belong in private artifacts.
