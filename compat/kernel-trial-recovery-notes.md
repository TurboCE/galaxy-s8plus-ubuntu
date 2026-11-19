# Read-only audit: unattended kernel-trial recovery

The current tree supports a conditional, user-space-controlled return to TWRP
without pressing keys. It does **not** implement a fail-safe automatic rollback
for a kernel that panics/hangs before initramfs PID 1 or USB initialization.
Preserving RECOVERY is essential but does not make an arbitrary candidate boot
self-recovering. No BOOT write, reboot, watchdog activation, recovery transition
or on-device helper execution was performed for this audit.

## Existing supported pieces and direct evidence

- `scripts/probe_kernel.py` validates an explicit trial/normal image mode, model,
  firmware/backup identity, current full BOOT hash and protected partitions. It
  writes BOOT only and verifies readback; it neither reboots nor installs a
  timeout/rollback controller. Its ADB command timeouts bound host operations,
  not the next kernel's ability to execute a recovery command.
- `scripts/pack_boot.py --kernel-trial` embeds `/etc/g955n-kernel-trial`. In
  `image/initramfs/init`, proc/sys/dev/run and the ECM+ACM USB gadget are prepared
  before that marker enters `rescue`. USERDATA/EFS discovery and mounts occur
  after the marker, so the successful trial path stops before mounting either.
  This still initializes built-in kernel drivers; it is not a hardware-free boot.
- `rescue` offers a root shell on ttyGS0 via setsid/cttyhack, retries indefinitely,
  and exposes optional BusyBox DHCP/HTTP diagnostics. It does not contain a
  deadline, recovery helper, automatic BOOT restoration, or normal-root handoff
  after the trial marker. If USB setup fails before binding, entering rescue
  does not itself create an independent second USB transport.
- A prior kernel #4 native trial actually reached this initramfs root shell and
  was returned to working TWRP using the tiny static helper, without a key
  sequence. Evidence: `inventory/abox-usb-kernel-trial/serial-initial.txt`,
  `serial-state.txt`, `recovery-reboot-transcript.txt`, and the corresponding
  third-native-trial entry in `docs/CHANGELOG.md`. This is historical working
  evidence for that kernel/USB/restart path, not an execution test of a new
  kernel candidate or a pre-init panic fallback.
- The existing helper source is `scripts/boot/reboot-recovery.c`; binary
  `artifacts/reboot-recovery-arm64` is a static AArch64 ELF, SHA-256
  `64b569ca1a888905be98a26e0cd035aebaf7dccb14a60e4cea436029c79456fc`.
  Its source invokes ARM64 syscall 142, Linux RESTART2, with the standard two
  reboot magic values and the literal `recovery`; a failed syscall exits 1.
  It needs no libc, Android init/property daemon, shell reboot option or writes
  to a block partition. Existing BusyBox help supports only reboot [-d] [-nf],
  so `busybox reboot recovery` must not be assumed to preserve a mode argument.

## Samsung mode mapping

`upstream/kernel/kernel/reboot.c` passes RESTART2's string to kernel_restart,
which passes it through machine_restart. The ARM64 restart path invokes
arm_pm_restart with that string. The enabled Samsung SEC_REBOOT driver's
`drivers/staging/samsung/sec_reboot.c` installs sec_reboot at subsys_initcall;
it maps `recovery` to SEC_RESET_REASON_RECOVERY = 0x12345674 in PMU INFORM3,
sets the normal-reset prevention state in INFORM2, then invokes the saved SoC
restart handler. This explains the prior successful TWRP return.

A plain restart, emergency restart or watchdog reset must not be described as
an equivalent recovery request. The Samsung handler's null/unknown command uses
its UNKNOWN reason; panic has separate upload-cause treatment. No automatic
boot-failure counter, A/B slot retry, or guaranteed recovery selection is
implemented by this repository. A watchdog reset alone does not restore BOOT.

The local request-locking build record pins Image.unqualified SHA-256
`59007047001bc02ce0b79f0f8a50046cabc778888069b39fff2e97be57e8cfe3`
and kernel.config SHA-256
`ac47c26e14b555536cc87abb0bf68bc4deff856566d3c3e26a9a842c979a4ddd`.
That config enables SEC_REBOOT, USB_CONFIGFS_ACM, S3C2410_WATCHDOG,
EXYNOS_SNAPSHOT_WATCHDOG_RESET and PANIC_TIMEOUT=5. Its build record says
not deployed/not hardware qualified. Apply this assessment to a new kernel-20
candidate only after matching its own exact embedded config/image provenance.

## What can and cannot be bounded

| Reached state | Available route | Bound and limitation |
| --- | --- | --- |
| Healthy current Ubuntu | Existing authenticated USB/SSH can invoke the verified helper, then host waits for target TWRP ADB | Host command/wait can time out; Samsung shutdown/restart can still hang. This audit did not execute it. |
| Candidate initramfs root shell and ACM enumerate | Recheck model/kernel/marker/mounts; transfer/hash the known static helper to RAM or embed it in the trial image; collect bounded diagnostics; explicitly request recovery | This path has historical proof. A timer can bound normal shell progress only after its process actually starts. Current image has no such timer/helper embedding. |
| TWRP ADB returns | Recheck root/TWRP/G955N bootloader identity; verify current BOOT receipt and protected hashes; restore the exact known-good full BOOT backup; full readback/protected checks; reboot normal | Technically automatable without touch once ADB is available. No ready transactional restore-and-retry controller currently exists. |
| Panic/hang before PID 1 or before USB | No shell timer, SSH service, host command or uploaded helper can run | Not bounded by existing software. A reset may repeat the same candidate or enter Samsung upload mode rather than TWRP. |
| USB/restart path itself fails | Host can detect missing serial/ADB | Detecting failure does not provide a replacement transport or force recovery. Physical recovery may remain necessary. |

`CONFIG_PANIC_TIMEOUT=5` schedules a reset only if execution reaches the relevant
panic path; it is neither a guarantee against hard lockup nor a recovery-mode
selection. The watchdog source hardcodes ATBOOT=0 and stops an unarmed timer in
probe; the config's WATCHDOG=y does not prove an independently armed early-boot
rollback watchdog. Snapshot panic handling can arm a watchdog later, which still
needs its driver initialized and does not install a known-good BOOT image.
Do not claim a five-second maximum outage from these config values.

## Host orchestration prerequisites, without assuming a new fallback

The host currently has a dedicated `/dev/cu.usbmodemG955N_UBUNTU...` surface.
`scripts/serial_shell.py` limits selection to that prefix, frames commands with
unique markers and returns 124 on incomplete responses. A reboot may remove and
recreate the node with a different suffix, so orchestration must rediscover the
unique matching surface rather than reuse an old descriptor. SerialShell.run
can use the existing root initramfs shell; SerialShell.login is specifically for
normal Ubuntu's ubuntu account and should not be applied to the rescue shell.
Every mode transition still requires live DT/kernel or TWRP/bootloader identity
checks; the Linux gadget's constant label is not a hardware-identity proof.

A bounded host experiment would have to stage the exact known-good full BOOT
backup plus verified recovery metadata before any write, monitor both candidate
ACM and TWRP ADB, stop after one attempt, and restore only BOOT on observed
failure/recovery. A smaller packed image written with notrunc can leave trailing
partition bytes different from an earlier full snapshot, so exact rollback uses
and verifies the full 40 MiB BOOT snapshot, not just an assumed equivalent image
prefix. No restoration may touch RECOVERY/EFS/CPEFS/RADIO/PARAM or rely on an
unverified image/partition hash. These are implementation requirements, not a
statement that this controller has been built or tested.

A shell-level recovery deadline embedded early in initramfs would improve the
case where PID 1 runs but later user-space bring-up stalls. It cannot cover the
remaining early boot interval. An initial remote transition on the known kernel
could validate today's host/recovery transport, but would not prove kernel-20
panic recovery; do not infer the latter from the former. Until a separately
proven bootloader-level fallback exists, unattended candidate verification
retains that explicit early-boot risk and cannot promise no physical help.
