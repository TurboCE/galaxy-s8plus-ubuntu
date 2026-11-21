# Current seven-requirement evidence audit

This remains an incomplete goal. The live SM-G955N runs kernel55 with the
native GNOME Mali -> DRM/KMS/PRIME -> DECON output. Current bounded evidence
supersedes the kernel32 checkpoint below; it does not certify all hardware,
indefinite reliability or an error-free untested subsystem.

| Owner requirement | Current evidence | Remaining acceptance |
| --- | --- | --- |
| Boot and touch login | Normal kernel55 GDM account/OSK/PAM login and actual lock/PAM unlock after timed resume; autologin remains off | Repeated physical cold starts and prolonged ordinary use |
| Accelerated, responsive GNOME | Mali-G71, no swrast, real KMS frame retirement without CPU final-buffer transfer; earlier54 same-boot drag comparison is retained | Physical latency and sustained app workload; software movement is not panel FPS |
| Fix kernel/driver errors | Fresh55 boot-start capture and tested intervals had taint0 and no new fault signatures; USB sleep quiesce/restart exercised | Longer/physical power tests, all remaining driver paths; earlier GNOME exit35 failures remain documented separately |
| Accelerometer, magnetic, steps and light | Active55 native accelerometer/light service, original measured matrix/calibration; real magnetic/gyro/step records previously captured on36; own inactive release repaired | Physical heading/gyro calibration, genuine step increase, repeated changing-light response on55 |
| Microphone and speaker | Normal PipeWire defaults/controls; owner confirmed continuous speech on54;55 post-resume duplex had no hardware-error growth and detected the test tones | Cold-capture startup transient, speech intelligibility and further physical audio routing |
| LTE modem | Native55 signed CP RAM boot and real ONLINE handshake passed; bounded trial shut down to OFFLINE with protected hashes intact; ModemManager has no usable transport | Native SIPC/RFS/control backend, then SIM registration, mobile-only traffic and resume/reconnect; SIM has not been supplied |
| Rotation, automatic brightness and standard toggles | Genuine lux/brightness response and standard toggle roundtrips previously passed32;55 native properties remain available | Dynamic rotation backend/touch mapping remains unimplemented; current physical response and long-use acceptance |

Recent55 USB trials passed20/45/180-second transport recovery, but two of those
lost the GNOME process and are not desktop passes. A rebuilt deadline-aware
presenter subsequently retained GNOME for179seconds. The corrected power-key
path also passed a30-second unlocked-desktop -> actual lock -> sleep -> wake ->
normal touchscreen/PAM sequence. ScreenSaver.GetActive alone was an invalid lock
criterion; the current harness checks logind LockedHint as well. No password or
authentication policy was weakened. See VALIDATION.md for the exact boundaries.

The first native CP boot trial reached ONLINE and shut down cleanly, with
post-trial GPU/audio and protected-input checks passing. A later experimental
read-only SIPC status trial lost all remote responses; its retained journal ended just after unit start, without proof of a GET. A
later no-query boot/off/read/soak comparison passed, but receive-only SIPC then
also lost all remote responses; its durable final-stage log awaits restart
recovery. The hard-freeze cause remains unconfirmed. The new modem query path is unqualified
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
