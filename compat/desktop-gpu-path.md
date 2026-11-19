# Desktop GPU path: source-based checkpoint

This is architecture research, not a device change or acceptance result. The
working desktop remains GNOME/Xorg on fbdev with llvmpipe. The separate Mali
pbuffer result establishes GLES rendering/readback, not window composition or
panel presentation. See `hwc-next.md` for the actual HWC/property/allocator
checkpoints; this note does not advance those results.

## GNOME does support GLES, but lacks the current display backend

The saved desktop journal identifies Mutter 46.2. Its actual source has
`gles2=true` by default, an independently selectable `COGL_DRIVER_GLES2`, and
`COGL_DRIVER=gles2` selection. EGL binds `EGL_OPENGL_ES_API` for that driver.
Therefore “GNOME always requires desktop GL/GLX” is incorrect. X11 GLX is the
current software path, not an intrinsic requirement of every GNOME session.
[Build options](https://github.com/GNOME/mutter/blob/46.2/meson_options.txt),
[Cogl driver selection](https://github.com/GNOME/mutter/blob/46.2/cogl/cogl/cogl-renderer.c),
[EGL context API](https://github.com/GNOME/mutter/blob/46.2/cogl/cogl/winsys/cogl-winsys-egl.c).

GLES selection alone cannot accelerate this native session. Mutter's native
renderer uses DRM/KMS/render devices and GBM/EGLStream infrastructure; it has no
HWC2 output backend in this source. Android Mali kbase/ION/gralloc handles do not
become GBM/KMS buffers merely by selecting libhybris EGL. A Mutter HWC2 backend
would require allocation/import, monitor modes, presentation timing, fences,
input/session ownership and client-buffer integration. That is substantial new
backend work, not an environment-variable fix.
[Native renderer](https://github.com/GNOME/mutter/blob/46.2/src/backends/native/meta-renderer-native.c).

GNOME Shell nested under another compositor is also not an immediate shortcut:
Mutter must import the host's supported Wayland buffers and possess an appropriate
nested EGL winsys. The Android `android_wlegl` protocol is not automatically the
standard Mesa dmabuf path. No accelerated nested-GNOME result is established.

## Concrete alternatives

| Route | Source evidence | Assessment for this Android 9 port |
| --- | --- | --- |
| Droidian wlroots HWC2 + Android renderer | Pinned fork `e7f6be5105b009a025b033ab696c34b287011156`, reports wlroots 0.17.4/ABI12a. HWC backend explicitly requires Android headers >=9 and libdroid; links libhwc2 and hybris window/common. HWC2 validates, accepts changes, sets client target, presents and propagates fences. | Strongest existing compositor backend candidate. Build a private minimal example before Phoc/Phosh or Wayfire; match its fork/API rather than replacing Ubuntu wlroots globally. |
| Existing old KWin hwcomposer | KWin v5.20.5 backend uses `hwc_composer_device_1_t` and HWC1 prepare/set. Backend is absent in v5.21.0 tree. | Old HWC1 code is not an Android9 HWC2 desktop solution. Do not begin a large KWin fork for the first panel proof. |
| Weston hybris | No maintained, inspected HWC2 Weston backend was established in this audit. Historical “Weston supports libhybris” references do not prove this device's presentation path. | A generic Weston EGL client/backend switch does not supply HWC2; require a specific pinned backend and fence implementation before selecting it. |
| Existing libhybris HWC native window + bounded GLES demo | Local pinned libhybris `7079712a42ea2754adf747e70c6cc75764c8596e` contains gralloc native windows and an application-provided present callback; its EGL hwcomposer platform is not itself a complete compositor. | Smallest useful panel proof after allocator/HWC readiness. It cannot by itself accelerate GNOME. |

[Droidian HWC dependencies](https://github.com/droidian/wlroots/blob/e7f6be5105b009a025b033ab696c34b287011156/backend/hwcomposer/meson.build),
[HWC2 presentation](https://github.com/droidian/wlroots/blob/e7f6be5105b009a025b033ab696c34b287011156/backend/hwcomposer/hwcomposer2.c),
[Android renderer](https://github.com/droidian/wlroots/blob/e7f6be5105b009a025b033ab696c34b287011156/render/android/renderer.c),
[KWin HWC1](https://github.com/KDE/kwin/blob/v5.20.5/plugins/platforms/hwcomposer/hwcomposer_backend.cpp),
[KWin 5.21 source](https://github.com/KDE/kwin/tree/v5.21.0).

The inspected Droidian HWC2 path calls `hwc2_compat_device_new(false)`. The local
libhybris wrapper still requires the Android-side `libhwc2_compat_layer.so`, so
that dependency and the graphics allocator/HWBinder runtime must be supplied
before claiming the backend can run. Copying only its compositor does not fix
the currently observed allocator wait.

## Small executable next proof

Build privately, without touching system GL libraries: a bounded single HWC2
client-target GLES/native-window test derived from the pinned window callback
and HWC2 sequence. First require successful real allocator/HWC initialization and
a verified display configuration. Then allocate two or three gralloc buffers,
render a known changing pattern with Mali GLES, execute validate/accept/
setClientTarget/present for a fixed small frame count, and account for every
acquire/release/present fence and buffer on every exit. Keep a watchdog and a
finally-restored exclusive display interval. A positive result needs panel
observation plus actual present/fence progression; pbuffer readback is insufficient.

Only after that proof build a private Droidian wlroots tinywl/example target
with HWC2 and Android renderer (the fork's own examples/API). Run one small
Wayland client, verify renderer strings and composition/presentation, then
qualify desktop shell, touch, resize, rotation and suspend. This provides a
real accelerated Ubuntu userspace desktop route without prematurely patching
Mutter or globally mixing Android EGL and Xorg's GLX libraries.


## Private compositor dependency build completed

On 2026-11-19, the isolated host build in `compositor-build/` produced ARM64
libdroid/libgbinder/libglibutil, Hybris EGL/GLES/Wayland/HWC glue, the Android9
Bionic `libhwc2_compat_layer.so`, Droidian wlroots ABI12a with HWC2 backend and
Android/GLES2 renderers, and its tinywl example. No full Android tree or phone
package installation was needed. The small actual Droidian buffer-count API
backport resolves one pinned-Hybris/fork interface mismatch. See
[build provenance and commands](compositor-build/README.md).

This removes the missing HWC2 compatibility-layer/build dependency as a source
blocker. It does not prove graphics services can initialize, buffers/fences can
present, or GNOME is accelerated. All objects are private build artifacts,
not executed on the phone at that build checkpoint. A subsequent private HOME
staging passed native loader-only dependency resolution after fixing intermediate
symlink packaging; no compositor backend has run. Existing GNOME, GL libraries and
services were unchanged. The new unexpected kernel reboot investigation blocks
live graphics trials; allocator/HWC qualification and a bounded exclusive
panel test remain prerequisites before running the tinywl candidate.
