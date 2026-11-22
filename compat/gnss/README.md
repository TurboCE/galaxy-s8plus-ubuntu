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
SM-G955N. It runs the vendor GNSS engine and trial client with the same
private `/data/vendor/gps` mount. Both sides can open the original named
pipes. The vendor XML keeps its original namespace and enables only local
standalone testing. The existing sensor/location hub owns the hardware
transport and continues to run throughout the trial.

The verified HAL initialized and accepted standalone mode and start. The
75-second trial completed without the previous callback crash and recorded
one assistance request, zero NMEA records, zero location/satellite callbacks,
and a nonzero stop result. Ubuntu's location service still needs a qualified
hardware data stream.
