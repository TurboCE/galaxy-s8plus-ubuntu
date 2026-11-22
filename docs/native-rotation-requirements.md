# Native GNOME rotation source checkpoint

SensorProxy readiness alone cannot qualify automatic rotation. The current
fbdev X driver returns false for RR_GET_INFO/RR_SET_CONFIG and does not advertise
runtime rotations. Its Rotate option is a startup setting. On this modern Xorg
ABI the old xf86DisableRandR call is compiled out, despite a misleading inherited
log message; do not claim all RandR functionality is disabled.

Source review uses Ubuntu's checked fbdev0.5.0 original archive and Xorg
server21.1.12 original archive, each checked against its official .dsc SHA256.
Raw source/build inputs remain under private artifacts/rotation. The relevant
X server legacy RandR hooks are hw/xfree86/common/xf86RandR.c and xf86str.h.
This is basic phone-display work, not HDMI/DisplayPort feature work.

A native runtime-rotation implementation needs all of the following:

* Explicit supported rotations and an RR_SET_CONFIG implementation, while keeping
  the physical framebuffer1440x2960 and its native scanout stride correct.
* Correct logical root-pixmap dimensions/pitch, shadow-copy rotation, full damage
  and rollback when changing between portrait and landscape. Do not merely
  advertise unsupported rotation bits.
* Stable pointer/touch transforms and panel identification to GNOME; correct
  physical touch after rotation must be measured separately from synthetic input.
* Integration with genuine SensorProxy orientation and Ubuntu's rotation lock.
  Existing Mali window-resize tests are useful but do not establish this path.

The stock production path at this checkpoint used the original fbdev driver.

The current accelerated DECON route uses `IDMA_G1` and a fixed-format native
scanout. In the pinned SM-G955N source, `dpp_reg_set_rotation()` in
`drivers/video/fbdev/exynos/dpu/dpp_reg.c` is a stub. A working GNOME route
therefore needs a compositor transform into the existing native-size DMA-BUF
and a matching logical output and input transform. Advertising a DRM rotation
property alone would leave the pixels and touch coordinates unrotated.


On kernel55, real SensorProxy orientation events reached the desktop session.
The live RandR output was `default`, and XRandR rejected a left-rotation dry
run. The standard GNOME rotation-lock setting accepted both values and was
restored. This verifies the setting and sensor path while leaving panel
rotation and touch remapping open.

The pinned Mutter XRandR backend recognizes the `ConnectorType` atom
`Panel` as a built-in monitor. The current synthetic RandR output does not
provide that identification. Mutter's orientation management also requires
touch mode and an accelerometer. Both valid CRTC rotation and built-in panel
identification are required before enabling the GNOME rotation control on
this path. The presenter additionally guards native portrait dimensions and
format, so rotated rendering must still deliver correctly arranged pixels in
the native Mali DMA-BUFs that DECON scans out.


### Mali rotation of native buffers

`compat/compositor-build/x11-rotation-probe.c` uses the existing private
libhybris EGL stack in the owner X11 session. It allocates separate
2960x1440 and 1440x2960 RGBX gralloc buffers, checks the same layout used by the
direct DECON presenter, and imports each as an EGLImage-backed texture. Mali
paints a source pattern and renders both quarter-turns into the portrait
buffer. The probe checks the expected four destination regions per turn.
Pixel readback is used only for the test. Neither gralloc buffer is CPU-mapped.
The probe uses an EGL pbuffer and opens no visible window or KMS scanout.

The actual SM-G955N on kernel55 passed both directions on the Mali-G71, with
the stock phone display session still running. This establishes a GPU path
between the logical and panel-size buffers. The Xorg output transform, touch
coordinate mapping, and submission of rotated frames by GNOME remain open.

### Runtime RandR and direct Mali/KMS trial

The opt-in fbdev module in `compat/fbdev-rotation` publishes a built-in
`DSI-1` output with `ConnectorType: Panel`. It supports the native portrait
and transposed landscape root pixmap with the underlying scanout fixed at
1440×2960, 60 Hz. It applies the RandR transform to shadow damage so that
the greeter and the framebuffer fallback can display either orientation.

Build the ARM64 module with Ubuntu fbdev 0.5.0 and Canonical's matching Xorg
SDK. The build script checks the source archive digest.

```sh
compat/fbdev-rotation/build.sh xserver-xorg-video-fbdev_0.5.0.orig.tar.gz out-fbdev
```

Pass `--native-rotation` to the private X11 bridge builder. In the direct
GNOME path, the bridge reads the RandR CRTC rotation and imports the compositor
DMA-BUF into Mali. Portrait uses the original native buffer. Other orientations
use a Mali draw between native buffers. There is no CPU pixel mapping or copy
in this path. Each rotated target stays in use until its KMS replacement is
confirmed. The GPU pass requires reading the source, writing a second buffer
and waiting for completion.

On kernel57 a separate Xorg drove the real panel in portrait, both landscape
orientations, inverted and back to portrait. All four mapped framebuffer
regions matched the expected colors after every transition. A separate
Mali-G71 test checked the production helper's target pixels and EGL context
restoration. The KMS probe imported those same Mali DMA-BUFs, modeset once and
completed three subsequent KMS page flips, including reuse of the first
rotation slot. The original GDM configuration was restored after the test.

The root-owned trial supervisor accepts `--drm-kms --rotation-driver
PATH --rotation-driver-sha256 SHA256` in addition to the bridge candidate and
its digest. An unconfirmed trial restores the original Xorg files, bridge, manifest and
session launcher on timeout or reboot. After on-device qualification, use
`--confirm-rotation-default` to retain the running trial across boots.
Boot verification checks the Xorg configuration and driver along with the
EGL and session files and probed KMS capability. A mismatch restores the
snapshotted desktop. `--restore` also restores it explicitly.


In the normal GDM trial the actual Mutter greeter recognized the candidate
`DSI-1` as the primary built-in panel and reported
`PanelOrientationManaged=true`. The user GNOME session was not entered during
the four-minute window. The phone restored all five snapshotted files
byte-for-byte, cleared the lease and returned to its original GDM.


A subsequent kernel57 trial used the normal GDM touchscreen and numeric
on-screen keyboard through PAM. The first GNOME quarter-turn exited while
creating the GPU program, although the rotation pbuffer had bound successfully.
Resolving the GLES calls explicitly through the active Mali EGL provider
fixed the failure. The unchanged GNOME Shell then completed all five
temporary Mutter configurations (0°, 90°, 270°, 180°, 0°), with the expected
root dimensions and coordinate transforms on the real touchscreen. The
compositor reported at least 60 retired KMS frames in that session.

An RTC-alarmed system sleep produced kernel entry and exit records about
24 seconds apart. After resume the same boot, owner session, KMS lease, USB
and Wi-Fi were present. A journal query in the original receipt worker timed
out just after resume and the separately attempted on-screen PIN unlock did
not complete. This leaves post-suspend touch authentication open. Sensor-driven
motion, physical touch latency, and permanent activation are still separate
acceptance items.


The first coordinate test revealed that a valid Mutter rotation matrix was
still being scaled by the old portrait desktop bounds inside Xorg. The fbdev
resize now refreshes the server-wide input dimensions. Touch events injected
through the handset's actual evdev device reached their independently
calculated X11 target in all four orientations. After default activation
and a warm reboot, ordinary on-screen GDM/PAM login and the same five
rotation/tap transitions passed again.

The three scripted window-move runs per path reported mean whole-device
CPU use of 16.74% through the original X11 copy route and 9.07% through
direct KMS. All runs saw 179 of 180 requested movements, with a 17 ms median
geometry-update gap on both routes. This measures a scripted workload and
does not establish physical drag latency or panel FPS.
