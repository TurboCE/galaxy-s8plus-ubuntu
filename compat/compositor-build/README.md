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

The explicit panel candidate also applies bounded-present error handling and an
opt-in color-pattern fixture. Failed HWC RPCs or timed-out prior fences terminate
the supervised compositor instead of reusing uncertain buffers. Only
G955N_PANEL_TEST_PATTERN=1 enables the fixture; ordinary tinywl behavior stays
unchanged. The panel coordinator supplies a systemd deadline/restore action and
requires real GPU log/present acceptance plus DECON/DSIM counter progress. These
changes do not by themselves establish successful physical presentation.


### Native GPU-to-panel handoff checkpoint

Kernel24 and the private Android/HWC compositor completed two bounded 8-second
panel-pattern trials. The first clean ownership/IPC trial retained Mali-G71
OpenGL ES3.2, accepted at least60 HWC presents, advanced the two DECON frame
counters by78 each and DSIM by83, and received/waited real present fences.
The test pattern intentionally changes at10Hz; this is not a frame-rate benchmark.
Both trials restored GDM and the native presenter, removed private processes,
retained host mount/property state, boot identity and taint0, and recorded no new
kernel fault signatures. Physical color confirmation is separately pending.
GNOME remains on its original CPU rendering path; a pattern compositor pass is
not desktop/app/touch/suspend qualification or resolution of kernel22 corruption.

Actual failures corrected during these trials:
- Prepared the Android graphics/fb0 alias using the existing native fb0 rdev.
- Supplied a separate private128MiB /dev/shm for17MiB scene buffers; increased
  only the compositor file-size limit from4MiB to128MiB. Logs remain bounded.
- Passed the output from scene rendering through the output-aware renderer
  dispatch; the previous NULL target produced No native window set and invalid
  framebuffer draws. Ordinary modern renderer dispatch remains available.
- Captured original Android log datagrams and obtained a real FMQ CHECK failure;
  syscall tracing proved /dev/ashmem EACCES followed by mmap EBADF. Set only the
  new private Ashmem inode to graphics-group access for the composer scope.
- Exposed the existing private fimg2d node for display scope. A second successful
  run eliminated the prior repeated libacryl missing-device/performance errors.

The coordinator uses exact source/library manifests, a systemd deadline and
independent display restoration. Debugger/tracer runs cannot qualify a panel
pass. Vendor/runtime outputs, syscall traces and device identifiers stay private.
Private evidence: compositor-build/panel-{ashmem,g2d}-result.json, preceding
failure/debug/trace results, output-dispatch-build.log and current-host-tests.log.
Existing optional-extension/property/log-directory findings remain recorded;
no blanket error filtering or fake HWC/fence/property success was introduced.


### Real Wayland client and EGL thread-state fixes

A private Mesa9 es2gears client now completed the bounded8-second trial on
Mali-G71, reporting252 rendered frames/5seconds (50.319FPS) at its300x300 window.
The full1440x2960 HWC output accepted420 presents by7.2seconds, with DECON frame
counters advancing468/467 and DSIM472. Both client and compositor remained alive
until supervised cleanup. Real fences, private process cleanup, unchanged host
state, restored GDM/presenter and taint0/no new kernel fault signatures passed.
No preload, debugger, fabricated seat capability or GL success override was
active in this passing run. This is a short client/scanout proof, not GNOME,
input, app-suite, thermal, suspend or long-term acceptance.

Source fixes and direct evidence:
- RGBX EGLConfig on an always-RGBA Wayland native window caused EGL_BAD_MATCH.
  Patch0008 selects the actual EGL native visual on the hidden Wayland window
  before the original driver validates it; HWC/null platforms are unaffected.
- Original Mesa EGLUT unconditionally destroyed a NULL keyboard for the legal
  initial seat capabilities=0. A real gdb stack and exact source confirmed it.
  Patch0009 guards transitions and repeat-timer ownership; patch0010 reports the
  actual renderer after successful real EGL context binding. These affect only
  a separately built private fixture, not the installed system Mesa package.
- Hybris's get hook deliberately rejects Bionic key0, but direct glibc creation
  could return that valid host key. Native tracing showed successful EGL binding
  followed by lost EGL state at the first glCreateShader and a Mali NULL-state
  failure during drawing. Patch0011 keeps host key0 reserved if allocated,
  returns nonzero Bionic keys and consistently rejects invalid zero set/delete.
  Existing host key0 ownership is preserved. Actual-hook Linux pthread tests
  passed thread isolation/destructors, existing host-zero preservation and128
  reuse cycles; the former create/get mismatch was reproduced separately.
- The actual Mesa keyboard callback passed ASan/UBSan no-keyboard/repeated grant/
  removal/timer ownership checks. Thirty host guard tests and both target builds
  passed. Private runtime manifests pin the client and diagnostics before any
  display change; diagnostic/interposition runs cannot qualify a pass.

Private evidence: compositor-build/panel-client-key-result.json, earlier
client-{visual,debug2,safe-debug,safe-trace*} results, pthread-key-model.log,
keyboard-model/, client-build.log and pthread-key-build.log. GNOME46's source
selects the X11 nested backend for --nested; launching it directly as a Wayland
client of this HWC compositor is not an available integration route. A working
accelerated client/compositor does not silently replace the current GNOME session.

The pinned Mesa archive in sources.json is an optional offline fixture input.
Use build-wayland-client.py --archive <downloaded-pinned-archive> --output <fresh-directory>
in the cross-build image; only seven MIT-noticed source/header files are extracted.
The program is built/hashed, never run or copied to a phone by that script.
trace-client-gl.c is optional diagnosis only: build with the ARM64 C compiler
as a shared object and -ldl. It prints real calls/results without substituting
values. Any reviewed preload run is explicitly ineligible for qualification.
Mutter integration source: https://github.com/GNOME/mutter/blob/gnome-46/src/core/meta-context-main.c


### GTK4 and private working-directory correction

The unchanged system GTK4/Zenity application completed a separately reviewed
20-second HWC trial, reporting actual Mali-G71 binding from the private EGL
library, with no preload or debugger. Client/compositor remained alive, real
presentation/counter progress, namespace cleanup, display restoration, same boot,
taint0 and no new kernel fault signatures passed. Fontconfig errors disappeared.
The ordinary8-second renderer/client scopes remain separate; the20-second scope
requires the fixed hash-pinned GTK client. Host guard tests now total31.

The font errors were not allocation exhaustion or solved by cache alone:
nsenter --wd=/ opens that directory before namespace entry. It retained a
working directory outside the chroot and getcwd failed (also seen in earlier
gdb logs). Fontconfig canonicalizes its relative reject globs and mislabeled
that path failure as out of memory. All property/buffer/panel nsenter entry
points now use --wdns=/, resolved after namespace/root entry. The panel guard
checks actual root/CWD identity and every child explicitly starts at /. Font
cache is separately read-only; no host cache is rewritten.

Enabling GTK4's OPENGL debug flag exposed another upstream diagnostic-only bug:
find_egl_device unconditionally requests eglQueryDisplayAttribEXT even when the
required EGL device-query extension is absent; libepoxy aborts correctly. That
flag was introduced only for this diagnostic and is not part of normal startup.
Normal GTK GPU drawing works without it. Optional private EGL reporting uses
real driver glGetString only after successful eglMakeCurrent, once per thread/
context, preserving results and all capability lists. It supplies the required
renderer evidence without using that unsupported diagnostic route. No fake
extension/device or error-return override was added; the GTK debug-path issue
remains separately recorded, not claimed fixed in the system GTK library.

Private evidence: compositor-build/panel-gtk4-cwd-result.json and preceding
GTK4 failures; egl-report-build.log. The current GNOME session still uses its
previous CPU path. Source for a potential X11 EGL connection was located in
pinned Droidian/libhybris and a public same-GPU S8 reference; neither reference
is device qualification or permission to copy another device's binaries.
