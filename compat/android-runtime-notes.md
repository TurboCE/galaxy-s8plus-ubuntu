# Real Android property/HWBinder trial scaffolding

This work targets the missing runtime dependency observed while opening the own
Samsung hardware composer. It does not make the current GNOME desktop accelerated.
The private PID/mount selftest passed. One real property/HWBinder startup trial
created valid shared property areas, but stock hwservicemanager aborted before
readiness because its original service-context files were missing. Providing the original files through read-only binds enabled a complete
30-second real-service trial; readiness was published by the actual supervised
stock process and independently read through Bionic shared properties.

## Verified without an Android toolchain download

`android-cli-start.c` calls stock Bionic `__libc_init` using the pinned Android 9
CRT ABI. `build-android-runtime.sh` uses existing AArch64 GCC, explicit private
stock `libc.so`, and `-nostdlib`; the runtime/daemon objects have stack protection.
The resulting executable requests `/system/bin/linker64` and has only `libc.so`
as a DT_NEEDED library. Native `--abi-selftest` passed as UID 1000: a real Bionic
`clock_gettime` and `close(-1)` / Bionic `__errno` result were checked. It did not
initialize or write any property area, open hardware, or start a service. No NDK
or multi-gigabyte Android build-tree download is needed for this executable.

`make-property-info.py` produces a 128-byte serialized Android 9 property-info
file. The original parser from pinned AOSP system/core accepted it and resolved
all tested names to its default context and string type. The file contains no
property values and no ready-state value. The old AOSP parser's GNU zero-length
array triggers GCC 13's uninitialized warning; the host-only parser check kept
that warning visible and non-fatal, without modifying its original code.

## Implementation and qualification limits

- `android-property-server.c` uses the real stock Bionic area-init/add/update APIs
  and Android property-service protocol v2. It imports bounded read-only stock
  properties and advertises the protocol version it actually implements.
- It never seeds `hwservicemanager.ready`. Only the actual supervised stock
  hwservicemanager child's credential-checked request may publish readiness.
  Unknown requests, init control messages and HAL autostart are rejected.
- It requires root as private namespace PID 1, an explicit marker, PID/mount
  namespace IDs different from the original supervisor, a fresh read-only procfs
  and private tmpfs property/socket locations before area initialization. The
  outer supervisor retains the host child PID and handles timeout/finally cleanup.
  Parent-death signaling kills namespace PID 1 if the supervisor disappears.
  The trial is bounded to at most 300 seconds and reaps its service child.
- `android-runtime-namespace.py` is inert without `--run-trial`. It prepares a
  small chroot under a private `/run` tmpfs. The runtime has a fresh PID namespace
  and read-only procfs, so host `/proc/1/root` and `/proc/*/fd` are not exposed. Android system/vendor and native
  executable/library directories are bound read-only; `/data` is a new private
  directory. `/sys` is read-only. A new `/dev` exposes standard character and
  Binder nodes, with no block/audio/calibration devices or EFS mount.
- `--include-display-devices` only exposes a small display-node allowlist for a
  separately coordinated future probe; it performs no device open itself.
- The namespace never executes Android init. It does not alter global property
  directories or start vendor audio, radio or sensor services.

Android 9 Bionic creates areas even if SELinux xattr setup fails, while returning
-1 for the labeling error. The controller distinguishes an invalid area from
this diagnostic-only labeling failure via the real area serial and a real
add/read verification. This is not a production SELinux/property-policy setup.

## Root-coordinated next trial

1. Review the scaffolding and stop conflicting hardware-service-manager trials.
2. Stage the generated metadata and built runtime in the handset private build
   directory. Mount the verified own-device SYSTEM read-only using the existing
   guarded BSP helper before entering the trial namespace.
3. First invoke `--namespace-selftest`: it verifies actual private PID/mount/proc
   isolation without initializing a property area or starting hwservicemanager.
   Only then explicitly invoke `--run-trial` with a bounded duration and private
   log capture. Verify that stock hwservicemanager itself sends its ready request and
   that the real shared property can be read from another process in the same
   namespace. Exit zero requires an observed, verified ready publication.
4. Only then, in a separate exclusive display interval, enter the namespace with
   mount, **PID and root** (for example nsenter's --mount --pid --root), run the HWC2 metadata
   open probe with a timeout, and restore the working display services in finally.
5. Hardware composer open may expose further TLS/HIDL/vendor dependencies. There
   is no ready-property override, service-success stub, or assumption of success.

Source references are pinned in the repository's `sources.json`: AOSP bionic
196632fb3c59ebbf1184d791a3e7124dd0c3f22b and system/core
3655b3122e299c619cc42b874077e4952fb5fb21. The implementation uses their public ABI
and format definitions; vendor binaries remain private and are never included.

## Actual kernel-15 trial evidence

The namespace selftest confirmed private PID 1, fresh read-only procfs, no
EFS/block/audio/GPU nodes and no initialized property area. The outer supervisor's
PID/mount namespace IDs and complete mountinfo SHA-256 were unchanged, the child
was gone afterwards, and no host property directory or hwservicemanager remained.

The following real-service trial created Bionic property areas (initial serial
0), imported 131 actual read-only stock properties and started the v2 socket.
Stock hwservicemanager then reported failure to acquire its SELinux service
context handle and exited with SIGABRT. No ready property was seeded or received;
the trial correctly returned failure. The same cleanup/preservation checks passed.
Raw diagnostics remain in ignored private artifacts.

The expected service contexts are in the original Samsung BOOT ramdisk, not the
SYSTEM tree. `extract-stock-service-contexts.py` verifies the exact stock BOOT
SHA-256 and extracts only five selected context files into ignored artifacts.
Two independent extractions matched all hashes. The namespace runner now requires
the verified platform/vendor hardware-service contexts before a real trial and
provides them at their original root fallback paths using file-specific read-only
bind mounts. Neither the original policy contents nor vendor binaries enter Git.

## Completed real-service checkpoint

With the verified original contexts supplied read-only, the corrected collector
completed a 30-second trial (30.669 seconds elapsed), exit 0. Stock hwservicemanager
PID 30 in its namespace sent the credential-checked request; peer PID matched
the supervised child PID. An independent Bionic process read actual shared
`hwservicemanager.ready=true` at global property serial 133. Host PPid/NSpid
metadata identified the same manager process. Kernel Binder debugfs showed that
process attached to the hwbinder context with its live context-manager node.
All five live context-file hashes and read-only mount options matched.

The service child and namespace PID 1 were reaped. No manager/property directory
remained in the host, and the host PID/mount namespace IDs and complete mountinfo
SHA-256 matched the baseline. No GPU, audio, radio or display device was opened.
The prior collector had incorrectly assumed /proc/.../children was present; the
new collector detects that optional vendor-kernel feature and falls back to a
host PPid/NSpid scan, always retains raw logs, and never aborts a trial merely
because optional evidence is unavailable.

This proves the minimal property/HWBinder runtime checkpoint, not HWC open, GPU
desktop scanout, complete Android property permissions or production isolation.
Further daemon/device trials require their own explicitly coordinated interval.

## No-device HWC dependency diagnostic checkpoint

`run-property-trial.py --hwc-open-no-devices` is an explicit optional diagnostic.
It leaves the namespace's display-node option disabled. Only after a real
credential-checked ready request and an independent shared-property read does
it check that EFS/block/audio/GPU/display nodes are absent and /sys is read-only.
It then enters that PID/mount/root namespace and starts one HWC metadata/open
probe under a 15-second timeout (2-second kill grace), with a separate bounded
outer supervisor and raw private strace capture. The probe's namespace PID,
launcher host PID, exit status, output and cleanup state are recorded.

The probe drops SYS_ADMIN, MKNOD, SYS_RAWIO, SYS_MODULE and SYS_BOOT from its
capability bounding set and enables no-new-privileges. It therefore cannot add
missing hardware nodes, remount writable sysfs or request a system reboot.
The hardware service manager/property server remain separate supervised
processes; rejected init/HAL-autostart requests are not converted into success.
This diagnostic does not stop GDM or the framebuffer presenter and never
registers an accelerated desktop as qualified. `passed` and
`property_runtime_passed` refer to the property-runtime/restoration checkpoint;
HWC exit/error and `rendering_qualified=false` are reported separately.

This mode was subsequently executed once under root coordination. The native
probe verified dangerous-capability removal and no-new-privileges using prctl,
verified read-only sysfs/procfs with statvfs, and verified missing hardware nodes
before loading any composer module. Namespace PID 36 reached composer_open and
made real HWBinder version/write-read calls. The previous property busy-spin
was replaced by actual service IPC and one-second futex waits.

The next missing dependency was the unstarted
android.hardware.graphics.allocator@2.0::IAllocator/default service. The real
manager requested ctl.interface_start; the strict property controller rejected
that unsupported autostart instead of claiming success. /dev/ion was deliberately
absent and returned ENOENT. HWC open remained incomplete and timed out at 15
seconds (exit 124); no GPU/display/audio device was opened. The 30-second property
runtime and complete host-state restoration still passed. The private trace was
179,507 bytes, not truncated. Actual allocation/presentation/device trials remain
separately coordinated intervals; this result does not qualify GPU desktop output.


## Offline allocator dependency review and next diagnostic contract

No allocator service was started during this review. The verified own-device AP
SYSTEM image was decompressed in a separate offline Linux review volume. Selected
stock ELF/RC inspection stayed private; no vendor executable/policy was added to
Git. The original stock BOOT hash is already pinned by the context extractor.

The original vendor allocator RC starts exactly
`/vendor/bin/hw/android.hardware.graphics.allocator@2.0-service`, service name
`vendor.gralloc-2-0`, class `hal animation`, user `system`, groups `graphics drmrpc`,
and capability `SYS_NICE`. Its `onrestart restart surfaceflinger` is an Android
init rule, not a requirement to launch SurfaceFlinger in this diagnostic. The
supervisor must not execute Android init, that restart rule, the composer service,
or generic property-triggered service activation.

The original vendor manifest declares allocator 2.0 `IAllocator/default` over
hwbinder and mapper 2.0 `IMapper/default` as 32/64-bit passthrough. The allocator
service ELF needs allocator@2.0, libhidlbase/libhidltransport, liblog/libutils,
libc++, libc/libm/libdl. Its allocator implementation additionally needs libbase,
libcutils and libhardware; strings identify the downstream gralloc module load.
These static dependencies establish no successful allocator registration.

Original BOOT ueventd.samsungexynos8895.rc declares /dev/ion mode 0666, owner/group
system/system (file SHA-256
4c94b8657cb4f7558497cb1a47f7c60ca7274e4a729cb0a921cda14efdaa227e).
Copying that world-writable permission is unnecessary. A future separately
coordinated ION-only diagnostic can expose just the existing character device at
/dev/ion, owned by Android system UID 1000 and mode 0600, in the private dev tmpfs;
no host chmod/chown and no whole-/dev bind. Keep the service's graphics/drmrpc
supplementary IDs 1003/1007 explicit rather than resolving native Linux group
names. SYS_NICE would require a separate assessed scheduling need; it must not
restore SYS_ADMIN/MKNOD/RAWIO/MODULE/BOOT. ION allocation still accesses a kernel
allocator and is outside this quiet checkpoint. Neither its necessity nor its
sufficiency for registration is yet established by a service run. Keep ION absent
in the first dependency-only trial; registration may fail honestly at ENOENT.

The next opt-in diagnostic has the following reviewable scaffold contract; no
executable activation switch is installed until the registration client is built
and verified:

1. Reuse the genuine bounded runtime and verify independent shared readiness,
   child PID/mount isolation, contexts/hashes and readonly proc/sys. Reject any
   EFS/block/audio/display/GPU/ION node; reject an already running allocator.
2. Start exactly one original allocator executable after dropping privileges to
   UID 1000/GIDs 1003,1007, dangerous capability bounds and NNP. Preserve only
   the private namespace property/Binder environment. Record actual child PID
   and maps; bound startup/observation to 10 seconds. No allocate method calls.
3. Query the *binderized* service manager with a minimal Bionic HIDL client:
   defaultServiceManager -> list -> match the exact allocator descriptor/instance
   -> get on that listed instance -> IBase::getDebugInfo. Require the reported
   server PID to match the supervised allocator's namespace PID, plus host
   PPid/NSpid mapping. Require transport=hwbinder from the original manifest.
   Missing registration, wrong PID or IPC timeout are failures. A live process,
   log message or property alone is not a registration check. Never seed ready
   or return fake success for ctl.interface_start; keep unsupported ctl rejected.
4. Finally stop/reap the allocator before the manager; kill after bounded grace.
   Confirm its registration is absent and its child PID gone, then perform the
   existing exact host namespace/mount/property/manager restoration checks.
   Report service startup, HIDL registration and allocation/rendering as separate
   results; this diagnostic cannot qualify GPU presentation.

Pinned Android 9 frameworks/native cmds/lshal/ListCommand.cpp has no --types
binderized-only filter. Its fetch() unconditionally obtains the passthrough
manager and enumerates libraries. Do not substitute default lshal or assume a
newer-version flag exists. The minimal exact-instance query requires public
Android 9 generated HIDL manager/base headers and a matching Bionic C++ build
against libhidlbase/libhidltransport/libutils/libc++; the current small GCC/libc
runtime builder intentionally supplies none of these. Preparing those public
headers/toolchain and verifying the client without any allocator/device calls
is the concrete blocker before a safe executable activation mode. No NDK or
new large source package was downloaded for this checkpoint.
