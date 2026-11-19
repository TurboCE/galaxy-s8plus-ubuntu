# Private HWC2 compositor cross-build

Build-only work for SM-G955N/dream2lteks, Android9/API28. Nothing here installs on
or contacts the handset, starts a compositor/HAL, changes a daemon, replaces
system EGL/GL or qualifies GPU presentation. The current GNOME applications stay
untouched. Outputs and original device libraries are private artifacts, not Git
content.

The small existing-compositor route is the pinned Droidian wlroots fork with
HWC2 backend + Android GLES renderer, then its own tinywl example. This is an
alternate compositor candidate, not a GPU backend retrofit for GNOME/Mutter.
The separate Android `libhwc2_compat_layer.so` supplies the ABI expected by
libhybris's glibc libhwc2 wrapper. It still needs the real Android property,
HWBinder/allocator/composer runtime before an exclusive display trial.

## Sources and licenses

`sources.json` pins four public compositor/library commits and archive hashes,
and the additional small Android9 component commits. Existing Bionic/core/
libhardware/native sources and libhybris use the repository's `sources.json`;
HIDL/libc++/hardware-interface versions use `compat/hidl-query-sources.json`.
No full Android tree/Soong build is required: public headers/generated HIDL plus
four HWC2 C++ units link to the owner's matching SYSTEM libraries.

- wlroots: MIT, upstream LICENSE retained in source archive.
- libdroid C library: BSD-3-Clause, COPYING retained; its Debian packaging is
  GPL-3+ and is not used to build/install a Debian package here.
- libgbinder/libglibutil: BSD-3-Clause, upstream LICENSE files retained.
- Android headers/HWC2 adaptation: source-file Apache-2.0 notices retained.
- libhybris has multiple per-file licenses, including LGPL-2.1 and Apache-2.0;
  retain its LICENSE.* files and individual notices when packaging.
- Samsung/Android own-device binaries are private link inputs; this work does
  not establish permission to redistribute them.

## Host-only environment and inputs

The Docker engine used here is amd64. `Dockerfile` installs a native host
compiler/generator and arm64 target development packages. A separate Meson cross
file and cross GCC build Linux/glibc libraries; clang targets Android28/Bionic
for the compatibility layer. Target executables are never run, and all actual
build containers use `--network none` and no device/privileged mounts.

```sh
docker build --platform linux/amd64 -t g955n-compositor-builder:24.04 \
  -f compat/compositor-build/Dockerfile compat/compositor-build
python3 compat/compositor-build/fetch-public.py \
  --output artifacts/compositor-build
docker volume create g955n-compositor-build
```

Keep pre-existing input volumes read-only. This investigation copied only the
already prepared `android9-headers`, public `aosp`/`libhybris`, existing native
hidl-gen, and own link inputs from `g955n-hybris-build` into the new volume's
`/work/input/`. Original source and system-review volumes were not modified.
Public archives are unpacked into `/work/sources`.

Export the pinned Git objects, not a potentially case-collided macOS checkout,
into these additional private paths:

| Private path | Pinned component / selection |
| --- | --- |
| `/work/public/libhidl` | existing Android9 libhidl commit, including transport/token headers |
| `/work/public/libcxx` | existing Android9 libc++ commit |
| `/work/public/libfmq` | pinned libfmq commit |
| `/work/public/hardware-interfaces` | existing Android9 hardware/interfaces: graphics, configstore, media/1.0 |
| `/work/public/frameworks-hardware-interfaces` | pinned frameworks/hardware/interfaces: vr/composer |
| `/work/public/libhwbinder` | pinned libhwbinder: include |

For example, Git archive can stream into a network-disabled container's `tar -x`
under the corresponding `/work/public` directory. `stage-own-libs.sh` separately
reads `/stock/system.img` from the existing read-only
`g955n-stock-system-review` volume. It requires exact model/device/API properties
before extracting the explicitly listed `.so` files and records their hashes.
No calibration/radio/recovery/userdata is read or modified by that script.

## Build commands

With the source/input layout above, bind this script directory read-only and
mount only the dedicated work volume writable:

```sh
docker run --rm --network none \
  -v g955n-compositor-build:/work \
  -v "$PWD/compat/compositor-build:/scripts:ro" \
  g955n-compositor-builder:24.04 \
  bash /scripts/build-hwc2-compat.sh /work

docker run --rm --network none \
  -v g955n-compositor-build:/work \
  -v "$PWD/compat/compositor-build:/scripts:ro" \
  g955n-compositor-builder:24.04 \
  bash /scripts/build-linux-stack.sh /work
```

The Bionic script generates only the needed HIDL headers and compiles HWC2.cpp,
HidlComposerHal.cpp, ComposerHal.cpp and hwc2_compatibility_layer.cpp. libc++'s
wrapper headers precede Bionic's C headers; nativebase and HybridInterface/
hwbinder include roots are explicit. Shared-object linking uses `-z defs` for
its object references and allows the owner's platform shared-library dependency
chains, rather than inventing missing functions.

The Linux script builds/stages libglibutil→libgbinder→libdroid→libhybris→wlroots
and tinywl into `/work/prefix`. Small reviewed Meson patches disable unnecessary
GIR scanning for this cross-build and make already-conditional systemd directory
metadata optional. It stages only libdroid's C library/headers/pkg-config files;
HAL service units are not installed or started. Private `.pc` paths and an
`android/` include alias point to the same real public Android9 headers.

Ubuntu's separate `libwayland-egl-backend-dev:arm64` is required by libhybris's
Wayland platform. libdrm/GBM development dependencies provide common renderer
APIs/FourCC metadata; selecting HWC2 does not imply this kernel has DRM/KMS.
No system loader configuration or global GL library is changed.

Patch 0004 also corrects an actual upstream const-parameter mismatch between
one HWC2 definition and its public C declaration: otherwise the sideband-stream
function exports only a C++ mangled overload. Its HAL call is unchanged. ELF
validation now requires that unmangled C export and every HWC2 call made by the
pinned wlroots backend. The upstream glibc wrapper also advertises
`hwc2_compat_display_present_or_validate`, absent from its Android implementation;
pinned wlroots does not call it. This candidate is **not** qualified as a complete
implementation of every public Hybris HWC2 wrapper entry point.

## Qualification boundary

A completed link is not a runtime result. Check ELF target, SONAME/NEEDED, export
ABI and input/source hashes before any separate deployment review. The Bionic
compatibility layer must stay in a private Android loader path; Linux compositor
and Hybris libraries need process-scoped private search paths. Do not execute an
HWC2 compositor against the display concurrently owned by GNOME/fbdev.

The runtime graphics allocator/composer services, real buffers/fences, a bounded
client-target panel proof, a Wayland application and eventual shell/input/resume
still require independent qualification. The current kernel's unexpected reboot
investigation takes priority over any live graphics trial. These build scripts
perform none of those trials.

## Actual offline result (2026-11-19)

The complete cross-link succeeded in the dedicated container:

| Target | SHA256 |
| --- | --- |
| Android9 Bionic `libhwc2_compat_layer.so` | `ba3898a015dc17b5726c2ca956a6ec30e195ef49e21f725860b1a0a8a2007106` |
| glibc `libwlroots.so.12a` | `b0f4668804bbc3b0c9cd0a7c19a44cdd614c9cdb0f365b09b20c2320c86b78c3` |
| glibc `tinywl-g955n-candidate` | `7ac5444c5ef2f0d6feb45e47b9d53a319fc76bc447d99fd3ef625bd6d59f6b59` |

libdroid, libgbinder/libglibutil and Hybris EGL/GLES/Wayland/gralloc/HWC glue
also built. All six audited final objects are AArch64 ELF and have no TEXTREL;
tinywl is PIE. The Bionic layer exports 28 defined hwc2_compat C symbols. This is a compile
and link result; target executables and shared objects were never run.

One additional source compatibility issue was real: this pinned wlroots calls
`HWCNativeWindowSetBufferCount`, absent from the existing pinned upstream
libhybris. Patch 0003 backports Droidian's actual C wrapper and public method
access from pinned commit 9cfe3f5. It calls the existing buffer-count
implementation unchanged; no return-success stub or wlroots call removal is
used. Original per-file Apache notices remain. Source linkage:
https://github.com/droidian/libhybris/blob/9cfe3f583156881f5971b158011a197ca5a0f6df/hybris/egl/platforms/hwcomposer/hwcomposer_window.cpp#L80

Private evidence: `artifacts/compositor-build/linux-stack-final.log`,
`hwc2-final-build.log`, `final-validation.log`, `build-record.json`, and
`private-compositor-build.tar.gz`. The JSON records ELF NEEDED/search paths,
compiler/packages, source/build-file hashes and own private link-input hashes.
The archive includes upstream license files. It contains no vendor link-input
libraries; those remain separately private.

This is a build prefix, not an installable phone bundle. Generated pkg-config
metadata and ELF search paths include `/work/prefix`; deployment must recreate
or deliberately relocate this private prefix, audit the Linux/Bionic loader
boundary and include the exact needed host library versions. Some examples
and Hybris test binaries are staged by upstream install but none was executed.
`record-build.py` only invokes host readelf/compiler-version/package tools.

After the kernel reboot cause is resolved and allocator/composer initialization
is qualified separately, the smallest compositor proof is this fork's tinywl
with explicit `WLR_BACKENDS=hwcomposer,libinput` and `WLR_RENDERER=gles2`,
whose inspected factory falls back to its Android renderer when there is no
usable DRM FD (the fork does not accept an `android` environment selector),
process-private Hybris/Android search paths, and exclusive display ownership.
That is a reviewed future experiment, not a command these scripts run. A shell,
accelerated GTK/Qt clients, touch, suspend and eventual GNOME interoperation
remain untested. Current GNOME remains installed and unchanged.

## Private runtime packaging follow-up

`package-prefix.py` reads the build volume and packages the selected compositor,
plugins, recursively required private Linux libraries and Bionic HWC2 layer. It
never runs them or contacts a handset. Intermediate symlink targets must be
copied as well as final ELFs; the first native loader check exposed that omission
and it was corrected. The staged HOME prefix then passed native loader-only
dependency resolution. This executes no compositor constructors or backend.
Manifest variables override the build prefix for EGL/linker/plugin searches;
global Ubuntu GL libraries remain unchanged. Physical display ownership and
restoration supervision are still prerequisites for execution.
