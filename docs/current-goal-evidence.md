# Current seven-requirement evidence audit

The SM-G955N is currently on kernel57. Normal GNOME uses Mali → DRM/KMS/PRIME
→ DECON with the rotation-capable Xorg driver after a verified warm boot.
The startup controller retains the previous graphics files for recovery.
The table tracks live and earlier results separately.

| Owner requirement | Current evidence | Remaining acceptance |
| --- | --- | --- |
| Boot and touch login | Kernel57 normal touchscreen/OSK/PAM login after warm reboot and touch-only PAM unlock after a 23.93-second RTC suspend passed | Repeated cold starts and a physical power-button wake sequence |
| Accelerated, responsive GNOME | Kernel57 normal GNOME kept Mali/KMS and retired at least 60 frames across the rotation exercise | Physical drag latency and a sustained app workload |
| Fix kernel/driver errors | Kernel57 remained untainted in the panel tests. A roughly 24-second RTC sleep recovered USB and Wi-Fi with the same owner GNOME session | Longer and repeated physical power tests including a logged-in desktop and all remaining driver paths |
| Accelerometer, magnetic, steps and light | On 57 SensorProxy advertises accelerometer, ambient light and proximity. IIO exposes the magnetometer, gyroscope and step counter. Earlier captures recorded these device streams | Physical heading and gyro calibration, genuine step increase and longer-range light response |
| Microphone and speaker | Kernel57 duplex captured both built-in speaker test tones on the internal mic, with zero hardware-error growth | Cold-capture startup transient, speech intelligibility and further physical audio routing |
| LTE modem | Eight kernel57 trials returned the CP to OFFLINE. The latest captured two stock file-open requests, one carrying flags that can modify data. ModemManager still detects no modem | SIPC/RFS or a qualified vendor RIL adapter, then SIM registration, mobile-only traffic and reconnect |
| Rotation, automatic brightness and standard toggles | Earlier lux/brightness response and standard toggle round trips passed. Kernel57 normal GNOME kept the built-in panel and the internal touchscreen targets correct in all four commanded directions, including after reboot | Physical sensor-triggered rotation and rotation-lock behavior |

Recent55 USB trials passed20/45/180-second transport recovery, but two of those
lost the GNOME process and are not desktop passes. A rebuilt deadline-aware
presenter subsequently retained GNOME for179seconds. The corrected power-key
path also passed a30-second unlocked-desktop -> actual lock -> sleep -> wake ->
normal touchscreen/PAM sequence. ScreenSaver.GetActive alone was an invalid lock
criterion; the current harness checks logind LockedHint as well. No password or
authentication policy was weakened. See VALIDATION.md for the exact boundaries.

Before the seven kernel57 passes, the first native CP boot trial reached ONLINE and shut down cleanly, with
post-trial GPU/audio and protected-input checks passing. A later experimental
read-only SIPC status trial lost all remote responses; its retained journal ended just after unit start, without proof of a GET. A
later no-query boot/off/read/soak comparison passed, but receive-only SIPC then
also lost all remote responses. Its last-stage evidence was incomplete. The hard-freeze cause remains unconfirmed. The new modem query path is unqualified
and is not a persistent boot service. Offline inhibitor/correlation tests do
not substitute for live recovery or a second successful boot.

Supporting state: docs/VALIDATION.md, greeter-touch-validation.md,
kernel26-power-investigation.md, ondemand-panel-lifetime.md,
compiler-reference-comparison.md, panic-decoder-and-safe-recovery.md and
native-rotation-requirements.md. Device records/images and addresses remain in
ignored private artifacts, not this document.

## Historical kernel24-32 recovery and controlled comparisons

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
