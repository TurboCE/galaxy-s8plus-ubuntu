# SM-G955N automatic brightness

GNOME Settings uses `ambient-enabled` from the standard
`org.gnome.settings-daemon.plugins.power` schema. SensorProxy supplies
calibrated SSP lux samples. The power plugin keeps the normal session, display
blanking and manual brightness controls.

An on-change sensor can report one new light level and then stay silent. The
patched power plugin computes a target when lux changes and lets a 100 ms
timer move the backlight by at most three percentage points per step. Each
step waits for the previous level to appear in the existing backlight
interface. A missing hardware response ends the timer within one second.
The timer stops on manual brightness input, disabled automatic brightness,
display blanking or an inactive session.

Build `gsd-power` from the pinned Ubuntu 24.04 source package
`46.0-1ubuntu1.24.04.1` using `build.sh SOURCE_ARCHIVE_DIR NEW_OUTPUT_DIR`.
Run the script with that source package's build dependencies in an Ubuntu
24.04 ARM64 environment or with the repository ARM64 cross toolchain and
target development packages. The cross build targets the power plugin only.

The offline image builder accepts `--ambient-power-daemon PATH` with a
matching Ubuntu package. The user service launches the built power plugin
from `/opt/g955n-ambient-brightness`. It starts the packaged plugin after
the Ubuntu package version changes, until a matching build is installed.
Removing the drop-in restores package selection at the next session start.
