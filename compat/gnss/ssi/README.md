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
The original daemon, `ttyBCM` stream, actual patch transfer and
`bbd_sensor` exchange still require end-to-end qualification.
