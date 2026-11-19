# Port change log

## 2026-11-18 — initial bring-up

- Created TurboCE/galaxy-s8plus-ubuntu at the user's request.
- Confirmed connected Android model, device codename, bootloader and revision.
- Collected read-only GPU, sensors, services, storage and partition baseline
  privately. No phone settings or partitions modified. This is not a backup.
- Confirmed stock Mali-G71 r16p0 GLES 3.2 renderer and LSM6DSL sensor listing.
- Pinned candidate kernel and two reference repositories. No upstream code or
  firmware binaries copied into this repository at initialization.
- Added explicit model/device/bootloader guard and tests rejecting other models.
- Started Korean kernel source acquisition and graphics ABI investigation.
- Full Ubuntu hardware validation remains pending.
- Generated and checked the Korean S8+ Ubuntu bring-up configuration in an
  isolated case-sensitive Linux volume. Preserved r16p0 Mali selection and
  revision-10 Korean DT selection. Build does not access USB.
- Started the first Image/DTB compilation with GCC 13 as a compatibility probe;
  this is not a hardware-qualified kernel or an installation image.
- Privately extracted stock 64-bit Mali/gralloc/HWC and inspected ELF
  dependencies. Confirmed nativewindow/ION/Bionic dependencies requiring a
  compatibility stack; proprietary binaries were not committed.
- Identity guard tests: 3 passed. Python compilation, shell syntax and Git
  whitespace checks passed.

## 2026-11-18 — firmware build fix and runtime diagnostics

- Initial Image/DTB attempt failed because the out-of-tree firmware rule emitted
  an objtree path for exynos8895_acpm_dvfs.fw, which is shipped in srctree.
  Added a reviewable patch selecting the source binary when present, retaining
  objtree paths for firmware generated from ihex. ACPM support was not disabled.
- Restarted compilation in the isolated G955N volume. ACPM firmware assembly
  now passes. Full build result remains pending at this checkpoint.
- Added FHANDLE, AUTOFS4, USER_NS and tmpfs ACLs to the next configuration
  revision for Linux user-space integration. The in-progress compiler probe
  still uses the previous generated configuration; do not conflate them.
- Added guarded read-only Linux/SSH capture and kernel log audit. The audit
  distinguishes missing/partial captures, priority errors, warnings and traces.
  It certifies neither all hardware nor long-term stability.
- Tests: 7 passed, including denied log access, partial logs, warning/error
  priorities and a kernel exception logged at notice priority.
- Confirmed stock dmesg access is denied; kernel logcat produced no entries.
  No claim of an error-free stock or Ubuntu kernel is possible from that result.
- Matched exact KTC stock restore version through Samsung firmware service and
  started private download. Shared storage copied (38 files, 19,522,945 bytes);
  app-private data, EFS, CPEFS, RADIO, BOOT and RECOVERY are not backed up yet.
- Observed Android reports block-encrypted /data, no external microSD, OEM
  unlock allowed=1, flash.locked=0, verifiedbootstate=orange and warranty_bit=0.
  These properties do not independently prove Download Mode flash permission.
- No on-device settings, firmware or partitions changed.

### Completed build and recovery preparation checkpoint

- Patched kernel compile/link produced an AArch64 vmlinux and a 31 MiB raw
  Image, plus a valid revision-10 DTB explicitly containing SM-G955N.
  Raw Image SHA256: ad2963a665a78deca0284b2600a173e0517c36caff1f64f26fa3b73b9c90d2b6.
  DTB SHA256: b21e37a3033246439e65be6603392fdee172aeb349f7705d09f8517a3a6ef106.
  These use the initial generated configuration hash recorded in PORTING.md,
  not the later FHANDLE/USER_NS configuration revision. Neither is boot-qualified.
- The outer runner failed after compilation because its file was edited while
  Bash was executing it. Added an immutable Python snapshot launcher and
  per-run artifact directories to avoid mixed configurations/results. A redundant
  confirmation build was stopped; already-completed artifacts were exported
  and independently checked as ELF64/AArch64 and FDT with SM-G955N identity.
- Updated configuration generation through the snapshot runner completed.
- Source fetching now uses bare repositories on macOS. All three source HEADs
  were fetched and verified against sources.json, without overwriting existing
  working checkouts with case-collided Linux filenames.
- Exact Samsung restore ZIP CRC and AP MD5 verification passed; private stock
  BOOT/RECOVERY images and stock CSC PIT extracted. Official TWRP download
  SHA256 verified. These are restore materials, not raw backups of this phone.
- Prepared docs/INSTALLATION_REVIEW.md for privileged recovery bootstrap.
  Knox is still reported as 0. No flashing, format or data wipe performed.

### Authorized recovery bootstrap

- Owner authorized the permanent Knox change after its effect and the initial
  TWRP recovery bootstrap were explained. Recorded the narrow RECOVERY exception
  in AGENTS.md. No /data formatting authorization is inferred.
- Entered Download Mode from the verified SM-G955N ADB target. Read-only live
  PIT acquisition succeeded; all 30 entries match the Korean stock CSC PIT.
  Verified RECOVERY ID 8 and 46 MiB capacity versus 40,546,304-byte TWRP payload.
- First explicit RECOVERY attempt with samloader 2.2.0 failed in the initial
  ODIN handshake, before any payload/session. Device remains in Download Mode;
  requested a physical mode restart and any on-screen error text. No blind retry.
- Started compilation of the updated FHANDLE/USER_NS configuration through the
  immutable snapshot runner in the isolated build volume while awaiting device
  mode restart. This is still a build-only operation without phone access.

### Root recovery and first native image preparation

- After the user's physical Download Mode restart, the RECOVERY command exited
  0. Actual TWRP 3.7.0_9-0 root ADB, original G955N bootloader and Knox 1 were
  independently verified. RECOVERY prefix equals the official approved SHA256.
- First raw backup correctly failed its size guard because raw ADB exec merged
  remote dd statistics into the file. The .part file is unverified and must not
  be restored. Suppressed statistics on the remote side, then completed a fresh
  backup of BOOT/RECOVERY/EFS/CPEFS/RADIO/MISC/PARAM with exact byte counts and
  independently matching host/device SHA256 for all seven partitions.
- Read-only SYSTEM/EFS mounts enabled own-device firmware and graphics/HAL
  inspection. No calibration write was performed. Recovery's dmesg was captured
  and contains priority errors/warnings/traces; it is not an Ubuntu clean-log pass.
- TWRP reports no compiled crypto support. The owner explicitly authorized app
  data initialization after being told encrypted app-private data was not backed up.
- Updated native kernel/DTB compilation completed through the snapshot runner.
  Built a 36,354,064-byte G955N boot image with native BusyBox init, ECM/serial,
  own audio firmware and DT. Independently checked its image ID, Samsung trailer,
  FDT model, size bound and CPIO listing. Not yet boot-qualified.
- Started a fresh signed-archive Ubuntu noble ARM64 rootfs build in an isolated
  container with no USB. Added offline validation and guarded USERDATA/BOOT
  installer, per-chunk and full readback verification, protected-partition checks,
  and private SSH-key/host-key handling. No Ubuntu installation success claimed.
- Ten host tests pass, including wrong-model rootfs and malformed/appended raw
  backup rejection. Rootfs generation/finalization and device boot remain pending.

### 2026-11-19 — native kernel trials and early-boot corrections

- Two explicitly guarded BOOT-only trials preserved USERDATA and the working
  recovery. Readback matched each image; Samsung last_kmsg was recovered after
  each failed boot. Neither trial establishes Ubuntu or peripheral acceptance.
- First trial panicked because the supplied gzip initramfs had no compiled
  decoder. The packer now selects legacy LZ4 from the actual build configuration;
  the second trial successfully unpacked the initramfs.
- The second trial exposed an ABOX audio firmware/probe race: asynchronous
  firmware completion entered abox_enable before regmap initialization, causing
  a NULL dereference. Patch 0003 submits the firmware request after probe state
  and codec registration are ready. Rebuild and hardware retest are pending.
- Samsung configfs parks symlinked USB functions in a separate list until its
  functions attribute selects them. The bootstrap now selects cdc_ethernet/acm
  before UDC binding and enables the Samsung gadget afterward. Runtime retest
  remains pending; no USB networking success claimed.
- Patch 0002 replaces the vendor's hardcoded stock /proc/config.gz with the
  actual build configuration. Extracted IKCONFIG from the rebuilt Image is
  byte-identical to its saved kernel.config.
- Added early console nodes and persistent Samsung kernel-buffer logging for
  native init, reviewed backup-chain support for repeated BOOT-only probes,
  and guarded first-boot USERDATA filesystem growth tooling.
- Original raw backups remain intact. After recovery reentry, EFS changes in
  the first review were limited to six superblock metadata bytes; PARAM changes
  were limited to 52 boot-history-like bytes. Neither was blindly overwritten.
  Every later write still requires reviewed current protected-partition hashes.
- Fifteen host checks pass, including real legacy-LZ4 roundtrip and corruption
  guards. The boot packer also rejects a supplied configuration that differs
  from the kernel's embedded configuration. The signed Ubuntu ARM64 package installation is still in progress.

- The final installer now validates the exact previously verified BOOT trial
  before any USERDATA write and again before replacing BOOT. It rejects rescue
  images as normal Ubuntu boot images. Prior-trial identity and incomplete
  readback rejection are covered by host tests.

### Third native trial and rootfs qualification

- The ABOX/USB corrected BOOT image passed full readback/protected-partition
  checks and booted into the native initramfs. The new G955N USB serial function
  was matched by its dedicated device serial; live DT model/kernel/mounts were
  verified before diagnostics. No USERDATA mount or write occurred in this trial.
- Captured live raw dmesg, taint 0, GPU/ION and ALSA device enumeration. Recovered
  the 2 MiB Samsung prior-boot buffer after returning to recovery; it contains a
  Linux boot marker and no Kernel panic marker. Logs still contain other errors;
  no clean-log or peripheral functionality pass is claimed.
- A tiny explicitly invoked ARM64 RESTART2 helper returned this native kernel
  to working TWRP, without another manual key sequence or a partition write.
- Signed Ubuntu package installation and offline ext4/content validation passed.
  Added a physical USB serial bring-up login so diagnostics do not depend on
  host network configuration. The adjusted filesystem is being regenerated and
  requires validation again before installation.
- Added native VT/framebuffer-console configuration and a larger kernel log
  buffer for the next kernel build. The boot packer selects tty0 only when the
  supplied, embedded-verified configuration actually supports it.

### First Ubuntu boot and Wi-Fi traffic

- Installed the offline-validated root filesystem through 48 individually
  verified 64 MiB chunks, then verified the full 3 GiB hash before writing BOOT.
  BOOT readback matched and RECOVERY/EFS/CPEFS/RADIO/PARAM hashes were unchanged.
- Native Ubuntu 24.04 started systemd and a physical USB Ubuntu login. The first
  status capture reports running with zero failed systemd units; root growth
  completed successfully to about 113 GiB. Kernel logs are not clean.
- Wi-Fi association and pinned-host-key SSH succeeded. Initial Internet access
  failed because debootstrap retained Docker's private DNS address. Configured
  NetworkManager to manage resolv.conf using DHCP DNS, and removed the inherited
  resolver from future filesystem finalization. Actual bound-wlan DNS/TLS/HTTP
  200 downloads of 254968 bytes passed separately at 2467 and 5745 MHz. Network
  names, credentials and addresses remain private.
- USB Ethernet reported carrier but RX/TX stayed at zero. Vendor u_ether moved
  request allocation/freeing into bind/unbind, but only RNDIS/NCM were updated.
  Patch 0004 adapts ECM too, including partial-bind cleanup; hardware test pending.
- Found DECON's missing copyarea/imageblit callbacks before enabling fbcon on
  the phone. Patch 0005 supplies the generic CFB operations and console mapping
  is limited to primary fb0. This candidate is not yet booted.
- Patch 0006 keeps real ENOSYS for glibc's optional native rseq probe without
  misreporting it as a register-dump exception. Other unsupported calls and
  genuine kernel faults retain diagnostics. This does not implement rseq.
- Added explicit normal BOOT-only update gates and predecessor installation
  readback verification; the updater still never writes USERDATA or reboots.
- The owner reports no SIM; cellular end-to-end acceptance cannot be completed
  on the current physical setup. Cellular software investigation remains open.

### Native kernel 9, physical display and desktop preparation

- The next BOOT-only update preserved the installed Ubuntu filesystem. Kernel
  9 booted with taint 0 and no failed systemd units in the initial capture.
  Corrected ECM queues carried actual USB SSH traffic with zero RX/TX errors
  in that capture. Wi-Fi automatically reconnected at 5745 MHz.
- Enabled native HCI UART/H4/BCM support; registration appears in the boot log.
  The controller has not yet been attached or paired. VTS now loads its private
  firmware and downloads it before runtime resume; voice recognition is untested.
- Source inspection and recorded .cmd files identified a GNU Make hash-escaping
  incompatibility. Backported upstream 9564a8cf422d with attribution. A repeated
  build compiled only init/version.o, rather than rebuilding all C objects.
  Preserve matching vmlinux/System.map beside each future Image for fault analysis.
- Repeated early poweroffs were orderly logind shutdowns on short power presses,
  followed by Samsung's charger-connected reboot, not captured kernel panics.
  Ignore short power/suspend/hibernate keys during bring-up. A proper phone screen
  power handler remains necessary; this policy is not full suspend acceptance.
- Verified owner-requested local account password using its private shadow hash
  and an actual USB login. Manual login now replaces USB autologin. Future image
  finalization optionally reads a private /inputs/ubuntu-password file. No secret
  or hash is stored in versioned files; SSH password authentication stays disabled.
- An explicit unblank/scanout probe showed physical console text confirmed by
  the owner. Closing a userspace framebuffer fd disables the panel even while
  fbcon owns it. Patch 0009 retains the console owner. A bounded CPU framebuffer
  presenter handles command-mode scanout; it does not implement GPU acceleration.
- The running command line proved that S-Boot ignored the custom boot header.
  Patch 0010 and CMDLINE_EXTEND preserve firmware arguments, then append native
  overrides. The resulting candidate is built but not yet boot-qualified.
- Installed ubuntu-desktop-minimal and fbdev/libinput support on the handset;
  dpkg audit is empty. Staged manual GDM X11 login, 2x UI scaling and an on-screen
  keyboard. Desktop activation awaits the panel-lifetime kernel correction.
  Future rootfs builds include these packages and use an 8 GiB staging image;
  the base stage no longer creates a redundant image before finalization.
- Built a pinned libhybris/Android 9 header adaptation in the handset user's
  private prefix. The initial EGL probe did not succeed; Android's O_NOFOLLOW
  rejected a symlinked linker config. The preparation helper now copies that
  own-device configuration from read-only SYSTEM. GPU qualification remains open.

### Desktop enumeration panic isolated

- Kernel 10 booted and reached native systemd, but repeatedly restarted.
  Disabling GDM and the framebuffer presenter did not stop the restarts.
- Captured an unambiguous previous-boot journal: WirePlumber's VIDIOC_QUERYCAP
  reached fimc_is_ixs_video_querycap+0x24/0x64 and caused a fatal kernel exception.
  Registration stores struct fimc_is_video; QUERYCAP incorrectly casts it to
  struct fimc_is_core. This is separate from the earlier manual hard-reset hook.
- Patch 0011 obtains the registered V4L2 platform parent with the correct type,
  preserving intended device name/capability flags. The same bug exists in DIS,
  SCC, SCP and VRA and is corrected there too. Incremental kernel/image build
  passed. Live ioctl regression and desktop acceptance remain pending.
- Temporarily masked WirePlumber while diagnosing and retained manual desktop
  startup. After masking, kernel 10 remained available through a 90-second
  checkpoint with the framebuffer presenter active; this is only isolation
  evidence. Camera streaming and audio remain unqualified.

### Kernel 11 native desktop acceptance checkpoint

- BOOT-only candidate readback and protected partitions were verified before
  reboot. Original USERDATA/desktop installation was preserved. Native kernel
  11 booted; explicit QUERYCAP on ISP0/ISP1, VRA and DIS0/DIS1 returned without
  the former fatal exception. Re-enabled WirePlumber for both user/greeter;
  GDM, Xorg and GNOME then ran in the same boot.
- Owner confirmed the physical login screen, then touch/on-screen keyboard
  password entry and the Ubuntu desktop. Manual authentication is retained.
  Set graphical.target for subsequent boots and enabled the framebuffer helper.
  IBus and Hangul support are installed and included in future rootfs builds.
- This is a CPU/fbdev display checkpoint, not GPU or suspend acceptance.
  Kernel warnings remain: camera QUERYCAP device_caps omissions and codec
  format-description gaps taint the kernel. Audio backends are not routed.
  Do not describe the logs as clean or camera capture as working.
- A subsequent private libhybris EGL probe exits with SIGSEGV; GPU qualification
  remains open. Installed Ubuntu GL libraries are not globally overridden.

### Mali offscreen rendering and calibration mount correction

- Located the EGL SIGSEGV at stock Bionic __ctype_get_mb_cur_max, whose TLS
  accesses conflict with glibc. A local libhybris locale hook uses the matching
  host-libc function. Native rebuild passed and EGL now enumerates 27 configs.
- Added a model-guarded shader/readback probe. ARM/Mali-G71/GLES 3.2 r16p0
  completed 300 alternating verified frames at both 64x64 and 1440x2960, exit 0.
  The full-size run took 0.677 seconds. GNOME remains CPU/fbdev; this is not
  desktop acceleration, continuous workload or suspend acceptance.
- Public source exporter now applies compatibility patches and records their
  hashes. Re-export passed. Original vendor libraries stay private and read-only.
- Found `mountpoint: applet not found` in initramfs: EFS mounted read-only before
  switch_root but was not moved, leaving Ubuntu /efs empty. Mount EFS directly
  under the new root with ro,noload and fail closed on errors. This source fix
  awaits the next BOOT update. The live filesystem is mounted read-only after
  checking its EFS partition identity; calibration remains unmodified.
- Stock Bluetooth vendor library identifies ttySAC1. A bounded ROM/H4 bring-up
  receives real controller responses; original Bluetooth address was restored
  from read-only EFS into controller RAM. Firmware adaptation/pairing remain open.

### Independent verification and next cleanup candidate

- Three owner-requested verification agents independently checked kernel logs,
  GPU rendering and remaining hardware. GPU shader/readback reproduced at
  1440x2960, 300 frames, Mali-G71, exit 0 (0.668 s). The actual logged-in GNOME
  GLX renderer is llvmpipe / Accelerated:no. Keep these separate acceptance items.
- Native HWC module metadata loads from the own-device read-only vendor image.
  Added a separately gated direct HWC2 vtable/config probe; device-open mode
  is not yet executed. Stock lacks the libhwc2_compat_layer.so wrapper dependency.
- Patches 0012/0013 fix camera queue direction/device_caps, return an honest
  EINVAL from unimplemented ENUM_FMT callbacks and describe the five actual
  Samsung MFC FourCCs. They do not implement camera capture or disable warnings.
- Patch 0014 corrects two DWC3 diagnostics that incorrectly call successful
  zero-length packets DMA/TRB errors. Mapping failures and error propagation
  are retained. Built with EXT4 POSIX ACL and ALSA verbose proc diagnostics;
  the BOOT-only candidate is packed, live regression pending.
- Network startup timeout traced to an autogenerated wired p2p0 DHCP profile.
  Exclude exactly that pseudo-Ethernet helper; retain WLAN, swlan0/AP and native
  P2P devices. Applied live configuration and explicit managed=no for the
  existing device, restarted wait-online successfully; bound-WLAN HTTPS 200.
  Fresh-boot policy remains to be verified. USB remains owned by networkd.
- Bluetooth controller RAM now uses the original read-only EFS address. A
  twelve-second discovery probe received nine devices. This temporary ROM/H4
  bring-up is not firmware, pairing, throughput, audio or resume acceptance.
- The stock own-device LHD initialized the Broadcom 4774 MCU and verified its
  RAM patch; SSP reports MCU sensor init done and matching runtime firmware.
  Bounded native IIO capture received 220 accelerometer and 220 gyro records
  with distinct payloads and strictly increasing timestamps; all enable/buffer
  settings restored. Ambient light produced only one zero-count record, so
  the combined probe correctly failed. Physical response/calibrated units and
  desktop integration remain unqualified.
- Existing speaker RDMA7 is a realtime frontend. A normal RDMA0 comparison
  requires PCM proc diagnostics, absent in kernel 11. The new probe now
  distinguishes missing diagnostics from a busy device. No fabricated success.

### Kernel 15 regression results and audio fault isolation

- Kernel 15 booted, mounts original EFS ro,norecovery automatically and exposes
  PCM proc diagnostics. The p2p0 startup rule survives reboot and wait-online
  succeeds. Actual named-user ext4 ACL read permission and write denial passed.
- The initially zero taint became 512 after GDM's codec enumeration exposed six
  additional known MFC formats. Patch 0015 covers the full 33-format driver
  inventory; it is built but not yet deployed. No clean-log claim is made.
- Normal RDMA0/SIFS1/UAIF4 speaker routing completed two seconds/96000 frames,
  aplay exit 0, progressing hardware pointer, no xrun and verified mixer restore.
  The owner's acoustic check was postponed when they went to sleep. No further
  tones, microphone recording or physical-action requests are scheduled overnight.
- Installed ALSA UCM metadata and discovered a separate ACP behavior: Noble's
  Pro Audio profile construction probes every PCM even with UCM. A later native
  scan provoked an Abox SysMMU write fault and reboot; the previous log is saved.
  Fault 0x0a400080 is not the driver's WDMA4 IOVA. CALL RDMA4 SRAM acquisition
  failed while VTS was active but the old kernel ignored the failure.
- Temporarily masked WirePlumber and stopped both user audio engines to isolate
  that trigger. This is a mitigation, not audio/kernel acceptance. The desktop
  display remains available; normal playback remains unqualified acoustically.
- Rebuilt only SPA ALSA from the exact authenticated Ubuntu 1.0.5-1ubuntu3.3
  source, preserving all 31 distribution/security patches, with upstream
  a8b9ce2050dfb3f91c19061562d0a161117c3ab8's Pro Audio opt-out. AArch64/public
  symbol ABI and distro hardening checks passed; stock libraries are unchanged.
- Installed the new plugin in a private root-owned SPA tree with checked stock
  links for other plugin families. A root-owned hash/version guard prevents
  fallback to stock ALSA and checks exact UCM/card rules. Root and gdm guard
  checks passed independently. Global/user activation remains masked pending
  a bounded quiet profile-enumeration trial. Runtime UCM is intentionally muted.
- The original stock LHD successfully loaded/verified the sensor MCU with the
  reviewed location-hub wrapper/service. Sensor calibration initialization
  validated the original version/checksum, changed only MCU RAM, and preserved
  the entire raw EFS hash. Light remains physically unverified and OnChange
  reports are not treated as continuous-rate sensor failures.
- A longer isolated GPU test passed all 10000 shader/readback frames at
  1440x2960 in 21.989 seconds without reboot, renderer ARM/Mali-G71. This still
  does not accelerate the GNOME/GLX desktop or qualify suspend/thermal limits.
- Prepared real Bionic/property/HWBinder diagnostic scaffolding without Android
  init. A private PID/mount namespace selftest passed, preserving all parent
  mounts. Initial real-manager trial failed honestly on missing stock service
  contexts; selected original BOOT context files are staged privately. Later
  actual ready-property observation is separate from HWC/presentation acceptance.

### Quiet trial follow-up

- The bounded muted gdm profile trial loaded the exact private ALSA plugin and
  applied `api.acp.disable-pro-audio=true`; final profiles were Off/HiFi only.
  Despite that, 211 special PCM/backend/VTS log events occurred during its
  interval. The process ended, Speaker Gain remained 0, and the boot ID stayed
  unchanged. This is an unresolved probe-isolation failure, not an audio pass.
  Default WirePlumber remains masked and both users' audio engines are stopped.
  Future rootfs overlays now retain the global mask and finalization checks it.
- Rebuilt the revised per-endpoint CALL CPU-vote ownership patch together with
  the DMA buffer mapping-size correction. Matching Image/vmlinux/System.map are
  saved privately; no new BOOT image has been flashed while recovery assistance
  is unavailable. Compiler success does not qualify the kernel fault correction.
- Patch 0019 also checks CPU-vote table exhaustion before access/PM side effects
  and propagates failed votes before CALL L2/PCM requests. Extracted actual
  functions passed ASan/UBSan full-table, existing-ID and failure-path checks;
  the combined candidate rebuilt successfully. Concurrent insertion and
  asynchronous clock-programming error propagation remain separate work.
  A separate fresh Linux extraction of the pinned kernel accepted all 19 active
  patches in order with strict added-line whitespace checks. The excluded
  hidepid proposal is not part of this build or qualification.
- Source review found that WirePlumber renames duplicate device objects before
  applying policy. Candidate primary/debug-card rules now match verified bus
  paths and card identity instead of mutable names. Lua syntax passes; this
  plausible explanation of residual probing is not confirmed by a new trial.
  Revised rules are not installed on the running phone.
- Versioned a default-read-only light-calibration validator from the earlier
  successful private diagnostic. It checks the actual EFS partition/mount,
  reviewed version and original coefficient checksum before an explicit runtime
  hook, then compares the entire partition and original files. The refactored
  script passed syntax checks and its default read-only mode on kernel 15
  (version/checksum valid, runtime initialization false). No further calibration
  hook or physical sensor trial was run overnight.
- Independent review tightened calibration parsing to the stock driver's
  bounded records, signed/unsigned integer ranges and checksum order, with
  value-redacted parse failures. Offline malformed-record checks and the revised
  default read-only validation both passed; runtime-hook acceptance is unchanged.
- Real HWM/property trials passed ready-property authentication, second-process
  reads, bounded lifetime and namespace cleanup. A no-device HWC diagnostic then
  reached real HWBinder communication but waited for graphics allocator 2.0,
  which has not been started. Original allocator/mapper files and manifest
  declarations are present. ION was intentionally unavailable; desktop GPU
  acceleration remains pending.

### Autonomous reconnect and CPU observations

- Added an explicit bounded Wi-Fi reconnect probe using existing profiles and
  no credential reads. On kernel 15, three cycles at 5745 MHz passed in 38.180
  seconds and three at 2467 MHz passed in 50.206 seconds. Each cycle performed
  a wlan0-bound HTTPS download: HTTP 200 and 254968 bytes. The original 5 GHz
  profile was restored automatically; the boot stayed unchanged. USB serial
  provided independent observation during intentional network disconnects.
  This is reconnect/traffic evidence, not whole-system suspend/resume acceptance.
- Added a bounded two-worker, low-priority CPU observation with a 65 C stop.
  CPU0 and CPU4 completed the six-second workload. Observed clocks included
  455000–1690000 and 2158000–2314000 kHz respectively; both clusters changed
  frequency, both exposed idle-state residency counters advanced, and governor
  and min/max settings were unchanged. Peak observed temperature was 54 C.
  No system power policy, thermal trip or suspend setting was written.
- Patch 0020 serializes CPU/L2 vote table updates and L2 control, and fixes a
  VSS runtime-PM reference lost during clear. Extracted actual functions passed
  ASan/UBSan and ThreadSanitizer concurrent-table checks; the complete candidate
  compiled. It has not been deployed. L2 ACK timeout recovery remains a documented
  unresolved contract in an excluded proposal, not an automatically applied fix.

### Driver stabilization candidates and quiet containment

- Patch 0022 corrects FIMC binary I/O results: EOF/short read and zero-progress
  write are failures, original negative errors are preserved, and positive
  partial writes continue correctly. Actual-function ASan/UBSan fault injection
  covered complete/short/EOF/error and caller-owned buffers. This does not supply
  missing Android camera firmware selection or qualify camera operation.
- Patch 0023 preserves DECON framebuffer mmap page offsets through the existing
  dma-buf/ION bounds and protected-buffer checks. Non-ION cannot falsely return
  mapping success. Actual-function offset/overflow/bounds/error models passed.
  Offset-zero display behavior is retained; this does not add GPU scanout.
- Patch 0024 classifies successful PCIe clock/L1SS/ACK events correctly without
  removing clock calls or changing transitions. Nonzero clock results and real
  handshake timeouts remain error messages; no global priority filter is used.
- Patch 0025 checks the actual PHY-clock array slot and validates fixed-array
  DT counts before indexing. The reproducible host actual-function harness
  passed 25 ASan/UBSan cases and detects the uncorrected regression. Existing
  enable/disable and optional panic policy remain byte-identical. Full PCIe
  clock-failure ownership/IRQ/MMIO unwind is an excluded proposal, not a partial
  rollback change that would introduce double disable or unclocked MMIO.
- The complete candidate with 24 active patches compiled and its normal BOOT
  image passed embedded-config, model, capacity/header/hash/footer checks. This
  image is **not flashed**: live kernel 15 is unchanged. The existing initramfs
  reboot helper cannot recover a panic before PID1/USB; automatic recovery is
  not assumed merely because build or host timeout succeeds.
  A fresh case-sensitive Linux export of the pinned kernel also accepted all
  24 active patches in order with strict added-line whitespace checks.
- Installed the reviewed private hardware-scoped ALSA plugin without replacing
  Ubuntu libraries. V1 correctly refused special PCMs but also refused UCM's
  namespace decoration and exported Off only. V2 handles the actual bounded UCM
  prefix, then independently validates real card/PCM/direction and opens through
  minimal private numeric ALSA configuration; user alias/configuration overrides
  cannot redirect it. Independent source, ELF, mock, parser and fuzz checks pass.
- A muted 21.2-second v2 trial exported Off/HiFi and the normal speaker sink.
  Both core and policy mapped the reviewed private module; open/openat evidence
  in both processes contains only pcmC0D0p. No unsupported PCM opened, no reset
  occurred, all Speaker Gain observations remained 0, and audio test processes
  were stopped. This qualifies bounded scope/profile probing, not audible audio,
  microphone capture or a cure for the kernel DMA/firmware ownership defect.
  Global WirePlumber remains masked. A separate guarded core launcher/drop-in
  prevents a default PipeWire engine from loading the original unscoped module.
  A second 21.24-second test started that core through its normal installed
  drop-in, without a transient manager SPA override. Off/HiFi/speaker, both
  private module maps and only pcmC0D0p opens passed again; gain stayed 0 and
  all test engines were stopped. The test waits for the guard to exec the real
  core rather than treating systemd's early simple-service activation as ready.
- Added and installed root-private per-boot kernel evidence capture, preserving
  raw current and previous last_kmsg with byte counts/hashes and explicit taint,
  boot-start and incomplete-qualification fields. Atomic directory publication
  prevents an interrupted capture masquerading as complete. The live oneshot,
  private permissions and file hashes passed. Persistent journal files are now
  present with a 256 MiB journal size limit and no severity suppression. The
  current capture still has taint 512 and does not establish a clean boot.
- Corrected private Android-runtime inode permissions, including read-only
  property areas and a private graphics-group hwbinder node; host inode modes
  were unchanged. The UID1000 permission-only test and a subsequent original
  allocator registration lifecycle passed. Real manager-registered PID matched
  the supervised child, termination/reap and registration disappearance passed,
  and host state was restored. No ION or rendering device was exposed and no
  buffer allocation/presentation was attempted; desktop GPU acceptance is pending.

### Authorized kernel 22 deployment and desktop login

- With the owner next to the handset and explicitly authorizing replacement,
  saved and verified the complete working kernel-15 BOOT before a graceful TWRP
  transition. Fresh protected backups passed full read/hash verification.
  EFS differed only in ext4 mount/write timestamps, mount count +1 and write
  counter +4; PARAM only appended the expected N,N,R boot history. Calibration
  payload, RECOVERY, CPEFS, RADIO and MISC were unchanged.
- The reviewed installer wrote only the normal BOOT image and verified its
  prefix and full-partition hashes. USERDATA was not rewritten. Kernel #22
  booted into the installed Ubuntu filesystem; live build-id and configuration
  match the final pcie-clock-bounds artifacts, including patch 0025.
- Initial and subsequent captures report taint 0, no new WARN/BUG/panic/SysMMU
  fault, active GDM/presenter and zero failed system units. Five modern syscall
  negotiations retain actual ENOSYS without dumping registers. Explicit MFC
  format coverage, special PCM access and whole-device suspend were not tested.
  Existing ISP/pinctrl/I2C/panel/P2P/thermal/hidepid/IPI findings remain; this is
  not an error-free kernel qualification.
- Wi-Fi 5 GHz wlan0-bound HTTPS returned 200 and 254968 bytes after boot. CPU
  policy matched the baseline and both clusters accumulated idle residency.
  The owner confirmed manual on-screen-keyboard login to the GNOME desktop.
  The account row initially only focused; a Return activation opened the password
  prompt. This workaround does not establish that the touch activation issue
  is fixed. The kernel input device is correctly classified as direct touch.
- Fixed the persistent locale target: boot-time compatibility setup makes
  /etc/default/locale a symlink to /etc/locale.conf, so shipping only the former
  creates a dangling link after reboot. Added the canonical file and matching
  overlay symlink, verified native PAM can now read LANG=C.UTF-8 without
  restarting the owner's desktop session.
- The live GNOME renderer remains llvmpipe, Accelerated:no. Dragging is also
  limited by the temporary full-frame CRC/pan presenter; desktop GPU acceleration
  has not been enabled by the kernel replacement.

### Reduce CPU framebuffer presentation overhead

- Replaced repeated synchronous whole-frame reads with an isolated active-X11
  DAMAGE observer and coalesced pan requests, capped at 30 request starts per
  second. The main process retains the framebuffer fd while session discovery
  and Xlib I/O run in disposable subprocesses. Worker failure/reconnect tests
  passed without signalling Xorg or ending the owner's desktop session.
- Whole-frame CRC remains as a low-rate asynchronous safety scan; missing
  observation restores the prior checksum fallback. Sparse RGB samples are an
  additional safety signal, not a correctness replacement. No GPU renderer or
  global GL library was changed. Image finalization stages the observer module.
- Natural idle observations measured the whole new service at about 14.74% of
  one core versus 43.59% for the earlier presenter sample. These were not a
  perfectly controlled identical-scene benchmark. A first animation sample was
  behind the lock screen and was explicitly excluded from visible-update claims.
- After confirming unlocked state, one temporary owned-window test observed
  38 successful FBIOPAN_DISPLAY returns, matching 38 DSIM and both DECON
  frame-done interrupt increments; all test resources were cleaned up and taint
  remained 0. Notification counts/request limits are not a measured 30 FPS
  guarantee. The owner reports some improvement but continued sluggishness.
- GNOME is still llvmpipe/CPU rendered. The improvement reduces the temporary
  presentation bottleneck; it does not complete desktop GPU acceleration.


### Kernel-22 stability failure and full BOOT rollback

- Subsequent operation produced three unexpected reboots. Preserved complete
  private previous-kernel buffers and persistent journals; initial taint-0
  captures did not qualify sustained stability. Latest faults include workqueue
  worker/stack pointer corruption and scheduler/RCU faults. Earlier sections in
  Samsung's retained buffers belong to older boots and must not be counted as
  new faults. A particular driver, governor, display path or idle state has not
  been established as the cause. No new ION/GPU/HWC buffer trial was executed.
- Stopped live graphics experiments. Restored the exact original framebuffer
  presenter and made the new damage/threaded mode an explicit, disabled-by-default
  source option. Its performance measurements remain historical; the user still
  reports lag and GNOME remains llvmpipe, Accelerated:no.
- Added an explicit full-partition BOOT rollback tool. It verifies the working
  backup hash/length/model, normal reference-image hash and matching prefix,
  current predecessor receipt, exact recovery identity/capacity, protected
  backups and live hashes before writing only BOOT. Complete readback and
  protected-partition hashes passed; USERDATA was not rewritten. Seven new
  guard tests pass, bringing the host suite to 23. This is tooling verification,
  not whole-device hardware acceptance.
- Fresh recovery backup differences were limited to ext4 EFS mount/write
  metadata and expected PARAM boot history; calibration payload and other
  protected partitions were unchanged. Complete kernel-15 BOOT was restored
  from its pre-trial backup. Native uname confirms kernel 15, GDM and original
  presenter are active, Wi-Fi has an address and no system units are failed.
  Existing taint 512 remains; no clean-kernel or long-duration acceptance claimed.
- Added an inactive bounded ESS work-history-on-panic proposal and validation
  notes. Strict patch application, actual object compilation and extracted-helper
  ASan/UBSan checks passed; it remains excluded from automatic patches, without
  a full integrated kernel build, deployment or live panic-persistence test.
  CPU idle review has not proved a suspend-register defect; changing idle states
  would be a separate diagnostic, not an established fix.

### Offline graphics preparation; runtime held

- Added bounded private allocator CPU-buffer and optional EGLImage/GLES readback
  probes with model, boot-ID, reviewed hash manifest, private-node/namespace,
  actual registration, trace and cleanup checks. No new buffer probe has been
  run on this phone. Prior-boot review manifests cannot authorize a later boot.
- Cross-linked private ARM64 Android9 HWC2 compatibility, Hybris/libdroid and
  Droidian wlroots/tinywl candidates from pinned public sources and own private
  link inputs. Source patches preserve attribution; vendor binaries and build
  outputs are excluded from Git. Compilation is not phone presentation evidence.
  Kernel stability, allocator/fence proof and an exclusive bounded display trial
  remain prerequisites. Existing GNOME and global GL libraries are unchanged.


### Native-buffer synchronization and composer dependencies

- Stopped verification subagents at the owner's request; subsequent diagnosis,
  code changes and device tests are performed directly.
- Added separately hash/boot/taint-pinned CPU, GLES and no-display composer scopes.
  Exact known taint512 is explicit for the existing MFC WARN; every new kernel
  warning/fault signature and taint change still fails the trial. CPU-only
  manifests cannot authorize GLES. No display node is exposed in these scopes.
- Actual CPU buffer lifecycle passed. Found stale later native-buffer reads;
  fixed the probe's shared-buffer CPU ownership/cache synchronization with real
  per-frame mapper lock/unlock after GPU completion. Three distinct full-frame
  colors, mapper and GL readback and final CPU contents passed, with no new
  kernel fault signatures or reboot and full outer host-state restoration.
  The original pbuffer reference again passed 300 alternating Mali-G71 frames.
- Fixed private composer Binder permissions and supplied the original standard
  service manager with bounded cleanup and real IPC readiness. Composer reached
  actual manager registration; missing display nodes still prevent a panel pass.
  Retained passthrough metadata requires a separate live-registration check.
- Added private runtime packaging and fixed missing intermediate library links.
  Native loader-only dependency resolution passed; no compositor/panel trial or
  global GL replacement was performed. See graphics-buffer-investigation.md.
- Compared 12 actual critical kernel15/22 function disassemblies: normalized
  instructions match; no direct change explains the corruption. A fresh
  baseline diagnostic candidate (#23), patches1..16 plus bounded ESS panic
  history, compiled and packed. Its configuration and DT match the prior build;
  deployment and runtime stability remain unverified. Source builds never flash.


### Preserve the native framebuffer through hardware-composer handoff

- Found a concrete lifetime defect before the first physical GPU handoff: the
  initial console framebuffer shares the replaceable HWC scanout slot, whose
  release drops the ION kernel mapping and IOVA while fb_info keeps its addresses.
  It is not established as the cause of kernel22's earlier pre-HWC resets.
- Added an explicit candidate ownership patch that moves the boot allocation
  to a framebuffer-lifetime owner, keeps HWC frame slots separate, maps the
  persistent buffer and stops native scanout before teardown. An actual-helper
  ASan/UBSan model passed 128 three-plane handoffs and stable mmap selection; the
  original-lifetime counterfactual triggers real heap-use-after-free.
- Fresh kernel24 built from baseline patches1..16, mmap fix23, ownership
  candidate28 and diagnostic27. Verified config/DT and every output hash, then
  packed and wrote only BOOT with full readback. Fresh seven-partition backups
  passed. EFS changes were only ext4 timestamps/count/write counter; PARAM only
  expected normal/recovery history. MISC and calibration payloads were unchanged.
- Native kernel24 booted with matching GNU build-id and active GDM/presenter/
  Wi-Fi. Initial raw log has WARNING0/panic0 and taint0; existing other driver
  findings and sustained stability still require qualification.
- Added an exclusive bounded panel runtime with systemd deadline/restoration,
  exact boot/build/hash checks, private devices and read-only context. Host tests
  now total28. The first attempt refused a missing Android framebuffer alias
  before starting the compositor and restored the original display services;
  private alias preparation was corrected. Physical presentation remains pending.


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
