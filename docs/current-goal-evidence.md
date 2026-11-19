# Current seven-requirement evidence audit

This is an incomplete-goal checkpoint. No requirement is removed or weakened by
this audit. The latest running kernel is32 with ABOX safety and SSP sysfs count fixes,
plus the reversible MIF-floor mitigation. Native sensor/brightness response,
actual Mali GNOME trials and100 sensor-active DPMS cycles have bounded passes.
The initiating corruption without the floor and the remaining hardware/UI
acceptance are still open. This is an incomplete-goal checkpoint.

| Owner requirement | Evidence actually available | Remaining acceptance |
| --- | --- | --- |
| Boot, select account and enter GNOME by touch | Owner confirmed manual account/password/desktop after repaired GDM and a26 reboot; authentication/autologin settings unchanged | Repeated stable boots and long use; power-hang failures prevent overall pass |
| Real accelerated GNOME and fast touch response | Actual normal GNOME Mali-G71, EGL/Exynos gralloc, no swrast; three26 composition/popup passes; real27 Mali login | Physical response/latency and sustained application/display-power workload; commits/sec are not FPS |
| No kernel errors; fix real driver defects | Reproduced/fixed DPP metadata lifetime, pan/power serialization, QoS ordering and Ondemand lifetime source bugs; private real RCU/stack-check fault records | Actual initiating corruption remains unresolved.26/27/28 hang;29 never reached Ubuntu due to a build error. Corrected30 also auto-rebooted without the diagnostic floor. Proposal32 improves a recovery path only |
| Accel, magnetic, pedometer and ambient-light operation | Real31 raw records;32 native accel/light stream, owner tilt/shade response, measured mount matrix and actual SIGKILL cleanup. Step increase and physical magnetic/gyro acceptance remain open | Boot-time genuine firmware/calibration, actual claim/SIGKILL cleanup, live magnetic/step/ALS and physical motion/light acceptance |
| Microphone and speaker | Bounded selected speaker PCM progress; scoped audio policy experiment | Acoustic speaker and microphone acceptance, stable routing and safe default policy. WirePlumber remains masked |
| LTE modem without driver errors | Original protected RADIO/calibration preserved; modem device nodes; no SIM supplied | Actual modem bootstrap/driver checks; native modem control. Later SIM registration, mobile-only data/reconnect; no-SIM is not a modem pass |
| Automatic rotation/brightness and normal Ubuntu toggles | 32 actual reported light2..189lux and backlight1091..11961 response; standard brightness setting roundtrip. Sensor orientation corrected; fbdev dynamic rotation missing | Runtime screen rotation with correct touch mapping, genuine light response/backlight control, and actual Ubuntu enable/disable behavior |

Supporting state: docs/VALIDATION.md, greeter-touch-validation.md,
kernel26-power-investigation.md, ondemand-panel-lifetime.md,
compiler-reference-comparison.md, panic-decoder-and-safe-recovery.md and
native-rotation-requirements.md. Device records/images and addresses remain in
ignored private artifacts, not this document.

## Recovery and controlled display-power comparison

The owner returned and recovered the device. The previous connection block is
resolved.28 accepted owner touch login and three ordinary Mali GNOME composition
trials, but failed in a later repeated DPMS trial. It remains unqualified.

29's retained matching panic identified an unsupported gzip **builtin** archive
inside Image. The corrected builder supplies lz4; linked-Image and pack guards
now reject that exact failure.30 keeps28's source patches/config and external
ramdisk/DTBH bytes while using GCC7 and a genuine legacy-LZ4 builtin archive.
It has passed build/codec checks and BOOT-only write/readback/protection checks;
these are not evidence of runtime stability.

After restoring28, a bounded test held a per-file-descriptor
PM_QOS_BUS_THROUGHPUT minimum of421000kHz. All100 actual desktop DPMS off/on
cycles completed with runtime suspended/active, the same boot and taint0.
Observed off frequencies were at least421000kHz. The descriptor was closed and
its vote released; the driver minimum remained208000kHz. This is a diagnostic
condition and a cause clue, not a permanent power-management fix. A direct
min_freq write had previously failed read-only without changing that value.
The next compiler comparison must run without the diagnostic floor.

The recovery-entry EFS raw-hash difference was investigated without EFS writes:
118 file/link contents match the original and only eight bytes differ, entirely
within the ext4 superblock. Current calibration was preserved; no rollback or
identifier changes were made. Protected partitions remained unchanged across
each recorded BOOT write.

HDMI/DisplayPort is deferred. S9+ remains separately managed; no S9+ operation is
part of this session. The seven core requirements above remain unfinished.


The QoS holder rebooted successfully on30: it became active before GDM,
normal PAM authentication succeeded, and three further actual Mali GNOME trials
passed. A subsequent minute-interval test completed two off/on pairs; its third
final sample was off while the system stayed responsive, same boot/taint0.
GNOME idle-delay is300seconds and the real idle counter exceeded that threshold.
This is an open policy-interference classification, not a power pass or a new
kernel-hang claim. A repeat records/reset activity through actual XTest motion
and verifies Mutter's idle timer before each on interval.

The sensor candidate now journals settings before mutation and has a same-boot,
actual-device, exclusive-lock recovery helper. Nine root-owned isolated fixtures
and its AArch64 build pass; actual sensor runtime/kill/reboot acceptance remains
pending. Kernel31 with the four previously reviewed ABOX safety patches added
also builds/packs with matched config/ramdisk/DTBH and genuine builtin LZ4; it is
not yet installed. All unfinished requirements remain open.


Latest sensor details and failed live-claim boundaries are recorded in
ssp-sysfs-return-counts.md. No physical step increase, axis/matrix or changing-light
response is claimed from the raw stationary capture or the failed user trial.


Latest32 acceptance supersedes the earlier stopped-sensor checkpoint: native
claims now stream after the SSP count fix. Sensor orientation and brightness
response work; actual display rotation is still a separate unfinished feature.
See the latest VALIDATION section for physical actions, daemon cleanup, locked
visibility handling and mitigation-bound desktop power evidence.
