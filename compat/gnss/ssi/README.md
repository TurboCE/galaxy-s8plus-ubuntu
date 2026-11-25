# SM-G955N BCM4773 SSI transport

This out-of-tree module implements the half-duplex SPI framing used by the
Broadcom hub. It is based on the framing and wake sequence in Samsung's
Exynos8895 `drivers/sensorhub/brcm/bbdpl/bcm_gps_spi.c`. The code uses the
6.18 SM-G955N diagnostic DT node and its existing regulator and GPIO
descriptors. It does not autoload.

Build against the exact configured ARM64 kernel build directory:

```sh
make -C /path/to/kernel-build M="$PWD" ARCH=arm64 \
  CROSS_COMPILE=aarch64-linux-gnu- W=1 modules
```

The module registers a root-only, exclusive `/dev/g955n-bcm4773-ssi`
endpoint. Open holds the hub regulator. Closing an opened endpoint
releases the supply. `poll(2)` reports a pending receive and TX readiness.
`read(2)` reports `EAGAIN` on an idle link. Each transfer handles at most
254 payload bytes. Callers must handle short writes. Received bytes are
raw Broadcom wire data that still require BBD/RPC demultiplexing.

On 6.18 VPN2, the endpoint passed exclusive open, idle receive, release
and driver unbind with a descriptor still open. Each release left the
regulator disabled. No nonempty payload was sent during that test.
The raw endpoint does not decode SSP sensor data or GNSS receiver output.
Do not install this as the phone's default sensor driver until those
consumers and suspend behavior are qualified.

The [revision 10 pinctrl proposal](../../../patches/proposals/0139-mainline-sm-g955n-bcm4773-power-pins.patch)
selects GPIO output for the second hub power gate. The driver verifies the
active level and restores the old GPIO state on close. On the corrected
trial DT, `bbd-chip-id.py` issued the documented SSP WHOAMI read using
the Broadcom BBD framing. The tool accepts no arbitrary SSP commands.
The complete 21-byte request was transferred, with no bytes received
during the response window. The hub firmware startup and a live reply
remain prerequisites for desktop integration.

## Verified BBD patch reader

The optional `expose_legacy_patch=1` module parameter provides the
root-only, read-only `/dev/bbd_patch` device used by the original daemon.
Install the file obtained from the owner's working Samsung kernel as
`samsung/g955n/bbd-patch.bin` in the kernel firmware search path. The
firmware file is kept outside this repository. The driver accepts only
the exact size and SHA-256 verified on this Korean handset. Missing or
mismatched inputs are reported at open. Closing an open descriptor
releases its firmware reference.

Verified on 6.18 with a byte-for-byte readback of the handset's stock
patch stream. This endpoint supplies the file to a future legacy-daemon
bridge. It does not send the patch to the hub.

## BBD firmware lifecycle control

With `expose_legacy_control=1`, the module adds root-only
`/dev/bbd_control` and the read-only status file
`/sys/class/misc/bbd_control/daemon_status`. It accepts the firmware
lifecycle notifications `ESW:NOTREADY`, `ESW:READY`, `ESW:CRASHED`,
and the SSI patch transfer delimiters. Reading an idle control stream
returns EOF, and the endpoint signals hangup on SPI unbind. It does not
yet issue the kernel's `BBD:RESET_REQ` or change SPI framing based on the
transfer flag.

The status describes notifications supplied by the caller. It does not
establish that the hub booted. On-device tests injected control messages
and verified state transitions, input validation and descriptor lifetime.
The original daemon, actual patch transfer and `bbd_sensor` exchange still
require end-to-end qualification.

## Queued legacy byte stream

With `expose_legacy_stream=1`, the driver also provides root-only
`/dev/ttyBCM`, a misc character device matching the stock endpoint's
queued byte-stream model. The raw SSI endpoint and the queued stream
share one exclusive link owner. The stream accepts up to 32 KiB of
queued output and splits it into SSI transfers. A worker services input
first and forwards received wire bytes. Empty reads return zero bytes.
Poll for writable capacity and handle short writes.

`/sys/class/misc/ttyBCM/transport_status` reports transferred and queued
byte counts and latches the first transport error until reopen. A write
reports bytes accepted into the queue. The transmit count advances after
the SPI transfer completes, before any response from the hub.

With the revision 10 power pin configured, an on-device, 315-byte
write of read-only SSP chip-ID requests completed over two SSI
transfers. The hub sent no response in that test. The stock patch
bootstrap, power-control ABI and SSP RPC routing still need
qualification before the original daemon can provide desktop sensors.

## Legacy daemon power control

With `expose_legacy_stream=1 expose_legacy_power=1`, the driver exposes
the Korean rev10 board's power controls at the original paths:

- `/sys/class/sec/sensorhub/mcu_power` controls the 1.8 V rail.
- `/sys/class/sec/gps/GPS_PWR_EN/value` controls the independent GNSS
  enable GPIO.

Both accept root writes of 0 or 1. The MCU gate remains asserted
between rail cycles and both pins return to their saved states on
unbind. The opt-in mode requires an explicit rail-on command before
stream I/O. The original raw SSI mode powers its link on open when
daemon power control is disabled.

A same-device #58 trace established the startup order and the
`BBD:PassThru` notifications. An isolated 6.18 trial of the original
daemon reproduced the power sequence and exchanged bytes in both
directions. This first trial stopped at autobaud before reading the
firmware patch. Subsequent controller trials are described below.
The service remains opt-in.

## Read-only SSP initialization probe

With the legacy control, power, stream and firmware reader enabled,
`probe_legacy_ssp=1` adds the exclusive, root-only `/dev/bbd_sensor`
endpoint. On a new `ESW:READY` notification, it queues one
length-prefixed SSP chip-ID request for the original daemon to send.
The probe expects device ID 0x55. It does not enable any sensor
stream or register an IIO device.

On the exact handset, the vendor daemon finished firmware transfer and
returned a CRC-valid SSP chip-ID response using temporary USI8 clock
and microsecond-delay driver trials. The persistent integration still
needs a qualified boot with proposals 0139 through 0141, followed by
sensor RPC routing and IIO consumers.

## Boot integration on Linux 6.18

The SM-G955N root filesystem overlay provides
`g955n-location-hub-mainline.service`. Enable it after installing the SSI
module built against the running kernel, the matching SPI controller
module, and the verified on-device patch file. The unit starts only
with the `g955n.bcm4773=1` boot parameter. The matching board DT needs
proposals 0139 through 0141 and the USI8 SPI compatible from 0140.

The original daemon runs with the vendor and EFS partitions mounted
read-only with journal replay disabled. The service disables the GNSS
enable and MCU rail when it stops. Check live startup by reading
`/sys/class/misc/bbd_control/daemon_status`. The dedicated service was
verified across two normal boots on the integrated SM-G955N image.

## Native IIO accelerometer

With `expose_legacy_accel=1`, the driver registers
`g955n-bcm4773-accel` and exposes the standard IIO raw X, Y and Z
attributes and the physical scale. Reading an axis starts the SSP
accelerometer on demand at a 100 ms sampling interval. The driver
requests removal after two seconds without an axis read. It validates
the BBD transport CRC and response length before decoding a sample.
GNSS bytes and the original daemon's input continue through the
existing SSI stream.

On the opt-in mainline boot, a systemd generator masks the older
Samsung packed-IIO SensorProxy drop-in. Ubuntu's packaged
`iio-sensor-proxy` uses the normal polling backend, with the
SM-G955N display mount matrix supplied by udev. The mainline unit
enables the accelerometer option on boot. The stationary handset
passed the IIO and SensorProxy tests. A physical rotation trial has
yet to qualify desktop orientation transitions.

## Native light and proximity inputs

`expose_legacy_environment=1` adds standard IIO illuminance and
proximity devices alongside the accelerometer. The driver serializes
SSP add and remove commands across these devices. Each sensor starts
on demand and stops after its own idle threshold.

The light input reports lux from the firmware's bypass record. The
proximity input preserves the firmware's near/far decision. Its
primary raw channel encodes far as 0 and near as 2 with scale 0.5.
Ubuntu SensorProxy uses a udev threshold of 1 between those levels.
The separate `in_proximity1_raw` channel retains the sensor ADC count.
No proximity thresholds or light calibration coefficients are written
by this driver.

The integrated handset has passed simultaneous IIO reads and stock
SensorProxy discovery after reboot. Light-level changes and the far
state were observed. Physical near/far transition still requires verification.


## Native motion and barometer inputs

`expose_legacy_motion=1` adds IIO angular velocity, magnetic field,
pressure, barometer temperature, and a step count. The gyroscope uses
the signed 32-bit XYZ SSP layout. The magnetometer uses the calibrated
signed 16-bit XYZ record and ignores samples with its overflow byte
set. The physical scales and axis alignment of these two streams still
require validation, so they expose the firmware's numeric values.

The LPS22H pressure scale is 1/40960 kPa per count and its temperature
scale is 10 millidegrees Celsius per count. No factory pressure offset
is loaded from protected storage by this driver.

Reading the step input starts its on-change stream. It stays active
after the first read so intervals between reads do not discard step
deltas. The IIO counter sums unsigned firmware deltas for the lifetime
of the driver binding. A stationary reading of zero only checks the
counter endpoint. A physical walking trial is still needed.
