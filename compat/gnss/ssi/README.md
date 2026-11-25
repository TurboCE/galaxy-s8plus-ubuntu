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
The Samsung BBD control/sensor/patch devices, SSP sensor data and GNSS
receiver output are outside the endpoint's current implementation.
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
