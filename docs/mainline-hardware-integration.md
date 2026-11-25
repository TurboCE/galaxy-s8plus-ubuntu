# SM-G955N mainline hardware integration

Live baseline on 2026-11-25: Ubuntu 24.04.5 LTS with
`6.18.0-g955n-usb-r100-vpn2`, the corrected speaker DTB, and
the integrated BCM4773 transport, and the shared MAX77865
haptic and RGB LED drivers.
Older Samsung 4.4 evidence is in [VALIDATION.md](VALIDATION.md);
it does not qualify a device on the current mainline boot.

| Hardware | Current Ubuntu path and evidence | Remaining live verification or integration |
| --- | --- | --- |
| OLED, GPU and touch | The built-in DSI connector is connected and the active GNOME Wayland process holds the DECON KMS card and Panfrost render node. STMFTS registers a touchscreen. | Brightness control, physical touch and rotation after sleep, and sustained rendering. |
| Panel brightness and ambient light | Standard SensorProxy reports live light changes in lux. The Linux backlight starts before GDM and passed GNOME manual and stepped ambient requests. Post-s2idle brightness writes verified the calibrated S6E3HA6 register profiles. | Controlled changes in external light, optical luminance, and validation with the packaged automatic-brightness service. |
| Buttons and sensors | GPIO keys are registered. The BCM4773 exposes acceleration, light, proximity, gyroscope, magnetic field, pressure, temperature and steps through IIO. Ubuntu SensorProxy sees acceleration, light and proximity, and serves magnetic heading to GeoClue through the standard Compass API. | Physical button/wake, rotation, near/far transition, gyroscope and magnetometer scale and axes, physical compass calibration, and a walking trial. |
| Audio | PCM 0 is the MAX98506 bottom speaker and remains the default PipeWire output after the GPH3 DT correction. PCM 1 is the microphone and PCM 2 the receiver. Bottom playback and microphone capture were verified acoustically. | Exercise receiver/voice and headset routes through actual playback and recording. |
| Wi-Fi and Bluetooth | NetworkManager reports Wi-Fi connected. BlueZ sees a powered controller with Samsung firmware build 0405. A bounded Adapter1 discovery session received eight advertising peers and stopped cleanly. | Bluetooth pairing and data/audio, Wi-Fi reconnect across sleep and two-band checks on this build. |
| Battery and charging | UPower reports a present MAX77865 battery and charge state. | Measure wired and wireless charging and charge-state transitions. |
| USB and storage | USB Ethernet carried authenticated device queries. The installed Ubuntu filesystem boots from internal UFS. | USB host and accessory operation, and removable microSD read/write. |
| Location | GeoClue returns an approximate network location. Native BCM4773 exposes no GNSS receiver source. | Qualify satellite reports and a receiver fix before enabling a native GeoClue GNSS feed. |
| LTE | ModemManager is active and lists no modem. | Securely bring up the Exynos modem transport, then validate SIM registration and mobile data in NetworkManager. |
| Cameras and iris sensor | No video device. Samsung's board source lists alternatives for the front and rear sensor modules, so the actual variant must be identified. | Qualify capture through the Linux media stack and a standard Ubuntu camera app. Iris functionality needs a separate userspace interface and security review. |
| NFC | The handset's own firmware inventory identifies S3NRN82. Samsung's board DTS shows the I²C address and GPIOs, and the vendor driver controls the NFC supply and an AP clock. The Linux 6.18 S3FWRN5 I²C match table does not include this variant. | Qualify the exact I²C transport, clock and supply before attempting read-only tag discovery. Exposing a controller is separate from card emulation or payment support. |
| Fingerprint, haptics and LEDs | No fingerprint service observed. The haptic actuator exposes force feedback through Linux input. The accelerometer detected vibration and confirmed it stopped. Haptics and the three Linux LED class devices ran alongside the BCM4773 hub before and after s2idle. | Measure LED light output, connect and test desktop notification policies if supported, and qualify fingerprint enrollment and unlock. |

The legacy GNSS socket and its daemons require the Samsung 4.4 board-service
stack. On the mainline boot the unit files now match that kernel requirement.
The live root filesystem uses the shipped network-only GeoClue profile. The
previous mixed profile and unit copies are in a private backup on the device.

## BCM4773 sensor and GNSS transport

The Samsung sources under `drivers/sensorhub/brcm/bbdpl/` and
`ssp_bbd.c` establish the dependency on the Broadcom location-hub
daemon. Kernel SSP requests go through `bbd_send_packet()` to
`/dev/bbd_sensor`. Samsung's `lhd` daemon wraps the requests as RPC and
uses `/dev/ttyBCM` to send them over SPI/SSI. The downstream worker
services pending outbound bytes independently of the high-level
`HOST_REQ` input used for pending receive data. A passive wait for
`HOST_REQ` with no BBD client cannot qualify sensor startup.

The [experimental Linux transport](../compat/gnss/ssi/) implements bounded
SSI reads and writes. On-device tests covered power ownership and
idle I/O. The BBD WHOAMI request was transmitted with the Korean revision 10
power gate correctly muxed, but no reply was received. The existing board
daemon requires `ttyBCM`, `bbd_control`, `bbd_sensor`, `bbd_patch`, and
the board power controls before it starts. The first functional test
should exercise the ordinary SSP chip-ID request through the same
transport. Then qualify sensor measurements independently from NMEA or
satellite status before exposing either source to the Ubuntu desktop.

A same-device #58 startup reached `ESW:READY` and returned chip ID 0x55
after the vendor daemon read the original patch and transferred it on
ttyBCM. On 6.18, the opt-in patch reader and inbound control messages
passed separate endpoint tests. The opt-in `ttyBCM` stream also transferred
a 315-byte query across multiple SSI frames with the revision 10 power pin
configured. With the legacy daemon power controls connected, the original
daemon exchanged bytes with the hub. Its initial autobaud sync timed
out while the source clock stayed too high. A controller trial programmed
the USI8 divider and matched the first #58 replies.
[Proposal 0140](../patches/proposals/0140-mainline-sm-g955n-bcm4773-usi8-clock.patch)
applies that clock correction to the kernel and board DT.
[Proposal 0141](../patches/proposals/0141-mainline-sm-g955n-bcm4773-short-spi-delays.patch)
avoids tick-rounded delays during short transfers. The integrated handset
image automatically starts the original daemon using the mainline systemd
unit. Two boots reached ready and the SSP probe returned chip ID 0x55
over the integrated driver. Acceleration, illuminance and proximity
go through standard IIO to Ubuntu's packaged SensorProxy. Simultaneous
stationary readings and D-Bus detection passed. Physical rotation,
near/far transitions, other sensor measurements and a satellite fix
remain unverified.
