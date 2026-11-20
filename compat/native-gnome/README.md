# Native GDM / Ubuntu GNOME with Mali-G71

This is the qualified **normal login** route on SM-G955N/kernel24, not a
nested/private trial or a replacement mobile shell. GNOME46 uses GLES2 with
EGL_XLIB and the private Hybris X11 bridge. GDM/PAM, the native user/PID/session
and the ordinary Ubuntu session remain in use. Automatic login stays disabled.
The owner manually authenticated and reached the desktop on 2026-11-19.

Reference: [mur44ev's Galaxy S8 GPU project](https://github.com/mur44ev/postmarketos-samsung-s8-gpu),
pinned e0e971b8be11c28a794d9cb7b6c909a1d09eca0d. Reuse its Android9/X11
and opt-in legacy-property setup. Do not enable its musl TLS-zero or blanket
gralloc-delete quirks on this glibc build; patches11/15 supply the correct
ownership/TLS behavior. Reference licensing is retained in the packaged prefix.

## What the native integration fixes

* Patch21 makes the reference legacy-property setting effective on the pinned
  newer Hybris. Patch22 permits a static own-device property file. Native
  `/system/build.prop` alone lacks the vendor board platform; old Hybris also
  truncates `/proc/cmdline` to1023bytes before the hardware field. Preparation
  merges original SYSTEM/vendor and the **complete actual** boot metadata.
  No service-ready state or invented hardware property is supplied.
* Correct board selection loads `gralloc.exynos5.so`, avoiding the default
  allocator/ashmem fallback. Normal `ubuntu:ubuntu`, its existing video group,
  and existing ion/mali0 permissions suffice. No Android manager/allocator,
  global shared properties, namespace broker or Binder permission changes are
  needed for this session. Earlier shared-property trials are separate tools.
* Patch23 defers gralloc device close/DSO unload while buffer references remain.
  The stock GNOME GLES checker exposed this real exit-order fault: Mali printed
  correctly but late native-window destruction called unloaded gralloc code.
  Actual checker shutdown and explicit pixel-fixture shutdown now pass.
* `session.py` checks root-owned library hashes and runs GNOME's **real** GLES
  helper. It deletes stale X11 acceleration cache atoms before the stock full
  session check; it never forges acceleration or disables that check. GNOME
  exports this session's environment to its ordinary user services. Logout
  cleanup restores activation variables. The existing CPU session is retained.
* The original native X11 presentation transfers GPU buffers through XPutImage /
  CPU copies. The verified kernel50 normal GNOME session now sends its final
  composition DMA-BUF directly to DECON. This is a Samsung-specific path.
  See [direct-output validation](../../docs/gnome-direct-panel-output.md).
  `60-panel-commit.conf` opts into the reference60Hz DECON commit pump, replacing
  the old200ms checksum loop. Empty Samsung fb0/blank reads mean unknown, not
  blanked; explicit blank levels suspend pumping. Actual ioctl counts are
  reported separately from rendering/panel FPS. The legacy mode stays available.

## Build, explicit deployment, verification

Build the pinned X11 prefix with `../compositor-build/build-x11-platform.py`
(patches13..23 selected there), then package with
`package-prefix.py --include-x11 --destination /opt/g955n-native-gpu`.
These build tools do not access a handset. Keep all proprietary inputs private.

On the **verified target**, after original SYSTEM is mounted read-only and the
private prefix manifest/ELF hashes have been checked, install the packaged prefix
root-owned at `/opt/g955n-native-gpu`. Stage `session.py`, `prepare-properties.py`
and `verify-session.py` there, root-owned0755; stage the compiled pixel fixture
as `bin/session-x11-pixel-probe`0755. Install `ubuntu-g955n.desktop` in
`/usr/share/xsessions`0644. Run `prepare-properties.py --prepare` as root.
The generated `device-properties` is own-device metadata: **never commit it**.

For reboot persistence, install `g955n-native-gpu-prepare.service` in
`/etc/systemd/system` and explicitly enable/start it. Its required dependency on
`display-manager.service` runs the checked own-device BSP preparation (SYSTEM
mounted read-only, without journal replay) and regenerates the property snapshot
before GDM. Existing symlinks alone do not mount SYSTEM: this omission caused
`eglGetDisplay` failure and software fallback after reboot. The unit starts no
Android init or hardware service. The original SYSTEM and calibration remain
unchanged. Verify the service and real renderer after a fresh boot.

Run `session.py --check` as ubuntu with the actual native DISPLAY/XAUTHORITY.
Then explicitly run `select-login.py --select-default` as root; it backs up GDM
and account configuration and preserves manual authentication. A GDM restart
ends the current graphical session and is a separate runtime operation. After
successful normal login, run as root:

```
/opt/g955n-native-gpu/verify-session.py --verify --probe-sha256 REVIEWED_FIXTURE_SHA256
```

It checks the actual owner's GNOME mappings (private EGL, Mali, Exynos gralloc,
no swrast), runs three real six-color client/overlay checks and20-sample calendar
checks, and verifies same shell, same boot, taint0 and no new fault signatures.
The normal-session calendar test uses the installed Super+v binding, avoiding
assumptions about scaled top-panel pointer geometry. This is synthetic input;
it does not itself qualify physical touch. Private evidence stays under
`/var/lib/g955n/native-gpu`; no screenshots, logs or credentials enter Git.

After qualification, install the updated overlay `g955n-fb-display` program and
`60-panel-commit.conf` as
`/etc/systemd/system/g955n-fb-display.service.d/90-native-gpu.conf`; reload systemd
and restart only that presentation service. Initial trial used a `/run` drop-in
before persistence. No BOOT/RECOVERY/calibration partition changes are involved.

## Remaining boundaries

The account-row touch repair is tracked separately under `../greeter` and
`docs/greeter-touch-validation.md`: the owner confirmed password/desktop entry
after the repair, without an injected Return. Cold-boot regression is pending. Optional calendar/Thunderbolt/DBusMenu
service warnings remain. Long-term suspend/cold-boot, physical smoothness/FPS,
other apps/APIs and other phone hardware are separate acceptance work. Historical
failed experiments remain in raw logs; passing the final interval does not mean
all historical kernel messages are clean. Stock Ubuntu on Xorg remains available
in the greeter session chooser for recovery; fallback switching is not newly
qualified by this result.


## MIF stability mitigation (separate from GPU acceleration)

`hold-mif-qos.py --hold` and `g955n-desktop-mif-qos.service` hold a per-fd
421000kHz memory-bus minimum on this model. This is a reversible mitigation for
the native-desktop screen-power failures, not a proven corruption root-cause
repair. The CPU governor/idle states and higher bus operating points remain
available; idle power may increase. Deep suspend is not qualified by DPMS tests.
See `docs/mif-desktop-stability.md` for bounded actual evidence and limitations.

The root-owned script goes under `/opt/g955n-native-gpu`; the unit under
`/etc/systemd/system`. Verify model and file hashes, validate the unit and run
actual lifecycle/display-power checks before enabling it. `Type=notify` only
reports ready after kernel acknowledgement. Enabling adds a display-manager
requirement with startup ordering before GDM; it must be active before exposing
the known failing low-bus screen-off path. No partition or OPP edits are needed.
For rollback, first keep the panel on and disable automatic DPMS, then disable
and stop this unit and remove its installed files. Closing the fd (including
SIGKILL) removes only its own QoS vote; other kernel requests are preserved.
