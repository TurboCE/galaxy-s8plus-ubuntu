# Hardware validation

Status date: 2026-11-19. Android discovery does not prove end-to-end operation.
Native Ubuntu 24.04 userspace has booted on the phone under systemd.
No row may become PASS from configuration or compilation alone.

Runtime capture tooling exists in scripts/collect_linux.py; it refuses an
unexpected kernel/DT. Stock dmesg was denied and kernel logcat returned no
entries. Thus neither stock nor Ubuntu logs have been certified clean.
Sixteen host tests pass; these are tooling checks, not hardware acceptance tests.
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
| Boot / storage / USB recovery | ADB authorized, stock 4.4.111; partition names readable | Repeated cold boot, logs, ext4 read/write, recovery path | Partial: Ubuntu/systemd/USB login and 113 GiB root observed; kernel 9 USB SSH transferred data. Kernel 11 desktop running; repeated cold-boot/suspend qualification pending |
| Display / touch | SurfaceFlinger active; input proc access denied | Correct resolution, touch coordinates, rotation, brightness | Partial: owner confirmed GDM login, touch/OSK authentication and GNOME desktop on kernel 11; CPU/fbdev only, rotation/brightness/resume pending |
| GPU | Mali-G71, r16p0, GLES 3.2 renderer | EGL renderer Mali/Panfrost, actual rendered frames and sustained workload; reject llvmpipe | Partial: private libhybris Mali-G71 shader/readback passed 300 frames at 64x64 and 1440x2960; desktop presentation, sustained workload and resume pending |
| LTE data | Telephony service dump collected privately | SIM registration, mobile-only DNS/HTTPS, reconnect after suspend | Not tested; owner reports no SIM |
| Calls / SMS / VoLTE | No call/message test performed | Incoming/outgoing calls with two-way audio, SMS, carrier IMS registration | Not tested; no SIM |
| Wi-Fi 2.4 / 5 GHz | Framework dump collected privately | Separate association + traffic test on both bands, reconnect | Partial: association/DHCP/DNS/TLS HTTP 200, 254968-byte download at 2467 and 5745 MHz; reconnect/suspend pending |
| Bluetooth | Framework dump collected privately | Discovery, pairing, audio and reconnect | Partial: original-address controller RAM and 9 discovered devices; temporary ROM/H4 only, firmware/pairing/audio/resume pending |
| GPS / GNSS | Location service dump collected privately | Fresh outdoor fix with plausible coordinates and timestamps | Not tested |
| Accelerometer / gyroscope | LSM6DSL listed by sensorservice | Live samples respond to motion; units, axes, timestamps | Partial: LHD/MCU initialized and 220 native IIO records each with changing payloads/increasing timestamps; controlled motion, units, axes and desktop integration pending |
| Other sensors | LPS22H pressure listed; full sensor list private | Magnetometer, proximity, light and other present sensors, calibration | Incomplete: ambient light capture only one zero-count event; no physical response acceptance |
| Cameras | Camera service dump collected privately | Front/rear preview, capture, video, autofocus and flash | Not tested |
| Audio | Audio service dump collected privately | Speaker, earpiece, microphones, headphone jack and routing | Not tested |
| Charging / battery / thermals | Power service dump collected privately | Current/voltage/temp telemetry, controlled charge and thermal limits | Not tested |
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
