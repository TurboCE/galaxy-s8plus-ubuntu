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
| GPS / GNSS | Location service dump collected privately | Fresh outdoor fix with plausible coordinates and timestamps | Not tested |
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
