# SM-G955N camera and flash board bring-up

The Samsung Korean revision 10 board connects the S2MPB02 camera and flash
power IC to USI10 HSI2C25 at address 0x59. Its NFC and optical sensors share
the other USI10 channel, HSI2C26. Samsung selects both channels in the USI
system register. The mainline DTS fragment `compat/nfc/g955n-usi10.dtsi`
selects the corresponding dual I²C mode and enables both child controllers.

Build the optional `g955n-s2mpb02-readback` module against the running
SM-G955N kernel and load it once for diagnosis. It claims the address
only during the reads and releases it before module initialization returns.
It does not scan other addresses, register a persistent client, enable an
emitter, or change regulator settings. On the handset, the boost
configuration byte 0x90 matched Samsung's revision 1 detection. Reboot
removes the diagnostic module on kernels built without module unloading.

The result confirms communication with the shared power and flash IC.
Camera regulator control, sensor identification, flash output and V4L2
capture are separate checks.

## White torch

Include `g955n-s2mpb02-torch.dtsi` with the dual-channel USI10 fragment
and install `g955n-s2mpb02-torch` for the exact kernel release. Linux
exports `/sys/class/leds/white:torch/brightness` with levels 0 through 3.
The enabled range follows Samsung's ordinary 20, 40 and 60 mA table
entries. The driver reads the enable pin and programmed current to
report brightness. It keeps the high-current flash trigger inactive
and leaves the second illuminator and camera rails untouched.

Boot, shutdown and standby use the kernel LED class. An off request
drops the physical enable and restores the original torch current
selector. Suspend powers the output down and resume restores the
prior level.

## Camera module identification

Include `g955n-camera-rom-id.dtsi` after the torch fragment and install
`g955n-camera-rom-id` for the same kernel. The torch driver provides the
two camera ROM supplies through the regulator framework. It checks both
voltage selectors before registration. The read-only model attributes
are available to root on the I²C and SPI camera ROM devices.

The front device uses USI11 HSI2C28 at address 0x51 and S2MPB02 LDO6.
The rear device uses camera SPI0, with GPC3-1 as active-low chip select,
and S2MPB02 LDO17. Each read enables only the ROM supply it requires,
reads the first five bytes of the stock module header, and disables the
supply. The attributes publish just the model name. The observed front
module is S5K3H1 and the rear module is S5K2L2.

The ROM path supplies the camera module information for this unit. The
sensor clock, power and reset sequence for streaming, CSI receiver and
V4L2 capture path still need their own bring-up.

## Front imaging sensor

Include `g955n-s5k3h1-readback.dtsi` after the camera ROM fragment.
The added driver controls the front sensor on USI11 HSI2C27 at 0x35.
The front EEPROM remains on HSI2C28. The front sensor takes its stock
four rails from the S2MPB02 and a 26 MHz CIS_CLK1 on GPK0-1. GPC0-3
is the active-low reset. The regulator provider applies and verifies the board selector on a
disabled rail at registration and before enabling it. It refuses to
alter a rail already enabled at a different voltage.

The root-only `sensor_registers` attribute checks the powered sensor
model, revision and standby state. Writing `1` to root-only
`stream_probe` applies the stock 1632×918 at 30 fps mode, watches the
sensor frame counter advance and checks the return to standby.
Both operations assert reset, idle the clock pin and drop the power
rails at the end. The probe generates and discards the sensor stream.
A separate CSI receiver and media pipeline are needed to capture pixels
in V4L2.

## Front CSI link check

The checked capture path starts at CSIS1 0x12cb0000. The handset reports
receiver register version 0x03070000. The tested stock front mode
uses two lanes, RAW10, 1632×918 and settle code 7. For the test the
camera bus is raised from its 33.3125 MHz boot rate to 133.25 MHz.
The lower rate produced a CSIS receive overflow before the change.

Build `g955n-csis1-link-test` for the live kernel. The bounded probe
logs when CSIS1 is armed. Start the front driver's `stream_probe` from
a second root process during the reception window. The module checks
frame start and end, the receiver counter, receiver errors, and that
all four DMA channels stay inactive. It restores the receiver, the shared
PHY controls and camera clock immediately afterward. A successful test
reports its result through the kernel log and returns EAGAIN from
module initialization so the one-shot can be repeated without reboot.

`config/mainline618-camera-media.fragment` enables the standard V4L2
and media-controller core for a separate kernel build. The reception
test uses the existing handset kernel and allocates no capture buffers.

## CAM0 frame buffer mapping

The board routes CSIS1 DMA through the normal-world CAM0 System MMU
at 0x12d10000. The handset reports System MMU version 7.0. CAM0 uses
the standard Exynos IOMMU driver plus its board clock gate. The
camera and ABOX attach to separate IOMMU groups.

The CAM0 diagnostic fragment and its two modules check a translated
4 MiB, 32-bit DMA aperture. The test matches all 1024 page translations
against the allocated buffer and verifies that the mapping is removed
when it finishes. The 32-bit end check permits an inclusive last byte
of 0xffffffff. The test performs no camera DMA and records no pixels.

### Stock CSIS1 DMA reference

The 8895 CSIS receiver registers and the CSISx4 DMA common registers
are separate blocks. Samsung's clock tables assign the common DMA
ACLK, asynchronous master and peripheral gates to CAM CMU offsets
0x2078, 0x2038 and 0x2118. The Samsung sensor clock setup includes
both the CSISx4 DMA Q-channel at 0x3028 and its QoS Q-channel at
0x3038. The stock gate logic distinguishes the manual gate value
from the automatic clock-gating bit. The common DMA register window
starts at 0x12ce0000. A gate snapshot alone does not establish that
the common block is accessible.

`clock_status=1` reports the three CSIS1 gates. `clock_register=` selects
one additional, allowlisted CAM CMU register and logs immediately before
and after that read. Both modes hold the camera bus at the same enabled
rate as the link test, then restore the initial rate. Neither accesses
the receiver or runs DMA. They return EAGAIN after a completed snapshot.
Read-only snapshots without the bus hold interrupted handset response.
The bus-held sequence completed on the handset and restored the boot
clock rate after each read.

`dma_common_status=1` reads the shared DMA control while holding the
same bus rate and checking the mux, three gates and both Q-channels.
`dma_common_setup=1` additionally applies Samsung's arbitration,
processing, SRAM split and matrix settings with the receiver idle,
then verifies and restores all four registers. Both modes return
EAGAIN after success. The test leaves the per-channel DMA disabled.

For the front sensor's SBGGR10 mode, Samsung's receiver uses legacy
2D RAW10 storage with the PACK12 flag set and the parallel DMA input.
The stock buffer sizing is `ALIGN(width * 5 / 4, 16) * height`, or
2048 bytes per line and 1,880,064 bytes per frame at 1632×918.
The single-buffer setup points all eight VC0 slots at the same mapped
address. A capture test must confirm the actual format and write
extent, DMA completion and quiescence before returning the buffer.

`capture=1` runs a bounded VC0 test using the stock setup and the
translated CAM0 DMA device. Start the sensor's short `stream_probe`
after `VC0 waiting for first CSI frame with DMA disabled`. The test
checks two DMA completion events, disables VC0 and waits for the
abort acknowledgement before examining the buffer. It verifies that
each of the 918 rows changed and that the memory beyond the expected
frame remains intact. Pixel data is discarded in the kernel. If DMA
stop cannot be confirmed, the test retains the mapping and holds
CSIS1 in reset until reboot.

On the handset the test currently reaches both completion events and
stops the engine, with the entire checked frame still at its initial
value. It returns EIO for that result.

## V4L2 front sensor subdevice

Keep the same front sensor fragment and build the module against the
kernel using `config/mainline618-camera-media.fragment`. The driver
checks the chip ID and CSI-2 endpoint, then registers one V4L2 source
pad for 1632×918 SBGGR10 at 30 fps. The media receiver can query the
two D-PHY lanes and start and stop the stream with the existing sensor
power sequence. Root-only readback shares the stream lock, so a
diagnostic cannot reset an active stream. Suspend is rejected while
the sensor is streaming until the receiver owns suspend and restart.

On kernels without the media core, the module retains the readback
interface. The endpoint is ready for a receiver link and a capture
queue later. The subdevice alone provides no application capture node.

For camera power failures, enable the front module's root-only
`trace_power` parameter and run the existing `sensor_registers` check.
The trace records the supply, clock, reset and I²C steps and the
power-down result. With the retained console DT fragment installed,
include informational messages in the kernel console level during the
test so the operation preceding a hang can be recovered after reset.
