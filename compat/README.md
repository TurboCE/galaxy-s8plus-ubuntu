# Native Android ABI investigation

Sources and commits are pinned in `sources.json`. `scripts/prepare_compat_headers.py`
exports public Android 9 headers and applies `compat/patches` to libhybris inside
its separate Linux volume. Export metadata records each patch SHA-256. No vendor
firmware or original phone libraries are included in Git.

`scripts/build_compat_native.sh` builds that source only into the handset user's
private prefix. Keep system Ubuntu GL libraries unchanged. First prepare the
own-device read-only SYSTEM paths with `g955n-android-bsp` on the handset.

The isolated probe environment is:

```sh
export LD_LIBRARY_PATH="$HOME/g955n-compat-install/lib"
export HYBRIS_ANDROID_SDK_VERSION=28
export HYBRIS_EGLPLATFORM=null
export HYBRIS_LD_LIBRARY_PATH=/system/lib64:/vendor/lib64
export LIBEGL=/vendor/lib64/egl/libGLES_mali.so
export LIBGLESV2=/vendor/lib64/egl/libGLES_mali.so
```

Use these variables only for the test process. `HYBRIS_ANDROID_API` is not the
SDK override recognized by the pinned source.

`gpu-pbuffer-probe.c` compiles against the private EGL/GLES libraries. It rejects
other phone models and software renderers, compiles vertex/fragment shaders and
checks alternating pixel colors after every frame. Define `GPU_WIDTH`,
`GPU_HEIGHT` and `GPU_FRAMES` at compile time for larger bounded trials.

Observed on native kernel 11: ARM / Mali-G71 / GLES 3.2 r16p0, 300 verified frames
at 64x64 and at 1440x2960, exit 0. The larger run took 0.677 seconds; this is a
short offscreen correctness test, not a display frame-rate benchmark or sustained
thermal result. The running GNOME desktop still uses CPU/fbdev presentation.
HWC/Wayland presentation, desktop acceleration and suspend recovery are pending.

The locale hook fixes a captured SIGSEGV in stock Bionic
`__ctype_get_mb_cur_max`: its pthread TLS layout differs from glibc. It resolves
the same function through host libc, alongside the existing host locale hooks.
This does not establish that all stock Bionic/HAL TLS uses are compatible.
