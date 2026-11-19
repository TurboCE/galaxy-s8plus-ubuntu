# Hardware validation

Status date: 2026-11-19. Android discovery does not prove end-to-end operation.
Native Ubuntu 24.04 userspace has booted on the phone under systemd.
No row may become PASS from configuration or compilation alone.

Runtime capture tooling exists in scripts/collect_linux.py; it refuses an
unexpected kernel/DT. Stock dmesg was denied and kernel logcat returned no
entries. Thus neither stock nor Ubuntu logs have been certified clean.
Twenty-three host tests pass; these are tooling checks, not hardware acceptance tests.
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
| Boot / storage / USB recovery | ADB authorized, stock 4.4.111; partition names readable | Repeated cold boot, logs, ext4 read/write, recovery path | Failed kernel-22 stability: three unexpected reboots; two have pointer/state corruption traces and the third has a watchdog/safe-panic reset record, despite initially passing boot/login. Restored complete known-working kernel-15 BOOT with readback; Ubuntu/GDM/Wi-Fi returned, taint 512 remains. Cold-boot/suspend qualification pending |
| Display / touch | SurfaceFlinger active; input proc access denied | Correct resolution, touch coordinates, rotation, brightness | Partial: manual OSK login/desktop confirmed. Desktop remains llvmpipe and sluggish. Experimental damage-driven presenter is quarantined after kernel-22 failures; original presenter restored. Rotation/brightness/resume and account touch activation pending |
| GPU | Mali-G71, r16p0, GLES 3.2 renderer | EGL renderer Mali/Panfrost, actual rendered frames and sustained workload; reject llvmpipe | Partial: private libhybris Mali-G71 shader/readback passed 10000 frames at 1440x2960 in 21.989 seconds; private HWC2/wlroots/tinywl cross-link completed only, never executed on phone. Buffer/fence/presentation, thermal qualification and resume pending |
| LTE data | Telephony service dump collected privately | SIM registration, mobile-only DNS/HTTPS, reconnect after suspend | Not tested; owner reports no SIM |
| Calls / SMS / VoLTE | No call/message test performed | Incoming/outgoing calls with two-way audio, SMS, carrier IMS registration | Not tested; no SIM |
| Wi-Fi 2.4 / 5 GHz | Framework dump collected privately | Separate association + traffic test on both bands, reconnect | Partial: three explicit disconnect/reconnect cycles per band, each with bound-interface TLS HTTP 200 and 254968-byte download at 2467/5745 MHz; original profile restored, same boot. Full suspend/resume pending |
| Bluetooth | Framework dump collected privately | Discovery, pairing, audio and reconnect | Partial: original-address controller RAM and 9 discovered devices; temporary ROM/H4 only, firmware/pairing/audio/resume pending |
| GPS / GNSS | Location service dump collected privately | Fresh outdoor fix with plausible coordinates and timestamps | Not tested |
| Accelerometer / gyroscope | LSM6DSL listed by sensorservice | Live samples respond to motion; units, axes, timestamps | Partial: LHD/MCU initialized and 220 native IIO records each with changing payloads/increasing timestamps; controlled motion, units, axes and desktop integration pending |
| Other sensors | LPS22H pressure listed; full sensor list private | Magnetometer, proximity, light and other present sensors, calibration | Incomplete: ambient light capture only one zero-count event; no physical response acceptance |
| Cameras | Camera service dump collected privately | Front/rear preview, capture, video, autofocus and flash | Not tested |
| Audio | Audio service dump collected privately | Speaker, earpiece, microphones, headphone jack and routing | Partial: normal RDMA0 2-second PCM progress passed, acoustic check postponed. Installed v2 scoped plugin exported Off/HiFi/speaker in a muted 21-second trial; both core/policy traces opened only pcmC0D0p. Default policy remains masked; microphone/headphone/kernel-fault acceptance pending |
| Charging / battery / thermals | Power service dump collected privately | Current/voltage/temp telemetry, controlled charge and thermal limits | Not tested |
| CPU scaling / idle | No measured Android baseline | Both cluster frequency response, idle residency, unchanged governor and thermal policy | Partial: bounded CPU0/CPU4 load completed, both frequencies changed and both idle states advanced, policy unchanged, peak observed 54 C. Battery draw/full thermal/suspend qualification pending |
| Suspend / resume | No Ubuntu evidence | Measured idle draw, wake sources, repeated resume with radio/GPU recovery | Not tested |
| NFC / fingerprint / iris | No end-to-end baseline tests | Device enumeration and actual sensor/service operation | Not tested |
| USB OTG / external display / SD | No end-to-end baseline tests | Hotplug, keyboard/storage, external frames and SD read/write | Not tested |
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
