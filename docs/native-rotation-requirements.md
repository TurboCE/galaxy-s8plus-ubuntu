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

No replacement display driver is installed or claimed working at this
checkpoint. Kernel screen-power stability takes priority before changing this
production display path. HDMI/DisplayPort Alt Mode remains explicitly deferred,
including after the two porting projects finish unless newly authorized.

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
