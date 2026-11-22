# SM-G955N standalone GNSS probe

Build the AArch64 client with `build.sh AOSP_TREE ANDROID_HEADERS OWN_LIBS
OUTPUT_FILE` in the Android 9 build environment. The binary links the
reviewed handset's Bionic libc and libdl. Keep the binary and the owner's
Samsung firmware outside Git.

The SM-G955N GPS library extends the Android 9 AArch64 `GpsCallbacks`
structure with a single-boolean location request callback at byte 96.
The probe registers that callback and records assistance requests. It runs
the ordinary legacy Android GPS interface in standalone mode and emits
counts of NMEA sentences, satellite reports, and location callbacks.

Use `run-probe.py --client PATH --sha256 HASH --seconds 75` as root on the
SM-G955N. It runs the vendor GNSS engine and trial client in the same private
`/data/vendor/gps` mount. This isolates their state from the running
sensor/location hub, so this command is an ABI test. Use Ubuntu Location
Services below to exercise the real receiver through the hub's shared FIFO.

The verified HAL initialized and accepted standalone mode and start. The
75-second trial completed without the previous callback crash and recorded
one assistance request, zero NMEA records, zero location/satellite callbacks,
and a nonzero stop result.

## Ubuntu Location Services

The desktop integration connects GeoClue to `/run/g955n-gnss/nmea.sock`.
The socket admits the GeoClue account and activates the Samsung GNSS engine
on demand. The relay forwards checksum-valid receiver sentences. The vendor
engine and the existing Broadcom location hub share their original
`/data/vendor/gps/.pipe.gpsd_to_lhd.to_server` and `.to_client` FIFOs.
A separate bind-mounted directory breaks this link even when the path of each
FIFO looks identical.

The GeoClue drop-in uses BeaconDB for network positioning and disables
coverage submissions. Network assistance uses recent Wi-Fi results and
available LTE cells from ModemManager, with IP fallback. The lookup runs
while Ubuntu Location Services is enabled. A private short-lived estimate
can seed the receiver, and a synchronized system clock supplies UTC.
Vendor GNSS processes stay network isolated.

`lto.py` adapts the S9 port's GPL-2.0-only downloader for the SM-G955N's own
Android `gps_debug.conf`. It accepts the Broadcom URLs declared in that
configuration, uses HTTPS, and checks size, age and integrity before caching.
The GNSS helper uses the GPS XTRA extension to pass the checked download to
the receiver.

For deployment on this image, install the reviewed client as
`/usr/local/lib/g955n-gnss/hal-probe` and its Python support files alongside
it. Install `run-probe.py` there as `run_probe.py` for the service import.
Place the socket, template, BSP preparation and two assistance services in
`/etc/systemd/system`. Install `80-g955n-location.conf` through GeoClue's
`conf.d` directory, reload systemd, and enable `g955n-gnss.socket`.
Use GNOME's Location Services setting to grant desktop access.


For an offline image, pass the reviewed private ARM64 client to
`python3 scripts/build_rootfs.py --gnss-client /path/to/hal-probe`. The builder
installs GeoClue and time synchronization, stages the client and helpers, and
enables the socket in the image. GNOME retains control of the Location Services
preference. The first request prepares the board's read-only Android ABI paths
and allows time for the location hub to create the shared GNSS FIFO.
