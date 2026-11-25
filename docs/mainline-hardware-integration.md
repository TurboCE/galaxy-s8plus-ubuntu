# SM-G955N mainline hardware integration

Live baseline on 2026-11-25: Ubuntu 24.04.5 LTS with
`6.18.0-g955n-usb-r100-vpn2` and the corrected speaker DTB.
Older Samsung 4.4 evidence is in [VALIDATION.md](VALIDATION.md);
it does not qualify a device on the current mainline boot.

| Hardware | Current Ubuntu path and evidence | Remaining live verification or integration |
| --- | --- | --- |
| OLED, GPU and touch | The built-in DSI connector is connected and the active GNOME Wayland process holds the DECON KMS card and Panfrost render node. STMFTS registers a touchscreen. | Brightness control, physical touch and rotation after sleep, and sustained rendering. |
| Panel brightness and ambient light | No backlight class device. The GNOME Power Screen brightness property is -1. | Wire the physical OLED brightness interface to Linux backlight and the ambient sensor to SensorProxy before testing GNOME's slider and automatic control. |
| Buttons and motion sensors | GPIO keys are registered. No IIO devices are exposed. The BCM4773 test driver binds to SPI but supplies no sensor measurements. | Exercise the physical buttons and wake path. Expose accelerometer, gyro, magnetometer, step count, illuminance, proximity and pressure through the appropriate sensor interfaces where present. |
| Audio | PCM 0 is the MAX98506 bottom speaker and remains the default PipeWire output after the GPH3 DT correction. PCM 1 is the microphone and PCM 2 the receiver. Bottom playback and microphone capture were verified acoustically. | Exercise receiver/voice and headset routes through actual playback and recording. |
| Wi-Fi and Bluetooth | NetworkManager reports Wi-Fi connected. BlueZ sees a powered controller with Samsung firmware build 0405. A bounded Adapter1 discovery session received eight advertising peers and stopped cleanly. | Bluetooth pairing and data/audio, Wi-Fi reconnect across sleep and two-band checks on this build. |
| Battery and charging | UPower reports a present MAX77865 battery and charge state. | Measure wired and wireless charging and charge-state transitions. |
| USB and storage | USB Ethernet carried authenticated device queries. The installed Ubuntu filesystem boots from internal UFS. | USB host and accessory operation, and removable microSD read/write. |
| Location | GeoClue returns an approximate network location. Native BCM4773 exposes no GNSS receiver source. | Qualify satellite reports and a receiver fix before enabling a native GeoClue GNSS feed. |
| LTE | ModemManager is active and lists no modem. | Securely bring up the Exynos modem transport, then validate SIM registration and mobile data in NetworkManager. |
| Cameras and iris sensor | No video device. Samsung's board source lists alternatives for the front and rear sensor modules, so the actual variant must be identified. | Qualify capture through the Linux media stack and a standard Ubuntu camera app. Iris functionality needs a separate userspace interface and security review. |
| NFC | The handset's own firmware inventory identifies S3NRN82. Samsung's board DTS shows the I²C address and GPIOs, and the vendor driver controls the NFC supply and an AP clock. The Linux 6.18 S3FWRN5 I²C match table does not include this variant. | Qualify the exact I²C transport, clock and supply before attempting read-only tag discovery. Exposing a controller is separate from card emulation or payment support. |
| Fingerprint, haptics and LEDs | No fingerprint service or LED class devices observed. No haptics event device. | Identify and qualify the actual board interfaces, then prove fingerprint enrollment/unlock, force feedback, and LED output separately. |

The legacy GNSS socket and its daemons require the Samsung 4.4 board-service
stack. On the mainline boot the unit files now match that kernel requirement.
The live root filesystem uses the shipped network-only GeoClue profile. The
previous mixed profile and unit copies are in a private backup on the device.
