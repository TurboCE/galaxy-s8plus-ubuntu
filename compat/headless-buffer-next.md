# Reviewed headless buffer test, before any display integration

GNOME currently uses llvmpipe/CPU framebuffer presentation. A Mali pbuffer pass
or allocator registration does not make GNOME accelerated. The next small gate
is one real gralloc/ION native buffer, then a headless GPU import of that same
buffer. These candidate sources have been compiled, not executed against ION,
Mali or a HAL. No GDM stop, HWC open, display node, window or present operation
is part of either mode.

Runtime is on hold after three unexpected kernel-22 resets. Kernel 15 and the
original presenter have been restored. No buffer probe was executed; old-boot
review manifests are deliberately unusable on the restored boot.

The earlier read-only identity check found SM-G955N kernel #22,
4.4.111-g955n-ubuntu-experimental and taint0; the exact boot identity and
connection endpoint are recorded only in ignored private evidence. The original SYSTEM
paths were not mounted at /android/system. A future coordinated trial therefore
needs the existing verified read-only stock BSP preparation first. No such
mount, device open or service activation was performed for this preparation.

## Source and ABI

The public Android9 graphics sparse checkout is pinned in hidl-query-sources.json
at hardware/interfaces commit f53f4c35268154fd5e320bb39d772e8a61d200ff.
`generate-headless-buffer-headers.sh` uses the already built original Android9
hidl-gen and schemas for base/manager1.0, graphics/common1.0, mapper2.0 and
allocator2.0. No hand-coded HIDL C++ vtable, full Android build or large NDK is
needed. The existing isolated Linux builder and owner's stock libraries are
used by the two build-only scripts. Native-buffer layout comes from pinned
frameworks/native libs/nativebase/include/nativebase/nativebase.h through the
existing public header exporter; AArch64 sizeof168/common offset0 are asserted.
The public constructor initializes common magic/version, and the plugin sets
all remaining fields explicitly.

## Stage 1: one CPU buffer, only after explicit runtime review

The standalone probe accepts --allocate-only EXPECTED_ALLOCATOR_PID EXPECTED_BOOT_ID.
It first verifies model/kernel/exact boot, private PID/mount provenance, real
NNP, removed dangerous capability bounds, read-only proc/sys/system/vendor,
real ready, the original allocator process command, ION character node and
absence of Mali/display/audio/block/EFS nodes. It requires actual allocator
list/debugDump registration PID matching that process; get() is never called
for an absent listed instance. It uses the declared original passthrough mapper
and rejects a remote mapper, so returned mapped pointers stay in-process.

The mapper creates a 64x64, one-layer RGBA8888 descriptor with CPU read/write
usage. Exactly one allocator buffer is requested, the raw hidl_handle is cloned
using the real HIDL handle ownership implementation, and importBuffer creates
one mapper-owned import. Stride is bounded to 64..4096 pixels, limiting accessed
RGBA memory to at most 1 MiB. CPU lock/write/unlock/fence and lock/read/unlock
must verify every active pixel, excluding padding. Every API status and callback
must be consistent; raw FD/int counts are reported without publishing vendor
handle contents.

Normal cleanup waits for release fences, frees the mapper import, then releases
the cloned raw handle/Fds. A missing/contradictory import/lock callback,
transport ambiguity, unlock failure, failed fence clone/wait, or mapper free
failure does not proceed with uncertain manual free/FD reuse: it logs and exits
21, leaving kernel process teardown to close all FDs/maps. This is an explicit
failure, not a buffers-cleanup success. The future outer supervisor must record
that exit and reap it before stopping the original allocator and manager.
A ten-second process alarm bounds ordinary IPC, with an outer deadline still
required; a task stuck uninterruptibly in a kernel driver cannot be guaranteed
recoverable just by a userspace timer.

The CPU probe has no EGL/Mali DT_NEEDED and never loads our GLES plugin in this
mode. Offline stock mapper implementation and gralloc.exynos5 dynamic entries
also have no EGL/GLES/Mali dependency, and earlier actual allocator maps contained
libion/gralloc without Mali. This is static/historical evidence; future live
maps and opens must still be checked rather than assuming undocumented vendor
dlopen behavior. The CPU mode refuses any /dev/mali0 presence.

## Stage 2: import the allocated buffer into Mali, still no display

The separate --gles-native-buffer PID BOOT_ID PLUGIN mode adds only GPU_TEXTURE
and GPU_RENDER_TARGET usage, permits a private Mali character node, and explicitly
loads the reviewed plugin. The plugin itself has only libc++/libc/libdl DT_NEEDED;
Mali is dlopened lazily inside its one exported test function. Merely linking or
building the executable/plugin does not load the GPU driver.

A one-pixel pbuffer only establishes an ES2 context. The **allocated gralloc
buffer**, wrapped in the public Android9 native-buffer structure with tracked
reference callbacks, becomes EGL_NATIVE_BUFFER_ANDROID -> EGLImage -> texture
-> FBO. Three shader frames alternate colors, wait glFinish and verify FBO
readback. The last frame is checked independently through mapper CPU lock/read,
so the test cannot pass just by rendering to the unrelated pbuffer.
Renderer must identify Mali and reject llvmpipe. No native window, buffer queue,
HWC or present method is called.

The cleanup order is GPU finish, GL objects, EGL image, unbind, context/surface,
terminate, native wrapper, then the caller's mapper import/raw handle. Failed
unbind/destroy/terminate or retained native-buffer references cause process exit
20 rather than freeing a handle that the driver might still use. The plugin is
not dlclosed while vendor thread/TLS destructors may remain. This does not
promise GPU-driver robustness; abnormal exits must be recorded and quarantined.

## Private runtime boundary and remaining controller work

The namespace source has explicit --include-ion-device and
--include-mali-device options. They require --run-trial, Mali requires ION, and
they cannot combine with --include-display-devices. Default remains no hardware
nodes. Only a private ION node (UID1000:GID1000/0600) and optional private Mali
node (root:GID1003/0660) are added; host nodes are not chmodded/chowned. This
source change does not itself start a test or register an accelerated desktop.

The prior no-ION lifecycle controller deliberately rejects ION/extra nodes and
is unchanged. Separate source-only CPU controllers now implement the lifecycle
below; their exact hash manifest still requires review before activation: verified BSP and
source/binary hashes; real property/manager runtime; the original allocator at
UID1000/GID1003/supplementary1026 and actual registration; one CPU buffer probe;
service/query/log/FD-map evidence; stop/reap probe then allocator then manager;
verify registration absence, process cleanup and exact host namespace/mount/
properties restoration. Stage 2 is a separately reviewed device scope, even
though it uses no display. No actual ION/HAL/GPU trial is authorized by this file.

Both C++ targets compiled with Android28 AArch64 Clang, -Wall/-Wextra/-Werror,
public Android9 headers and original own-device libraries; ELF startup arrays
are rejected, and the plugin link rejects unresolved object symbols or implicit
EGL/GLES/Mali DT_NEEDED. Source-level independent review caught and corrected
unsafe failure cleanup before any device test. Shell syntax, Python parsing and
invalid device-option combinations were also checked. Private build records are
under artifacts/hidl-query/; build success is not a hardware result.

After these gates pass, GPU desktop work still needs actual HWC2 output with
correct client-target/fence ownership and a compositor backend using that route.
Replacing system GL libraries or claiming GNOME acceleration from this headless
test would skip the unresolved presentation integration.


## Separate reviewed CPU-only controller (not yet executed)

run-cpu-buffer-trial.py defaults to help. Actual activation requires --cpu-buffer,
root, exact reviewed boot ID, an untainted baseline, a complete kernel-journal
cursor, preexisting canonical read-only BSP and --reviewed-manifest plus the
manifest's explicit SHA-256. The manifest also pins the exact expected boot UUID,
so changing only the CLI boot argument cannot reuse an older approval after a
reboot. The manifest fixes exactly seven executed files:
the outer/inner CPU scripts, old evidence/no-ION helper modules (unmodified),
namespace helper, Bionic runtime and headless buffer ELF. Symlinked, missing or
changed files and incomplete/wrong-scope manifests are refused; hashes are checked
again immediately before namespace launch. make-cpu-buffer-review.py only reads
staged files and writes this review artifact, never a device operation.

The fresh runtime defaults to 50 seconds (allowed 40..60) and includes ION only.
Before any original allocator starts, the inner controller checks real NNP,
capabilities, read-only mounts, allowlisted private dev, exact ION/hwbinder inode
modes/owners, exact boot/model/kernel and actual registration absence. It then
traces the original service at UID1000/GID1003/supplementary1026, finds its actual
traced child PID (not the strace wrapper), verifies credentials/capabilities and
real manager registration PID, and calls only --allocate-only. The service is
bounded to 15 seconds plus termination/reaping grace; the client has its own
10-second alarm and the inner wrapper has an outer deadline. No GLES flag,
plugin, Mali or display node is passed by this controller.

Both service and client have private bounded strace logs covering process/openat/
FD/mmap/ioctl calls. Their actual maps and FD inventories are captured. The client
has two controlled 40ms evidence windows inside its ten-second alarm, before
driver calls and after import; these are observation windows, not a speed test.
Missing required client/allocator maps or empty/truncated traces prevent a full
proof pass even if the buffer itself reports a successful roundtrip. Mali load
attempts and forbidden-node attempts are retained verbatim, including failures;
a Mali library sighting or successful forbidden device open prevents success.

Normal finalization stops the probe group before the service group, reaps traced
orphans using a subreaper, checks actual registration disappearance and no group/
process leftovers, then allows the manager/runtime to finish. The outer records
real readiness/PID/context evidence, kernel cursor delta, taint and boot identity,
and exact host namespace/mount/property/manager/allocator restoration. Raw logs
stay in private artifacts. Kernel fault signatures, a reboot, new taint, missing
kernel-delta completeness or failed cleanup prevent overall success. A blocked
kernel driver can defeat userspace termination; no unproven reboot/rollback is
attempted by these scripts.

Local checks cover altered executable/review hashes, registration PID mismatch,
legacy NNP metadata absence, empty trace rejection and failed Mali-load evidence.
The updated C++ client rebuilt against the correct Android9 ABI. The pending
review manifest and staged files are under artifacts/hidl-query/cpu-buffer-*. No
ION/HAL/device trial has been run by this preparation.


An unexpected subsequent kernel-22 reboot was reported before any CPU ION/HAL
trial or staging occurred. All handset staging and hardware trials are on hold
while the parent investigates prior-boot evidence. Preparation remains offline;
any earlier-boot review manifest must refuse the new boot and is not silently
retargeted. Independent controller review is not yet complete.
