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
