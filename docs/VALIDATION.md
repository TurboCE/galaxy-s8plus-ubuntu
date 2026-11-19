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
| GPU | Mali-G71, r16p0, GLES 3.2 renderer | EGL renderer Mali/Panfrost, actual rendered frames and sustained workload; reject llvmpipe | BOUNDED PASS for normal GNOME GLES/EGL rendering/composition: real Mali-G71 shell, private EGL/Exynos gralloc and no swrast; three client/overlay/calendar trials passed on26. Normal27 login also loads Mali. Overall objective remains PARTIAL because sustained stability and physical response latency are unqualified. XPutImage CPU copying remains; panel commit counts are not rendered FPS |
| LTE data | Telephony service dump collected privately | SIM registration, mobile-only DNS/HTTPS, reconnect after suspend | Not tested; owner reports no SIM |
| Calls / SMS / VoLTE | No call/message test performed | Incoming/outgoing calls with two-way audio, SMS, carrier IMS registration | Not tested; no SIM |
| Wi-Fi 2.4 / 5 GHz | Framework dump collected privately | Separate association + traffic test on both bands, reconnect | Partial: three explicit disconnect/reconnect cycles per band, each with bound-interface TLS HTTP 200 and 254968-byte download at 2467/5745 MHz; original profile restored, same boot. Full suspend/resume pending |
| Bluetooth | Framework dump collected privately | Discovery, pairing, audio and reconnect | Partial: original-address controller RAM and 9 discovered devices; temporary ROM/H4 only, firmware/pairing/audio/resume pending |
| GPS / GNSS | Location service dump collected privately | Fresh outdoor fix with plausible coordinates and timestamps | Not tested |
| Accelerometer / gyroscope | LSM6DSL listed by sensorservice | Live samples respond to motion; units, axes, timestamps | Partial: LHD/MCU initialized and 220 native IIO records each with changing payloads/increasing timestamps; controlled motion, units, axes and desktop integration pending |
| Other sensors | LPS22H pressure listed; full sensor list private | Magnetometer, pedometer, proximity, light and calibration | INCOMPLETE: one ambient-light event is not physical response acceptance. Magnetic/u64 accumulated-step parsers pass protocol fixtures but new live/physical measurements are pending. SensorProxy accel/light prototype builds but is uninstalled and lacks abrupt-termination recovery; stock HRM accelerometer misclassification is not an actual accel pass |
| Cameras | Camera service dump collected privately | Front/rear preview, capture, video, autofocus and flash | Not tested |
| Audio | Audio service dump collected privately | Speaker, earpiece, microphones, headphone jack and routing | Partial: normal RDMA0 2-second PCM progress passed, acoustic check postponed. Installed v2 scoped plugin exported Off/HiFi/speaker in a muted 21-second trial; both core/policy traces opened only pcmC0D0p. Default policy remains masked; microphone/headphone/kernel-fault acceptance pending |
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
