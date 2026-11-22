# Hardware validation

Status date: 2026-11-19. Android discovery does not prove end-to-end operation.
Native Ubuntu 24.04 userspace has booted on the phone under systemd.
No row may become PASS from configuration or compilation alone.

Runtime capture tooling exists in scripts/collect_linux.py; it refuses an
unexpected kernel/DT. Stock dmesg was denied and kernel logcat returned no
entries. Thus neither stock nor Ubuntu logs have been certified clean.
Fifty-one host tests pass at the native-GNOME checkpoint; these are tooling checks, not hardware acceptance tests.
BOOT-only trials recovered concrete panic logs: the initial gzip decoder mismatch
was fixed and unpacking succeeded on the second trial. That trial then panicked
in ABOX regcache initialization and failed USB gadget binding. The third trial
with the ABOX ordering and Samsung USB selection fixes reached a native shell
over its own G955N USB serial function. Live identity/uptime/mounts and raw dmesg
were captured, with no kernel panic and taint 0 in that capture. GPU/ION nodes,
two ALSA cards, battery interfaces and WLAN/rmnet interfaces enumerated; these
are not end-to-end feature passes. Initial-console and firmware errors and
unsupported-syscall diagnostics remain. A later verified installation replaced
USERDATA and BOOT under the owner's authorization. First Ubuntu status reports
systemd running, zero failed units, Ubuntu login and successful growth to 113 GiB.
The first Ubuntu raw-log audit has 285 error-priority and 1811 warning-priority
lines; this includes vendor informational messages at incorrect priorities and
real issues. It is not a clean-log result. No global severity filter is applied.

| Feature | Android baseline evidence | Ubuntu acceptance test | Ubuntu status |
| --- | --- | --- | --- |
| Boot / storage / USB recovery | ADB authorized, stock 4.4.111; partition names readable | Repeated cold boot, logs, ext4 read/write, recovery path | FAILED stability: kernels22/24/25/26/27 suffered unexpected reset or hard hang. Last verified running kernel27 passed13 desktop DPMS cycles then hung; a later greeter boot also stopped responding. BOOT backups/full readbacks and protected-partition hashes were verified before authorized installations. Kernels28/29 build/pack but are not deployed; proposal32 is object-tested only. No current SSH/USB-console response. See kernel26-power-investigation.md and compiler-reference-comparison.md |
| Display / touch | SurfaceFlinger active; input proc access denied | Correct resolution, touch coordinates, rotation, brightness | PARTIAL: persistent GDM account-tile repair passed owner-confirmed account touch, password and desktop entry after reboot on26, without injected Return/autologin. Native1440x2960 works; later27 actual PAM login also succeeds remotely. Screen-power hard hangs remain; physical touch latency, dynamic rotation and automatic brightness are unqualified |
| GPU | Mali-G71, r16p0, GLES 3.2 renderer | EGL renderer Mali/Panfrost, actual rendered frames and sustained workload; reject llvmpipe | The verified kernel36 build defaults to GNOME Mali-to-DECON DMA-BUF output. GDM touch login, fullscreen and repeated display off/on passed before and after a warm reboot. Physical response latency and full suspend remain open |
| LTE data | Telephony service dump collected privately | SIM registration, mobile-only DNS/HTTPS, reconnect after suspend | Kernel36 reports modem OFFLINE. Native modem boot and modem-control integration are pending; owner reports no SIM |
| Calls / SMS / VoLTE | No call/message test performed | Incoming/outgoing calls with two-way audio, SMS, carrier IMS registration | Not tested; no SIM |
| Wi-Fi 2.4 / 5 GHz | Framework dump collected privately | Separate association + traffic test on both bands, reconnect | Partial: three explicit disconnect/reconnect cycles per band, each with bound-interface TLS HTTP 200 and 254968-byte download at 2467/5745 MHz; original profile restored, same boot. Full suspend/resume pending |
| Bluetooth | Framework dump collected privately | Discovery, pairing, audio and reconnect | Kernel36 BlueZ discovery received 18 BLE advertising reports with the ROM/H4 controller; firmware/pairing/audio/resume pending |
| GPS / GNSS | Location service dump collected privately | Fresh fix through Ubuntu Location Services | Kernel55 field trial passed through GeoClue with 144 receiver fixes and 246 satellite reports. GeoClue reported a best accuracy estimate of 1 m. Independent position error and repeatable time-to-fix are unmeasured |
| Accelerometer / gyroscope | LSM6DSL listed by sensorservice | Live samples respond to motion; units, axes, timestamps | Kernel36 streams both through IIO. GNOME uses SensorProxy for accelerometer orientation, previously verified against controlled poses. Physical gyroscope response and axis calibration remain open |
| Other sensors | LPS22H pressure listed; full sensor list private | Magnetometer, pedometer, proximity, light and calibration | Kernel36 reads magnetic and light records and a zero step total while stationary. GNOME's light response passed a controlled shade trial on kernel32. Compass calibration, actual step increase and proximity remain open |
| Cameras | Camera service dump collected privately | Front/rear preview, capture, video, autofocus and flash | Not tested |
| Audio | Audio service dump collected privately | Speaker, earpiece, microphones, headphone jack and routing | Kernel36 GNOME playback and primary microphone capture passed through scoped RDMA0 and WDMA1. Audibility, microphone acoustic quality, other inputs/outputs and suspend recovery remain open |
| Charging / battery / thermals | Power service dump collected privately | Current/voltage/temp telemetry, controlled charge and thermal limits | Not tested |
| CPU scaling / idle | No measured Android baseline | Both cluster frequency response, idle residency, unchanged governor and thermal policy | Partial: bounded CPU0/CPU4 load completed, both frequencies changed and both idle states advanced, policy unchanged, peak observed 54 C. Battery draw/full thermal/suspend qualification pending |
| Suspend / resume | No Ubuntu evidence | Measured idle draw, wake sources, repeated resume with radio/GPU recovery | Not tested |
| NFC / fingerprint / iris | No end-to-end baseline tests | Device enumeration and actual sensor/service operation | Not tested |
| USB OTG / external display / SD | No end-to-end baseline tests | USB/SD hotplug and read/write; external display explicitly deferred | USB OTG/SD not tested. Owner explicitly deferred HDMI/DisplayPort Alt Mode feature work until both core ports finish and a new user instruction authorizes it; no automatic resumption |
| 5G NR | Unsupported hardware | Not applicable; do not confuse with 5 GHz Wi-Fi | Not applicable |

Samsung Pay/Knox and proprietary Android apps are not Linux peripheral drivers;
their availability cannot be guaranteed by hardware enablement.

Later bring-up evidence: physical console text was confirmed by the owner during
an explicit unblank/scanout test while keeping fb0 open. Closing the fd disables
the panel in the Android-oriented DECON release path. A correction is built;
normal boot persistence and GNOME login remain pending. Ubuntu Desktop packages
are installed with a temporary CPU/fbdev presentation path. This is not GPU
qualification. Short-power-key logind shutdown is temporarily disabled after
previous-boot journals proved it caused repeated charger-connected restarts.

Desktop failure isolation: installed packages are not desktop acceptance. Kernel
10 repeatedly panicked in fimc_is_ixs_video_querycap while WirePlumber enumerated
camera nodes, including with GDM/presenter disabled. Patch 0011 fixes five stale
QUERYCAP driver-data casts; build passes, hardware regression pending. Temporary
WirePlumber masking stops that trigger and is not a camera or audio fix.

Kernel 11 checkpoint: owner confirmed physical manual login and desktop using
touch/on-screen keyboard. Former ISP QUERYCAP panic does not recur in the five
explicit node probes or re-enabled WirePlumber/GDM startup. Existing V4L2 bad-caps
and format-description WARNs remain (taint 512); no clean-kernel acceptance is
claimed. Hardware GPU EGL probe still faults in the private compatibility prefix.

Independent hardware audit also observed CPU0/CPU4 ondemand frequency changes
and WFI/deeper CPU idle residency. This does not qualify system suspend, power
consumption or peripheral resume. Kernel 11 still has real audio/VTS/ISP issues
and taint 512; candidate fixes must be retested on a fresh complete boot log.

Overnight checkpoint: no audible tests, microphone capture or user motion/pairing
requests while the owner sleeps. Code/native metadata tests may continue. Kernel
15 had one captured Abox SysMMU panic during broad audio probing; global/user
WirePlumber masking is only isolation. A privately installed patched ALSA plugin
and hash-guarded UCM scope passed install/read-only checks. A bounded 30-second
gdm trial loaded the private plugin, retained Speaker Gain 0 and exposed only
Off/HiFi, no Pro Audio/capture profile. Nevertheless its kernel interval contains
211 special PCM/backend/VTS events. No reboot occurred, but this disproves complete
probe isolation; default WirePlumber stays masked and audio cores were stopped.
The current running kernel is not the newly built audio-ownership candidate.
Fresh image overlays preserve the same global mask; a build cannot silently
reactivate unrestricted stock probing.

Android graphics dependency checkpoint: a real stock hwservicemanager set its
own ready property through the Bionic property server in a private namespace;
separate-process reads and host mount/process cleanup passed. A subsequent HWC
open diagnostic reached real HWBinder but timed out waiting for the absent
graphics allocator 2.0 service. Its automatic start request was rejected rather
than acknowledged artificially. No ION/Mali/display/audio/block nodes were
exposed. This diagnoses dependencies, not accelerated desktop output.

Stabilization checkpoint: patches 0022–0025 correct binary I/O error propagation,
framebuffer offset mapping, success-message priority, and PHY-clock lookup/bounds.
Their integrated BOOT candidate passes build/image checks but has not been
deployed; do not attribute these fixes to running kernel 15. The camera
firmware-selection lifecycle, L2 timeout recovery and full PCIe clock-failure
unwind remain unresolved. Current and previous kernel evidence is saved privately
with hashes; persistent journaling is installed without hiding priorities.

The installed v2 audio scope additionally requires verified control/PCM INFO,
rejects unvalidated endpoints, and resolves PCM through independent configuration
instead of user-overridable aliases. A 21-second muted trial exposed Off/HiFi and
the speaker sink; traces in both policy and core opened only pcmC0D0p. Both mapped
the same reviewed private module. No microphone samples or playback samples were
sent, no reset occurred, and the test services were stopped. Default policy stays
masked pending broader qualification; this is not kernel DMA-fault acceptance.

Later graphics runtime checkpoint: original allocator startup and exact HWBinder
registration/termination passed after private inode permissions were corrected.
Host namespace/process/property state was restored and host hwbinder permissions
were unchanged. This used no ION/GPU/display/audio node and called no allocation
method; it does not qualify desktop acceleration or camera/audio drivers.


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


### X11 bridge, ownership repair and GNOME GPU startup

The owner confirmed the repeated red/green/blue pattern on the physical panel.
The optional private X11 bridge then passed48 every-pixel color readbacks, a
96x64 to128x96 resize, two EGL initialization/termination cycles and full buffer
teardown on Mali-G71. Real Xwayland/HWC presentation, private process cleanup,
restored GDM/presenter, unchanged host state, same boot, taint0 and no new
kernel fault signatures passed. It uses GPU drawing with synchronized CPU
XPutImage transfer; zero-copy presentation and desktop performance are not
qualified by this result.

Only six LGPL-noticed X11 files are selected from the hash-pinned public
mur44ev/postmarketos-samsung-s8-gpu reference, with its MIT modification license.
No reference musl/linker/gralloc/kernel/firmware patches or foreign binaries are
imported. Patch0013 adapts the current native-window ABI, bounded real fences,
actual XVisual/channel conversion, resize/format checks and display lifetime.
Patch0014 extends the private window-system callback table; packaging rejects
mixed old/new plugin ABIs. Real driver config validation precedes X visual
translation. Default builds do not enable the optional X11 route.

An actual local-handle double free was traced to the common gralloc1 release
branch. The Android gralloc1 contract and the owner's driver disassembly agree:
locally allocated handles are deleted by the driver; imported handles require
manual deletion only without RELEASE_IMPLY_DELETE. Patch0015 also preserves
ownership on failed release. An ASan/UBSan model of the actual branch passed all
eight local/imported, capability and error combinations; the original branch
reproduced real ASan use-after-free. No blanket capability quirk is used.

GNOME46 itself subsequently passed a20-second bounded X11 compositing-manager
startup on Mali-G71/GLES3.2, with a real high-priority EGL context, GNOME Shell
started message, live Xwayland/compositor, HWC/counter progress and all outer
cleanup/restoration/kernel guards. The first trial stopped because its private
environment lacked the real system bus. A second exposed Xwayland's inherited
4MiB file limit during RandR resize. The reviewed GNOME-only scope now binds
the actual native system bus socket, supplies a private monitor configuration
and allows128MiB framebuffer files for Xwayland, as already done for tinywl.
A socket bind is actual IPC access, not read-only IPC. Other scopes cannot
enable this access. All new private child PIDs are cleaned, including DBus
activation children outside the initial process groups.

This is a startup/presentation checkpoint, not a finished accelerated login
session. Current ordinary GNOME remains on the CPU path. Touch forwarding,
application compositing, full-size performance and normal session integration
remain pending. PID namespace versus native Polkit/logind identity causes
authorization warnings in this test; calendar registry, portal/FUSE/PipeWire,
DPMS and optional service warnings remain recorded, not hidden or claimed fixed.
The gralloc repair is separate from the unresolved old kernel22 corruption.

Validation:33 host guard tests, actual-branch ownership sanitizer model and
final incremental X11 cross-build passed. Private evidence: panel-owner-repeat,
panel-x11, panel-gnome, panel-gnome-x11 and panel-gnome-x11-sized result JSONs;
x11-platform-final-build.log, x11-host-tests.log and
gralloc-ownership-model-final.log under artifacts/compositor-build/.


### Real touch, full-panel geometry and physical popup coherency

The owner confirmed the physical RGB pattern, then a720x1480 GNOME desktop
scaled by the parent to the1440x2960 panel with real touchscreen interaction.
The60-second interactive trial recorded13 actual contacts delivered with
nonzero Wayland serials. The actual Mali-G71 client also passed six complete
window-to-GNOME-overlay pixel comparisons. This is an experimental standalone
GNOME session, not permanent GDM integration or all-feature acceptance.

Patch0016 forwards genuine touchscreen down/motion/up/frame/cancel events, keeps
contact motion on the original surface, tracks device destruction and advertises
only currently present touch/keyboard/pointer devices. The private scope exposes
only the sysfs/rdev-verified sec_touchscreen event0, root-only, with an unchanged
copy of its real udev record on a private read-only metadata mount. A hash-pinned
Ubuntu seatd0.8.0-1 executable brokers actual input descriptors; its package is
only extracted privately, with no host package/service activation. No uinput or
synthetic touchscreen device is used. XTest actions in the separate pixel/UI
fixture are explicitly synthetic and cannot qualify physical input.

Patch0017 offers a process-private2x output scale. GNOME initially rejected the
private monitor configuration because xrandr's two-decimal refresh rate lost
precision, then selected the advertised5120x2880 preferred mode. The owner saw
cropped content and unresponsive controls despite16 real touch events. The
controller now derives the precise rate from actual pixel clock/totals; the
next trial retained720x1480 and the owner confirmed geometry and basic touch.
GNOME60 requires the fixed client, reviewed native bus/input/broker and actual
delivered contacts, with enlarged bounded runtime/independent restoration.

Two genuine X11 producer defects were also repaired: patch0018 reports unknown
retained contents as age0 instead of the hardcoded age2; patch0019 presents real
queueBuffer submissions in submission order, validates ownership, waits actual
cancel fences and avoids reading a loaned cached buffer on a no-submit swap.
Actual-method ASan/UBSan checks passed out-of-order submission, duplicate/foreign
rejection, cancellation and no-submit retention. The old methods reproduced a
wrong-buffer presentation. These repairs alone did not cure physical flicker.

The owner's calendar popup still alternated with its old background even while
automated GNOME-overlay samples were stable. The final fault was downstream:
one wlroots swapchain token wraps an EGL surface that rotates native buffers,
but the modern scene path used only the outer token's history. Patch0020 reads
the renderer's native history after binding, including unknown=0, before
computing repaint damage; Android's unjustified age+1 adjustment is removed.
Modern renderers without this hook retain their own swapchain history. An
actual-selection sanitizer model reproduced background/popup alternation with
the old path on its second native frame and passed eight alternating frames
with the fix. The owner then confirmed the calendar remains visible without
flicker on the real panel. X11/internal-only checks had missed this final stage;
that earlier result is not presented as physical popup qualification.

Automatic popup checking and owner checking are separate modes: the owner mode
never opens/closes the calendar automatically. The fixture retains Xlib
extension libraries until XCloseDisplay, fixing its own diagnostic teardown
fault. Xwayland no longer advertises MIT-SHM on this SYSVIPC-disabled kernel;
Wayland SHM transport still works. Private namespace cleanup includes all new
child PIDs, including session-service activations outside initial process groups.

Validation:38 host guard tests, X11 submission/native-history sanitizer models
and final target builds passed. Private evidence: panel-gnome-{composite-final,
touch,interactive,touch-final,scaled-mode,submission,popup,native-history}-result
JSONs and corresponding manifests/build logs under artifacts/compositor-build/.
The ordinary login session still uses the prior CPU path pending normal-session
integration. The pre-existing account-row touch-activation workaround, native
Polkit/session identity, optional calendar/portal services, long-term stability
and other hardware features remain open; no blanket error-free claim is made.


Native-history follow-up: the completed60-second trial passed actual pixel
composition, five genuine delivered contacts, private cleanup, host-state
restoration, same boot/taint0 and no new kernel fault signatures. Bounded live
reports directly showed swapchain age1 while the bound native EGL buffer age
was3 (and0 during initialization). This confirms the history mismatch on the
actual device; the fix uses the genuine3 rather than forcing permanent full
redraws. The owner confirmed the physical calendar remains steady. The
ordinary GDM/CPU session was restored after the bounded experiment.


### Host-PID GNOME session precursor

A separately reviewed20-second host-PID GUI trial passed actual Mali-G71 GNOME
startup, six client/overlay pixel checks,20 stable popup samples, both private
and host-GUI cleanup, restored display services and no new kernel faults.
Only Linux GNOME gets a separate mount namespace and a fresh read-only procfs
using real host PIDs; the Android manager/HAL/compositor retain their private
PID/proc view. Capability sets are all zero and no-new-privileges is verified
before the fixed unprivileged command. Parent-death cleanup, source/ELF pins,
unit deadlines and independent restoration remain active.

The root broker uses an inherited private socketpair with actual descriptor
passing/process status. Host cleanup rechecks the unique GUI mount namespace
and unit cgroup before signaling each process; it cannot scan-kill the native
or Android mount namespace. Failed setup logs remain in the result. The first
setup exposed util-linux propagation on a chroot directory that is not a mount
point; unchanged propagation plus the actual private proc mount fixed it.
Native Polkit requests no longer refer to nonexistent namespace-local PIDs.
Actual PAM/local-session authorization, optional services and permanent GDM
integration are still pending. No permission result is overridden.

Validation:42 host scope guards passed. Private evidence:
compositor-build/panel-host-gnome-proc-result.json and preceding setup failures.
The ordinary native X server is independently confirmed at1440x2960/depth24;
its direct X11 EGL route remains an additional integration option to verify.

## Ordinary GPU GNOME login checkpoint — 2026-11-19

The owner authenticated manually through GDM into Ubuntu GNOME46; the installed
session was ubuntu-g955n, ordinary UID/GID1000, native seat0/X11, with real PAM.
Actual GNOME renderer: Mali-G71. The process maps the private EGL library,
libGLES_mali and gralloc.exynos5; swrast is absent. No global Android properties
or Android graphics daemon is needed. Three consecutive six-color client/overlay
and20-sample calendar-stability trials passed with the same shell/boot, taint0
and no new kernel fault signatures during the passing interval. The original
real GNOME GLES helper, including teardown, exits0 after the gralloc-lifetime fix.
Panel commit intervals reached1798–1800 requests/30s; do not interpret these as
measured rendering FPS. Presentation remains XPutImage/CPU copying. Physical
smoothness, long-term suspend/cold-boot and broad application/API tests remain
separate. The CPU GDM greeter still needed a Return key to reveal its password
prompt. Earlier failed checks/kernel-userland fault messages are retained and
not filtered from history. Private evidence: artifacts/native-gpu/*-probe.log,
*-gles-preflight.log, real-session-keyboard-check.log and target session JSONs.


## GDM touch / boot prerequisite repair checkpoint

Owner-confirmed account touch, password entry and desktop login now pass with
the GDM-only account-tile re-entry repair; ten event fixtures pass. Cold-boot
regression remains pending. This replaces the prior Return-key workaround.
The same login exposed missing original SYSTEM mount after reboot, so that
shell used the real software fallback. Requiring read-only preparation before
GDM restores a real Mali-G71 GLES helper pass; a fresh GPU session still needs
verification. See greeter-touch-validation.md. These bounded passes do not
qualify kernel stability or remaining peripherals.


### Kernel26 reboot / manual GPU login checkpoint

Kernel26 with proposal29 was built and installed to BOOT only. Whole-partition
readback passed; RECOVERY/EFS/CPEFS/RADIO hashes remained unchanged. Its config
matches kernel24 exactly (normal CPU idle); ramdisk/DTBH bytes match the prior
working image. Live build26, cpuidle off=0 and taint0 were verified after reboot.
GPU preparation completed before GDM and original SYSTEM is ro,norecovery.

Five actual DPMS off/on cycles returned suspended/off then active/on with the
same boot and taint0. The owner then confirmed smooth password entry and desktop
entry after reboot using touch. The ordinary GNOME shell reports Mali-G71,
loads private EGL/Mali/Exynos gralloc and no swrast. Three actual six-color
client/overlay plus stable-calendar trials passed with the same shell/boot,
taint0 and no new fault signatures in that interval. All54 host tooling tests
pass; extracted DPP lifetime/power-race tests pass separately.

This is bounded acceptance, not long-term stability or clean-log completion.
The raw initial kernel audit still contains vendor error-priority messages and
real open driver/compatibility issues. Sensor/audio/LTE/rotation/brightness goals
remain open. Private evidence: artifacts/panel-safety/{install-receipt.json,
power-cycles26.json,normal-login26.json,session26-verification.log,
kernel26-initial.raw,kernel26-initial-audit.json}.


### Later kernel26 power failure

The preceding kernel26 bounded passes remain their actual intervals. A later
GPU-desktop power trial hard-hung; after manual recovery, a second repeated DPMS
trial also hard-hung without physical input. Kernel26 is not stability-qualified.
See kernel26-power-investigation.md for retained RCU fault-site evidence, KASLR
handling, live host capture and the unqualified primary-QoS proposal30.


### Offline fault attribution / recovery source check

The matching-image decoder passes14 scope/relocation/input-preservation cases.
It decodes actual kernel27's stack-check caller as the secondary safe handler
and rejects damaged kernel26 input. Proposal32's actual disabled-logging
watchdog path and eight enabled CPU paths pass sanitizer fixtures; the actual
AArch64 object builds without changing kernel29. This is an inactive recovery
source proposal. No new device pass, clean-kernel claim or primary corruption
fix follows from these tests. See panic-decoder-and-safe-recovery.md.


### Restored28 diagnostic floor / corrected30 staging

Following the29 builtin-codec recovery, the ordinary GPU desktop on restored28
completed100 actual DPMS off/on cycles with a bounded421000kHz MIF PM QoS vote.
Every sample observed runtime suspended/active and DPMS off/on; same boot,
taint0. The per-fd vote was released on completion and min_freq stayed208000.
This is a diagnostic pass only; the earlier no-floor28 hang remains a failure.

The fixed GCC7 builder produced30 with genuine legacy-LZ4 builtin156 bytes.
Its actual linked payload was also decompressed and parsed as newc. Source patch
hashes/config and external ramdisk/DTBH match28. Fresh full28 backup and protected
hashes preceded30's BOOT-only write; full readback and all protected comparisons
passed. Boot and no-floor runtime acceptance remain pending at this checkpoint.
Private records: artifacts/ondemand-safety/{mif-qos-power100.log,
packed30-receipt.json,install30-returned-receipt.json}.


### Corrected30 runtime failure / reversible QoS service

30 booted and authenticated through actual GDM password PAM. Three ordinary
Mali GNOME composition/popup trials passed, same shell/boot, taint0. The default
bus-policy DPMS trial completed nine cycles and stopped during the tenth off
operation. Owner confirmed automatic reboot to GDM. Matching retained logs show
an invalid indirect request callback in blk_finish_request through UFS/SCSI
completion; the initiating corruption writer remains unidentified.

On the recovered same30 kernel, a per-fd421000kHz MIF-floor trial completed100
cycles with real runtime/DPMS state checks, same boot and taint0; its vote was
released. The explicit systemd holder passed unit validation and actual stop,
SIGKILL request-count cleanup and restart-readiness checks. Longer intervals and
reboot persistence are pending. No clean-kernel or full stability pass follows.
See mif-desktop-stability.md. Private lifecycle and power records remain ignored.


The installed holder also passed10 further desktop DPMS cycles with five-second
off/on intervals, including actual off-frequency421000kHz samples, same boot
and taint0. Enabled its ordered display-manager requirement and requested a
deliberate reboot for persistence qualification. That reboot result is pending
at this checkpoint; no sensor/audio/modem/rotation completion is inferred.


### Sensor recovery candidate / ABOX integration build

The SensorProxy prototype now persists root-private original-state journals
before sensor mutation. Added a boot/device/lock-checked recovery helper,
firmware/read-only calibration preparation and an example stop/start drop-in.
Nine root-owned isolated recovery cases pass (including preserved foreign bits,
failed-write retry and untrusted/stale records); its real AArch64 build passes.
These pieces remain uninstalled; physical sensors and abrupt-termination cleanup
on the phone are not yet qualified.

The diagnostic builder can now explicitly add reviewed ABOX fixes17..20,
recording the choice in its plan. Candidate31 builds and packs with actual LZ4
builtin verification and the same config/external ramdisk/DTBH as30. The only
extra source patches are those four audio ownership/bounds/locking fixes. No
new BOOT write or audio runtime pass is claimed at this checkpoint.


### Installed31 and signal-wait holder

Fresh independent full30 backup preceded BOOT-only31 replacement. Full readback
and unchanged RECOVERY/EFS/CPEFS/RADIO/PARAM/MISC passed.31 boots with the holder
active before GDM, three ordinary Mali GNOME composition trials pass, and owner
confirmed normal touch password/desktop entry. Actual holder CPU ticks stayed0
for5seconds in do_sigtimedwait; normal termination exited0 and SIGKILL released
its request. An independent guard vote prevented a floor gap during that test.
The runtime policy remains a mitigation, not a kernel corruption fix. Earlier
long-on state failures and the later three60-second off/five-second on30 pass
are distinguished in mif-desktop-stability.md.


### Actual31 sensor capture and SSP sysfs defect

Genuine MCU initialization, read-only original calibration and bounded native
accel/gyro/magnetic/light/step0 records succeeded on31. SensorProxy discovery
worked but actual claims failed; the requested user motion trial yielded no
acceptance data. Both real IIO poll_delay reads were empty. Original show/store
callbacks always returned0, including stores that changed the RAM period.

Patch0026 fixes the counts and unknown-index errors. Extracted original/fixed
functions reproduce/pass under address/undefined sanitizers. The rebuilt backend
rejects empty/non-numeric snapshots before mutation; actual31 negative testing
verified unchanged mask/FIFO/scan/current-period state and no residual lease.
Real IIO rules now request service activation. Candidate service remains stopped
pending32 (same31 chain plus0026), which is building. See
ssp-sysfs-return-counts.md for the failed claim's period-restoration limitation.


### Kernel32 live SSP, brightness and desktop acceptance

32's only source addition over31 is0026; config and external ramdisk/DTBH match.
Actual builtin codec, fresh independent full31 backup, BOOT readback and all
protected-partition comparisons passed. On reboot the native MCU, SensorProxy
and QoS holder start automatically. Actual poll_delay reads/writes work and the
native accel/light claims run. Original calibration initialization preserves EFS.

Owner-confirmed tilt/cover actions produced real SensorProxy orientation changes
and2..189 reported lux. Concurrent read-only backlight capture observed31 distinct
values over1091..11961 raw units. This is bounded automatic-brightness response,
not absolute photometric accuracy. The standard ambient-enabled setting roundtrip
and a five-second constant-brightness off interval were checked/restored; a
separate physical shade-under-off acceptance remains open.

Known upright and left-edge-up poses originally reported bottom-up/right-up.
Changed the measured mount matrix to diag(-1,-1,1); the same maintained
left-edge-up pose then reports left-up. This fixes sensor orientation, not the
still-missing dynamic display rotation backend. Actual SIGKILL of the daemon
restored both complete journals, original masks/FIFO/scan/period settings, and
removed its leases; the service then restarted successfully, same boot/taint0.

A first32 pixel fixture ran behind a genuine screen lock and failed visibility,
without a kernel exception. The verifier now refuses locked/unknown visibility
before any fixture. After owner unlock, all three actual Mali GNOME trials pass.
With a real owner-session idle inhibitor and the MIF mitigation,100 further
actual desktop DPMS off/on cycles passed, same boot and taint0, with native
sensor enable masks recorded. The inhibitor is transient, not an authentication
or permanent power-policy change. Core corruption without the mitigation,
long-term/deep-suspend, audio, modem and physical step/heading work remain open.


### System Monitor install and measured refresh cost

Installed Ubuntu ARM64 gnome-system-monitor46.0-1build1 and confirmed its real
owner-session visible window, Mali/private EGL/Exynos libraries and no swrast.
Included the package in the reproducible image and set the default graph update
to1000ms instead of the package's100ms. Existing user preferences remain editable.

A five-second visible100ms observation used about23percent of all8 CPUs; the
minimized interval was about5percent. A preliminary1s result was invalid because
the window remained iconic and is excluded. After normal application activation,
verified unlocked/visible/panel-on before and after, the same1s view measured
10.18percent overall (kernel1.35percent), versus22.78percent visible baseline.
Per-process percentages use one core as100, unlike the whole-device percentage.
GNOME composition and the app load Mali without swrast, but final X11/fbdev
buffer transfer still has CPU copies; no zero-copy or FPS qualification follows.
Private measurement logs remain under artifacts/system-monitor-*.

### Native GNOME drag baseline

On kernel32 with the ordinary unlocked X11 GNOME session, three drag trials
requested 180 pointer positions each. Each trial observed nine test-window
position changes. Whole-device CPU busy was 20.28–21.29% and median intervals
between geometry changes were 279–300.5 ms. Same boot and taint0 were checked.
These measurements are for the existing CPU transfer path. The direct output
path and before/after improvement are pending.

### System Monitor refresh default restored

At the owner's request, restored the package default of 100 ms. The owner
preference was reset on the SM-G955N and a readback confirmed 100 ms. The
image no longer overrides this key. System Monitor remains installed.

### Direct panel submission build check

The AArch64 DECON helper and a fixture extracted from the pinned kernel
compiled with warnings treated as errors. The fixture checked structure sizes,
the source offset and accepted format enum values. No panel ioctl, on-device
direct presentation or before/after drag measurement was performed.


### GNOME direct-panel trial

Connected the ordinary GNOME Shell's full-screen RGBX overlay output to the
primary Samsung DECON display through its real DMA-BUF. Fixed the aligned
ioctl payload and verified member offsets against the pinned vendor header.
Wait for the previous buffer's release after queuing a replacement on the
DSI timeline. During the explicit trial the old framebuffer pan honors the
same exclusive lease. Kernel32 advanced real retire fences and primary panel
frame interrupts, with taint0. The three-by-three same-boot GNOME drag A/B
measured16.04% to11.15% overall CPU busy and501.5ms to33ms window-coordinate
median update intervals. See gnome-direct-panel-output.md for scope and
measurement limitations. The supervised trial restored the ordinary output.

On kernel32, three direct-output DPMS off/on cycles suspended and resumed
the DECON runtime device. The active GNOME Shell PID and boot ID were
unchanged. Each resumed workload advanced the DECON timeline and taint
stayed 0. A separate controlled reboot with the tracked trial armed restored
all three original file hashes, cleared trial state, and brought up GDM and
the legacy panel service on the new boot. Extended uptime, cursor rendering
and system suspend are still open.

The extended direct-output test passed another 18 off/on cycles on the
real device with the same GNOME process, unchanged boot and taint0.
Each cycle processed additional DECON work after resume. The trial
restored the original output.

### Shared DPP DMA registers

The recovery boot still reported six failed requests for the same DPP
DMA common register range. All seven channels declare that range. The
old probe tried to claim it once per channel and treated the mapping error
pointer as usable. The channel start path can access those common registers.
Proposal0032 reserves and maps the shared range once, validates each
channel's range, and propagates errors for the per-channel mappings.
It also clears the published channel pointer on probe failure and lets
devres release the allocation. The kernel33 AArch64 build and built-in
initramfs check passed with kernel32's config and identical Korean DTB.
Kernel33 is a build candidate. Runtime hardware acceptance remains open.

### Persistent GNOME direct output

Installed the persistent Mali-to-DECON configuration on the SM-G955N and
verified that boot recreated the lease. Replayed touchscreen contact events
on the actual evdev device to select the GDM owner and type the credential on
the screen keyboard. The real PAM session and direct GNOME Shell started.
This is software event replay through the touchscreen path. Digitizer
response needs separate physical acceptance.

Eight post-boot DPMS off/on cycles on the first persistent configuration
resumed with new DECON work, unchanged boot and shell, and taint 0. Nine
workload samples over 260 seconds remained active before a deliberate
redeploy. Fixed opaque fullscreen X11 clients bypassing the GNOME overlay.
After the correction and another reboot, repeated touchscreen login passed.
The fullscreen fixture reported zero empty overlay samples and 170 new
DECON timeline points. Extended operation after this correction is pending.

Full system suspend remains open. The original image masks the systemd
sleep targets. A bounded freeze test temporarily unmasked them, requested
an RTC wake and then lost both network and USB console. Host-side USB
re-enumeration did not recover the handset. The test included timer and
next-boot policy restoration. The last kernel suspend stage is unconfirmed.

The S2MPS17 parent IRQ carries the nested RTC alarm on this board. Source
review found that the late suspend callback calls enable_irq_wake() and
then disables that parent IRQ. The generic suspend-to-idle path relies
on wake-marked IRQs remaining available. Proposal0033 keeps the wake
line enabled and returns errors from wake setup. The AArch64 kernel34
build, built-in initramfs check, and comparison with kernel32's exact
config and Korean DTB passed. This is a candidate. The RTC alarm and
actual no-transport failure still need a hardware check after recovery.

### Recovered suspend failure and kernel35 staged diagnostics

After a physical restart and USB reconnect, recovered kernel32's previous
journal and Samsung last_kmsg. The journal confirms system suspend entry.
The retained buffer contains late-suspend completion, HSI2C transmit
timeouts, a noirq failure and early-device resume. It contains an S2MPS17
RTC alarm interrupt and repeated FTS touch messages waiting for PM resume.
The final panic is in Samsung's deliberate hard-reset key hook. The retained
buffer has corruption and gaps. It cannot identify the first failing
callback or prove that the alarm caused normal resume.

For the HSI2C timeout, the controller's address field selects slave 0x36
on 10970000, the MAX77865 fuel gauge address on this board. The caller
was not preserved in the buffer. Proposal0034 marks the existing ordered
battery workqueue as freezable, retaining reclaim semantics and resuming
queued jobs after thaw. Kernel35 also enables PM_DEBUG and PM_SLEEP_DEBUG
for bounded freezer/device/platform tests. The AArch64 build, built-in
initramfs and BOOT pack checks passed. The Korean DTB and external ramdisk
are byte-identical to kernel32.

Saved and verified the full kernel32 BOOT and a fresh set of seven
partitions in TWRP. Differences from the older EFS and PARAM references
were confined to eight EFS superblock bytes and an appended normal/recovery
boot-history string respectively. Kernel35 was written to BOOT only.
Protected partition hashes matched immediately before and after the write.
Kernel35 booted Ubuntu with taint 0. Its deliberate version mismatch made
the direct-output boot service fall back to the original output during
this kernel trial.

On kernel35, the five-second freeze-processes callback test returned in
5.16 seconds with errno 0, same boot and taint 0. The bounded device test
temporarily lost the host transports. After the screen became responsive
and USB reconnected, live suspend statistics showed two successes and
zero failures. The persistent journal then confirmed that the device-stage
test had completed in 5.24 seconds with errno 0, in the same boot as the
freezer test. The original timeout report reflected transport loss.

The device-stage journal contains a Broadcom DHD PCI-state warning during
suspend. During later USB recovery, the DWC3 gadget also warned on an endpoint
command and returned a run/stop timeout before the next successful
enumeration. These logs confirm two separate driver observations. The
device-stage test ends before late/noirq or actual system sleep, so the
platform stage and a timed low-power interval require separate evidence.
The full kernel32 rollback backup remains available.

A separate kernel35 bounded platform-stage test was scheduled through
verified Wi-Fi while USB was also available. Both transports stopped
responding during the test. After a physical power cycle, the previous
boot's service journal showed the start without a result. Its kernel
journal recorded suspend entry; its last entries were in ABOX runtime
power-down. The retained Samsung buffer also contained older boots and
provided no matching platform-test completion. The last printed callback
does not identify the first failing component. This test remains
unqualified. No further system-suspend test was run.

Reentered verified TWRP and restored the full known-good kernel32 BOOT
from the fresh backup. Full BOOT readback matched the backup; the
protected partitions matched their immediate pre-write hashes.

After returning to kernel32, reinstalled the default GNOME direct-output
configuration and rebooted. The boot guard regenerated the lease, all
installed hashes verified, GDM and the framebuffer service were active,
and taint was 0. System sleep and suspend targets remained masked.

Replayed touchscreen events through the actual input device and the GDM
on-screen keyboard. Normal PAM login reached GNOME and the restored
direct path reported 60 completed DECON frames. The panel was active and
taint remained 0 in this bounded check.

### ABOX power-down follow-up on the kernel35 base

The latest platform-test journal ended around ABOX runtime power-down.
Review of the driver found two lifetime defects independent of the log tail.
It cut DSP/clock power before waiting for the GIC handler, which reads the
GIC registers. It also repeated shutdown on an inactive device and called
enable outside runtime PM accounting, although a PM notifier already releases
and reacquires the runtime reference around sleep. Proposal0035 drains the
IRQ after final IPC and before power removal, guards repeated disable, and
keeps the notifier as the owner of that system transition. The recovered
journal cannot prove this was the first failing callback.

On the restored kernel32, SensorProxy and ModemManager answered service
queries. IIO exported accelerometer, gyroscope, light, geomagnetic and
step-counter devices. Bluetooth was inactive in the snapshot. WirePlumber
remained masked, and ModemManager reported no modem. Device enumeration
alone does not establish calibrated motion or pedometer accuracy. This
checkpoint also leaves dynamic screen rotation, acoustic speaker and
microphone operation, mobile data/calls, GPS and Bluetooth pairing/reconnect
open. The earlier bounded auto-brightness and two-band Wi-Fi results stand.

Kernel36 builds from kernel35 plus proposal0035. The AArch64 build and
linked initramfs check passed. The kernel35 configuration and Korean DTB
match byte for byte.

Verified a fresh full kernel32 BOOT backup and protected partition hashes
through TWRP, installed kernel36 to BOOT only, and verified readback.
Kernel36 booted with taint 0. The bounded freezer-stage test returned in
5.13 seconds with errno 0, the same boot and taint 0. Its trace shows the
ABOX GIC IRQ being disabled before the DSP is powered down, then runtime
resume, GIC initialization and DSP power-up after the test.

The next bounded platform-stage request again lost the two host
transports and USB-console response. No completion record was retrieved
in the observation window. Full system suspend remains disabled, and
the platform result must be read after the S8+ becomes accessible.

### Ubuntu-native hardware staging

The rootfs builder can stage the already verified Samsung SSP
SensorProxy backend and the scoped ALSA plugin into their normal Ubuntu
service paths. Sensor staging installs the matched backend, udev
matches, runtime recovery helpers and service override together. GNOME
uses its ordinary SensorProxy D-Bus API for orientation readings and
ambient light. Xorg runtime output rotation remains a separate task.

Speaker staging verifies the pinned Ubuntu ALSA plugin and reviewed
candidate against the build record. Both the PipeWire core and
WirePlumber must have the reviewed launcher before the installer
removes the default WirePlumber mask. The ordinary ubuntu user service
then supplies the single reviewed RDMA0 speaker PCM to GNOME Sound.
There is no microphone or extra PCM in this scope.

A disposable Ubuntu package snapshot passed both staging cases using
the actual AArch64 SSP daemon and the reviewed scoped ALSA build.
Missing audio input left the WirePlumber mask in place. This is an
offline packaging check. SSH and the S8+ USB serial console remained
unavailable, so the staged changes were not applied to the phone.

The rootfs uses NetworkManager for Wi-Fi, BlueZ for Bluetooth and
ModemManager for supported modem control. The builder now explicitly
enables ModemManager. This does not supply a Samsung modem transport,
a calibrated compass/step integration, a Bluetooth firmware load,
a GNSS data source or a microphone driver path.

### Live native services on kernel36

After reconnect, the ordinary system SensorProxy D-Bus interface returned
HasAccelerometer and HasAmbientLight true, orientation normal, and a 20 lux
reading. ModemManager was active and returned no modem despite the kernel
exporting eight rmnet interfaces. These interfaces do not provide a
ModemManager-compatible Samsung control transport.

Installed the native BlueZ ROM/H4 attachment service using the previously
observed ttySAC1 at 115200 with flow control. It sets the original address
only in the uniquely matched UART controller RAM, with EFS mounted read-only
and no recovery replay. The built-in controller appeared in BlueZ and was
powered. Enabled the unit as a Bluetooth service dependency. A matching
firmware load, pairing and reconnect are still unqualified.

The guarded WirePlumber trial in the owner GNOME session exported the normal
internal speaker sink. No physical microphone was exposed. This graph
enumeration alone did not establish actual PCM playback.

The normal Ubuntu WirePlumber/PipeWire graph linked the speaker stream, but
its default S32_LE/MMAP PCM did not advance the RDMA0 hardware pointer.
The bounded trial stopped and restored the earlier mask. Added a rule for
the exact built-in speaker sink to use 48 kHz S16 and read/write access.
With the reviewed UCM speaker gain and that rule, normal GNOME WirePlumber
and PipeWire started, the two-second playback completed, and RDMA0 moved
through 21 distinct observed hardware positions. Both engine scopes stayed
within the reviewed private ALSA module and kernel taint stayed 0. Left
the desktop services enabled. Actual audibility and microphone capture
are separate acceptance tests.

The bounded WDMA0 microphone probe initially failed to configure a backend.
The pinned ABOX graph routes SIFM0 to WDMA1. Corrected the WDMA0 diagnostic
to select UAIF0 through NSRC0, RSRC0 and RECP PIFS0. On the device it then
negotiated 48 kHz S16 capture, but returned EIO with zero captured frames
and a stationary hardware pointer. The ABOX GIC count did not advance
during the bounded read. The diagnostic restored the mixer state and
kernel taint stayed 0. Microphone remains outside the desktop PCM scope.

### Kernel36 hardware retest

The regular GNOME PipeWire speaker completed another two-second stream and
showed 21 distinct RDMA0 hardware pointer positions. Physical audibility
remains unverified. BlueZ entered discovery for eight seconds and returned to
idle without a controller error, but reported no peers in that window.
NetworkManager was associated at 5745 MHz and received all three replies from
the default gateway over the Wi-Fi interface. ModemManager listed no modem.
SensorProxy exposed the accelerometer and reported 24 lux. GNOME's standard
automatic-brightness setting was enabled during the reading.

The active microphone snapshot showed DMIC1, the codec bias and transmit
chain, UAIF0 and the WDMA0 route powered during capture. The kernel logged
both WDMA0 and UAIF0 start triggers. Reducing the period to 1024 frames,
bypassing SPUM ASRC0, using mmap and enabling automatic RECP rate selection
each left the hardware pointer at zero. The standard read returned EIO and
the mmap test timed out. Starting simultaneous silent 48 kHz stereo playback
also left capture at zero while RDMA0 advanced through 38 distinct positions.
Every trial restored the controls. The remaining failure is past ALSA route
selection. Whether samples reach the ABOX DSP and whether WDMA0 starts a
transfer are still unverified.
The kernel remained on the same boot with taint 0 during these checks.

### Kernel36 native microphone and modem diagnosis

The mounted stock Android mixer selects UAIF0 into NSRC0 for AP recording.
Its base controls route NSRC0 via SPUM ASRC1 and SIFM0 to WDMA1. With that
route and the stock codec HPF setting, a bounded native ALSA read delivered
48,000 frames with 36 distinct hardware-pointer values. Both channels carried
the same primary-microphone signal. The recorder kept samples in RAM and
restored the touched mixer controls.

The v3 private ALSA module and HiFi microphone route were installed in the
standard GNOME session. `pw-record` used the default internal source, with
48 kHz S16 interleaved read/write access, 34 distinct WDMA1 hardware-pointer
positions and 520,192 bytes captured during a bounded three-second trial.
The ordinary PipeWire speaker completed two seconds and showed 26 distinct
RDMA0 positions afterward. Successful PCM opens were confined to card 0,
device 0 playback and device 9 capture. The boot stayed unchanged and taint
stayed 0. Listening quality and microphone calibration were not measured.

The modem driver's read-only state was OFFLINE. The SIPC nodes and network
interfaces are registered before the modem boots. The stock image contains
Samsung's CP bootstrap daemon and RIL, and static inspection of the daemon
shows paths into modem boot and NV storage. No bootstrap was run. ModemManager
still needs a compatible control transport once modem boot is implemented.
See [ModemManager port detection](https://modemmanager.org/docs/modemmanager/port-and-device-detection/).

A separate nine-second BlueZ discovery trial returned 18 BLE advertising
reports at the HCI layer and restored idle discovery state. It did not
observe classic inquiry results or attempt pairing.

A 12-second native SSP trial returned 64 accelerometer, 64 gyroscope,
58 geomagnetic, seven ambient light and one step-counter record, with
increasing timestamps in each multi-record stream. The stationary step
total was zero. Restored the original sensor settings, restarted the
standard SensorProxy service and verified its accelerometer and light
properties on the same boot with taint 0.

### Kernel36 direct display boot retest

On normal boots the verified direct-output configuration passed real GDM
PAM login via replayed touchscreen events, including the on-screen keyboard.
It passed eight checked screen off/on cycles before and eight after a warm
reboot. Each cycle waited for agreement between X11 DPMS and kernel panel
runtime state, then verified new DECON work and unchanged boot and shell.
Fullscreen remained composed and kernel taint was 0 during the checks.
The active configuration was left enabled. These are display-power checks,
not whole-system suspend. Kernel logs still showed panel command failures
in earlier rapid transition tests.

### Kernel36 device suspend and Broadcom candidate

The devices-only kernel PM test returned EBUSY after 0.38 seconds. The
per-device trace identifies Broadcom PCI device 0000:01:00.0. Its
RX, control and scan wake locks were active. The diagnostic restored
`pm_test` to `none` and returned to the same boot with taint 0.

The Wi-Fi-off comparison lost USB networking and console response before
its completion record could be read. The host requested re-enumeration,
but the radio restoration and stage outcome could not be confirmed.
System sleep targets were kept masked in both comparisons.

Proposal0037 associates the PCI wiphy with its actual PCI device before
registration and cancels an outstanding scan in the wiphy suspend callback.
This orders the wireless layer's cleanup before PCI suspension. The
original bus-busy and wake-lock checks remain in force. Kernel38 built
and packed with the same configuration, DTB and external ramdisk as
kernel36. It has not been installed or qualified for runtime suspend.

### Kernel38 installation and Wi-Fi check

After the owner restarted the phone, the retained kernel36 journal
confirmed that the Wi-Fi-off devices-stage comparison had returned in
5.19 seconds with errno 0. The USB transport did not recover in that window.

In TWRP, saved the verified full kernel36 BOOT and protected-partition
backups. Wrote kernel38 to BOOT only and verified its readback and all
protected-partition hashes. Ubuntu booted kernel38 with taint 0. The live
wireless device's parent was the expected PCIe endpoint 0000:01:00.0.
Wi-Fi associated at 5745 MHz on boot and again after an explicit connection
disconnect/reconnect. Both checks received three gateway replies out of
three and completed Wi-Fi-bound HTTPS with HTTP 200.

The connected devices-only PM test on kernel38 then lost USB SSH, USB
console and the known Wi-Fi route. Mac-side USB re-enumeration succeeded
at the port but did not restore the session. No matching PM return record
was available through those transports. System sleep targets stayed
masked and no full-system sleep cycle was attempted. A recovered journal
is required to distinguish a PM callback hang from a transport-only failure.

The owner reported an interactive power menu before restarting. The
recovered journal confirmed the connected devices phase returned in
5.29 seconds with errno 0. The wireless child ran before its PCIe parent
at suspend and after it at resume. The PCI core still warned that the
driver cleared its state-saved indicator. The host transports did not
reconnect in the original observation window.

The subsequent platform phase rebooted the handset. The matching retained
kernel38 trace recorded a fatal write fault in `klist_next`, reached through
`device_for_each_child` and `__device_suspend_noirq`. The printed relocation
offset matches those three frames in the local kernel38 symbol map. The
fault destination resolves within a kernel function. The preceding trace
reports actual suspend operating points of 208 MHz MIF and 107 MHz INT.
The corruption site does not identify the writer.

Proposal0038 compares the runtime-stable 421 MHz MIF and 178 MHz INT pair
through suspend. A DTB comparison verified exactly two changed suspend
fields for the Korean revision 10 board. The kernel binary, config and
external ramdisk match the original kernel38 build byte for byte.

Wrote the comparison image to BOOT after backing up the exact original
kernel38 BOOT. Verified BOOT readback and protected-partition hashes, then
read both edited properties from the running device tree. The PCI parent
also made predictable interface naming rename the primary Wi-Fi device on
some boots. The existing autoconnect profile required wlan0. Installed a
matching systemd link rule for this PCI device and driver. After a normal
reboot the interface stayed wlan0 and NetworkManager reconnected without
editing the saved profile.

With the comparison image, two connected platform requests and one
disassociated request returned EBUSY before late suspend. Broadcom reported
different active PM, RX/TX-flush and control wake locks. All three requests
returned to the same boot and verified Wi-Fi gateway traffic. Those attempts
did not reach the earlier fatal noirq point.

With the radio temporarily off, another comparison request returned EBUSY
after 3.23 seconds on the same boot. The on-device recovery re-enabled
Wi-Fi and verified gateway reachability. Taint 512 was reported after
the test. Subsequent USB and Wi-Fi SSH attempts did not retrieve the
matching kernel trace, so the callback and source of the warning still
require verification. Full suspend and RTC resume remain untested.

### Broadcom deferred PM work and retained panic decoding

The `pm-1` wake-lock report identified queued Broadcom station power-management
work as one blocker. Proposal0039 cancels that work from the existing wireless
suspend callback when WoWLAN is absent. Cancellation releases the corresponding
wake lock only if it removed the queued work. Already-running work still releases
its own lock. PCIe checks continue to protect active RX, TX and control work.

Kernel39 compiled and packed successfully. Its kernel configuration, packaged
DTB and external ramdisk match the kernel38 operating-point comparison image.
The device was unreachable over USB and Wi-Fi during this build, so kernel39
has no installation, reconnection or suspend results. The change does not
establish the source of the kernel38 noirq corruption.

The panic decoder identified the original kernel38 boot record after ignoring
the copied banner printed by Samsung `sec_debug` during the panic. The exact
kernel38 build verified the relocation from the reported boot offset and the
matching PC/LR pair. The retained diagnostic and decoded report stay local.

### Live kernel39 and voltage-policy suspend comparison

USB reconnection allowed retrieval of the full kernel38 OPP comparison log.
In the radio-off trial, the fuel-gauge VCELL read hit two Exynos HSI2C transfer
timeouts after late suspend completed. The PM core aborted the noirq phase,
and the subsequent resume logged a DWC3 gadget warning while processing a
USB endpoint completion with an empty request queue. The log does not identify
which wake source caused the abort or how the USB completion lost its request.

Installed kernel39 from verified SM-G955N TWRP after backing up the kernel38
OPP BOOT and protected partitions. Verified BOOT readback and unchanged
protected hashes, then verified a new boot running build 39 over USB SSH.
On 5745 MHz, automatic association and explicit reconnection each returned
three gateway replies and interface-bound HTTPS 200 on the same boot without
taint. The connected devices test returned EBUSY within 0.13 seconds. Broadcom
reported `pm-0` and `txfl-1`, with no other listed wake lock. The on-device
radio-off platform test returned EBUSY within 0.26 seconds on the same boot,
then re-enabled Wi-Fi and reached its gateway with taint still zero. USB and
Wi-Fi SSH subsequently stopped responding, so no matching callback trace was
retrieved for that radio-off attempt. Neither test qualified full suspend.

The vendor `vol_dvfs_kthread` independently calls the fuel gauge, bypassing
the already freezable battery workqueue. Proposal0040 makes that kthread join
the freezer before device interrupts stop, preserving low-voltage policy
and normal polling outside suspend. Kernel40 compiled and packed with the
same config, DTB and external ramdisk as kernel39. The kernel40 change has
no live evidence yet.

### Live kernel40 and FTS suspend wake

Installed kernel40 with a verified backup and BOOT-only readback. Automatic
association and explicit reconnection at 5745 MHz each received three gateway
replies and Wi-Fi-bound HTTPS 200 on the same boot. Initial taint was zero.

The radio-off platform test returned EBUSY in 3.25 seconds, recovered the
Wi-Fi gateway on the same boot and still had zero taint. The matching on-device
capture identified `fts_touch` as the first wake IRQ. The FTS handler timed
out waiting for its PM resume callback during the noirq abort. The saved
trace contains no HSI2C or VCELL timeouts in that trial. The live input device
remained disabled after the attempted transition.

Proposal0041 opts the Korean revision 10 FTS device into system sleep without
mutating input-core user counts. Touch wake defaults off through the standard
wakeup control, and active input users get the controller restored on resume.
The candidate's config and ramdisk match kernel40 byte for byte. The decoded
DTB adds only the FTS desktop-suspend property.

Kernel41 was installed after taking and verifying a current kernel40 BOOT
backup. Protected partition hashes remained unchanged. A new boot verified
kernel41, GDM, zero taint and the disabled default FTS wake policy over SSH.
The radio-off platform test completed all device, late and noirq phases in
5.34 seconds and returned successfully to the same boot. NetworkManager
restored Wi-Fi and gateway traffic, with zero taint. The FTS input device
was still enabled and no FTS wake or VCELL timeout appeared in the captured
interval. PCI core still reported power-state warnings for both the Exynos
Wi-Fi root port and its endpoint during noirq resume.

The real `mem` test was scheduled with an RTC alarm and a persistent on-device
report. After the alarm window, neither the USB serial console nor SSH over USB
or the captured Wi-Fi address returned a completion record. A targeted USB
re-enumeration did not restore access. The exact sleep or resume failure point
and RTC delivery are unverified until the retained record can be retrieved.
The normal systemd suspend targets remain masked pending this validation.

### Kernel42 Exynos WLAN PCI sleep ownership

The kernel41 platform test logged D3 warnings for both the root port and the
Broadcom endpoint during noirq resume. The Exynos host backs up and restores
root-port configuration when it powers the link back on. Broadcom restores
the endpoint in its regular resume callback. The PCI core's earlier noirq
restore attempted configuration access between those operations, while the
host was off.

Proposal0042 makes the Korean revision 10 WLAN PCIe host report configuration
availability from its existing link state during system sleep. The PCI core
defers the generic configuration accesses while that host is down. The
regular driver callbacks remain responsible for restoring power and config.
Other PCI hosts retain the default policy.

The ARM64 kernel42 build and boot image passed the build checks. The kernel
configuration and external ramdisk match kernel41. A decoded DTB comparison
found only the opt-in property on Exynos WLAN PCIe channel 0. The Linux host
test suite passed all 102 tests. USB, Wi-Fi and TWRP were unreachable, so
kernel42 remains uninstalled. Live PCIe warning, Wi-Fi reconnection and RTC
resume results are pending, as is the retained record of kernel41 real sleep.

### Recovered kernel41 deep-sleep record and live kernel42

After the operator's forced restart, the kernel41 on-device report contained
only the entry record with a programmed RTC alarm. The matching retained
kernel log reached the end of noirq suspend, offlined the secondary CPUs and
entered the Exynos SYS_SLEEP syscore configuration. It reports a DPU power
domain shutdown error before that point. The segment ends without a resume
record, followed by the bootloader's pin-reset report. An earlier, different
RTC alarm fired while the phone was awake. Delivery of the full-test alarm
and return from the platform sleep instruction are still unverified.

Installed kernel42 from TWRP after backing up and verifying the kernel41 BOOT
and protected partitions, then verified a new kernel42 boot over SSH. The
forced restart had preserved the previous test's software radio-off state.
Restored Wi-Fi and verified 5745 MHz association and manual reconnect, each
with three gateway replies and interface-bound HTTPS 200. The radio-off
platform diagnostic returned successfully on the same boot in 5.32 seconds,
explicitly reconnected Wi-Fi and passed gateway traffic with zero taint.
The matching live trace completed device, late and noirq phases with both
previous PCI D3 warnings absent. GDM remained active and the touchscreen
input device was enabled. The later `mem` diagnostic limited to `pm_test
core` was armed, but did not yield a visible record over USB or Wi-Fi.

### Kernel43 noirq power-domain failure recovery

The generic power-domain noirq callback discarded the hardware power-off
error, recorded the domain as powered off and allowed the system sleep to
continue. Proposal0043 returns the error to the PM core, preserves the
failed domain state and restores the current device before earlier devices
unwind. When a parent power-off fails, the unwind restores the child and
its parent usage counts. This prevents proceeding after a noirq power-off
failure. The cause of the original DPU refusal still requires live traces.

Kernel43 built and packed with kernel42's configuration, DTB and external
ramdisk. The Linux suite passed all 102 tests. USB re-enumeration did not
restore a management path after the kernel42 core trial, so kernel43 has
no device installation or resume record at this checkpoint.

### Exynos syscore early-wake sequencing

The kernel42 core diagnostic can bypass the platform `enter` callback and
still invoke syscore resume. The previous Exynos code left the early-wake
flag at its previous value until the PSCI call returned. A skipped entry
could therefore use the normal post-sleep sequence even though system
sleep never occurred. VTS state was also queried again during restore, so
it could select a mode different from the one prepared.

Proposal0044 initializes each attempt for early unwind, records the chosen
mode once, and keeps the normal firmware result when actual entry returns.
It propagates Exynos preparation errors and records preparation, firmware
and restore boundaries for retained diagnostics. This is a source-level
finding. The kernel42 core hang still has no recovered device record and
the RTC wake path has not been qualified.

Kernel44 compiled and packed with kernel43's configuration, DTB and external
ramdisk. The Linux host test suite passed all 102 tests. The target remained
unreachable over USB, Wi-Fi and TWRP. Neither kernel43 nor kernel44 was
installed or exercised on the device in this checkpoint.

### Recovered kernel42 core diagnostic

The forced restart made the matching kernel42 retained log and its synced
entry record accessible. The diagnostic reached noirq completion, secondary
CPU offlining and Exynos SYS_SLEEP preparation. The `pm_test core` wait
marker confirms it bypassed firmware sleep. The following Samsung pinctrl
resume entry logged a successful return from its firmware call. The retained
segment ends without a system resume or userspace completion record.
The recovery log establishes that this failure occurred without an RTC alarm
or platform sleep entry. It does not yet identify the exact callback at which
all execution stopped.

Installed kernel43 from verified TWRP and verified BOOT and protected
partition readback before the new boot. With `mem` limited to `pm_test
platform`, the same boot returned in 5.31 seconds, restored Wi-Fi gateway
traffic and retained the enabled touchscreen and active GDM with zero taint.
The DPU shutdown refusal did not recur in this bounded test, so this pass
does not exercise the new power-domain failure branch.

Installed kernel44 after TWRP backed up and verified the exact kernel43 BOOT
and protected partitions. BOOT readback matched and SSH identified a new
boot running kernel44.

With Wi-Fi temporarily disabled, kernel44 entered actual suspend-to-idle
(`freeze`, `pm_test` disabled) and returned on the same boot after 27.79
seconds. The first wake IRQ was the S2MPS17 parent, and the retained trace
logged the RTC alarm handler at that wake. Wi-Fi re-associated and passed
traffic to its gateway. GDM was active, touchscreen input remained enabled
and kernel taint remained zero. This verifies one RTC wake from suspend-to-idle.

The subsequent `mem` test limited to `pm_test core` was armed with extra
syscore logging. It did not return a readable completion record over USB or
Wi-Fi. The retained log must be recovered before attributing this failure to
pinctrl, Exynos restore or a later callback. The normal desktop sleep targets
remain masked while the core path is unresolved.

### Recovered kernel44 failure and kernel45 comparison

The forced reboot recovered the kernel44 core test entry and its retained
kernel log. This attempt aborted during noirq after an Exynos DPU0 power-off
failure. It reached noirq resume completion and began early device resume.
The retained segment ends before system resume completes and contains no
Exynos syscore restore marker. This test therefore did not exercise the
kernel44 syscore fix. The exact later callback that stopped the unwind is
unverified because the tail of the retained log is damaged.

The Exynos local power-off routine could leave a changed power request
when its hardware wait failed. Generic PM still treated the domain as
active, so there was no hardware power-on in that rollback. Proposal0045
uses the existing local enable and saved-register restore before returning
the original error. The build also includes proposal0036 and its explicit
SM-G955N opt-in. The forced restart booted into charger mode with GDM active,
and kernel44 declined to bind the touchscreen. Kernel45 keeps the same
DTB and ramdisk and adds only the charger touch argument to kernel config.
All 102 Linux tests passed.

Installed kernel45 from verified TWRP with the kernel44 BOOT backed up and
readback and protected hashes checked. A new normal-mode boot verified the
charger touch opt-in, bound FTS input, active GDM and zero kernel taint.
This boot did not exercise the charger-mode exception.

The first two attempted RTC suspend-to-idle runs returned EBUSY before
noirq. With Wi-Fi associated, DHD reported active RX, control and event
wake locks. After disconnecting only the managed `wlan0` link, control
and event locks still blocked entry. Both attempts returned to the same
boot and passed Wi-Fi gateway traffic, with touchscreen still enabled.

Putting NetworkManager itself into temporary sleep also left RX and TX-flush
wake locks active at PCI suspend entry. The request returned EBUSY and the
original Wi-Fi connection recovered. These three cases do not qualify the
ordinary GNOME suspend action while Wi-Fi is enabled.

The radio-off `mem` core diagnostic completed on the same kernel45 boot.
Its retained log shows Exynos mode 8 preparation and early-wake restore,
with no platform sleep entry. Wi-Fi reconnected and passed gateway traffic.
The touchscreen was still enabled, GDM was active and taint remained zero.
This was the first observed successful core test in this comparison series.

A subsequent real `mem` test with Wi-Fi temporarily off and RTC wake
scheduled did not return a completion record over USB or either known
Wi-Fi address after the alarm window. The USB port re-enumeration request
was accepted but did not restore access. The retained record must be
recovered to distinguish an entry failure from a wake or resume failure.
Deep suspend and default GNOME sleep remain unqualified.

### Kernel46 Broadcom system-suspend work drain

The kernel45 connected association, interface disconnect and NetworkManager
sleep comparisons all stopped in the ordinary DHD PCI suspend callback,
before the noirq or Exynos platform paths. In the NetworkManager case the
PCI callback returned EBUSY in 19 microseconds with active RX and TX-flush
holds. Thus the radio's system-sleep preparation still needs to cope with
in-flight work even after the desktop asks NetworkManager to sleep.

Proposal0046 waits no longer than the existing 1500 ms DHD event timeout
before taking the bus lock and starting the suspend transition. It polls
without clearing any wake lock. The existing wake-lock check, bus-idle
check and firmware D3 handshake still decide whether suspend can proceed.
The runtime PM path keeps its current behavior. This is a separate test
candidate from the Exynos deep-sleep wake path.

Kernel46 compiled and packed with the same configuration, DTB and ramdisk
as kernel45. The Linux test suite passed all 102 tests. USB, Wi-Fi and TWRP
remained unreachable, so kernel46 has no installation or live suspend
result. The retained log from the previous kernel45 real `mem` test has
not been recovered.

### Recovered kernel45 deep trial and live kernel46

The forced restart exposed the kernel45 real `mem` test entry record and
its programmed RTC alarm. The retained log reports DPU0 power-off timeout
and repeated RCU stalls before noirq completed. It contains no matching
Exynos platform sleep entry or return. This failure cannot be attributed
to RTC wake delivery or PSCI resume because the test stopped earlier.

Installed kernel46 with a verified kernel45 BOOT backup and verified BOOT
and protected partition readback. With Wi-Fi connected soon after enabling
the radio, the kernel waited about 1.5 seconds. DHD RX, control, event and
TX-flush holds cleared, then the station PM hold alone blocked entry. The
matching live `iw` output showed WoWLAN enabled. The driver had excluded
WoWLAN sessions from its pending station work cancellation.

After the connection settled, kernel46 actually entered `freeze` with
Wi-Fi connected and returned on the same boot after 34.42 seconds. The
S2MPS17 wake IRQ and RTC alarm handler matched the programmed wake. Wi-Fi
passed gateway traffic and GDM and touchscreen input remained active.
Kernel taint was zero. Default GNOME sleep remained gated.

Proposal0047 pauses the deferred station PM timer across the wiphy system
suspend callback, including when WoWLAN is configured. It preserves the
requested delay and re-arms deferred work on resume. The firmware wake
configuration and other DHD wake checks stay in place. Kernel47 compiled
with kernel46's config, DTB and external ramdisk. All 102 Linux tests passed.

Installed kernel47 with a verified kernel46 BOOT backup and BOOT-only
readback, then verified a new boot. Immediately after a managed Wi-Fi
reconnect, suspend-to-idle entered and returned without EBUSY. It stayed
asleep for only 0.56 seconds because the Broadcom host-wake IRQ arrived
before the RTC alarm. The same boot retained Wi-Fi traffic and touch.

A bounded standard systemd suspend trial also used `freeze` and returned
within 0.96 seconds. The RTC alarm interrupt occurred over 23 seconds after
that exit while the device was awake. Checking that event's ordering avoids
counting the alarm as the wake source. Restored and verified both masks.

Proposal0048 zero-initializes the stock WoWLAN default structure. The old
allocation explicitly assigned four flags and left `any`, `magic_pkt` and
`rfkill_release` uninitialized. Those unspecified flags had been reported
as enabled by `iw`. Kernel48 compiled and packed with kernel47's config,
DTB and external ramdisk. Its wake timing needs a separate device test.

Installed and verified kernel48 after backing up kernel47 BOOT. With no
user configuration change, `iw` showed only the four explicitly initialized
WoWLAN triggers. The first associated suspend-to-idle test entered
successfully but returned in 0.59 seconds on the Broadcom host-wake IRQ
before its RTC alarm. Wi-Fi, GDM and touch remained accessible, and kernel
taint was zero. Initializing the trigger fields corrected their reported
state but did not prevent that host-wake event. All 102 Linux tests passed.

A second associated kernel48 RTC trial was started after the connection
settled. USB still enumerated initially, but neither USB SSH nor Wi-Fi
returned a completion record after the alarm window. The retained log is
pending. The Broadcom out-of-band IRQ is separately armed by the vendor
driver, so the corrected cfg80211 trigger display alone cannot establish
the cause of host wake or reliable RTC recovery. Both desktop sleep targets
were restored to masked after the earlier standard systemd trial.

### Kernel49 separates WLAN system wake from the runtime IRQ

The vendor WLAN driver called `enable_irq_wake` at host IRQ registration,
independently of the WLAN system sleep wakeup setting. The kernel48 first
trial shows that this separate host IRQ can wake the phone even after
uninitialized cfg80211 trigger flags are removed.

Proposal0049 opts the Korean revision 10 image into the Linux PCI device
wakeup control. WLAN system wake defaults off. If enabled on the device,
the driver uses the kernel wake-IRQ framework for that sleep attempt and
clears its association during completion. The endpoint's PCI PME request
follows the same policy during system sleep. Runtime IRQ delivery and the
separate power-button and RTC paths retain their existing wiring.

Kernel49 compiled and packed. The configuration and ramdisk match kernel48
and the decoded DTB adds only the board wake opt-in property. All 102 Linux
tests passed. The enumerated kernel48 USB serial console gave no response,
SSH and recovery remained unreachable, and USB re-enumeration did not
restore console access. Kernel49 installation and hardware validation
remain pending, including RTC sleep and opt-in WLAN wake.

### Recovered kernel48 shallow failure and DPU0 retention comparison

The manual restart recovered the same kernel48 shallow-sleep attempt that
lost both management paths. Its synced record contains the programmed RTC
alarm and no return event. The journal confirms the test entry. In the
retained kernel log, DPU0 timed out during noirq power-off and CPU stalls
followed. This is the same hardware transition that blocked kernel45 `mem`.
The evidence places this shallow failure before any RTC wake.

Proposal0050 retains this one board-specific display power domain during
synchronous system-device suspend. It leaves the domain accounted as on,
so a parent domain does not lose an active dependency. Device suspend and
resume callbacks still run and normal runtime power-off is unchanged.
This comparison carries a potential sleep-power cost. It does not qualify
full SoC sleep.

Kernel49 was installed after the restart with verified BOOT and protected
partition readback. The running PCI WLAN wake setting was disabled and RTC
wake enabled. The associated device-only diagnostic completed in 6.21
seconds without reboot. Wi-Fi gateway traffic, GDM and touch recovered and
kernel taint remained zero. That bounded test stops before DPU0 noirq.

Kernel50 compiled and packed with the kernel49 configuration and ramdisk.
Decoded DTBs differ only by the DPU0 system-sleep retention property.
All 102 Linux host tests passed.

Installed kernel50 after verifying the kernel49 BOOT backup and protected
partition readback. With WLAN connected and its system wake disabled, a
raw `freeze` test resumed on the RTC alarm after 30.20 seconds. The same
boot recovered WLAN gateway traffic and touchscreen input with active GDM
and taint zero. The standard systemd path then completed a 24.71 second
RTC wake using a temporary `SuspendState=freeze` setting. Both RTC events
occurred inside the corresponding kernel suspend intervals.

The live handset now has the tracked suspend-to-idle configuration in
`/etc/systemd/sleep.conf.d` and the matched device-tree guard in
`/etc/systemd/system/systemd-suspend.service.d`. This limits normal GNOME
suspend to the verified `freeze` path. The service's entry guard requires
both the board WLAN wake policy and the DPU0 retention property. The
temporary validation config and boot recovery unit have been removed.
The rootfs builder's sleep masks remain the initial baseline for unpaired
images.

A repeat using the installed systemd configuration completed in 24.38
seconds. The same kernel50 boot remained active, the RTC interrupt preceded
kernel suspend exit, and systemd finished its suspend service successfully.
Full `mem`, standby battery draw and physical power-key wake have not been
qualified under this configuration.

A controlled reboot verified the persistent settings, logind `CanSuspend`,
GDM, touch and WLAN gateway traffic on the new kernel50 boot. The host
initially lost management access during the next standard suspend request.
On USB recovery, the current boot's journal showed the RTC interrupt inside
the 24.66-second suspend interval and successful systemd suspend completion.
The handset remained on that boot. SSH to the handset's current WLAN
address succeeded using the pinned USB host key. The targets were remasked
for subsequent bounded tests.

A second post-reboot standard suspend trial was scheduled and collected
entirely through WLAN SSH, with the targets temporarily unmasked. After
24.22 seconds, the RTC woke the same boot and WLAN SSH reconnected with the
same pinned key. No new kernel warning appeared in the suspend interval.
Taint was 512 both before and after the test: the recovered journal shows
a DWC3 endpoint command warning followed by a gadget run/stop timeout on
a USB cable detach, over four minutes after the first post-reboot RTC
wake. The USB detach path needs separate validation.

A two-minute standard suspend trial through WLAN SSH repeated that result.
The RTC woke the same boot after 120.22 seconds, systemd completed the
operation, and the existing GNOME Shell process and kernel taint were
unchanged. No new warning appeared in the suspend interval. GDM was
active, the touchscreen input remained enabled, and three WLAN gateway
probes received replies. The timed cleanup restored both sleep target
masks and removed the temporary boot recovery unit. Enabling daily
desktop suspend still requires testing physical wake and screen recovery
without a scheduled RTC alarm. Deep sleep and battery draw remain open.

The SSH collector also verified fallback on the handset using a deliberately
unreachable primary address and its current WLAN address. Both probes use the
same pinned key and the capture checks the device model and kernel identity
before collecting logs.

### Manual GNOME suspend enabled on kernel50

The running system initially advertised `CanSuspend=no` because both
systemd targets were masked. USB SSH was unavailable, so configuration
and qualification ran over authenticated WLAN SSH. Installed GNOME
desktop and greeter defaults that leave idle suspend off on both AC and
battery. Enabled the two systemd targets after checking the running
kernel properties, the installed suspend policy and the GPIO-key and
RTC wake settings. The installed policy still uses `freeze`.

The standard logind `Suspend` request finished after a 33.26-second RTC
wake. The same boot and active seat returned with Mutter reporting
normal display power, a powered panel with positive backlight, active
touch input, and three successful WLAN gateway probes. The kernel
reported no new warning in the suspend interval, and the existing
USB-detach taint remained unchanged. The test rollback units were then
removed and the manual suspend targets were left available.

The live desktop and greeter previously used GNOME's interactive
power-button action. The installed profile now uses `nothing` so GNOME
does not open a shutdown dialog when it sees the button. Verified the
effective values in both profiles and polkit authorization for the
active GNOME Shell process. The kernel GPIO device still reports wake
enabled. A repeat with the final policy resumed on RTC after 45.68
seconds with the same boot and seat, active panel, touch and WLAN,
and no new warning in the suspend interval. Physical-button wake and
deep sleep are still unverified.

### Suspend console and Bluetooth UART

The owner saw the framebuffer console during a later sleep comparison
and confirmed that the normal screen returned. The system remained on the
same boot with the active X11 session back on tty2. The driver registers
a framebuffer that requires VT switching, so the PM core temporarily
uses tty63 and redirects kernel messages there.

The sleep hook clears that reserved VT before suspend, limits console
output during the switch, restores the prior level after resume, and
records the first kernel-reported IRQ. It preserves the kernel ring
buffer. A WLAN-managed repeat with the hook showed normal panel power
and the same desktop seat after a 35.05-second RTC wake. The wake record
identified the S2MPS17 IRQ and the kernel journal contained the RTC
handler inside the interval. A direct VT read revealed that the first
version had skipped the pre-suspend clear because the sysctl could not
be read byte by byte. Reading it with awk let the hook lower the console
level and clear all 7,714 nonblank console characters in the direct check.
Physical-button wake has no matching record yet.

Both `could not set bt sleep pins` and `could not set bt default pins`
are reproducible in the UART callback. Proposal0051 adds the missing
states to the Korean board DT, using the existing Bluetooth sleep pins
and the same active mapping as `default`. Its DTB compiled and packed
with the exact kernel50 Image, configuration and external ramdisk. The
decoded DT comparison confirmed only the Bluetooth UART states and their
phandle assignments changed. This candidate is uninstalled.

The kernel50 `mem` `core` diagnostic completed on the same boot and
with unchanged taint. It passed DPU0 noirq, took secondary CPUs offline,
prepared Exynos mode 8, and ran the mode 8 early-wake restore. The
five-second core test skipped the actual firmware sleep entry.

Kernel50 also completed a direct `mem` request with an RTC alarm. The
kernel logged a 42.62-second interval, mode 8 restore with
`early wake: 0`, and the RTC alarm handler before suspend exit.
The request returned zero on the same boot and WLAN SSH recovered.

A separate standard logind test reset the runtime `SuspendState` list
before selecting `mem`. It recorded real PSCI entry and normal mode 8
restore after a 46.58-second UTC interval. Logind completed, the same
desktop seat and panel recovered, the touch input was enabled, and three
WLAN gateway probes passed. The temporary deep setting was removed and
the live manual default returned to `freeze`.

With the corrected console hook, another standard `mem` request
resumed on RTC after 30.92 seconds. The reserved VT was blank on direct
readback after the actual sleep cycle, and the original console level
was restored. The same boot, panel, seat, touchscreen input and WLAN
traffic were verified again. The manual default is `freeze` and
automatic suspend remains off pending physical-button testing.

### Power key wakes the active GNOME display

When the owner reported a black screen after pressing the power key,
kernel50 was reachable over WLAN and the hardware KEY_POWER interrupt
was counting events. The journal showed no new system suspend. Both
logind and GNOME had their power-key actions disabled to avoid opening
the shutdown dialog. There was no explicit display-wake action on the
ordinary GNOME path.

Installed and enabled the SM-G955N power-key service. It listens to the
same GPIO input as the desktop, selects the local graphical session,
and issues the display wake request with that user's privileges. The
Mutter property alone did not drive the native X11 framebuffer's
DPMS state. The X11 implementation now uses the active X server's
DPMS path. The Wayland fallback is unqualified on this device.

Three live X11 cycles forced DPMS off and confirmed DECON runtime
suspend, then injected a press and release into the real GPIO input
device's evdev stream. Each cycle returned to DPMS on and active DECON,
with a service acknowledgement, the same boot and an unchanged GNOME
lock state. This exercises the wake service and panel after display
blanking. A hardware IRQ issued while Linux is suspended is a separate
test.

The guarded system suspend resumed on its 105.70-second RTC fallback.
The same boot recovered tty2, active DECON, GDM and WLAN. The captured
wake IRQ came from the PMIC and the RTC alarm handler ran in the
interval. It provides no physical-button wake evidence.

The hook now also queues a delayed display wake for a kernel-reported
`gpio-keys: KEY_POWER` wake IRQ. This covers a brief press released
before GPIO input debouncing can report it to the resumed desktop.
A hook fixture confirmed dispatch for KEY_POWER and no dispatch for
the RTC's PMIC IRQ. The scheduled display action completed on the
live X11 session.

### Power key toggles display power

The owner confirmed that the original wake-only action left a lit
screen on. On the handset, a GPIO power event also wakes X11 DPMS
with the key service stopped. The toggle therefore records the panel's
power state before that event and blanks on release, after X11 handles
the key. The service treats a press during suspend or near resume as
a wake request.

On the running kernel50 handset, injected power-key presses and releases
on the GPIO evdev stream completed three active → suspended → active
DECON cycles. DPMS agreed with the hardware state and the GNOME lock
state was unchanged. A separate X11 blank followed by a key press
also returned the panel to active.

An on-device test scheduled a normal GNOME suspend with an RTC alarm,
then injected the first power press inside the recorded resume window.
The panel stayed active, the GNOME lock state was unchanged, and the
test returned on the same boot. The wake IRQ was RTC. A physical key
wake from system suspend remains unverified.

### Short-press suspend and long-press shutdown confirmation

On the X11 kernel50 handset, an evdev long press mapped the Power Off
confirmation window while the key was held. Releasing the key kept the
window open without requesting suspend. Closing the test window kept the
same boot. The dialog defaults to Cancel and has no countdown. It is
shown within the GNOME session, so a locked session must be unlocked to
interact with it. The test did not activate Power Off.

A separate injected short press on the active panel entered actual
systemd suspend. The programmed RTC alarm woke the same boot and a key
event in the resume window kept the panel active without starting a new
suspend. Kernel taint remained unchanged. A physical-button wake from
system suspend remains unverified.

With only the display blanked, a short press woke DECON and X11 DPMS
without starting the system suspend service.

### Kernel50 direct-output restoration

The live owner session loaded Mali-G71 and Exynos gralloc while its
direct-output environment and saved state were absent. A cold boot
provided a clear-taint baseline. The checked controller now recognizes
the running image's exact linked ELF notes and installs the previously
tested v6 direct module for ordinary GNOME logins.

After the normal PAM login the same image logged final GNOME frame
retirement without CPU pixel transfer and held the panel lease. In
three synthetic drags, mean whole-machine CPU decreased from 17.00%
to 10.91%, and median window-position update intervals decreased from
501–519 ms to 33 ms. These are synthetic input and geometry measurements.
Application buffer copies and optical panel FPS are separate.

Two DPMS cycles resumed the same GNOME shell with 176 and 177 DECON
retirements after wake. The fullscreen shape test retained its overlay
with zero hidden samples. USB reconnection introduced the known DWC3
warning bit before these graphics tests; it stayed unchanged. The legacy
overlay-image pixel fixture failed against direct scanout and cannot be
used to certify its panel pixels.

One system-suspend comparison returned the same kernel boot but GNOME
exited with bridge status 33 and systemd restarted it. A diagnostic
rebuild added stderr messages at the existing fence-failure exits without
changing wait behavior. The next RTC comparison kept the same GNOME
process. Its later panel-off state was consistent with the lock screen.
The original reviewed v6 module was restored and its installed hashes
rechecked. The intermittent fence exit remains unresolved, so direct
output with system suspend is still under qualification.

### DRM/KMS/PRIME integration development

Kernel52 registered the new primary-panel DRM card with PRIME import/export,
GEM, a fixed DSI mode, AddFB2 and asynchronous page flips. Its isolated fixture
presented 90 buffers through the real DECON update/completion path and restored
fbdev without kernel taint. The fixture CPU-filled its test patterns once;
production GNOME imports buffers rendered by Mali and never maps their pixels.

Xorg's unused platform-device probe initially kept DRM master through logind.
The bridge-specific udev rule separates this display-only card from that probe
while keeping fbdev, touch and authentication on seat0. A second failure was
an unnecessary root-only SetMaster request from a file already made master by
open; the presenter now checks its existing master status first.

The ordinary GNOME session then mapped Mali-G71, owned the DRM card and logged
60 real page-event retirements. Same-boot kernel52 synthetic drag trials gave:

| Measurement | X11 CPU copy | DRM/KMS/PRIME |
| --- | ---: | ---: |
| Whole-device CPU busy, mean of three trials | 15.64% | 12.90% |
| Trial median window-update gaps | 499.5 / 501 / 501 ms | 33 / 49.5 / 17 ms |
| Observed position changes out of 180 requests | 7 / 6 / 6 | 85 / 71 / 107 |

These are synthetic input/window geometry measurements, not optical FPS or
physical finger latency. They do not compare KMS against HWC or the older
zero-copy Samsung-ioctl route. Both production direct routes avoid a CPU copy
of GNOME's final composition; individual apps can still copy or render on CPU.

Five kernel52 DPMS cycles kept the same shell/boot and clear taint. System
suspend exposed an accepted flip reaching the worker after fbcon blanked the
panel, returning EHOSTDOWN and restarting GNOME. Kernel53 retains that buffer
and its event until real post-unblank scanout, publishes native power through
standard connector DPMS, and cancels deferred events before file destruction.

The next RTC trial exposed the userspace deadline spanning suspend-to-idle.
The presenter now checks already-readable events even at an expired deadline,
pauses while DPMS is off, and allows one bounded extra interval after a large
scheduler/suspend delay. It still requires a real completion event; a repeated
powered timeout fails. After that repair a 23.44-second RTC suspend preserved
the same kernel and GNOME. Real PAM unlock followed by a motion fixture retired
93 additional frames. The locked screen had correctly hidden the earlier
behind-lock fixture, so that zero-progress sample was not a valid drag test.

Kernel54 also records temporary panel blanking under the DECON state lock as
EAGAIN, closing the race where unblank completes before the worker sees the
return. The callback fixture verifies this case, off-panel retention, actual
completion, close cancellation and failure accounting. The real presenter
fixture verifies DMA-BUF identity caching, bounded eviction, off-panel waiting,
a single resume grace interval and failure after repeated delayed timeouts.

Kernel54 booted through verified BOOT-only replacement with protected partition
hashes unchanged. Its existing default files, runtime lease and ABI1.1 probe
survived the kernel update without adding a kernel54 hash allowlist. Injected
real touchscreen events selected the account, focused the password field,
opened the OSK numeric layer and authenticated through GDM/PAM. The owner GNOME
opened the DRM card and loaded Mali with no swrast mapping; kernel taint was 0.
Physical finger latency and optical display inspection remain separate checks.


Final kernel54 same-boot A/B kept the same application session while reloading
only GNOME Shell and switching its output activation variables. CPU-copy drag
CPU busy averaged 15.71%, with trial median geometry gaps 499/333/501 ms and
8/8/8 position changes. KMS averaged 14.34%, with gaps 34/33/34 ms and
70/102/74 changes. The saved default files/hashes were unchanged and KMS
activation was restored. Both routes used Mali rendering. The earlier USB
warning bit 512 was present before this comparison and did not change.

Kernel54 passed another five DPMS cycles in the same boot/shell with taint0,
retiring 101–130 additional frames after each wake. Its RTC suspend lasted
17.90 seconds and the same GNOME process subsequently retired 123 frames.
The USB/network transports were temporarily unreachable and required recovery;
this was not evidence of a kernel or GNOME reboot. Recovered logs placed the
RTC wake and suspend exit around uptime161s, with the DWC3 warning only around
uptime386s during the later USB recovery. USB recovery remains a separate
stability limitation; these results do not certify all kernel logs as clean.

A fresh export of the pinned kernel source built successfully using the
versioned full KMS/stability command. Its configuration and compiled board DTB
matched the installed kernel54 build, and recorded DRM source hashes matched
the checked-in sources. The presenter/driver callback fixtures passed, as did
106 Python tests (nine platform/root skips on macOS; one platform skip in the
Linux root builder).

After a further clean kernel54 reboot, the saved KMS hashes and capability-based
activation remained unchanged. Touchscreen/OSK/PAM login again reached the
ordinary Mali-rendered GNOME session. A 304-second session soak ran eleven
periodic motion samples, with 92–158 DECON retirements per sample (1,253 total).
The same shell and boot survived every sample, the panel stayed active, and
kernel taint stayed0. No new graphics/kernel fault signatures were found in
that interval. This is a bounded periodic-workload soak, not continuous maximum
GPU load or proof of hours-long reliability. The completed test unit and idle
inhibitor were removed; normal GNOME locking remains available.

### Kernel54 desktop audio continuity

The owner reported inaudible output, then heavily interrupted speech. A normal
PipeWire playback test reproduced increasing internal hardware errors, despite
successful pw-play exits. With the default S16LE stereo 48 kHz geometry
(period1024, buffer32768 frames /128 KiB), the eight-second fixture observed
20 additional sink errors between active samples and23 backwards ALSA pointer
transitions. MAX98506 repeatedly restarted within the same playback stream.

The guarded rules now request period2048, eight periods (buffer16384 frames /
64 KiB) and4096 frames of headroom. The smaller ring alone passed the short
trial but had one error in a20-second trial. With headroom, a subsequent
20-second trial had zero hardware errors and zero backwards pointer samples.
This establishes an effective desktop configuration, not the exact register or
firmware root cause of the larger-ring failure. No amplifier boost, calibration,
firmware or partition was modified. The previous rules/manifest remain privately
backed up; the installed startup manifest was updated and its guard passed.

The owner confirmed that the standard Front Center voice was audible without
interruptions after the ring change. The final five-second duplex trial had
zero sink/source hardware-error growth, advancing RDMA0 and WDMA1 pointers,
both expected synthetic tone responses in microphone data, and zero steady
capture clipping. Volume/mute were restored and no new kernel fault signatures,
boot change or taint change were seen. Raw microphone audio was not saved.
Cold capture still has a transient concentrated in its first100 ms; the test
reports the first250 ms separately and does not certify speech intelligibility
or startup quality. This remains an audio quality issue to resolve.

GNOME multimedia-key actions changed sink volume from0.67 to0.61, muted the
speaker and muted the microphone through the standard services. Original levels
and mute states were restored. PipeWire, pipewire-pulse and WirePlumber were
enabled; built-in speaker/mic default names persisted through policy restarts.

### Kernel54 power state versus unresponsive input

A later apparent freeze was recovered without reboot by reconnecting USB.
Recovered logs showed a normal power-key suspend request followed by actual
suspend-to-idle, lasting about126 seconds until a PMIC/charger wake. An earlier
instance similarly remained asleep about189 seconds. These instances were
actual sleep, not proof of a persistent kernel deadlock. GPIO power-key wakeup
was enabled and its DT wake property present. Auto-suspend on AC/battery was
`nothing`, logind idle action was ignored, and Android autosleep was off.

The power-key service previously requested sleep without first blanking the
panel. It now forces DPMS off while the user session is available, verifies the
hardware runtime state and cancels sleep if the panel stays on. It restores the
display on a failed sleep request. Wake resets the X11 screen-saver timer before
DPMS on; a live counter query measured214214 ms before reset and133 ms after.
This does not unlock the session. The installed file was backed up and checked
against its expected previous hash; no kernel or partition was changed.

A live barrier fixture verified active panel -> hardware off -> simulated sleep
request -> active panel. A subsequent normal systemd suspend trial programmed
a20-second alarm and completed in21.03 seconds including setup. It retained the
same boot and GNOME process, returned with an active panel and the screen lock
still set, and added zero kernel fault signatures. Kernel taint512 predated the
trial and remained unchanged. The recorded wake IRQ was213 (PMIC); that number
alone does not identify an individual PMIC source. This is a bounded timed-wake
result, not repeated physical-button/OSK acceptance or a declaration that all
kernel errors are eliminated.

### Kernel54 lock keyboard and normal session recovery

The lock investigation captured `Argument descendant may not be null` in
`keyboard.js` through the unlock dialog, and a disposed-input-device stack in
automatic keyboard detection after X11 input refresh. The final overlay adds
only a missing-actor guard and skips automatic device inspection when the
accessibility keyboard is explicitly enabled. Native keyboard forwarding,
the distro unlock dialog, screen locking and PAM are retained. No global
event-forwarding replacement or credential handling is shipped.

An experimental forced restart of the Shell service activated GNOME's
failed-session target. The owner's white "Oh no!" screen was this failure UI;
a running replacement Shell alone was insufficient to recover the session.
Recovery used normal session shutdown and fresh touchscreen GDM/PAM login.
The final installer never restarts Shell. Its root-owned files, GPU manifest,
startup hashes and original-resource pins passed readback verification; the
experimental unlock-dialog resource was removed. It rejects changed original
GNOME resources until reviewed again after an update.

Early blind-coordinate trials entered input before the keyboard was prepared,
and sometimes used GDM entry coordinates for the different unlock layout. They
do not establish a routing defect or validate the discarded broad forwarding
prototype. The corrected private device harness waits for the actual protected
entry's focus and visible numeric keyboard using accessibility metadata. It
replays touchscreen events and verifies exactly one additional character per
key, without reading protected text. The owner-provided secret and test payload
remain outside Git. X11 root screenshots did not capture the actual composited
lock surface and were not used as evidence of authentication state.

With the final two-guard overlay loaded in a fresh normal session, touchscreen
GDM/PAM login reached GNOME. A subsequent20.41-second suspend/resume, including
setup and using a20-second RTC alarm, retained the same boot and Shell, restored
the panel and kept the screen locked. The prepared OSK then accepted all touches
without duplicate/lost characters, retained its numeric page and completed
normal PAM unlock. The failed-session screen was absent. Kernel taint remained
the pre-existing512; both the timed sleep and unlock intervals added zero kernel
fault signatures. GNOME still mapped Mali, reported Mali-G71, owned the KMS card
and retired60 frames without CPU pixel transfer. This bounded trial does not
certify indefinite reliability, eliminate the previous DWC3 warning, or replace
physical power-button wake acceptance. The generated-method fixture and JS/Python
syntax checks also passed.

### Kernel55 USB sleep ownership and transport recovery

A kernel54 host USB re-enumeration during timed sleep removed the Mac's USB
interfaces while the phone continued reporting `CONFIGURED`. Wi-Fi stayed
usable. A composite-only disable/enable attempt failed to restore the host
interfaces and added three DWC3 failure messages, including an ep0out enable
failure. Cycling the full peripheral/PHY path restored the actual host serial
port and model/kernel-verified USB SSH without reboot or owner cable action.
That first recovery still logged two errors while stopping the already broken
controller. A subsequent healthy reset with the versioned recovery tool added
zero USB failures and zero kernel fault signatures. These are separate outcomes;
device-side `CONFIGURED` is never treated as host transport acceptance.

The retained warning trace enters EndTransfer from resume -> OTG ready -> gadget
stop -> composite disconnect. Proposal0053 addresses the suspected hardware /
software sleep-state mismatch by quiescing the peripheral while clocks and PHY
are available. It keeps physical ID/VBUS inputs so the normal resume state
machine initializes a fresh peripheral, and excludes host-role policy changes.
A runner which passed its early ready check must check again under the mutex.
Real halt errors propagate, retain runtime/PHY ownership and reject system
sleep while attempting to restore the peripheral. Endpoint warnings are kept.

The fresh pinned-source kernel55 build and genuine builtin-LZ4 checks passed.
Its kernel configuration and external ramdisk match54. Semantic DT comparison
found exactly one added boolean on the Korean board's DWC3 node, with all other
properties and reservation ranges unchanged. Fresh recovery backups, matching
stock recovery material, BOOT capacity/hash/readback and protected-partition
hashes were checked. Only BOOT was written; USERDATA was not rewritten.

Kernel55 booted, passed normal touchscreen/OSK/PAM login and selected Mali/KMS.
The saved boot-start ring covered uptime0, had taint0, zero fault signatures and
zero DWC3 failure signatures. The USB quiesce/restart markers were actually
observed in 20.30-, 45.15- and 180.41-second timed cycles, with `CONFIGURED`, no
boot change, no taint change, no new USB failures and no new kernel faults.
Actual USB SSH and, after the long cycle, USB serial were independently verified.
The second and third cycles exposed a separate GNOME presenter timeout and are
**not whole-desktop suspend passes**. Display-session qualification is recorded
separately; USB success does not excuse those failures. A changed Wi-Fi DHCP
address was read over the verified transport and checked with the same pinned
SSH key before updating the private fallback record.

The explicit recovery tool was installed root-owned and hash-checked, without
automatic activation. Three fault-injection fixtures checked wrong-role/function
refusal, cleanup after a failed wait, and not overriding a real unplug/host swap.
The actual kernel helper fixture passed quiesce, unchanged ID/VBUS, failed-halt
restore, host exclusion and the stop/runner race under ASan/UBSan. These bounded
tests do not establish indefinite reliability or physical power-button wake.

### Kernel55 GNOME presentation deadlines

The 45.15-second USB trial ended GNOME with presenter errno110, submitted=1 and
exit35; normal session recovery was required. An initial fresh post-unblank
budget passed a44.86-second trial but failed the180.41-second trial. Those
failures are retained and are not USB-driver or kernel-reboot failures.

The final presenter additionally compares elapsed BOOTTIME and MONOTONIC. A
normal sleep interval is excluded from MONOTONIC, so merely checking whether a
poll overshot that deadline can miss resume altogether. The late-clock fallback
is retained for other scheduling/kernel behavior. The real production-method
ASan/UBSan fixture adds a180-second BOOTTIME-only gap and a wake at the last
off-panel deadline. The old method fails the new fixture. The final method
passes while preserving actual-event retirement, bounded powered timeouts,
DMA-BUF identity, cache bounds and ambiguous-buffer retention.

The rebuilt AArch64 bridge and probe were installed through atomic root-owned
file replacement with prior-file backups, full GPU manifest/startup hash checks
and readback. Normal logout/login activated the bridge; no forced Shell reload
or authentication change was used. The next179.30-second timed cycle retained
the same boot and GNOME process, panel power and the lock, with taint0 and zero
new USB/kernel faults. Actual KMS frame-retirement logs and touchscreen/PAM
unlock were observed afterward. That cycle did not emit the new wait-extension
marker: this is bounded runtime acceptance, not proof of the exact cause of
both earlier exits or an overnight stability guarantee.

Lock qualification now also reads logind's actual `LockedHint` and verifies its
clearing through normal PAM. ScreenSaver.GetActive alone is insufficient: a
later live sample returned false while logind correctly reported locked and
GNOME owned the modal input grabs. The interim test interpretation of missing
automatic locking was incorrect. No unlock/authentication bypass was added.

### Kernel55 SensorProxy release after inactivation

GNOME logged `Release of light sensors failed` with claim authorization denied
while its session became inactive. Ubuntu SensorProxy3.5 checked the claim action
for both Claim and Release. Patch0001 retains authorization for new claims and
leaves `client_release()` restricted to the unique caller's existing table
entry. It does not grant another client's reference or bypass authentication.

Actual unmodified dispatch/refcount/release methods failed the inactive-own-
release fixture. The patched production methods passed with real GLib under
ASan/UBSan: new unauthorized claims fail, own inactive release succeeds, a
foreign release does not remove ownership, and polling stops only after the
last reference is released. Unknown methods remain rejected before dispatch.
The pinned Ubuntu source plus the unchanged SSP backend cross-built for
AArch64. The installed prior daemon matched a retained reviewed build; the
replacement was installed root-owned with verified backup and rollback, then
the normal service was restarted. Existing calibration/mount-matrix and
startup/lease recovery helpers were kept.

Both native accelerometer and ambient-light interfaces returned. Later samples
reported genuine158lux; `undefined` orientation while flat is not a fabricated
pose result. An actual inactive unprivileged client could not make a new light
claim, while an unowned release returned a harmless no-op. The subsequent
29.91-second direct-systemd test had no new light-release denial, no GNOME frame
failure and no USB/kernel fault. Physical heading, steps, motion/brightness
response on55 and long-term power consumption remain separate acceptance work.

### Kernel55 power-key lock readiness and desktop integration

The root power handler now uses logind's Suspend method and its normal desktop
notifications. It honors `ubuntu-lock-on-suspend` and the lockdown setting,
requests the active session's standard lock and verifies logind `LockedHint`
before the existing hardware-blanking barrier. It never sets that hint itself
or submits credentials. If locking cannot complete, sleep is canceled and the
display is restored. A locked session with ScreenSaver.GetActive=false is
accepted as locked, without waiting indefinitely for the shield animation.
The interim GetActive-based lock-check attempt timed out safely and did not
enter sleep; it was replaced, rather than changing authentication policy.

The final handler was installed with a pinned previous file, verified private
backup/readback and an active service. Seven tests cover idle-reset ordering,
lock-before-blank-before-logind ordering, rejected lock/sleep/blanking, honoring
the lock setting and the already-locked-but-inactive-shield case. A live trial
started with actual LockedHint=false, used this handler, slept30.15seconds and
returned with the same boot/Shell, active panel, actual LockedHint=true,
configured USB and zero new USB/kernel faults. Light-release denials and GNOME
frame failures were also zero. The readiness-based touchscreen/OSK harness then
completed normal PAM and checked actual LockedHint=false, no duplicate/lost
characters and no failed-session UI. Synthetic XTest motion is not physical
touch acceptance, and physical button wake remains a separate check.

After the kernel55 resume work, a bounded desktop duplex audio trial again
passed: zero sink/source hardware-error growth,186 playback and224 capture
pointer positions, both expected synthetic tones detected in the mic, no
steady clipping or new kernel faults and restored volume/mute. The first
250ms still contained203 clipped samples. Cold-capture startup quality remains
open; no raw microphone audio was saved or new physical listening confirmation
claimed. SensorProxy and the ordinary audio services remain enabled.

### Kernel55 native CP RAM boot

Read-only inspection found SS355AP using the SS310AP/SIPC5 SHMEM driver, OFFLINE,
with no active users of the three bootstrap/control nodes. The own RADIO's
BOOT/MAIN/VSS section CRCs matched. Existing NV has the expected1MiB length;
its bytes matched the privately extracted verified EFS backup. A plain MD5 did
not match its companion file; no claim of corruption was made from that
comparison, no regeneration was attempted and the existing bytes were retained.

The new bounded native tool validates the exact layout, reserved-memory bounds,
non-overlap, CRCs and private hashes before any modem IOCTL. It uses packed28-
byte firmware and16-byte security arguments. The pinned old kernel does not
map modern mode7/12 security parameters, so its normal signed BOOT/MAIN path is
used. Only reinit return11 is accepted; normal verification must return0.
Eight tests cover invalid data, real pointer/layout, nonzero return propagation,
ordering/failure and truncated replies. Public Samsung/Lineage source blobs
were verified against their pinned Git tree and attribution/license retained.

All seven most recent pre55 partition backup files and the matching stock
recovery were verified on the host. The older backup's EFS hash differed; the
most recent pre55 EFS matched the running device. PARAM differed from the
preboot backup in three bytes (offsets0x700200,0x700cfa,0x700cfb) before any CP
trial. Original backups were kept and the current PARAM was separately captured
and pinned; no field meaning or cause is inferred. Preflight then matched all
five protected current hashes and the original NV. It does not silently accept
arbitrary future differences.

An independently supervised65-second systemd trial actually loaded the four
sections into CP RAM, passed signed verification0, received both boot replies,
observed CP_START/INIT_END and normal init completion, and reported ONLINE
both immediately and five seconds later. Cleanup reset/powered off the CP and
read-only state returned OFFLINE; unit exit0. No raw partition/NV storage write,
Android init, crash/dump/panic/reboot command or status-clearing IOCTL was used.
Post-trial preflight again matched every protected/NV hash. The boot was the
same with taint0; the ordinary GPU manifest/startup hashes stayed valid and
failed-session UI was absent. The subsequent normal PipeWire duplex had zero
hardware-error growth,182/221 playback/capture positions, both test tones and
zero new kernel faults. Its193 startup-clipped samples remain a known issue.

This is CP bootstrap acceptance, not cellular service. ModemManager still lacks
a compatible native SIPC/RFS/control backend, and the trial is not enabled at
boot. No SIM was available. Registration, data, calls/SMS/VoLTE, persistent
modem crash recovery and modem sleep/reconnect remain open.


### Experimental SIPC status and recovery boundary

A second independently supervised CP trial added an original bounded FMT/RFS
receiver and two read-only GETs, power state and SIM status. It does not enable
RF, submit a SIM PIN, answer RFS or write NV. Five tests pass fragmented and
coalesced parsing, invalid lengths, exact query restrictions, sequence/type
correlation and truncated status rejection. Its wire-format reference is the
pinned public Lineage libsamsung-ipc source; that older device table does not
supply a G955N/SS355 backend. It was not installed as one.

USB SSH, pinned Wi-Fi SSH and the dedicated serial console stopped responding
after this trial was started. The unit's actual failing stage and cause have
not been recovered; neither query success, an automatic reboot nor an idle-
suspend explanation is inferred. The owner was asked only for USB reconnection.
The earlier ONLINE/offline, protected-hash and post-trial GNOME/audio receipt
belongs to the FIRST trial and does not qualify this later experiment.

Offline changes now hold a genuine acknowledged logind sleep/idle inhibitor
through trial cleanup, in addition to the kernel Android wake lock. Real-child
host tests cover ready/EOF lifetime and failure before entering the trial body.
The installed trial predates this correction and the correction has not passed
live acceptance. The existing NV's salted companion MD5 separately matched the
public Samsung format; preflight now checks it alongside SHA256. The total is
11 boot/integrity/inhibitor tests plus5 framing/correlation tests. No persistent
modem service or new kernel was enabled; current failed-trial evidence remains
pending transport recovery.


### Recovered55 freeze and no-query comparisons

USB reconnection and a short power press did not restore any response. The
owner forced a restart. Kernel55 returned with CP OFFLINE and taint0, and native
GPU manifest/startup hashes remained valid. Current protected firmware,
calibration, recovery and original NV hashes matched the privately verified
inputs; current PARAM was archived separately again. The retained previous
journal ended just after the second CP unit started, without a recorded
validation completion or new modem IOCTL sequence. No status-GET cause is
established. Last_kmsg contained bootloader records without a usable Linux
banner and was not decoded as a matched kernel panic.

Read-only partition/NV/CRC checks passed separately without opening a modem
node. The desktop's AC and battery automatic-sleep actions both read nothing.
This does not support an automatic desktop-sleep explanation. The original
buffered block-reader emitted five illegal UFS IOCTL21505 messages, i.e. TCGETS
terminal probing. The explicit os.open/os.read replacement passed three real
full preflights with zero new TCGETS errors, no modem commands and taint0. This
fix is not evidence that the harmless unsupported probe caused the hard hang.
The sleep inhibitor was also moved ahead of hashing/validation; an ordering
regression test rejects the former gap.

With model, stock recovery and seven private backups reverified, a separate
bounded no-query CP trial reached ONLINE, offlined normally, passed six more
full preflights and about60seconds of subsequent OFFLINE observation; unit
completed with taint0 and the connection intact. This is bounded acceptance of
that comparison, not indefinite modem stability.

A subsequent --observe-only trial sent no status request and received genuine
FMT frames after normal CP boot. It then lost USB/Wi-Fi/console response too.
No further modem boot trial is enabled at this checkpoint. Its exact final
stage awaits recovery of the private USERDATA progress stream, which was
fsynced independently of SSH. The host follower stopped early because its glob
also read an older completed run; its partial capture is retained, and the
monitor now requires inactive current-unit state as well as completion text.
Do not use that older marker or a missing transient unit's default Result=success
as a pass: retain LoadState and exact .service journal names. The new collector
also includes the newest individual durable logs.

Sixteen boot/integrity/inhibitor/read/cleanup and six framing/passive tests pass.
They cover actual pipe receive without any os.write, whole-preflight inhibition,
short/EINTR reads, descriptor cleanup, and attempted power-off after reset/log
failure. Added cleanup-stage markers and the later diagnostic changes have not
been exercised on the now-unreachable phone. No new kernel was flashed, no
permanent CP service was installed and the normal GNOME authentication policy
was not changed. The current scripted GDM/PAM attempt did not complete; it is not
an owner-confirmed physical-login regression, and no autologin was substituted.


### Ordinary USB existing-log audit (2026-11-21 KST)

Read-only macOS USB records from08:14–09:12 and existing Ubuntu55 receipts
were compared without handset/SSH access or a new test. Selected19/44/179-second
host reconnect gaps align with the retained controlled sleep cycles. Chrome/
ChatGPT exclusive-open denials establish application contention, not a proved
CDC/serial disconnection cause. Cable/port failure and recent ordinary-use USB
failure cannot be isolated from these logs alone. No setting, USB state, kernel,
application ownership or log was changed/cleared. The excluded modem work was
not retried or modified. See usb-existing-log-audit.md; this is a diagnosis
boundary, not a newly verified USB fix or live connectivity pass.


### Existing-log narrowing of the later USB nonresponse

The10:25–10:55 KST macOS collection records three endpoint0 timeout
completions,39 transaction errors and two bulk-pipe aborts against the S8+,
without a named S8+ detach event in the later interval. This is request
nonresponse, not proof of a healthy cable or a whole-system hang. The final
kernel follower stopped early, so its last line is not a proved freeze site
and absence of a suspend/panic marker in that short capture cannot exclude
a later transition. Host machTimestamp ordering was checked within one boot;
a wall-clock-adjustment warning limits precise cross-clock correlation.
No handset/SSH access, excluded test/code work or settings/firmware change was
performed. See usb-response-loss-window.md for remaining candidates and limits.


### System Monitor ordinary desktop launch (2026-11-22)

The live SM-G955N/kernel55 owner session had System Monitor46.0-1build1 and a
valid org.gnome.SystemMonitor.desktop entry. Initial direct and desktop-entry
launches registered the application but exposed only an unmapped1x1 X window
during the observation. Both GL and Cairo trials showed this condition while
logind reported LockedHint=yes. That does not establish the cause of the
owner's earlier app-grid failure. The owner later confirmed a visible, updating
window during the Cairo comparison after unlocking.

A GNOME stack snapshot in g955n_kms_present/wait_readable was initially
interpreted as a stall. A later stack was in the ordinary GLib main loop and
ScreenSaver.GetActive replied in0.03seconds. The snapshot is therefore not
proof of a deadlocked presenter or a justification for a driver replacement.
An incompletely supplied diagnostic launch context also produced a linker-path
error; the actual Shell and user activation-manager GPU environments matched.
That diagnostic error is not attributed to the normal app-grid launcher.

After the owner unlocked, the original GL configuration produced a sized
window in1.04seconds. The comparison unit was then stopped and the original
desktop entry launched through Gio.DesktopAppInfo using the actual Shell
environment, with child output detached from the SSH capture pipe. Its launcher
returned success and a normal window became IsViewable in1.11seconds
after the launcher returned. The app retained GSK_RENDERER=gl, mapped the Mali
vendor library and had no swrast mapping. These are process/window and library
observations, not an independent GPU benchmark or physical touch retest of
this final launch. The owner's visible-update confirmation belongs to the
preceding Cairo trial, not the final GL run.

The graph-update-interval readback remained100ms. No per-user desktop override,
software-renderer default, authentication change, kernel/firmware update or
modem/USB recovery was installed. The temporary idle inhibitor was released
and the comparison unit was inactive. The app was left running from its normal
desktop entry. Recovery is observed; recurrence prevention and the original
failure's cause are not qualified. Private evidence is under
artifacts/system-monitor-current/normal-final.private.log.


### GNOME app-grid touch cancellation repair (2026-11-22)

The owner reported that Settings and other apps also failed from the app grid.
The installed entries and activation-manager GPU environment were valid. Files,
Help, xgps and Software & Updates could create viewable windows when launched
directly, so that observation alone did not qualify grid activation. A bounded
app-icon-only extension recorded the failing grid path: BUTTON_PRESS reached
software-properties-gtk.desktop, pressed became true then false, but no native
clicked signal or application launch followed. The touchscreen had no held
tracking slots or BTN_TOUCH between tests.

The stock46 app-title hover/focus reallocation and AppIcon's unconditional leave
fake_release interacted with X11 DND grab crossings. Holding title allocation
alone improved but did not eliminate the failed clicks. The final patch keeps
a real primary press through a synthetic leave only for the same device, at
most600ms, inside both original/current mapped reactive bounds, without drag or
open menu. Actual leave, touch cancellation, drag, menu and release clear the
record. It never synthesizes clicked or invokes application activation itself.
Pointer-hover title expansion is disabled on this handset; keyboard focus and
explicit menu highlighting can expand outside a held press.

Initial repetitions mixed XTEST mouse parking with touch replay and were
excluded from hardware acceptance after that difference was identified. The
controlled comparison parked through the actual sec_touchscreen evdev device,
opened the grid, and replayed the same fresh touch. With the original resource
restored, one of three trials activated and two lost the click. The final
resource passed an initial3/3 and, after the original-code comparison and final
installation,6/6 with120/300/450ms presses. Each accepted click closed the
overview normally; the final Software & Updates window was separately verified
IsViewable. These are real-device event-replay results, not optical latency or
a long-term reliability guarantee. The owner also reported the app opening
during the investigation; that is not substituted for every replay result.

Additional touch trials activated Software & Updates, Language Support,
Additional Drivers and Settings. Language Support and Software & Updates also
created normal X11 windows with the diagnostic extension disabled. Long hold,
drag outside and an outside/back cancellation did not launch the app; a normal
tap afterward did. Actual generated-method fixtures check native release,
same-device/bounds/time/visibility/drag/menu cancellation, duplicate release,
label allocation and keyboard-focus highlighting. Full generated-module syntax
was checked. An AT-SPI-focus plus XTEST Return/Space activation probe did not
activate the app, even though accessible focus was reported; it is not counted
as a keyboard pass. A physical keyboard was not tested and that route remains
unqualified; the native key press/release implementation was not modified.

The root-owned overlay, manifest and default record were installed atomically
with matching prior backups. Source and payload hashes, existing GPU hashes,
readback and ownership passed. The startup stock-resource pin covers
appDisplay.js, so a GNOME update requires review. Normal GDM/PAM login loaded
the resource; no kernel, firmware or graphics library was replaced. The final
GNOME mapped Mali without swrast, held the KMS card, reported kernel55/taint0,
and retained the100ms System Monitor preference. Both saved user extension
preferences were restored, diagnostics were inactive and the mode-required
direct-panel extension remained enabled. A final touch launch after this
cleanup passed, confirming the repair does not depend on the diagnostic module.

Private receipts remain under artifacts/system-monitor-current/, notably
native-park-stock.private.log, native-park-final-six.private.log,
native-multiple-apps-final.private.log, gesture-regressions.private.log,
no-diagnostic-acceptance.private.log, final-runtime-receipt.private.log,
restore-session-preferences.private.log and final-integrity.private.log.
The first historical System Monitor failure had no equivalent captured click
trace; these results qualify the reproduced grid-cancellation defect rather
than retroactively proving every earlier startup failure had the same cause.


### X11 touch replay with stock GNOME Shell and GDM (2026-11-22)

The live SM-G955N was running Xorg 21.1.12-1ubuntu1.9, libinput
1.25.0-1ubuntu3.7 and Mutter 46.2-1ubuntu0.24.04.18. The touchscreen reported
direct XI2 touch. The baseline loaded the original Ubuntu appDisplay resource
and a passive trace extension. In four replay trials Software & Updates failed
to activate. The independent evdev and libinput readers recorded both ends of
the test contacts. The Shell saw emulated button presses from X11 at the proper
icon coordinates. Logged failures cleared the pressed state before the contact
ended, with no drag, menu or clicked signal. A bounded debugger capture
identified the AppIcon call from clutter_stage_update_device under
meta_cursor_tracker_set_pointer_visible. This places the defect at Mutter's
Clutter repick, after the original input reached the compositor.

The package already carried the upstream absolute-coordinate repick for
incoming emulated touch. The cursor visibility change initiates a new pick
without an input event and loses that decision during the press. This patch
remembers the emulated button state for automatic repicks while its implicit
grab is active, clearing it at cleanup. It keeps real bounds checks and event
delivery. A fixture extracted the original and patched decision from the
source and checked the lost focus case, ordinary pointer, native touch and
post-release behavior.

The patched shared library cross-built from the hash-checked Ubuntu source
archives with the package patches applied. The candidate's initial build-tree
RPATH was normalized before graphical activation. The final AArch64 ELF agreed
with the matching Ubuntu binary for SONAME, installed RPATH, NEEDED entries
and all 1,202 public exports. Its installed SHA256 was
9ec9d72080a958fda83b22bc57911cd7205ed32e0aefe5aef8be964fdb13e83d. The stock
library and previous GDM and GNOME resources were backed up. The local
appDisplay, keyboard and GDM resource overrides were removed and the existing
GPU startup hashes were verified. The passive diagnostic extension was disabled
and the prior extension preferences restored.

Using the actual SM-G955N evdev and X11 routes, the stock Ubuntu Shell app grid
activated Software & Updates in 6/6 repetitions with 120, 300 and 450 ms
presses. Three included a mouse-to-touch transition. Software & Updates,
Language Support, Additional Drivers and Settings also activated in a separate
group. The Software & Updates and Settings windows were confirmed viewable.
Long hold, drag outside and leaving/re-entering a cancelled tap did not launch
the app, and the next normal tap activated it. The same kernel55 and Mali/KMS
output remained active and the kernel taint readback was 0. System Monitor
retained its 100 ms refresh preference.

Both normal GDM sessions loaded the replacement Clutter library, X11 and
unmodified GDM resources. Real-device touchscreen event replay selected the
account, brought up the password prompt and entered the password through the
on-screen keyboard, completing ordinary PAM and starting the desktop twice.
The counted repetition opened the password prompt on the first account tap.
Verification used replay through sec_touchscreen on the physical handset.
A separate manual finger acceptance run and suspend/resume qualification were
not performed for this change.

The private receipts are under artifacts/x11-touch/ and include the stock
combined input trace, full cancellation stack, final-apps, stock-shell-window
and stock-gestures records.

## 2026-11-22 — Native GNOME hardware integration on kernel55

- The standard SensorProxy proximity interface advertises availability. A
  live D-Bus claim started the proximity FIFO and reported four near/far pairs
  while the owner covered and uncovered the handset sensor. The client released
  the claim and confirmed the original scan, length, enable and polling
  attributes. No synthetic sensor events were used.
- SensorProxy exposes the accelerometer orientation and measured ambient light.
  GNOME's automatic-brightness setting was enabled. The normal X11 session's
  fixed `default` output exposes no runtime rotation, and Mutter reports
  `PanelOrientationManaged=false`. GNOME's rotation lock still requires an
  actual rotatable built-in output with correctly mapped touch coordinates.
- GeoClue is installed and Ubuntu gpsd has no configured input. The vendor
  location hub already owns `/dev/ttyBCM` and the Broadcom sensor/control
  devices. The examined live vendor configuration provides no exposed NMEA
  endpoint. GNSS location acceptance requires a vendor location producer and
  a fresh fix delivered to GeoClue.
- ModemManager is running and lists no modems. The exposed Samsung SIPC
  channels do not supply a supported control interface to ModemManager. Mobile
  Network settings and SIM registration are pending a functional backend.

### Automatic brightness ramp on kernel55

The Ubuntu 46.0-1ubuntu1.24.04.1 ARM64 power candidate built with the Ubuntu
source patches, and the device resolved its dependencies without undefined
symbols. A local fixture executed the patched ramp step and covered gradual
convergence, a missing write acknowledgement and a disabled adjustment.
Offline staging accepted the matching AArch64 build and rejected a rootfs with
a different package version.

The first activation attempt exposed a stalled graphical session. Mutter's
DisplayConfig and IdleMonitor calls timed out, including against the original
power service, and the compositor backtrace showed a synchronous KMS page
completion wait. X11 reported the monitor off. The established X11 wake
operation restored both Mutter calls without restarting the desktop or
touching login state. Retrying the version-matched power service then passed.

The running candidate reported 6% via its GNOME D-Bus brightness property.
The standard automatic-brightness setting accepted off and on, and the
original on value was restored. Accelerometer, ALS and proximity remained
available. A 32-second live recording saw a stable 338 lux at 6% brightness.
The ramp code is fixture-tested and installed; a timed physical light change
and optical transition are still open. This recording also does not qualify
the display path across arbitrary DPMS and system sleep sequences.

### DECON off-panel flip deferral on kernel55

A prior locked session tied up Mutter's main thread in the synchronous DRM
completion wait after X11 reported DPMS off. The new userspace presenter
yields while the connector is blank, retaining the current and pending
scanout buffers. Its X11 integration can use a third buffer to continue
handling redraws, and releases retained buffers only when the corresponding
replacement has reached the panel.

The host KMS fixture passed blank-before-submit, blank-after-acceptance, real
wake completion, timeout and DMA-BUF identity tests. A fixture running the
actual X11 ownership code passed 150 swaps while blank, followed by wake
with retirement of both replaced buffers. The AArch64 compositor module
built from the pinned sources. The owner's ordinary GNOME X11 session loaded
it via the built-in shell restart, with the same process and open session.

On the physical handset, three X11 DPMS off/on cycles passed. During each off
interval, both Mutter DisplayConfig and IdleMonitor calls completed. Each
wake retained the same GNOME process, Mali library and DECON DRM file. The
installed startup manifest and module digests matched after the test. A
separate system suspend and long unattended wake soak remain unqualified
for this module revision.

### Kernel55 suspend follow-up after the DECON userspace fix

A 25-second RTC alarm was programmed for the normal system suspend route.
The kernel journal recorded suspend entry and exit 25.79 seconds apart.
USB transport dropped during the test and returned. Once connected, the
owner's original GNOME process still mapped the candidate and held DECON,
Mutter answered the idle query, Wi-Fi was connected, the USB gadget was
configured, and the RTC alarm was clear. The transport timeout prevented a
continuous remote trace across the sleep interval.

### Native GNSS HAL and sensor follow-up

The handset's vendor GNSS engine started from a standalone scratch
configuration with the original XML namespace. Initially its FIFO opens and
the HAL's FIFO opens targeted different directories. Sharing the stock
`/data/vendor/gps` path within the trial allowed mode selection and start.
A longer session previously crashed in the location request marshaller.
The matching vendor library calls the AArch64 callback at offset 96 with one
boolean. The corrected client handled one request over 75 seconds without
that crash. HAL open, initialization, standalone mode and start returned
success; stop returned -1. The test produced no NMEA, satellite reports or
fix callbacks. GeoClue availability remains dependent on real receiver data.

A four-second native IIO capture recorded 19 rotation vectors, 19 gyroscope
records, 16 calibrated-magnetometer records and one step-counter record
with total zero while stationary. The original buffer and mask state was
restored and SensorProxy restarted. The first rotation vector's magnitude
was approximately 1,000,000 raw units, so a Q30 conversion is inappropriate
for this device. Physical heading calibration, a step increase and GNOME
rotation remain unqualified.

### Kernel55 location integration and sensor recheck

Ubuntu Location Services is enabled. Daemon and socket files passed readback
and systemd verification. The ordinary GeoClue demo received coarse network
locations with 25–26 km reported accuracy. The GNSS service accepted an
actual GeoClue connection. The vendor HAL accepted NTP-synchronized UTC,
cached network position and 122,527 bytes of fresh Broadcom orbit data from
the phone's own configured source. The assistance cache was reused on
subsequent requests. Network coverage submissions are disabled.

Process and filesystem checks showed the sensor hub and vendor GNSS engine
initially opened different instances of their named FIFO. After sharing the
existing vendor IPC directory, both processes opened the same pipe pair and
the HAL produced valid NMEA. An independent local reader received GGA, GSA
and RMC messages with zero fixed records.

The remaining early receiver exit was an actual SIGSEGV in
NdkSensorsInfo → NdkSensorsStart, where the optional Android inertial fusion
expects Android SensorService. The private vendor configuration now disables
that option. A supervised retest produced 245 checksum-valid NMEA sentences
with successful start and stop. The standard Ubuntu sensor service stays active.

Owner motion produced transitions between `normal` and `left-up` in
SensorProxy and real ambient-light changes. The stock orientation-lock policy
accepted on and off and was restored to its original value. XRandR reported
the fixed `default` output and rejected a left-rotation dry run. Mutter's
`PanelOrientationManaged` remains false. No genuine ModemManager modem was
present, although the Samsung SIPC device nodes were available for a future
qualified backend. LTE cell-based lookup and operator registration were not
exercised.

In the 180-second trial through the installed GeoClue service, the corrected
receiver stream delivered 1,389 checksum-valid NMEA sentences and stopped
with a zero HAL result. No satellite-status report or location fix was
received. The desktop client continued to get the network estimate with
25 km reported accuracy. Readback matched all ten deployed runtime files.
The Location Services preference was enabled, system time was synchronized,
and the sensor hub, SensorProxy and GNSS socket were active.


### Field GNSS and recovered LTE trace on kernel55

After moving the handset to a location with better sky visibility, the pinned
Wi-Fi host key identified its new lease. The normal GeoClue client started
with the 25 km network estimate. A 275-second request delivered 3,526
checksum-valid NMEA records, 144 HAL location callbacks and 246 nonempty
satellite reports. GeoClue then reported estimates down to 1 m. This is the
accuracy reported by the service. Absolute position error was not measured.
The HAL stopped with result zero. No coordinates or AP identifiers are retained
in the shared record.

The new GNSS BSP preparation unit ran successfully on demand on the handset.
The startup now allows the original hub to create its FIFO before opening the
vendor engine. A 95-second integration check then produced 606 NMEA records and
a successful stop, with only network estimates during that shorter interval.
A second 275-second acquisition ended normally with 2,244 valid NMEA
records, no satellite reports and only network estimates. The Broadcom
hub recorded CORE_ON and CORE_OFF for each trial, with no system suspend
between those markers. Repeatable satellite acquisition remains open.
The offline GNSS staging path was exercised twice in the Ubuntu builder with
the real reviewed ARM64 client, a fixture Ubuntu group database, and the socket
enablement link. It rejected a non-ARM64 input without replacing the client.
No newly generated rootfs was installed for this check.

The recovered, fsynced log for the earlier passive CP trial reports 28 FMT
frames, two RFS frames, zero transmitted status queries and no RFS replies.
Its last durable entry is CP ONLINE after the observation completed. No
shutdown completion or post-off read appears. The retained kernel journal
ends earlier, so the failure is narrowed to after passive observation and
before confirmed CP cleanup. It cannot distinguish reset, power-off, cleanup
of the endpoints or a concurrent kernel failure. Source inspection also
shows that the CP reset IOCTL can panic when the PMU reset does not reach
its expected state. The recovered record does not show that timeout.
ModemManager still exposes no usable modem, and SIM registration and mobile
data remain unverified.


The bounded CP trial now records start and completion for reset, power-off,
each endpoint close and wake-lock release. If an endpoint close raises,
the remaining closes and wake-lock release are still attempted. The host
regression test injects an RFS close failure and verifies the remaining
cleanup order and incomplete marker. This is a diagnostic improvement.
The modified trial has not been run on the handset.


### Standard Compass delivery on kernel55

The SM-G955N rotation-vector sensor advertises the pinned 25-byte packed
layout. The new ARM64 SensorProxy backend published 37 finite heading updates
to the standard Compass API during one five-second claim by the Geoclue
account. Release cleared the rotation-vector enable bit and restored scan,
buffer length, enable and polling. The same service still advertised
accelerometer, ambient light and proximity. Cardinal, tilted, wraparound,
zero and vertical-vector math fixtures passed. Absolute heading, movement
tracking and physical calibration are open. No latitude or longitude was
requested or recorded during this check.


### Mali native-buffer rotation on kernel55

An AArch64 EGL diagnostic used the same pinned libhybris EGL libraries and
owner X11 display as the normal session. Mali-G71 rendered both 90-degree
turns from a 2960x1440 RGBX gralloc buffer into a 1440x2960 RGBX gralloc buffer.
Both native handles matched the direct presenter's linear layout and each
turn's four pixel regions matched their expected colors. Diagnostic FBO
readback verified the result; no CPU mapping was used in the transform.
The test did not control the panel, acquire DRM master or replace GNOME.


### Repeated modem shutdown on kernel57

The timer cancellation patch applied to the pinned kernel and passed the
actual-helper fixture. The kernel57 build plan adds only proposal0055 to
kernel55. Kernel config, board DT and initramfs are byte-identical. A fresh
TWRP capture verified all seven partition backups and the current kernel55
rollback image. Only BOOT was written, and readback and protected partitions
verified before reboot. Kernel57 booted with taint0 and the standard GDM,
SensorProxy and GNSS socket active.

The first modem preflight refused a changed PARAM hash before powering the
CP. The current PARAM was archived independently and checked twice. Its
three differences match the previous recovery-to-normal boot history pattern.
The original raw backup is preserved. No firmware or NV writes were made.

On the same kernel57 boot, four passive and three read-only GET trials sent
the reviewed RAM image, received live SIPC frames and completed reset,
power-off, endpoint close and wake-lock release. All seven ended OFFLINE with
taint0. The control experiment changes the kernel timer code and uses enhanced
userspace cleanup tracing, so it does not establish the exact historical
hang site. The live dispatcher separately tracked the two correlated generic
GET results and asynchronous status notifications. The firmware's SIM
initialization/ready notifications do not verify a physical SIM or carrier
registration. No typed GET state reply was accepted. The RFS endpoint received
two command 0x11 frames in the passive capture, and no RFS reply was sent.
ModemManager still lists no modem.


An additional RTC-alarmed freeze test recorded a 25.49-second interval
between the kernel suspend entry and exit messages. Both USB and Wi-Fi
answered afterward with the pinned handset key and the same boot ID. GDM,
SensorProxy and the GNSS socket were active, taint remained zero and the
RTC alarm was clear. The first duration checker used the BOOTTIME/monotonic
difference, which did not advance during this s2idle interval. Acceptance
uses the kernel PM records and the independently checked transport recovery.

### Kernel57 SM-G955N runtime rotation

A separately started Xorg exposed a connected 1440×2960, 60 Hz `DSI-1`
with `ConnectorType: Panel`. Manual RandR transitions normal, left, right,
inverted and normal checked all four physical framebuffer regions after
each transition. An independent Mali-G71 probe verified the exact
production GPU transform by readback and checked the producer EGL binding.
KMS accepted the generated DMA-BUFs in one modeset and three completed flips.
The probe's CPU readback was used only for pixel verification. The standard
connector and buffer lifetime paths handled the panel submissions.

A temporary GNOME trial stages the two drivers, Xorg configuration and GPU
manifest together. Test status and limits are in
[native rotation requirements](native-rotation-requirements.md).

### Kernel57 stock RFS file-open qualification

Stock vendor dispatch identifies RFS command 0x11 as file open. A new passive
receipt classified one read-only and one potentially modifying open request
after validating the wire lengths. It exposed no filenames, file contents
or raw request payload. The test sent no RFS reply. CP exited OFFLINE, on the
same boot with taint zero. ModemManager still detects no modem.

### Kernel57 GNOME rotated-output and logged-in sleep retest

The normal GDM touchscreen/OSK/PAM path entered Ubuntu GNOME. The original
portrait candidate passed three screen-off/on cycles with the same shell,
Mali renderer and KMS file. Its first quarter-turn exited while creating
the GPU program. The rebuilt provider-dispatch version completed 0°, 90°,
270°, 180° and 0° through Mutter while preserving the session. Each
transform matched the direct touchscreen's coordinate matrix. The shell
reported at least 60 KMS retirements in the test session.

The subsequent RTC suspend produced an approximately 24-second elapsed
entry/exit interval in the kernel. USB and Wi-Fi returned and the same
logged-in GNOME session remained on the same boot, with taint zero.
The immediate journal read timed out and the attempted post-resume touch
unlock did not complete. The trial rolled back the bridge and Xorg files.

In a separate logged-in kernel57 audio test, the internal microphone
recorded both speaker tones. The playback and capture pointers advanced,
with zero hardware-error growth and zero steady clipping. The initial
capture transient showed 201 clipped samples during its first 250 ms.

### Kernel57 rotated touchscreen and graphics default

Before the resize fix, a landscape touch at panel coordinate (310,705)
landed at X11 (1097,637) instead of near (2255,310). Those ratios match the
old portrait dimensions still used in Xorg's absolute input normalization.
The revised fbdev hook calls the exported Xorg desktop-dimensions update as
part of the resize. The test then injected touch into the real device
and an independent X11 client received it at the calculated target in
normal, left, right, inverted and normal configurations.

With the final binaries verified, default activation saved their hashes
along with the Xorg configuration. A warm reboot recreated the lease
and normal GDM touch/PAM login reached GNOME with Mali/KMS in use. All five
touch/orientation transitions passed again without kernel taint.

A same-boot X11 fixture measured mean CPU 16.74% through the legacy copy
path and 9.07% through direct KMS for three scripted window-move runs per
path. Each run observed 179 of 180 position changes. Both paths measured
17 ms median window geometry gaps. This is not an optical latency or FPS
measurement.

Two further RTC suspend trials recorded 23.48 and 23.56 seconds and retained
the same GNOME and KMS session. An injected swipe brought up the real PAM
lock prompt and hardware-style key input completed unlock. Fixed-location
OSK input was not reliable in that test. It requires a readiness-aware OSK
test before claiming touch-only unlock after power transitions.

After the warm reboot, nine samples over 93.47 seconds saw the same
GNOME process and KMS ownership, with no new kernel fault signature.
Three postboot DPMS off/on cycles retained Mali/KMS and a responsive
Mutter bus. The standard GNOME rotation-lock and automatic-brightness
settings accepted both values and were restored to their previous values.
The real SensorProxy reported accelerometer, ambient light and proximity
interfaces. These setting tests did not require external motion or shade.

A postboot RTC cycle lasted 23.93 seconds and the same GNOME process
retained KMS after wake. USB and Wi-Fi recovered. With the real
screen-lock prompt visible and focused, the readiness-aware touchscreen
test used the numeric OSK. It counted one inserted character per key,
preserved the numeric page and completed normal PAM unlock. It checked
that logind cleared LockedHint, the boot and Shell were unchanged,
no failed-session screen appeared and no new kernel fault was observed.

The default build also passed injected power-button events through the
real GPIO evdev device. A long press showed the Power Off confirmation,
which was cancelled. The next short press made the power-key service
request suspend. The RTC woke the same boot and GNOME/KMS process after
23.98 seconds with taint zero. USB and Wi-Fi returned. Wake was by RTC
during this test.

### APT compatibility and private fbdev on kernel57

A root APT simulation using the handset's current indexes selected 52
upgrades, including systemd packages, with no packages added or removed.
No Xorg, Mutter, GNOME Shell, GDM or PipeWire packages were selected.
The installed package audit showed the original rotation module and the
touch Clutter library in Ubuntu package paths.

After migration, dpkg verified the stock fbdev package and the active Xorg
process mapped its rotation driver from the private GPU prefix. The
handset passed touchscreen login, all four rotation/touch targets, and warm
reboot with default GPU output. The reboot retained normal touchscreen
login, three DPMS off/on cycles and a 23.95-second RTC suspend/resume with
the same GNOME/KMS process and zero taint. Orientation lock and ambient
brightness settings accepted both values and were restored. The acoustic
loopback detected both test tones, with no new PCM hardware errors. After resume, the
numeric OSK accepted each injected touch exactly once and completed PAM
unlock. The timing probe put the microphone clipping between 18.31 and
26.46 ms after the beginning of capture, with no steady clipping or new
kernel fault signature.

### Standard graphics and audio prerequisites on SM-G955N

On kernel57 the new AArch64 fixture reached the native DECON DSI/PRIME
preflight and exited with a missing Panfrost render node. The only DRM
device was the DECON display card. The GPU render and present stages and
normal GNOME Wayland login, rotation and suspend are open.

The actual PCM policy passed the extracted-method fixture. Kernel58 built
with the exact kernel57 configuration and feature patch set plus the new
ALSA scope patch. Its packaged image reused the verified kernel57 external
ramdisk and boot parameters. Initial TWRP access succeeded, but the USB
connection disappeared during BOOT backup. The incomplete backup cannot
be used. No BOOT write was performed and the kernel58 and stock ALSA
hardware trials are pending.

### DECON-card GBM qualification

The Panfrost fixture now exercises the display-file GBM setup used by stock
Mutter. It checks the Mesa renderer and draws to linear DMA-BUFs allocated
with the scanout usage flag. The ARM64 build with Ubuntu Mesa 25.2.8 headers
passed with warnings as errors. The simulated KMS presenter check passed and
the Python suite reported 155 tests with 9 skipped.

The Ubuntu ARM64 Mesa package contains `exynos_dri.so` and `panfrost_dri.so`.
The current DECON wrapper reports `g955n-decon`; whether stock Mesa can
automatically pair that DRM device name with Panfrost remains unverified.
The handset did not enumerate on the host during this continuation, so the
new mode and the #58 ALSA kernel were not tested on hardware.

### Kernel58 stock Ubuntu audio and current GNOME regression checks

Recovery ADB confirmed SM-G955N. The host verified fresh copies of BOOT,
RECOVERY, EFS, CPEFS, RADIO, MISC and PARAM against the device hashes.
The trial changed BOOT alone and verified its readback. Kernel58 then
booted with taint zero and reported the native RDMA0/WDMA1 ALSA guard.

The live guard denied opens on 38 built-in PCM, compressed and debug nodes.
An isolated trial loaded Ubuntu's ALSA SPA module and passed a simultaneous
speaker-playback and internal-mic capture test. The permanent launcher
initially rejected the marker under the mode-1777 runtime directory and
the deployment restored the previous audio stack. Moving the receipt to a
root-managed systemd state directory allowed the stock module to run while
preserving the strict path check and same-boot validation.

The permanent stock audio setup passed the same duplex test both immediately
and after a warm reboot. It detected both speaker tones in internal mic
capture, with zero steady-state clipping, hardware error growth, xruns or new
kernel fault signatures in the test. No recording was retained. The brief
cold capture transient remained, with 217 saturated samples between 18.75 and
26.92 ms after capture began on the post-reboot test. Subjective audibility
and voice quality were not measured.

The current GNOME X11 session passed GDM touch and OSK/PAM login after each
boot. Temporary monitor rotations exercised 0, 90, 270, 180 and 0 degrees in
Mutter and synthetic taps through the touchscreen evdev device reached the
expected X11 targets. An RTC-alarmed s2idle trial recorded 23.46 seconds
between kernel PM entry and exit, kept the same shell, KMS and boot, and
recovered USB and Wi-Fi. The GNOME lock screen accepted the touchscreen OSK
password and resumed the same session with zero new kernel fault signatures.

Both Panfrost modes reached the DECON DSI and PRIME capability checks on
kernel58 and returned status 3 because the kernel publishes no accessible
Panfrost render node. These checks do not qualify Panfrost panel output or
stock GNOME Wayland login, rotation or resume.
