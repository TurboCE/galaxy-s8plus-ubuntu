# SSP poll-delay sysfs return-count defect

## Actual sequence

On31, the original own-device location-hub service initialized the MCU with
matching genuine firmware. Original EFS remained unchanged and the reviewed
runtime light-calibration hook succeeded without EFS writes. A bounded12second
native capture received68 acceleration,67 gyro,59 magnetic and3 ambient-light
records with increasing timestamps. One accumulated step record reported0.
All temporary enable/FIFO settings used by that raw capture were restored.
This proves records, not physical axes, heading, walking or light response.

The journalled SensorProxy candidate then recognized the real accel/light
channels, but claims failed and no user motion/light acceptance data was
captured during the requested physical trial. HasAccelerometer/HasAmbientLight
were discovery results only. The candidate was stopped for diagnosis.

Both real IIO poll_delay files exist but read as empty. Pinned SSP source
show_sensor_delay formats a numeric period into the buffer and then returns0.
set_sensor_delay changes the period and also returns0. Thus a native caller sees
EOF/no write progress despite a side effect. This prevents a truthful snapshot
and restoration of the sampling period. The original failed prototype could
therefore change the RAM-only period to100ms while recording an empty original;
its old empty write did not restore that period. No original calibration file
was changed. A fresh kernel boot reinitializes this RAM state; do not represent
the failed claim as complete original-period restoration.

## Fix and checks

Patch0026 returns scnprintf's actual read count and the consumed write length,
and rejects an unknown sensor index with EINVAL before mutation. Existing numeric
parsing and the delay/MCU implementation are retained. Proven successful sysfs
accesses no longer emit misleading error-priority messages; real parse/index
failures remain errno failures. No global kernel-log filtering is introduced.

scripts/check_ssp_sysfs_counts.py extracts the actual original/patched functions
from the pinned source, applies the real patch and runs address/undefined
sanitizers. The original reproduces zero counts despite a changed period; the
patched read/write counts, unknown-index failures and parse-failure state pass.
The native backend now refuses empty/non-numeric settings before its first
sensor mutation. Its rebuilt AArch64 daemon was tested on actual legacy31:
claims fail safely, the mask/FIFO/scan settings and current period remain exactly
unchanged, and no lease remains. This is an actual negative guard check, not a
positive sensor-service pass.

The real IIO udev rules now request SensorProxy through systemd as well as
identify its packed channels. The initial live installation overlapped a queued
udev/service transition; an explicit subsequent start ran preparation and the
candidate. The discovery properties then appeared but measurements failed for
the count bug above. The service is deliberately stopped pending the fixed32
kernel; no production/physical/reboot acceptance is claimed yet.

Kernel32 is building with the same31 source selection plus only this SSP patch,
GCC7 and actual builtin codec verification. It is not yet installed at this
checkpoint. Private records are under artifacts/sensors, including actual
stationary records, installation/failure logs, source-count regression and
empty-guard before/after results. Runtime calibration values remain private.
