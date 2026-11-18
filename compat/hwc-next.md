# Direct HWC2 bring-up checkpoint

The native GNOME/Xorg session is currently software rendered. Independent live
`glxinfo -B` on the logged-in user's display reported llvmpipe / Accelerated: no;
Xorg uses FBDEV ShadowFB and DRISWRAST. The private Mali offscreen probe separately
passed 300 shader/readback frames at 1440x2960 in 0.668 seconds. Neither result
establishes a GPU accelerated desktop.

`hwc-module-probe.c` is a bounded next step. Compile on the native handset against
the pinned Android 9 headers and the private libhybris prefix:

```sh
gcc -std=gnu11 -Wall -Wextra -Werror -O2 hwc-module-probe.c \
  -I"$HOME/g955n-compat-build/android9-headers" \
  -I"$HOME/g955n-compat-install/include" \
  -L"$HOME/g955n-compat-install/lib" -lhardware -lhybris-common \
  -o hwc-module-probe
```

Use only the process-scoped compatibility environment documented in README.md.
Default / `--metadata` mode calls no hardware-device open, layer, power, buffer or
present method. This mode passed on kernel 11:

- `gralloc.default`: Graphics Memory Allocator Module; module API 0x0001.
- `hwcomposer.exynos5`: Samsung Exynos hardware composer; module API 0x0001,
  HAL API 0x0100; module open entrypoint present.

These are module versions, not proof of the device's HWC2 API version.
`hw_get_module("hwcomposer")` initially returned -ENOENT: stock Android init
normally supplies hardware-selection properties, which the native session lacks.
The probe instead loads the observed own-device module with process-local
`hybris_dlopen`, checks its hardware tag/id and supplies its own dso handle. It
writes no global Android property, configuration or vendor file.

`--open-hwc2` is deliberately separate. It can initialize the display hardware,
so coordinate an exclusive display interval before invoking it. It opens the
composer, checks the device API before interpreting the HWC2 vtable, reads
capabilities/function availability, registers metadata callbacks, waits at most
five seconds for hotplug and queries display configurations before closing.
It does not create layers, set power, enable vsync, enqueue buffers or present
frames. This mode has not
yet been executed; metadata success must not be relabeled as display success.

The installed `libhwc2.so` is a wrapper that loads `libhwc2_compat_layer.so`, which
is absent from the stock phone / private prefix. Merely running the upstream
HWC2 test cannot supply that Android-side library. The direct C vtable offers a
smaller first experiment without rebuilding all Android framework dependencies.
If the device API/vtable validates, the next implementation needs hotplug/config
selection, a gralloc-backed native window, GLES client-target buffers, validate /
accept / present, and correct acquire/release/present fence ownership. Keep the
CPU framebuffer presenter and any other display owner stopped during that test;
restore the working desktop afterwards. Binder/property/TLS dependencies may
still emerge when opening hardware or presenting, despite metadata loading.

Even a successful HWC2 standalone demo would not change GNOME's GLX provider.
Desktop integration needs a compatible accelerated compositor/backend and a
supported EGL/GLES presentation route (or a separate native DRM/KMS/Panfrost
port). Globally substituting the private Android EGL library into the current
Xorg/GLX environment is not a demonstrated fix.
