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
On Linux 6.18, the relay joins the mainline hub's mount namespace and clones
it privately. Hard links preserve the original FIFO inodes in the GNSS
session's temporary cache directory. The stock Android system and EFS remain
read-only. An indoor test verified the NMEA feed and a coarse GeoClue network
estimate. Satellite reception and a GNSS position fix are pending.

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

For deployment, install the reviewed client as
`/usr/local/lib/g955n-gnss/hal-probe` and its Python support files alongside
it. Install `run-probe.py` there as `run_probe.py` for the service import.
Place the socket, template and assistance units in `/etc/systemd/system`
and install `80-g955n-location.conf` in GeoClue's `conf.d` directory. Use
`g955n-gnss-mainline.socket` on Linux 6.18 with `g955n.bcm4773=1` on the
kernel command line. The Samsung 4.4 setup uses `g955n-gnss.socket`, the
BSP preparation service and the legacy LTO download unit. The Linux 6.18
relay can read a valid existing LTO cache and currently does not refresh it.
Use GNOME's Location Services setting to control desktop location access.

For an offline image, pass the reviewed private ARM64 client as
`--gnss-client /path/to/hal-probe` to `scripts/build_rootfs.py`. Include
`--mainline618` for the Linux 6.18 image. The builder installs the
matching socket and GeoClue drop-in when a reviewed client is supplied.
