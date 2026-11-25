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

### 2026-11-19 — ordinary GDM login now uses Mali-accelerated Ubuntu GNOME

Applied the pinned S8 project's legacy Android9 property-hook setting (patch21)
and adapted the static property cache (patch22) to read an own-device snapshot
of SYSTEM, vendor and complete actual boot metadata. The old cache's1023-byte
cmdline limit missed the hardware field, while SYSTEM-only metadata lacked the
vendor board platform. This selected gralloc.default and failed allocation or
pixel checks; the corrected native route selects gralloc.exynos5. It works as
the ordinary ubuntu user with existing video/ION/Mali permissions, no Android
manager/allocator, global shared-property mount or Binder permission expansion.
Prior successful bounded native-X11/shared-property trials are retained as
separate review scopes with authority/lease cleanup guards, not production needs.
Unused indefinite Android-service experiments were removed before this commit.

The genuine GNOME GLES helper exposed a separate shutdown SIGSEGV after reporting
Mali: gralloc's exit callback closed its device/unloaded its DSO before late EGL
native-window releases. Patch23 accounts for outstanding buffer references and
defers teardown. Real GNOME helper now exits0; repeated native EGL/resize/release
checks pass. An actual-code sanitizer test covers late buffers and failed-release
ownership, rejecting the early-close counterfactual. This does not suppress or
convert failing renderer checks into success.

Installed a root-owned private prefix/session wrapper and a separate Ubuntu GPU
session desktop entry; GDM/account defaults now choose it with automatic login
disabled. The owner manually entered their private credential and confirmed the
normal desktop. The actual native GNOME shell reports Mali-G71, maps private EGL
and the Exynos/Mali drivers, and does not map swrast. Stock session acceleration
checks remain enabled; stale GDM/software X cache atoms are deleted, never forged.
The CPU session remains installed as a recovery choice. Its switching/logout
fallback is not newly claimed hardware-qualified.

The normal compositor passed three real six-color client/overlay trials and
three20-sample stable-calendar trials through the installed keyboard binding.
Pointer-coordinate/instant-click assumptions in the earlier popup fixture failed
and are not reported as GPU failures or passing popup results. Physical touch
acceptance is separate. Same GNOME PID, same boot, taint0 and no new kernel fault
signatures were verified in the passing interval. Earlier diagnostic SIGSEGVs
remain in historical logs; no all-history-clean claim is made.

The previous presenter checked the whole framebuffer every200ms. Added an
explicit opt-in60Hz panel commit pump, based on the public S8 X11 configuration,
without full-frame CRC reads on its hot path. Samsung's empty fb0/blank read is
unknown, not a blanked display. Live intervals report1798–1800 commits/30seconds;
these are ioctl counts, not measured rendered/panel FPS. Runtime-only activation
preceded persistent configuration. GPU composition still transfers through CPU
XPutImage/pixman; no zero-copy DRI/KMS claim. No kernel/partition flash was needed.

Validation:51 host tests; actual gralloc lifetime/ownership sanitizer checks;
private native pixel/resize/reinit/teardown, stock GNOME GLES-helper exit0 and
normal GDM/PAM GPU-GNOME trials. Raw evidence remains ignored under
artifacts/native-gpu and /var/lib/g955n/native-gpu. Original CPU GDM account-row
touch activation still needed one Return; optional calendar/bolt/DBusMenu service
warnings and long-term power/other hardware acceptance remain open.

### 2026-11-19 — subsequent kernel24 idle resets reopen stability acceptance

After the successful normal-GNOME graphics intervals, the target unexpectedly
reset repeatedly. The first newly saved kernel24 trace starts in finish_wait
on rcu_preempt, with a wait-list pointer targeting read-only kernel text; later
IRQ/block/scheduler exceptions lead to a fatal interrupt panic. This is genuine
kernel corruption. Temporal proximity to WLAN resume/display blank does not
identify the writer. Later resets are recorded as resets, not separate proven
instances of that exact first fault without segmented matching traces.

Preserved initial/previous kernel evidence and restored USB-console access as
WLAN leases changed across boots. No historical raw log is deleted or filtered.
The current kernel24 is not stability-qualified; the preceding short GPU passes
remain their actual bounded results. A runtime C2-only diagnostic, after verifying
the actual DT-backed state1 descriptions, did not prevent the next reset; already
corrupted pre-isolation state and other causes are both possible. It is not a fix.

Prepared a fresh-boot controlled diagnostic changing only the BOOT cmdline to
cpuidle.off=1. The whole original BOOT was independently backed up on target/host
and checked against the working kernel24 image; every byte outside the cmdline
is identical. Full written BOOT readback and unchanged RECOVERY/EFS/CPEFS/RADIO
hashes passed before the deliberate diagnostic reboot. No USERDATA/firmware/
calibration rewrite. The actual source routes cpuidle-unavailable to architectural
WFI, retaining the CPU governors; this is not the unsafe vendor enable_mask path.
Outcome and long-term/root-cause acceptance remain pending.

Also corrected the native panel pump's blank detection: Samsung's sysfs blank
read is empty, so the service now queries the native X server's actual DPMS state
through an isolated xset process. This avoids continuing60Hz pan requests after
panel power-down and avoids Xlib fatal-I/O handlers in the persistent fb owner.
This concrete display-state fix is not claimed to cure the unrelated-looking
pointer corruption. Reboot/blank/unblank verification remains necessary.

Sensor inventory found that hrm_sensor is misclassified by udev as the system
accelerometer; SensorProxy's HasAccelerometer=true is therefore not actual
accelerometer acceptance. Real SSP channels are packed IIO records, and the MCU
is not initialized after an ordinary boot because the reviewed original LHD
service remains disabled. Audio WirePlumber remains deliberately masked from
the earlier fault isolation; ModemManager currently discovers no modem. These
are explicit open usability tasks, not passes inferred from device-node presence.


### GDM touch and cold-boot GPU prerequisites

Account-only diagnostics reproduced press/leave/re-entry/release without a
clicked signal. A pinned GDM resource repair recovers only a same-device,
inside-tile, still-pressed primary release with no native click. Ten event cases
passed. The owner then confirmed account touch, password and desktop entry.
Cold-boot physical regression remains pending. No injected Return or autologin.

That login exposed a separate persistent-setup omission: original SYSTEM was
not mounted after reboot and vendor GPU library symlinks dangled. A required
read-only preparation unit now runs before display-manager. After preparation,
the actual GNOME GLES helper exits0 and reports Mali-G71. The previously running
software fallback session was not retroactively treated as GPU accelerated.

### Panel safety candidate and negative idle result

The BOOT-header-only cpuidle option was ignored; it was not a valid idle-isolation
trial. Kernel25 instead changes only the built-in config cmdline, and live
cpuidle off=1 was verified. It still reset unexpectedly. Deep idle is therefore
not necessary for this failure. A temporary legacy presentation override is a
controlled comparison, not a permanent performance fix.

Proposal29 replaces DPP's borrowed caller configuration pointer with owned
metadata, synchronizes deferred timer completion before teardown, and serializes
the native pan state check/MMIO with display power-down. Actual extracted code
passes sanitizer and blank-at-lock fixtures. The old implementation reproduces
stack-use-after-return and powered-down register access respectively. Removing
inline asm from the lifetime fixture was necessary for Clang's fake-stack
instrumentation; no failing acceptance assertion was relaxed. Kernel26 builds
from the normal-idle baseline; target installation and power-cycle/idle
acceptance remain separate. Presenter runtime-PM checks additionally avoid pan
requests while the fb parent is suspended or transitioning.


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


### Kernel26 repeat failure and next QoS source repair

Later GPU-desktop power testing hard-hung. After owner recovery, actual PAM login
and five repeat cycles passed, but a further cycle series hung again without
physical input. Retained RCU/GPU-DVFS fault-site evidence and managed live host
capture are preserved privately. Kernel26 is not stability-qualified; the earlier
bounded passes do not supersede this failure.

Proposal30 repairs concrete decon_blank QoS ordering and failed/secondary state
publication. Seven actual-function cases pass and the original fails pre-enable
ordering. Kernel27 builds this source change on top of proposal29, normal CPU
idle; no deployment or hardware stability claim. Current phone reconnection is
required for further device tests; the owner is away. Host work continues.


### Packed sensor protocol and uninstalled SensorProxy prototype

Extended the bounded native sensor capture to calibrated magnetic and accumulated
step-counter records using pinned Samsung layouts. Corrected on-change handling:
a single real light event is not a broken continuous stream; absent stationary
step events remain incomplete evidence (exit2). Added decoded values, strict
layouts/timestamps and a shared controller ownership lock. Eight protocol cases
pass; no new physical sensor acceptance is claimed while the phone is offline.

The native accelerometer/light SensorProxy prototype builds as AArch64 without
warnings. Its README records provenance, uninstalled status and required abrupt
termination/lease, physical matrix, firmware/calibration and GNOME integration
work. It is not enabled at boot and not represented as working phone hardware.


### Ondemand panel callback lifetime candidate

Proposal31 replaces unreferenced per-CPU governor-private dereferences with a
referenced, locked, verified Ondemand policy. The actual old callback reproduces
ASan heap-buffer-overflow with foreign private storage; the fixed callback passes
foreign/normal/teardown cases. Both observed device policies were ondemand, so
this source bug is not presented as the proven RCU-corruption cause. Kernel28
adds the patch as a build-only candidate; see ondemand-panel-lifetime.md.

The device later reconnected in a new kernel26 boot while the owner was away;
reboot origin is unconfirmed. Kernel27 BOOT installation then passed full readback
and unchanged protected hashes, followed by a deliberate reboot. New-kernel
functional/stability acceptance remains to verify.


### Compiler-reference candidate and latest device boundary

Kernel27 subsequently failed repeated DPMS after13 complete cycles. Retained
metadata proves a kernel-panic/watchdog reset; it is not a clean stability result.
Kernel28 (Ondemand lifetime) and kernel29 (same patches/config with GCC7.5) both
build and pack. Their ramdisk/DTBH match byte-for-byte. Neither is deployed:
the device stopped responding before the kernel28 backup/staging finished and
no BOOT write for28 was initiated. Last confirmed live kernel is27.

Recorded immutable compiler-image ID/version and explicit comparison build
number. Core porting takes priority; USB-C HDMI/DisplayPort work is deferred and
requires a new explicit instruction even after both porting projects complete.
The latest source/data checks are62 host tooling tests plus the independent
actual-function sanitizer/event fixtures. These do not certify phone hardware.


### Matching-image panic decoding and logging-independent recovery proposal

Added an offline retained-log decoder with compiled-banner/build-hash checks,
boot segmentation, independently checked KASLR displacement and call-instruction
attribution for stack-protector returns. Fourteen guard cases pass. The actual
kernel27 capture resolves to the secondary safe-fault handler; the damaged
kernel26 capture is refused. No raw device addresses/logs enter Git.

Proposal32 repairs a concrete safe-fault path that skipped its existing watchdog
request when optional snapshot logging was off, before its caller's terminal WFI.
The original fails the actual-function disabled-logging fixture; the fixed
handler and all eight enabled CPU paths pass. The actual modified AArch64 object
compiles against read-only kernel29 inputs. It is an inactive recovery proposal,
not deployed or an initiating-corruption fix. No deliberate hardware fault was
triggered. Host tooling suite:76 tests pass; hardware acceptance remains open.

### Current-state acceptance and recovery block

Reconciled the main validation rows with actual current evidence: the GDM touch
repair passes the owner's rebooted manual login, while kernel27 stability fails;
28/29 remain uninstalled. Added an explicit seven-requirement evidence audit,
without converting host fixture passes into hardware acceptance. Fresh console
and pinned Wi-Fi/USB SSH checks still fail; there is no active build to wait on.
Further on-device changes/verification need genuine recovery, and the owner is
away. Matching candidates and private recovery materials are preserved.


### Returned-device tests and builtin archive build correction

Kernel28 installed with verified full BOOT readback/protected preservation. Owner
touch login and three actual Mali GNOME trials passed.20 DPMS cycles passed, but
a longer repeat stopped in its second off transition. The alternate-governor
probe refused before writes because only ondemand is compiled.28 is not stable.

The matched-code/config GCC7 kernel29 reboot-looped on an unsupported gzip
builtin archive. The external ramdisk was correct; missing lz4 in the new builder
caused upstream's generator to put gzip data in a .lz4 file. This is our build
setup/validation defect, not a qualified compiler-runtime comparison. Restored
known-booting28 in matching TWRP with full readback. Quarantined bad packed images.

Added compressor preflight and actual linked-Image builtin codec/bounds/decoder
checks at build and packaging. Real bad29 now fails before packing; real good28
passes and retains identical image bytes. Nine new guards and85 total host tests
pass. Corrected GCC7 builder uses liblz4-tool; fresh30 build is in progress.
A pre-existing recovery-entry EFS raw-hash delta was preserved and investigated:
118 saved file/link contents match original, without any EFS write. See
builtin-initramfs-boot-failure.md. Hardware stability remains unresolved.


### Completed corrected image / bounded MIF diagnostic

Corrected GCC7 build30 passed linked builtin codec validation, actual LZ4/newc
payload decoding and matched source/config/external ramdisk/DTBH checks. Staged
to BOOT after fresh independent full28 backup, full readback and unchanged
RECOVERY/EFS/CPEFS/RADIO/PARAM/MISC. Runtime qualification pending.

Restored28 completed100 desktop DPMS cycles under a bounded per-fd421000kHz
MIF QoS minimum, then released its vote. This diagnostic result does not repair
or qualify the default power path. EFS comparison found only eight differing
superblock bytes, with118 file/link contents identical; no EFS write occurred.


### Kernel30 matched failure and scoped runtime mitigation

Corrected30 boots and passes three actual accelerated GNOME tests, but its
no-floor DPMS trial automatically rebooted during the tenth off transition.
Preserved the matching retained callback fault and verified relocation. This is
not evidence of the corrupting writer. Repeating with421000kHz per-fd MIF QoS
passed100 cycles, reproducing restored28's bounded diagnostic result.

Added an opt-in, model/device-checked QoS holder and ordered notify service,
explicitly documented as a stability mitigation with possible idle-power cost.
Actual30 lifecycle tests verify normal stop and SIGKILL remove the request and
restart adds only one. No OPP/minimum/calibration edits or CPU-idle disabling.
Longer power intervals and reboot persistence remain under qualification.


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


### Installed ABOX-safe31 / event-driven QoS holder

Installed31 with independent full30 backup, exact readback and protected data
preservation. Normal Mali GNOME tests and owner touch login passed. Removed
periodic holder wakeups using blocked termination signals/sigwait. Actual31
normal termination/SIGKILL cleanup and zero CPU ticks over five seconds pass;
a temporary guard retained the same minimum during lifecycle testing. See
mif-desktop-stability.md for precise display-power/policy boundaries.


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


### Installed32: actual SSP response and bounded GPU/power passes

Installed0026-only32 after a fresh full31 backup and protected/readback checks.
Cold boot initializes MCU/SensorProxy automatically. Owner motion/shade actions
produce actual orientation and2..189 lux plus backlight response. Measured two
axis signs and applied diag(-1,-1,1); a maintained reference pose then reports
correctly. Actual daemon SIGKILL restores both sensor journals completely.

Added an actual screen-lock precondition to the pixel verifier: locked visibility
is incomplete, not a graphics-driver failure. After owner unlock, three Mali
GNOME trials and100 sensor-active DPMS cycles pass under the explicit MIF policy.
Dynamic screen rotation and remaining acceptance are not claimed complete.


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

### GNOME direct output investigation

Added a reproducible synthetic GNOME drag baseline for measuring the CPU cost
and window-manager update intervals before changing presentation. Confirmed
that the installed session still transfers Mali buffers through XPutImage and
that the running kernel lacks a DRM device. See gnome-direct-panel-output.md
for the display ownership and synchronization work still required.

### System Monitor refresh default restored

At the owner's request, restored the package default of 100 ms. The owner
preference was reset on the SM-G955N and a readback confirmed 100 ms. The
image no longer overrides this key. System Monitor remains installed.

### Exynos8895 direct panel submission primitive

Implemented the userspace single-window DECON submission for a verified
linear DMA-BUF and its acquire fence. It returns the driver's completion
fence without reading pixels. The AArch64 ABI was checked against the pinned
kernel declarations. GNOME producer and panel ownership integration remain pending.


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

Tested three DPMS off/on cycles on the active direct GNOME session.
Added a boot recovery service and durable rollback snapshot. Verified
restoration of the baseline library, manifest and launcher on an SM-G955N
reboot during a staged trial.

Extended the direct-output power test to 18 cycles on the SM-G955N.
Prepared the kernel33 DPP shared DMA mapping fix after identifying the
repeated MMIO conflict in the recovery boot log. The build is opt-in via
`--dpp-shared-dma` in the diagnostic kernel builder. The device runs kernel32.

### Persistent Mali-to-DECON GNOME output

- Enabled the direct path on the installed SM-G955N. Verified persistent
  configuration and normal GDM/PAM entry using touchscreen-event replay
  after reboot. Eight DPMS cycles passed on the first persistent version.
- Reproduced an opaque fullscreen X11 client's compositor bypass and
  inhibited it only in the direct GNOME session. Rebooted and re-ran the
  fullscreen fixture successfully with the original Ubuntu GNOME mode.
- System suspend-to-idle lost both device transports during a guarded RTC
  wake test. Display DPMS and system suspend have distinct acceptance status.
- Prepared an opt-in kernel34 candidate which keeps the S2MPS17 wake IRQ
  available and propagates setup errors. Verified a build with kernel32's
  config and device tree. No kernel or partition write took place.

### Kernel35 staged suspend diagnostic

- Collected the recovered kernel32 journal and Samsung last_kmsg. Observed
  HSI2C timeouts, a noirq failure, an RTC alarm interrupt and a subsequent
  deliberate hard-reset-key panic.
- Built and installed kernel35 after a verified full kernel32 backup and
  BOOT-only readback. The candidate uses a freezable battery workqueue and
  exposes the PM stage controls. The freezer and device-stage tests passed.
  USB transport loss initially hid the device-stage completion. The
  recovered journal confirmed the return and recorded DHD and DWC3 warnings.
- After kernel35's platform-stage test lost both transports and produced
  no retained result, restored the complete verified kernel32 BOOT and
  verified its readback. Preserved the protected partitions.
- Reinstalled GNOME direct output as the default on restored kernel32.
  Rebooted and verified its lease, installed files and GDM. System suspend
  remains disabled pending qualification.

### Kernel36 ABOX suspend ordering candidate

- Drained the ABOX GIC IRQ before cutting clocks and DSP power.
  Removed parallel system-sleep callbacks that bypassed runtime PM
  accounting. Kept the existing suspend notifier and made repeated
  disable safe. Built kernel36 on the kernel35 diagnostic base.

### Ubuntu hardware service staging

- Made the reviewed Samsung SSP acceleration and light backend install
  into the standard SensorProxy service during an opt-in image build.
- Added opt-in staging of the matching scoped desktop speaker for the
  standard PipeWire and WirePlumber services. Checked both startup
  guards before unmasking WirePlumber for the ordinary desktop user.
- Added the missing compat mount in the finalizer and explicitly enabled
  ModemManager alongside NetworkManager and BlueZ. No new modem backend
  was installed. Verified staging with the authentic Ubuntu packages
  from the rootfs snapshot.
- Connected the built-in UART Bluetooth controller to standard BlueZ on
  kernel36 and enabled the attachment service. Preserved original EFS
  calibration and verified BlueZ sees one powered built-in controller.
- Enabled the regular GNOME speaker on kernel36 with the scoped ABI.
  Fixed the stalled default PCM negotiation by using S16 at 48 kHz and
  read/write access for the built-in speaker only. Verified completed
  playback and RDMA0 hardware pointer progress.
- Added a one-time snapshot of the active codec and ABOX capture route to
  the bounded WDMA0 diagnostic. The probe now declines to change mixer
  controls when built-in speaker playback is already active.
- Switched the internal microphone to the working stock SIFM0/WDMA1 route.
  Added its UCM device and enabled it as the standard GNOME audio input.
  Updated the private ALSA module to allow only RDMA0 playback and WDMA1
  capture. Verified both in the default desktop audio services.
- Traced a missing touchscreen on kernel36 to the bootloader's charger
  mode. Built kernel37 with an explicit SM-G955N desktop opt-in for the
  regular touchscreen probe during charger boot. Verified the build and
  matching ramdisk/DTB. Live charger-mode validation remains pending.
- Enabled direct Mali-to-DECON GNOME output on the exact verified kernel36
  build. Supervised trials apply the same fullscreen policy as default
  sessions. Explicit rollback cancels its timer to allow immediate retry.
  Verified touch login, fullscreen and display power cycles across reboot.
- Isolated a kernel36 device-stage suspend failure to the Broadcom PCIe
  transport with active scan and receive/control wake locks. Built and
  packed kernel38 with the PCI wiphy parent and a scan cleanup callback.
  The kernel candidate is pending live testing.
- Built kernel39 with a targeted Broadcom Wi-Fi suspend fix. Cancel queued
  station power-management work before the PCIe transport suspends without
  WoWLAN, and let already-running work release its own wake lock. Verified
  the boot image against the kernel38 operating-point comparison settings.
  Device installation and suspend validation are pending.
- Fixed the retained-panic decoder to skip the Samsung panic-time copy of the
  boot banner. Decoded the original kernel38 panic against its exact build.
- Installed kernel39 after taking a verified BOOT and protected-partition
  backup. Confirmed 5 GHz Wi-Fi autoassociation and explicit reconnection.
  A connected PM test still met an active TX wake lock. The radio-off
  platform test also returned busy and both management paths later dropped.
- Made the Exynos voltage-policy polling thread participate in the system
  freezer. Built and packed kernel40 for a separate device comparison.
- Installed kernel40 with a verified BOOT backup. Wi-Fi passed automatic
  association and manual reconnection. The radio-off suspend trace identified
  the FTS touchscreen as the first wake interrupt, and the input device stayed
  disabled after the abort.
- Added a Korean revision 10 touchscreen sleep policy for native Ubuntu. It
  preserves input users across suspend and exposes touch wake as an opt-in.
- Installed kernel41 with a verified BOOT backup. Its radio-off platform
  diagnostic completed suspend and resume, restored Wi-Fi traffic and left
  desktop touch enabled. The PCIe noirq resume warnings remain.
- Scheduled a real `mem` test with RTC wake on kernel41. The test did not
  return a visible completion record, and USB and Wi-Fi became unreachable.
  Normal desktop suspend remains gated pending a verified full resume.
- Built kernel42 to defer generic PCI config access while the SM-G955N WLAN
  host is deliberately powered down for system sleep. The existing Exynos
  host and Broadcom resume paths still restore their saved configuration.
- Recovered the kernel41 deep-sleep entry record following the manual reset.
  Installed kernel42 and verified Wi-Fi reconnect and the complete device
  suspend/resume diagnostic. The two PCIe D3 warnings were absent.
- Built kernel43 to unwind noirq suspend if a device power domain refuses
  shutdown. Kernel42's core diagnostic still has no visible return record.
- Corrected Exynos syscore unwind when a pending wake or the core diagnostic
  skips platform entry. Added retained log markers around preparation, PSCI
  entry and return, and the restore path.
- Recovered the kernel42 core test and verified that it reached syscore
  resume without entering firmware sleep. Installed kernel43 and kernel44
  with verified backups. Kernel43 passed the bounded `mem` platform test.
- Verified a live RTC wake from kernel44 suspend-to-idle, with same-boot
  Wi-Fi recovery, active GDM and an enabled touchscreen.
- The follow-up kernel44 deep-prepare core trial did not produce a visible
  completion record. Desktop suspend remains gated pending verification.
- Kernel45 restores Exynos power-domain hardware after a failed shutdown
  sequence and includes the SM-G955N desktop charger-mode touch opt-in.
- Installed kernel45 and verified Exynos mode 8 unwind in the bounded core
  diagnostic. Wi-Fi reconnected and the desktop touch device stayed enabled.
- Kernel45's actual RTC deep-sleep trial did not yield a visible return
  record. Wi-Fi activity also continues to prevent ordinary suspend entry.
- Added a bounded Broadcom system-suspend drain for transient wake locks.
  Kept all existing wake-lock checks and the firmware D3 handshake.
- Installed kernel46 and verified an RTC wake from suspend-to-idle with
  Wi-Fi connected. A separate boot-time connection test still exposed a
  deferred station power-management hold with WoWLAN enabled.
- Kernel47 postpones deferred station PM work during system suspend with
  WoWLAN enabled, and reschedules it after the PCI transport resumes.
- Kernel47 entered suspend-to-idle immediately after Wi-Fi reconnect, but
  Broadcom host wake interrupted it before the RTC alarm. Kernel48 zeros
  the unspecified WoWLAN flags in the default driver configuration.
- Installed kernel48 and confirmed only the four intended WoWLAN defaults.
  One connected shallow sleep returned early on Broadcom host wake. A later
  RTC trial had no observable completion. Desktop sleep remains gated.
- Kernel49 makes WLAN wake from system sleep an explicit device wakeup
  setting while preserving the runtime WLAN interrupt.
- Recovered a kernel48 shallow-sleep DPU0 timeout. Added a Korean board
  comparison that retains DPU0 during system device suspend.
- Tested a persistent GNOME suspend-to-idle policy on kernel50. It passed
  a standard RTC wake before reboot. The recovered journal confirmed that
  the post-reboot trial also resumed on RTC in the same boot. The standard
  systemd service checks the required kernel properties.
- Verified another RTC suspend-to-idle cycle over WLAN SSH alone. Added
  a pinned-key WLAN fallback to the read-only Ubuntu collector.
- Enabled manual GNOME suspend-to-idle on the live kernel50 handset after
  verifying RTC resume and recovery of the panel, desktop, touch and WLAN.
  Added GNOME defaults to keep idle suspend off and suppress the
  power-button shutdown dialog.
- Kept the reserved sleep console clear during suspend and recorded the
  kernel wake IRQ on resume. Added the Korean Bluetooth UART pin states
  to a built DT-only candidate for the repeated suspend and resume errors.
- Connected the physical power-key input to display wake in the active
  GNOME session. The short press can restore X11 panel power while leaving
  the screen lock in effect.
- Made the short power-key press toggle the active display. The wake
  gesture at system resume still requests display on.
- Changed a short press on the active display to request system suspend.
  A long hold opens a cancellable shutdown confirmation with no countdown.
- Restored final GNOME DMA-BUF scanout to DECON for the verified kernel50
  image. Measured lower CPU use and shorter drag-update gaps than the
  restored X11 copy path. The fallback presenter idles while GNOME owns
  the panel lease, and boot recovery reports a CPU-copy fallback explicitly.
- Added an opt-in Exynos8895 DRM/KMS/PRIME display driver and connected the
  existing Mali-rendered GNOME X11 composition directly to it. Kept native
  fbdev recovery and the qualified legacy Samsung ioctl route.
- Replaced per-build qualification for the KMS route with a trusted ABI1.1,
  PRIME, DSI-mode and DPMS capability probe plus installed-file hashes. Added
  display-card ownership rules to prevent Xorg's unused GPU probe conflict.
- Fixed deferred page-flip lifetime across panel power transitions and file
  close, including a concurrent unblank race. Added bounded post-resume event
  waiting without acknowledging frames that never reached the panel.
- Built and installed kernels52–54 with BOOT-only backup/readback checks, and
  recorded actual GNOME/PRIME output, synthetic drag measurements, touchscreen
  login and the resolved suspend failures in VALIDATION.md.
- Verified kernel54 default KMS persistence through another clean reboot and
  touchscreen/PAM login. Its 304-second periodic-workload soak kept the same
  shell/boot, taint0 and real DECON frame retirement. Kept USB recovery and
  longer-term/physical acceptance limits explicit.
- Reduced the guarded desktop audio ring to 64 KiB and added scheduling
  headroom after reproducing frequent RDMA0 pointer resets and choppy sound.
  Set the built-in speaker/mic as the normal persistent desktop defaults and
  verified GNOME volume and speaker/mic mute controls. Added a bounded duplex
  diagnostic which separates hardware errors and startup capture transients
  from acoustic acceptance. The owner confirmed uninterrupted voice playback.
- Required actual panel blanking before a short power-key suspend request and
  reset the X11 idle counter before display wake. Installed the handler and
  verified an on/off/on barrier plus a21-second timed suspend/resume in the same
  locked GNOME session with no new kernel fault signatures.
- Added a source-pinned GNOME keyboard overlay guarding absent event actors and
  avoiding disposed-device auto-detection when the accessibility keyboard is
  explicitly enabled. Kept native unlock-dialog routing and PAM authentication;
  removed the earlier experimental unlock overlay. Installed with private
  backups and matching GPU startup hashes, then activated by normal logout/login.
- Recovered the failed-session screen caused by a forced Shell service reload.
  Verified normal touchscreen GDM login and, with the final minimal overlay,
  a20-second timed suspend followed by touchscreen/OSK/PAM unlock in the same
  GNOME process. Mali-G71 and real KMS frame retirement remained active.
- Built and installed kernel55 with a board-specific USB peripheral quiesce
  before system power loss. Retained physical ID/VBUS inputs for fresh resume
  initialization, closed a stopped-state runner race, propagated halt failures
  and kept runtime/PHY ownership when halt fails. BOOT-only readback and all
  protected-partition checks passed. Timed USB recovery passed without a reboot
  or manual cable reconnection; a separate GNOME timeout remained under repair.
- Added an explicit, guarded USB peripheral/PHY recovery tool over Wi-Fi after
  reproducing a host-interface loss that a composite-only toggle could not fix.
  Verified actual host serial and pinned USB SSH recovery. The tool reports
  real command errors and is not installed as an unconditional sleep hook.
- Corrected two KMS presenter deadline cases: wake just before an off-panel
  deadline, and suspend excluded from MONOTONIC. Compare BOOTTIME and retain
  real-event retirement with bounded powered failure. Installed the rebuilt
  native bridge/probe with verified startup hashes and rollback. A subsequent
  179-second trial retained GNOME and the boot; earlier failed trials remain
  documented separately from this bounded pass.
- Kept SensorProxy claim authorization while allowing each D-Bus client to
  release only its own sensor reference after session inactivation. Installed
  the rebuilt native daemon with a prior-binary pin and rollback; accelerometer
  and genuine lux properties returned. Actual unauthorized new claims remained
  denied and new suspend-time light-release errors were zero in the live trial.
- Connected the power-key request to logind and checked the real session lock
  before panel blanking. Kept lock settings and normal PAM, canceled sleep on
  failed lock readiness and distinguished actual LockedHint from screensaver
  activation. An unlocked-desktop -> lock -> 30-second sleep -> wake -> touch
  PAM cycle passed without boot/Shell change or new USB/kernel faults.

### Native CP bootstrap checkpoint on55

- Implemented the G955N legacy SIPC SHMEM RAM-boot sequence against the pinned
  kernel and public Samsung/Lineage CP boot source. Added complete private-input
  validation, real signed-image/handshake qualification and bounded CP shutdown;
  no firmware/NV storage writes or persistent modem service were added.
- Passed eight ABI/bounds/failure tests and a supervised actual ONLINE ->
  observation -> OFFLINE trial. Protected/NV hashes stayed unchanged afterward,
  the same boot retained taint0 and ordinary GNOME/audio transport checks passed.
  Original PARAM backup and its three-byte pre-existing difference are retained
  separately from the fresh pretrial pin. LTE control/SIM traffic is unfinished.


### Experimental modem status query follow-up

- Added bounded SIPC status framing/correlation and explicit power/SIM GET-only
  diagnostics; no RF enable, PIN or NV-write backend. The live follow-up lost
  all remote responses, so status-query acceptance and its failure cause remain
  pending log recovery; the first CP boot success is not generalized to it.
- Added original NV's Samsung companion-checksum validation and an acknowledged
  logind sleep/idle inhibitor, with EOF cleanup and failure-before-trial tests.
  Eleven boot/integrity/inhibitor plus five framing tests pass. The follow-up
  inhibitor correction has not been tested on the currently unreachable phone.


### Modem preflight and failure capture on55

- Recovered the prior boot after owner restart. Kept the distinction between an
  unrecorded failure stage, missing-unit default status and actual CP success;
  preserved raw logs privately and did not symbolize an unmatched last_kmsg.
- Removed buffered-open TCGETS probes from raw block reads. Three real full
  preflights produced zero new illegal UFS IOCTL messages. Moved logind sleep
  inhibition before the whole preflight and added ordering/read failure tests.
- A bounded no-query CP boot/off/read/soak comparison passed with taint0; a later
  receive-only comparison got genuine FMT frames then lost all remote responses.
  The modem path remains unqualified. Added passive-only mode, phase/cleanup
  markers, exact-unit/LoadState recovery and durable-progress collection; fixed
  premature host-monitor completion on an older globbed log.22 host tests pass.
  No further modem trial or new kernel is automatically enabled.


### Ordinary USB audit within the narrowed scope

- Compared retained macOS USB events with existing Ubuntu55 sleep receipts.
  Distinguished controlled recovery, host exclusive-open contention, GNOME
  failure and whole-device loss; an ordinary-use USB root cause remains unknown.
- Added docs/usb-existing-log-audit.md with evidence and limits. Preserved all
  logs and existing out-of-scope edits. No handset access, SSH, modem rerun,
  setting change, reboot/flash or new driver activation was performed.


### Existing-log USB response-loss refinement

- Identified endpoint0 timeouts and bulk-pipe aborts while the Mac retained its
  S8+ device object; kept physical-link and host/device causes unconfirmed.
- Corrected the interpretation of a prematurely ended kernel capture and noted
  the wall-clock-adjustment warning. Recorded candidate priorities without
  live access, test replay or changes to excluded code.


### System Monitor launch recovery (2026-11-22)

- Diagnosed the owner-reported app launch on SM-G955N/kernel55 without changing
  the kernel, GNOME output path or the100ms graph preference. Restarted only
  System Monitor and verified the ordinary desktop entry creates a viewable
  window with the original GL configuration. No persistent renderer override
  was installed; the initial failure's root cause remains unproven.


### Repair lost app-grid touch activation (2026-11-22)

- Reproduced Software & Updates receiving a real touch but losing its pressed
  state without a native click. Kept a valid primary press across X11 synthetic
  grab crossings inside the same tile and froze label allocation during presses.
  Native releases still generate clicks; no forced launch or fake click is used.
- Added a pinned resource builder, guarded atomic installer/backups/startup hashes,
  actual-method fixtures and a separate opt-in bounded diagnostic extension.
- Corrected the comparison to use touchscreen parking rather than XTEST pointer
  warps: original code failed2/3 trials; the final repair passed6/6 across
  three press durations, plus four app launches and cancellation checks.
  Restored owner extension preferences and disabled diagnostics. Mali/KMS and
  the100ms System Monitor preference were preserved.


### Preserve X11 touch presses in Mutter (2026-11-22)

- Traced the lost app-grid click to the cursor-visibility repick in Clutter
  after Xorg had already delivered a pointer-emulated press. Preserve its
  absolute coordinates across automatic repicks until the implicit grab ends.
- Built and installed the matching ARM64 Clutter library with the stock
  package interface. Removed the local GNOME app-list, keyboard and GDM
  resource overrides. Verified baseline failures, six successful repeated
  taps, other app launches and two normal GDM touch logins on the handset.

## 2026-11-22 — Ubuntu proximity sensor

- Added the actual Samsung SSP proximity record to Ubuntu SensorProxy using
  its standard claim and proximity properties. The backend uses the same
  guarded FIFO lease and restores only its own sensor settings.
- Installed the ARM64 daemon and matching rules/recovery helper on kernel55.
  The owner covered and uncovered the sensor during a live recording. The
  D-Bus client observed four near/far pairs and release restored the original
  FIFO and polling attributes.

## 2026-11-22 — GNOME automatic brightness ramp

- Build an Ubuntu package-matched ARM64 GNOME power plugin that advances
  brightness in bounded steps based on real SensorProxy lux. Use the same
  GNOME automatic-brightness option, backlight service and manual controls.
- Add a version-matched service drop-in and opt-in offline image staging.
  The handset is running the modified power service. The original enabled
  setting was restored after the on/off check.

## 2026-11-22 — Preserve GNOME responsiveness while DECON is blank

- Return to the X11 GNOME event loop while an accepted KMS flip awaits panel
  wake. Retain the real scanout and pending frame until the KMS event, and
  keep a third buffer available for rendering.
- Rebuilt and activated the SM-G955N output module with the existing
  accelerated desktop session. Three real display off/on cycles passed.

## 2026-11-22 — Standalone GNSS diagnostics and rotation-vector records

- Add the board-matched Android GNSS test client and bounded launcher. Share
  the vendor GPS FIFO directory between the HAL and engine, and supply the
  extra Samsung callback using the reviewed AArch64 callback layout.
- Decode the pinned rotation-vector IIO records alongside the existing
  magnetic, gyroscope and step-counter formats.

## 2026-11-22 — Ubuntu Location Services and GNSS assistance

- Connect the native receiver to GeoClue using a demand-activated NMEA socket.
  Keep network lookup and receiver measurements as separate GeoClue sources.
- Load checked clock, coarse network-position and Broadcom orbit assistance.
  Share the existing GPS IPC directory with the Broadcom sensor hub and
  disable the vendor's optional Android-only inertial fusion path in the
  private runtime configuration.


## 2026-11-22 — GNSS field fix and rootfs integration

- Verify satellite fixes through the ordinary Ubuntu location client after
  moving the handset to better sky visibility.
- Stage the GNSS adapter in the offline image with the reviewed ARM64 client.
  Prepare the vendor ABI at acquisition startup and wait for the shared FIFO.
- Recover the earlier passive CP trial's durable trace and narrow its failure
  interval to the end of observation and the unconfirmed shutdown sequence.


## 2026-11-22 — Ubuntu compass on SM-G955N

- Publish SSP rotation-vector headings through the standard Compass interface.
- Reuse checked sensor claims and restore the rotation-vector lease on release.


## 2026-11-22 — Hardware rotation proof for GNOME buffers

- Verify both 90-degree GLES transforms between native Samsung gralloc
  buffers at desktop and panel sizes on the real Mali-G71.


## 2026-11-22 — Modem timer shutdown on kernel57

- Avoid waiting for a SHMEM modem timer callback while holding its modem lock.
- Verify BOOT-only kernel57 deployment and repeated passive and read-only
  modem trials. Report generic replies, unsolicited state and RFS command
  totals without dumping payloads.

### SM-G955N RandR and Mali/KMS rotation trial

- Added opt-in Xorg output rotation, a built-in panel identifier and a Mali
  rotation pass for direct KMS. Kept the portrait scanout dimensions fixed.
- Verified all four directions on the handset and submitted the rotated Mali
  DMA-BUFs through the physical display controller. Added rollback for Xorg
  as part of the same supervised GNOME trial.

### Normal GNOME Mali rotation follow-up

- Resolve the rotation shaders and draws through the active Mali EGL provider.
  The real GNOME session completed all four orientations and updated the
  physical touchscreen's X11 matrix.

### Retain the qualified SM-G955N graphics path across boots

- Refresh Xorg's absolute-input bounds after changing panel orientation.
  Real evdev touches now hit the expected X11 targets in landscape.
- Include the Xorg driver and configuration in the default graphics receipt.
  Validate normal GDM touch login and rotated touch after warm reboot.
- Let scripted window moves run without depending on mouse-grab
  prerequisites. The same-boot CPU comparison is in VALIDATION.md.

### Isolate the built-in display driver from Ubuntu packages

- Move the rotation-capable Xorg module into the private GPU prefix. Preserve
  the distro driver and check the exact Xorg server at boot.
- Add first and last clipping timestamps to the audio startup diagnostic.

### Mesa buffer scanout and kernel ALSA endpoint scope

- Add an ARM64 Mesa/Panfrost GBM and DECON PRIME test fixture.
- Add a kernel58 candidate that checks the built-in audio endpoint before
  native ALSA dispatches its open callback. Add an optional, boot-scoped
  selector for Ubuntu's standard audio packages.

### Stock Mesa GBM qualification

- Add a DECON-card GBM check alongside the Panfrost render-node and panel
  presentation checks. The new mode requires Mali-G71 Panfrost to render to
  linear buffers allocated for scanout without changing the running session.

### Kernel58 stock Ubuntu audio

- Activate Ubuntu PipeWire and WirePlumber's ALSA plugin after verifying the
  kernel endpoint guard on SM-G955N.
- Keep the same-boot guard receipt in a root-managed systemd state directory
  on installations where the top-level runtime directory is writable.

### SM-G955N Panfrost platform bring-up

- Add an experimental SM-G955N DTB for the Bifrost driver and expose the
  existing CAL G3D clock rate through the Common Clock Framework in Hz.
  The experimental DTB reuses the vendor G3D power domain and BUCK6 supply.

### Linux 6.18 early boot for SM-G955N

- Add an SM-G955N mainline device tree, uniLoader board profile, and
  initramfs-only boot probe. Build the probe with ARM64 Panfrost included.

### Linux 6.18 first BOOT-only trial

- Connect the Exynos8895 splash initialization to the uniLoader early-init
  callback and record the verified kernel58 rollback from the first trial.

### Linux 6.18 second boot trial and display regulators

- Record the second uniLoader boot observation and the recovery logs.
- Add an ARM64 S2DOS03 regulator driver and the SM-G955N panel and touch
  rail definitions. Keep the PMIC node disabled in the early boot DT.

## 2026-11-23 — first Linux 6.18 initramfs boot

- Added a warm-reset RAM trace that TWRP can read when the display remains on
  the Samsung logo. The first trace stopped after uniLoader relocation.
- Fixed the board early-init callback to return an explicit success result
  after initializing the SoC. The next SM-G955N trial reached Linux 6.18.0
  initramfs, confirmed on the panel and in the RAM log recovered from TWRP.
- Enabled syscon for the Exynos PMU after observing probe error -524. The
  rebuilt kernel links the syscon implementation. A device test is pending.

## 2026-11-23 — Exynos8895 PMU and pinctrl startup

- Verified Exynos PMU binding on the handset with syscon enabled.
- Kept the ALIVE wakeup IRQ path and skipped GPIO parent IRQ initialization
  for ALIVE and VTS. The VTS pinmux remains available for digital audio.
- Fixed firmware links for IRQ providers initialized without a platform
  device. Their consumers now retain the existing IRQ paths without an
  invalid proxy link to the SoC parent.
- Recorded the PMU, ALIVE, VTS and GPIO keys binding checks in the probe.

## 2026-11-23 — Linux 6.18 Exynos8895 embedded UFS

- Added the SM-G955N UFS host, embedded M-PHY and the board's storage
  supply. The new host uses Samsung's firmware interfaces for the secure
  storage controller and starts with a conservative PWM link mode.
- Added a read-only USERDATA probe and an opt-in handoff to the installed
  Ubuntu root. The warm trace reader recognizes each storage checkpoint.

## 2026-11-23 — UFS clocks and USB device diagnostics on Linux 6.18

- Add the UFS clock-frequency pairs consumed by the 6.18 UFS core and
  select the vendor UniPro rate and EVT 1.1 clock setup.
- Add SM-G955N USB2 PHY, cable orientation and DWC3 link clocks, plus a
  configfs CDC ACM diagnostic interface in the initramfs.
- Add a multi-user Ubuntu trial and an optional runtime recovery timer.

## 2026-11-23 — Linux 6.18 multi-user boot and DWC3 endpoint diagnostics

- Prepare the USB PHY before resetting DWC3 and match the Samsung
  clock and lane state used for initial EP0 configuration.
- Route the SM-G955N MAX77865 USB2 switch to the application processor
  in the fixed peripheral configuration.
- Capture the control endpoint register state on command timeout and carry
  the early USB snapshot into the systemd trial journal.
- Add namespace and virtual-network-device kernel options, and have the
  trial return to recovery after multi-user is active or its deadline expires.

## 2026-11-23 — Linux 6.18 storage and namespace diagnostics

- Enable file locking in the Ubuntu kernel fragment for systemd namespace setup.
- Route valid Exynos8895 SCSI sense responses through the existing UFS OCS quirk.
- Add opt-in authenticated USB console, network namespace and hardware checks.
- Store separate Hibern8 and STMFTS bring-up proposals for on-device qualification.

## 2026-11-23 — Linux 6.18 physical USB, UFS and touch trials

- Add FTS8CD56 reset, identification and FIFO handling to the STMFTS proposal.
- Add the Exynos8895 UniPro Hibern8 completion check for the UFS host.
- Add an opt-in read-only G3D supply snapshot for Panfrost bring-up.

## 2026-11-23 — Exynos8895 UFS shutdown MMIO

- Add a shutdown-only Exynos8895 guard against accessing the host's
  clock-stop registers after link-off and PHY isolation.

## 2026-11-23 — Exynos8895 UFS and G3D hardware trial

- Add an opt-in G3D clock snapshot to the loader and boot log. The
  loader checks that the power domain is on before reading clocks.
- Add the opt-in SM-G955N G3D clock and Mali device-tree proposal.
- Add a read-only Mesa shader rendering and pixel readback diagnostic.

## 2026-11-23 — Linux 6.18 boot timing and recovery diagnostics

- Allow the host to acknowledge receipt of the early USB log and end
  the fixed initramfs wait. Record boot handoff times.
- Start the kernel evidence collector asynchronously and support native
  SM-G955N 6.18 releases.
- Add the opt-in HS-B UFS calibration, acknowledged module load and
  direct read timing. Support a bounded syscall trace of the Mesa probe.

## 2026-11-23 — High-speed UFS boot and first Panfrost render

- Use the Exynos8895 UniPro power-mode result for the experimental
  HS-B UFS link. Boot the installed Ubuntu through the two-lane link.
- Apply the asynchronous kernel evidence collector through a runtime
  drop-in during the Ubuntu trial.
- Enable Panfrost MMU interrupts at probe so shader jobs can recover
  from growable tiler heap faults before any runtime resume.

## 2026-11-23 — Persistent Linux 6.18 boot and display DMA-BUF diagnostics

- Add an opt-in high-speed UFS boot with no USB acknowledgement and an
  authenticated USB serial login independent of the recovery timer.
- Render to a panel-sized linear GBM DMA-BUF and verify export and PRIME
  reimport during the 6.18 GPU probe.
- Record the inherited DECON0 window and IDMA route from uniLoader.

## 2026-11-23 — Linux 6.18 standard RTC and Ubuntu package maintenance

- Expose the Exynos8895 always-on RTC through the Linux RTC class.
- Report MAX77865 battery capacity and voltage through Linux power supply and UPower.
- Add optional USB CDC Ethernet alongside the authenticated ACM console.
- Keep the Ubuntu Clutter library package-owned. Use standard PipeWire
  and WirePlumber plugin lookup on 6.18 and apply the Samsung BSP
  services only on the vendor kernel.

## 2026-11-23 — Ubuntu desktop fallback and WLAN PCIe bring-up

- Expose the Linux 6.18 framebuffer device and give GDM a stock Ubuntu
  Xorg fallback scoped to the mainline boot.
- Add an opt-in Exynos8895 WLAN root port with DesignWare enumeration,
  then add BCM4361 firmware and RAM definitions to brcmfmac.

### R53–R58 WLAN PCIe bring-up

- Let the DesignWare PCIe core map ELBI once and register the platform
  interrupt after the mapping is ready. The revised R53 host driver
  enumerated the BCM4361 over a Gen1 x1 link.
- Prepare the board-specific 3 MiB TCM window and translated BCM4361
  control BAR for the Exynos8895 WLAN port.
- Keep the reserved CFG0 page inside the host-owned 4 MiB window so
  the BCM4361 BARs can be assigned. Add a handset-local firmware
  provisioning helper that rejects empty inputs and verifies copies.
  The binary firmware and calibration files are supplied by the handset.
- Include Ubuntu's signed Wi-Fi regulatory database in new root
  filesystem builds. Enable the codec and sensor hub SPI masters
  with the Korean Galaxy S8+ board pin mappings.
- Sync the persistent bring-up journal more frequently to narrow
  the log gap when a trial abruptly stops responding.

### R59 transport fault isolation

- Add an opt-in retained-RAM recorder for the Ubuntu scheduler
  heartbeat, USB gadget and Ethernet state, Wi-Fi state, and GNOME Shell.
- Add a diagnostic kernel configuration with symbol names and software
  lockup detectors. The trial keeps the Samsung TWRP pmsg layout.
- Recognize the Linux 6.18 kernel and UDC serial names in the host
  collector. Read-only SSH capture can continue over the pinned Wi-Fi
  route when USB drops, after verifying that the boot is the same.

### R60 secure camera RAM

- Reserve the Samsung secure camera carveout in the SM-G955N device tree.
  The recovered R58 panic interrupted page initialization within that region.

### R60 transport soak and R61 peripheral preparation

- Record paired same-boot USB and Wi-Fi checks during desktop use and
  concurrent data transfers on the installed R60 image.
- Build the native Cirrus Madera/CS47L92 codec and IIO cores. Add a
  model-specific ACPM diagnostic that validates the firmware queue
  layout and can read the S2MPS17 chip ID and peripheral rail registers.
- Add S2MPS17 regulator controls for the verified codec and hub rails,
  wire the CS47L93 SPI device to its suppliers, and build the ALSA
  sequencer required by the Ubuntu snd module setup.
- Restore the board's SPI MISO feedback phase. R64 binds the physical
  CS47L93 and its ASoC codec component.

### R66 through R68 graphics and peripheral qualification

- Add an opt-in stock Xorg modesetting/glamor path for GDM and GNOME
  using the distribution Mesa Panfrost driver. Supply the display DRM
  card path that logind resolves, and retain the fbdev fallback.
- Validate the inherited DECON G0 path with a model-specific direct DMA
  latch and restore test. Add an opt-in CMA DMA-BUF scanout diagnostic
  and an EGL/Panfrost producer for the same linear buffer.
- Enable and read back the S2MPS17 RTC output control used by the
  Samsung kernel. Add a BCM4773 power and wake diagnostic for the
  board-specific SPI pins and verified revision 10 power enable.

- Record R68 desktop rendering measurements and post-login GPU faults.

### R69 DECON DRM/KMS and audio prerequisites

- Expose the inherited SM-G955N DECON primary plane as an opt-in
  standard DRM/KMS connector with linear DMA GEM and PRIME support.
- Identify the task submitting a failed Panfrost job in the kernel log
  and exercise native KMS with Mesa's render-only GBM buffer path.
- Provision the matched ABOX firmware from the handset's read-only
  Samsung SYSTEM partition into Ubuntu's standard firmware directory.

### R70 Ubuntu Wayland boot

- Add a boot option for standard GDM and GNOME Wayland on DECON DRM/KMS
  with the distribution Mesa Panfrost renderer and an Xorg fallback.
- Add an optional Mesa AFBC isolation setting and a kernel fragment
  for input and suspend testing.

### R72 suspend recovery and stock touch login

- Defer Exynos8895 UFS vendor register access while the PHY is isolated.
- Stage the R72 suspend policy for the verified DECON configuration.
  Release the BCM4361 driver before sleep and bind it on resume so
  NetworkManager can reconnect.
- Verify stock GDM touch authentication via the bottom-edge keyboard
  gesture and distinguish the BCM4773 GPIO and SSI probe phases.

### 2026-11-23 — 6.18 R73 through R79 peripheral integration

- Connect the SM-G955N Bluetooth UART and wake pins to the stock Linux
  Broadcom HCI driver. Include RFCOMM, BNEP and AES for LE pairing in the Bluetooth fragment.
- Match the BCM4773 SPI input bias and check the host request before
  reading SSI. Exercise the board's optional GNSS power GPIO with
  readback and restoration of its original direction.
- Report the inherited ABOX PMU and clock state without cycling its
  active domain. Keep ABOX and BCM4773 probes opt-in.
- Report Samsung external-interrupt mux functions as GPIO inputs so
  gpiolib can claim the touchscreen interrupt.

### 2026-11-23 — 6.18 R80 codec clock and GNOME application rendering

- Connect CS47L93 MCLK2 to the S2MPS17 RTCBUF clock after verifying
  the PMIC enable bit through ACPM.
- Select the GTK 4.14 legacy OpenGL renderer in the desktop user's
  shared session environment. Keep ordinary package launchers.
- Select DejaVu Sans Mono 10 and 64 columns in the default GNOME
  Terminal profile. Keep the System Monitor graph refresh at 100 ms.

### 2026-11-23 — 6.18 R81 Korean input and Panfrost recovery

- Install Korean fonts and translations, add two-set Hangul to the
  owner's GNOME input sources, and backport upstream IBus Hangul
  support for on-screen keys that have no hardware keycode.
- Install the missing Evolution Data Server dependency for the
  stock GNOME calendar.
- Restore the Panfrost fault interrupt when re-enabling a previously
  faulted GPU address space.

### 2026-11-23 — 6.18 R82 Exynos8895 UFS link timers

- Preserve the Samsung UniPro timers after the Exynos8895 high-speed
  link setup. The existing UFS core power-mode path still applies
  on the PWM fallback.
- Recognize the mainline GPIO power key and use the DECON connector
  state for the Wayland display blanking check. Pass the session's
  GTK renderer to the shutdown confirmation dialog.

### 6.18 R84 Panfrost MMU error recovery

- Clear stale Panfrost fault interrupts before enabling a reassigned
  hardware address space.
- Roll back incomplete GPU page mappings, release failed heap chunk
  resources and report the mapping error in the MMU fault log.

### 6.18 R85 display wake and wake-source reporting

- Recheck the DECON connector if it appears after the power-key service
  begins, and restore the display if the blanking check or suspend
  request fails.
- Expose the kernel wake IRQ and recognize the mainline gpio-keys
  label so the sleep hook can request display wake after a power-key
  resume even if the key was released before evdev delivered it.

### 6.18 R86 transport recording and login dependencies

- End retained transport recording after a five-minute boot-time
  window, including time spent suspended, and write a completion marker.
- Record full Panfrost job addresses, raw status and slot configuration
  when a GPU job faults.
- Install the stock GNOME keyring PAM module in the Ubuntu rootfs.

### 6.18 R87 Samsung audio codec endpoints

- Enable the board I2C interface for the MAX98506 speaker amplifier
  and register a native ASoC I2S playback codec after revision detection.
- Describe the CS47L93 AIF and digital microphone bias references in
  the SM-G955N device tree.

### 6.18 R88 inherited ABOX clocks

- Expose the Samsung-programmed ABOX PLL, AUDIF and both codec
  serializer divider rates through the Common Clock Framework.
- Keep clock register reads behind the ABOX power-state check.

### 6.18 R89 UAIF bit-clock configuration

- Allow the idle SM-G955N ABOX UAIF0 and UAIF4 dividers to be
  configured through CCF after checking the ABOX power and clock
  state, DSP ownership, and serializer enable bits.
- Add an opt-in trial that verifies and restores the clock rates.

### 6.18 R90 and R91 native loudspeaker

- Attach the ABOX address space to the Exynos System MMU and limit
  DMA buffers so the ABOX exclusive end address fits in 32 bits.
- Connect RDMA0 through SIFS1 and UAIF4 to the MAX98506 speaker.
  Register a 48 kHz, signed 16-bit stereo ALSA playback PCM and
  load the board drivers through a model-specific systemd unit.

### R91 capture DMA diagnosis and browser installation

- Qualify the Exynos8895 NSRC0 sample-bank address with a bounded
  WDMA1 capture-transport trial.
- Install the Mozilla Firefox ARM64 package on the test handset.

### R92–R96 native microphone, duplex and Firefox playback

- Add the CS47L93 AIF1 and ABOX UAIF0 capture link using NSRC0 and
  WDMA1. Enable the codec's MICVDD regulator and use independent
  DMA rings for playback and capture.
- Set the primary microphone bias to the Samsung board's regulated
  1.8 V with soft start and configure the codec
  charge-pump supply for 3 V. Publish the native devices through ALSA UCM
  for WirePlumber and GNOME Sound.
- Add the 2 GiB upper DRAM bank from the Samsung board device tree
  and retain DMA32 for peripherals with low address limits.

### R97 Ubuntu hardware integration

- Restore Samsung's mono output routes on the CS47L93 codec.
- Use host-managed roaming for the SM-G955N BCM4361. The installed firmware
  does not complete P2P discovery interface creation, so this configuration
  advertises managed, AP and IBSS modes.
- Add a read-only SYSTEM provisioning helper for the qualified Semco E32
  Bluetooth patchram. The vendor firmware stays on the handset.
- Retry the logind session lock during GNOME startup before the power key
  blanks the display and requests suspend.
- Route the first short power press on a locked Wayland session after
  resume to display wake even if the DRM connector is marked enabled.

### R98 display and sensor transport

- Check the powered DECON G0 shadow register before skipping a repeated
  framebuffer. Re-latch the same DMA buffer if scanout no longer points
  to it or a window update is pending.
- Extend the BCM4773 diagnostic to read a bounded SSI payload after
  HOST_REQ. Report the received byte count without logging sensor data.

### Linux 6.18 Ubuntu userspace profile

- Build a separate offline image with stock PipeWire, WirePlumber, GeoClue,
  and the SM-G955N ALSA UCM files. Stage the verified r02j Wi-Fi and Semco
  Bluetooth firmware from the handset's private Android inventory.
- Stage the native ABOX service and the GNOME power-key service. Require
  the DECON display and the manual suspend boot flag before running the
  power-key and suspend services.
- Accept the reviewed modules for the matching SM-G955N kernel release.
  Check their release and regenerate module dependency metadata in the image.

### Linux 6.18 R98 handset deployment

- Installed and readback-verified the R98 BOOT image from TWRP after
  staging the matching modules on the existing Ubuntu filesystem.
- Deployed the pending power-key wake guard and verified service startup.

### Linux 6.18 R99–R100 audio

- Match the Samsung dream2lte MAX98506 filter setup and use 0 dB
  amplifier gain. Program the clock multiplier and unmute after the
  ABOX playback trigger starts the serial clock.
- Leave the CS47L93 dedicated IN3 input mode at its codec default and
  retain the board-specific MICBIAS1A setup.

### Linux 6.18 factory audio route trials

- Add the CS47L93 AIF1 ASYNCCLK setup as a capture trial for the
  Samsung LHPF1 and ASRC1IN1L route.
- Add a separate RDMA7 trial feeding the factory SPUS OUT7 selector.
  It supplies the hardware serial path without running Calliope DSM.

### Linux 6.18 Calliope and DSM bring-up

- Provision the stock DSM and audio data alongside the three Calliope
  images using the handset's read-only SYSTEM partition.
- Add a model-specific Calliope staging and bootstrap test with fixed
  IOMMU aliases, bounded SRAM IPC, and verified CA7 shutdown before
  memory reclamation. The test stays outside the boot-time audio path.

### Calliope audio IOMMU runtime PM

- Hold the runtime PM reference on the native ABOX client while the
  firmware test owns DMA backing and IOMMU aliases.
- Separate boot observation from the opt-in RESUME transaction. Report
  unsupported startup IPC instead of acknowledging an unhandled request.
- Map a zeroed private copy of the stock VSS address window during
  staging and release it after the core stops.

### Optional GDM startup login

- Add an opt-in service drop-in for GDM automatic login on SM-G955N
  mainline boots that use the generated GDM configuration.

### Calliope boot and DSM parameter read

- Handle bounded startup component reports and verify BOOT_DONE and RESUME.
- Add an opt-in ERAP DSM read after validating the inherited boot clock.

### Calliope silent PCM qualification

- Discover the stock ERAP DSM On mixer control from its component descriptor.
- Add an opt-in, zero-sample RDMA0 test with the stock UAIF4 selectors and
  hardware progress checks. Stop DMA and restore routing after each trial.

### R100 acoustic microphone and muted speaker feedback verification

- Repeated the physical microphone reference after correcting Mac output
  selection and increasing playback volume. Both recordings followed
  the reference sequence.
- Add an optional muted MAX98506 monitor setup and UAIF4 receive check
  to the Calliope PCM diagnostic.

### Experimental ALSA playback through Calliope

- Add an opt-in native module build that aliases the existing ALSA playback
  ring into the firmware's PCM window and manages the mailbox lifecycle.
- Handle firmware log and dump notifications during streaming and restore
  the speaker route and amplifier monitor configuration at teardown.

### Pace DSM-backed playback with the SIFS0 clock

- Restore the matching stock UAIF0/SIFS0 clock path alongside the
  UAIF4 speaker route. Restore only the serializer fields owned by
  the test so a prepared microphone can continue to capture.
- Keep ALSA playing when Calliope reports optional dump buffers.
  Acknowledge those notifications without reading the buffers.

### R100 loudspeaker serial-data check

- Verified that the Calliope DSM trial sent the expected PCM sample words
  through the SoC speaker pads. The loudspeaker remained silent.
- Discarded native SIFS0 routing and reset-clock comparisons that failed
  to recover output. Restored the installed R100 audio service.

### R100 amplifier feedback diagnostics

- Verified that WDMA1 drained the UAIF4 receive path with no reported
  receiver error in the isolated comparison. The captured amplifier
  feedback stayed zero during playback.
- Recorded MAX98506 supply-monitor readback limits. Removed the one-boot
  diagnostic modules from the normal audio startup.

### R100 amplifier load comparison

- Compared the battery fuel gauge during repeated amplifier enable and
  mute windows. The device-wide current measurement did not isolate
  the boost supply or speaker output.

### R100 Android HAL and WDMA4 ring comparison

- Traced the handset's Android speaker HAL auxiliary PCM sequence and
  compared it with the R100 DSM driver on hardware.
- Verified that WDMA4 selected a firmware-internal ring, separate from
  the host-provided PCM alias. Six snapshots of the internal ring were
  zero during the test stream. Speaker output remains unresolved.

### R100 kernel58 speaker route comparison

- Tested the earlier Ubuntu SPUS OUT0 route, a clock-settled amplifier
  re-enable, and the factory amplifier input/ALC settings with low gain.
- The handset microphone detected an external Mac reference after the
  comparisons. The handset's own speaker remained unqualified.

### R100 ABOX clock comparison and DSM diagnostic handling

- Compared the kernel58 48 kHz AUDIF clock request on R100. The lower
  rate produced playback I/O errors and was withdrawn.
- Handle asynchronous firmware diagnostic reports alongside the DSM
  response. Verified playback transport on R100 with the existing
  clock. Acoustic speaker output remains unresolved.

### R100 amplifier serial clock observations

- Verified raw I2C register access and restoration in a muted
  MAX98506 input-slot comparison.
- Compared the requested and observed speaker bit clock at 64
  bits per frame. The output pin only tracked 3.072 MHz after
  changing UAIF0 as well. The experiment was withdrawn.

- Isolated the UAIF0 divider. Doubling that clock alone doubled the
  speaker word-clock edge rate and halved the PCM playback time.

### R100 controlled kernel58 audio comparison

- Reject reordered or off-time test tones in the desktop acoustic
  check. The archived kernel58 positive result still passes, and a
  silent R100 capture that fooled the old detector is rejected.
- Compared ASRC0, the WDMA1 alias and the RDMA0 ring size one at a
  time. Audited the live IOMMU pages. The expected acoustic sequence
  was not recovered.

### R100 side-by-side SoC PCM output

- Verified zero data at the native speaker pad during nonzero test
  PCM and confirmed the matching sample words at the Calliope pad.
- Tested the native mixer-format field independently. The Samsung
  16-bit stereo setting did not restore data.

### R100 speaker level comparison

- Doubled the Calliope test PCM level while holding amplifier
  settings fixed. Playback completed and the handset microphone
  did not recover the complete timed reference sequence.

### R100 Samsung native playback control comparison

- Isolated UAIF0 pacing and the stock RDMA0 alias. The pacing
  change brought up the speaker clocks, but neither change
  recovered native PCM data at the pad.
- Adding the stock ASRC0 bit stalled the native playback pointer
  with the comparison mixer format and clock fixed.

### R100 amplifier feedback output and speaker pin drive checks

- Verified the stock amp divider low byte during playback. Neither
  temporarily disabling amp DOUT nor raising the three SoC I2S
  pad drive fields one step recovered the acoustic reference.
  Restored the installed R100 audio setup.

### R100 MAX98506 trigger errors

- Propagated codec startup errors to ALSA and checked the amplifier's
  hardware enables at trigger. Verified start and stop register
  states on R100 and checked error paths with a host fault simulation.
- Compared the stock ALC auto-mute bit on native ALSA and Calliope.
  The diagnostic did not recover the acoustic reference and was
  withdrawn.

### R100 desktop audio routing verification

- Updated the duplex diagnostic to recognize the native R100 ALSA
  card and capture PCM 1 while retaining the older card checks.
- Verified standard ALSA UCM, PipeWire and its PulseAudio compatibility
  layer. Replaced stale WirePlumber defaults with the current device names.

### R100 audio code path review

- Require RDMA0 movement before reporting successful Calliope playback startup.
- Check PipeWire errors on the selected built-in nodes only. Distinguish the
  recorder's expected SIGINT exit from an unexpected recording failure,
  and include new audio-specific kernel errors in the transport result.

### R100 loudspeaker and receiver route audit

- Confirmed during a GNOME/PipeWire playback that the MAX98506
  loudspeaker enables assert while the CS47L93 receiver remains idle.
  The current 6.18 ALSA card has no receiver playback PCM.

### R100 Samsung handset mixer comparison

- Identified the stock handset route from AIF1RX1/2 through HPOUT3L
  to HPOUT4 and compared it with the R100 capture-only codec link.
- Tested the receiver codec's tone route independently of the lower
  speaker and restored the mixer. Recorded an OUT3 Demux error
  propagation defect shared by Samsung's driver and Linux 6.18.

### R100 speaker and receiver driver corrections

- Propagate CS47L92 OUT3 demux errors and preserve the previous hardware
  route on programming failure when recovery succeeds. Verified the
  patched module on the handset.
- Read the firmware-owned RDMA0 position for Calliope playback independent
  of the native DMA channel. Leave native playback and capture unchanged.
- Select the Samsung HPOUT4 receiver route when UCM enables HiFi
  without enabling the receiver output or changing PCM assignments.

### R100 separate handset receiver profile

- Exposed the CS47L93 handset receiver as PCM 2 under Voice. Retained
  the HiFi speaker and existing microphone mappings. Verified
  profile switching and persistence after reboot.
- Tested loudspeaker and receiver independently. Both selected their
  intended output and completed PCM transport. The microphone did
  not reproduce either acoustic reference.

- The user confirmed the upper receiver's audible output. Retained the
  verified -18 dB codec gain for the Voice profile.

### R100 dual-microphone lower speaker audit

- Compared the native and Samsung Calliope loudspeaker paths with
  simultaneous handset and MacBook microphone measurements. Calliope
  preserved normal timing and SoC data pad activity. Neither path
  produced an acoustic match. Retained the confirmed receiver setup.

### R100 alternate ABOX loudspeaker route check

- Tested SIFS2 to UAIF4 both during a stream and before start. It
  stopped playback with EIO. The installed R100 route completed the
  same silent input after a reboot. Retained the receiver setup.

### R100 Samsung amplifier control comparison

- Compared Samsung's codec and ABOX start sequence with uncached
  MAX98506 reads on R100. Verified speaker/boost and global enable
  during silent playback, and recorded the remaining configuration
  and physical measurement gaps.

### R100 Samsung MAX98506 board settings

- Applied Samsung mono-board slot mapping, output monitor slots,
  ALC and boost current limiting to the installed codec module.
  Verified the live registers and shutdown on R100. The updated
  amplifier control did not restore native UAIF4 data or acoustic
  loudspeaker output in the two-microphone trial.

### R100 Calliope playback with the separate receiver

- Combined the optional Calliope speaker path with the native
  receiver and microphone driver. Verified resumed UAIF4 data
  activity and microphone close before playback teardown. Kept the
  firmware path opt-in because acoustic playback and capture-first
  duplex remain unresolved.

### R100 Calliope duplex start order

- Shared UAIF0 clocks and ABOX power across Calliope playback
  and native microphone capture. Verified both start orders,
  either stream finishing first, and simultaneous PipeWire
  transport. Lower speaker audibility remains unresolved.

### R100 earpiece acoustic capture

- The MacBook microphone detected the complete earpiece test
  pattern in two runs at the existing Voice gain. The handset
  microphone did not reliably detect it in this setup.

### R100 microphone noise isolation

- Compared earpiece and external-speaker references on both
  microphones. The handset captured the external code, and
  a controlled gain and routing test localized the high
  quiet-signal level to the IN3L input path.

### R100 primary microphone clock

- Set the native HiFi and Voice microphone profiles to use a
  1.536 MHz IN3 PDM clock. Verified a quieter capture after
  reboot and detection of the upper receiver reference on
  both the handset and the MacBook microphones.

### R100 audible loudspeaker and feedback retest

- Replayed coded tones with the quieter microphone setting.
  Confirmed SoC output activity and amplifier enables. The
  firmware sensing comparison returned zero power and no
  running feedback DMA. Physical loudspeaker output remains
  unverified.

### R100 sustained loudspeaker monitoring

- Varied the loudspeaker stimulus level during an uninterrupted
  15-second monitoring run. Amp enables and SoC data stayed
  active. Firmware power responses remained zero at both levels
  and no feedback DMA was observed.


### R100 Calliope playback boot gear release

- Acknowledge the firmware's boot gear release during an active PCM
  stream and hold its configured CA7 clock through playback. On the
  handset, the same 30-second stimulus passed the previous interruption
  point without an ALSA XRUN.

### R100 sound device labels

- Show Bottom Speaker and Earpiece as output routes and Microphone as the
  shared input. Use short names for the Standard and Voice configurations.


### R100 amplifier level detector comparison

- Compared two MAX98506 ALC threshold settings during uninterrupted
  PCM playback. The amplifier reported no level or fault flags and
  handset capture did not reproduce the stimulus. Restored the original
  amplifier threshold after the trial.


### R100 Ubuntu app compatibility and live #58 speaker comparison

- Enable memory-advice syscalls in the Ubuntu config. The official ARM64
  ChatGPT package reached its sign-in screen on the handset with native
  Wayland. Tailscale ran in userspace mode and awaited account sign-in.
- Reproduced the ordered speaker reference on #58 while R100 did not
  reproduce it. Captured direct amplifier reads and verified that the
  #58 boost request alone did not recover the R100 acoustic reference.


### Synchronized #58 and R100 speaker trace

- Captured playback clocks, ABOX state, GPIO-pad samples and direct
  MAX98506 reads during a matched test. Matching the amplifier start
  order and applying the measured #58 amplifier settings in separate
  R100 trials did not recover the ordered acoustic reference.


### R100 native speaker AUDIF divider comparison

- On the handset, matching the #58 AUDIF divider alone interrupted
  direct ALSA playback. Pairing it with the UAIF4 divider restored
  full-length PCM transport. Restored the production R100 module
  after the one-boot tests.


### R100 #58 AUDIF profile

- Add the Exynos8895 clock-provider profile for AUDIF at 6.144 MHz and
  UAIF0/UAIF4 at 1.536 MHz. Enable it on the R100 handset at boot.
- Direct lower-speaker PCM playback and microphone recording completed
  simultaneously. The recording did not detect the speaker reference.


### Paired #58/R100 lower speaker register comparison

- Reproduced the acoustic reference on #58 and the silence on R100
  with the same PipeWire stimulus on the same handset.
- Matched the #58 SPUS banks in two R100 trial modules. Enabling ASRC0
  stalled RDMA0. The bank changes alone allowed a full stream without
  acoustic output. Restored the installed audio module and kept the
  6.144 MHz AUDIF profile.


### R100 Calliope playback through #58 ASRC0

- Add an opt-in Calliope route that selects ASRC0 and SPUS OUT0
  through SIFS1 to the lower speaker. Direct ALSA playback and
  simultaneous microphone recording complete with ASRC0 enabled.
- The handset capture still lacks the ordered speaker tones. A
  short startup transient was present even with a silent PCM file.


### R100 #58 RDMA geometry and remaining register comparisons

- Match the #58 64 KiB ring and 8 KiB period on the opt-in ASRC0
  path. Direct ALSA playback and concurrent microphone capture passed.
- Tested the #58 amplifier settings and codec MCLK mux. The acoustic
  reference remained absent. A separate SPUM capture trial returned EIO.


### Independent review of R100 lower-speaker signal tests

- Verified the known stereo sample words in the ALSA ring. The
  firmware OUT7 path reproduced both words in SoC GPIO readback.
  ASRC0/OUT0 did not, including with UAIF0 transmit enabled.
- Tested the missing Samsung RDMA0 synchronization command and the
  PMU audio pad release sequence. Neither restored speaker output.
  Removed both diagnostic changes.


### MAX98506 I2C playback write comparison

- Recorded the bytes submitted to the EXYNOS I2C adapter on #58,
  stock R100 audio, and R100 Calliope ASRC0. Both R100 paths differed
  from #58 in gain, enable sequence, and teardown writes.


### Stepwise #58 MAX98506 playback parity tests

- Compared gain, staged amplifier enable, MDLL write omission, boost,
  codec-first trigger order, and omission of the VI prepare write on
  the R100 ASRC0 route. None recovered the ordered loudspeaker tones.
  Restored the previous codec and ASRC0 configuration.


### SM-G955N speaker I2C fast mode and #58 timing comparison

- Set the dedicated MAX98506 adapter to the Samsung 400 kHz rate.
  R100 playback and capture completed under the new DT setting.
- Matched the #58 enable-write interval and tested global-only
  amplifier shutdown without recovering the lower speaker tones.


## 2026-11-25 — Tailscale kernel networking on R100

- Added a 6.18 fragment for TUN, IPv4 and IPv6 policy routing,
  and the nftables backend with connection marks. Rebuilt the
  initramfs and versioned modules, including the deployed board
  audio overrides. The authenticated handset now uses the
  kernel TUN interface and reconnects automatically at boot.


## 2026-11-25 — Power key display toggle

- Changed the SM-G955N short power-key action to lock and blank
  the screen or wake it, without requesting system suspend.
  Retained the long-press shutdown confirmation.


## 2026-11-25 — Black scanout for the DECON output-off state

- Changed the inherited DECON DRM pipe to scan an opaque black
  DMA frame on display disable. This keeps the boot console out
  of the output-off transition while retaining direct desktop
  scanout on enable.

## 2026-11-25 — VPN2 speaker lifecycle and #58 internal PCM comparison

- A bounded VPN2 MAX98506 and Calliope lifecycle trial matched
  the observed #58 amplifier activation and buffer geometry
  without restoring acoustic output.
- Captured #58 SIFS1 PCM through the vendor NSRC0 and WDMA1 route,
  then replayed the captured signal on VPN2 under the same trial
  configuration. Restored VPN2 BOOT and installed audio modules.
- Qualified the MAX98506 voltage/current feedback on audible Samsung
  #58 using the same stereo stimulus and an ADC-off control. On 6.18,
  bypassing capture ASRC1 removed the feedback PCM read error, but the
  captured frames were all zero. This is diagnostic evidence and does
  not change the installed playback or microphone driver.

## 2026-11-25 — UAIF4 startup order comparison

- Compared enabling UAIF4 receive before and after transmit on
  VPN2. Both feedback recordings completed and contained only zero
  samples. The diagnostic module was removed after testing.
- Matched the working #58 UAIF0 format with the microphone idle.
  Playback timing was unchanged and amplifier feedback stayed zero.

## 2026-11-25 — SM-G955N bottom speaker pinmux

- Corrected the UAIF4 speaker pin group to GPH3-0 through GPH3-3,
  including the amplifier feedback input, using an isolated DTB
  change on 6.18 VPN2.
- Verified actual lower-speaker output over ALSA and the default
  PipeWire route after reboot. Saved the Standard audio profile
  for the lower speaker and preserved the separate Voice profile.

## 2026-11-25 — Ubuntu 26.04 upgrade handoff

- Recorded the verified 24.04.5 audio baseline, GPH3 DT patch,
  device-specific UCM settings and post-upgrade checks in the
  [upgrade handoff](ubuntu-26.04-upgrade.md).

## 2026-11-25 — Mainline hardware inventory and location profile

- Recorded the current Linux 6.18 SM-G955N hardware integration
  baseline and verified BlueZ discovery through Ubuntu.
- Guarded the Samsung GNSS bridge with its matching legacy kernel
  condition and switched live 6.18 GeoClue to its network-only profile.

## 2026-11-25 — BCM4773 transport audit

- Verified reversible SSI idle reads with the hub supply enabled
  and identified the missing outbound BBD path required to query
  the sensor hub from 6.18.

## 2026-11-25 — BCM4773 SSI endpoint

- Added a bounded half-duplex SPI transport for the sensor and
  location hub. Verified device ownership, idle I/O, regulator
  cleanup and unbind on 6.18 VPN2.

## 2026-11-25 — BCM4773 SSP query and power pin test

- Added a bounded BBD chip-ID probe and identified the missing GPA4-6
  GPIO mux. Validated transmission with the corrected board power
  setting and recorded the missing response on the current firmware path.

## 2026-11-25 — BCM4773 firmware startup baseline

- Confirmed the original daemon's firmware startup and sensor response
  on the working Samsung kernel. Added and verified the opt-in
  read-only BBD patch endpoint on 6.18.

## 2026-11-25 — BCM4773 firmware lifecycle endpoint

- Added an opt-in, root-only BBD control endpoint for daemon startup
  notifications and SSI patch delimiters on 6.18. The status records
  caller messages and qualifies only the control interface.
- Verified transitions, malformed input rejection and SPI unbind on the
  handset. Kept the trial module out of the boot configuration.

## 2026-11-25 — BCM4773 queued SSI stream

- Added an opt-in, root-only `ttyBCM` byte stream with bounded receive
  and transmit queues, link ownership shared with the raw SSI node,
  and transport byte and error reporting.
- Verified a 315-byte queued write and SPI unbind with an open descriptor
  on the Korean board with its revision 10 power pin configured.

## 2026-11-25 — BCM4773 legacy daemon power control

- Matched the same handset's #58 MCU rail, independent GNSS enable
  and BBD startup delimiters in the opt-in 6.18 stream.
- Verified the two power controls on the Korean board. The original
  daemon exchanged bytes in both directions before reaching an
  autobaud sync timeout. Firmware transfer remains pending.

## 2026-11-25 — BCM4773 USI8 source clock

- Identified a fixed SPI source rate despite driver requests for a lower
  rate. A same-board controller trial programmed the Exynos8895 USI8
  divider, recovered valid autobaud replies, and started vendor firmware
  transfer on 6.18.
- Added proposal 0140 for the USI8 clock tree and hub controller profile.
  The daemon still retries during transfer.

## 2026-11-25 — BCM4773 firmware completion and SSP identity

- Added proposal 0141 to keep short hub SPI delays at microsecond scale
  on the 250 Hz kernel. This resolved the firmware ACK stalls.
- Added an opt-in BBD sensor endpoint that queues one read-only SSP
  chip-ID query after the original daemon reports ready.
- Confirmed firmware completion, 549 acknowledged reliable frames with
  zero NACKs, and physical SSP ID 0x55 on 6.18.

## 2026-11-25 — BCM4773 automatic startup on 6.18

- Added the mainline location-hub systemd unit and an explicit Linux 6.18
  entry point to prepare the handset's read-only Android runtime.
- Booted the patched clock and SPI controller on the handset twice.
  The daemon started automatically each time. An integrated service
  restart also returned the real SSP ID 0x55.

## 2026-11-25 — Native BCM4773 accelerometer

- Added standard IIO axis and scale attributes with an on-demand SSP
  stream. The mainline boot selects Ubuntu's packaged SensorProxy and
  applies the handset display mount matrix through udev.
- Verified live acceleration values after reboot and a positive
  SensorProxy accelerometer property on the handset.

## 2026-11-25 — Native BCM4773 light and proximity

- Added illuminance and proximity IIO devices alongside acceleration.
  SSP stream requests share one ordered controller, with idle handling
  per sensor and the firmware's proximity decision retained.
- After reboot, standard SensorProxy recognized all three devices and
  reported actual light changes in lux and the far proximity state.

## 2026-11-25 — Identify the native OLED control path

- Added a guarded DSIM0 status snapshot with an opt-in panel ID request.
  Matched the same handset's Samsung boot log to the S6E3HA6 Dream2 A3
  SA calibration table. Linux backlight registration is still pending.

## 2026-11-25 — Recover OLED panel ID reads on 6.18

- The DSIM diagnostic waits for a ready clock lane and extends the
  bus-turnaround window for the ID read. It restores the timeout
  register before returning. The live panel returned ID `d11010`.

## 2026-11-25 — Read live OLED brightness calibration

- Added a panel-specific resource probe for MTP, ELVSS and HBM gamma
  through DSIM0. Verified repeated live reads, offset reset, lock-key
  transmission and DSIM timeout restoration on the SM-G955N.

## 2026-11-25 — Compute calibrated OLED gamma on the handset

- Added an optional AID probe using the pinned Samsung Dream2 A3
  tuning data and calculator. The 6.18 handset generated 74 gamma
  rows from factory MTP. Panel brightness remained unchanged.

## 2026-11-25 — Verify reversible writes to the OLED AOR register

- Added an opt-in AOR write and restore probe using Samsung's
  Dream2 A3 brightness table and latch command. Verified both
  register readbacks on the live panel.

## 2026-11-25 — Exercise the full OLED brightness command sequence

- Added the Samsung normal-brightness profile builder and an opt-in
  reversible panel test. The live panel accepted all eight brightness
  registers and returned the original profile after restoration.

## 2026-11-25 — Expose the OLED through Linux backlight

- Added standard backlight registration and cached gamma profiles.
  Validated stock GNOME power service brightness requests through
  to the real OLED registers on the running 6.18 handset.

## 2026-11-25 — Start the OLED backlight before GNOME

- Installed a systemd service for the native backlight module. Verified
  automatic registration on reboot, stepped ambient adjustment and
  working panel brightness updates after RTC-timed s2idle.

- Isolated GSettings for the administrator ChatGPT service. After a
  second reboot the service was still active and the Ubuntu user's
  runtime dconf file had the correct owner.

## 2026-11-25 — Expose native motion and barometer IIO devices

- Added gyroscope, magnetic field, pressure, barometer temperature
  and step-count attributes to the BCM4773 driver. Verified all seven
  IIO devices after reboot and retained Ubuntu's existing SensorProxy
  inputs, backlight, Wi-Fi and audio routing.

## 2026-11-25 — Expose the native compass to Ubuntu SensorProxy

- Decoded the BCM4773 rotation vector into IIO magnetic heading and
  connected the standard IIO trigger buffer. After reboot the packaged
  SensorProxy published heading through its GeoClue Compass API.

## 2026-11-25 — Bring up the MAX77865 haptic hardware path

- Confirmed the MAX77865 haptic block on the running revision 10
  handset. Added the matching PWM wiring, kernel config and Linux
  force-feedback driver for the candidate build.

## 2026-11-25 — Verify real MAX77865 vibration and stop

- The haptic BOOT trial registered a Linux force-feedback input.
  The handset microphone detected bounded motor pulses and returned
  to the noise floor after normal stop and explicit cancellation.
- Restored the integrated BOOT after the trial regressed the BCM4773
  firmware handshake. Identified the missing sensor clock and SPI
  overlay files in the trial's source tree.

## 2026-11-25 — Identify the notification RGB registers

- Extended the read-only MAX77865 probe to confirm the notification
  LED register block on the same handset and I²C address as haptics.

## 2026-11-25 — Expose the MAX77865 notification LEDs

- Added three standard Linux LED class devices with Samsung current
  limits, a shared haptic regmap, and a standalone LED-only binding.
  Verified each color's on and off register state on the handset.


## 2026-11-25 — Integrated vibration and notification LEDs

- Installed the combined MAX77865 haptic and RGB LED kernel on the
  BCM4773 baseline with the corrected USI8 clock and short SPI delays.
- Verified actual vibration, cancellation, s2idle motor shutdown,
  LED register state and the same hardware interfaces after reboot.


## 2026-11-25 — microSD and NFC electrical prerequisites

- Installed a read-only ACPM module update and verified the microSD and
  NFC I/O supply states after reboot.
- Prepared an opt-in, default-speed microSD kernel build using the
  board's pinmux, card-detect line and independently controlled supplies.


## 2026-11-25 — Read-only charger input integration

- Tested standard MAX77865 wired and wireless input status in UPower.


## 2026-11-25 — Native microSD host on the handset

- Enabled standard MMC host registration in the integrated 6.18 BOOT
  after verifying regulator sequencing, s2idle and a normal restart.
  No card enumerated during this test.


## 2026-11-25 — Charger input autoload and USI10 adapter

- Enabled the read-only charger input driver at boot and verified the
  wired and wireless source states in UPower after reboot.
- Enabled the USI10 I²C adapter used by the NFC and optical heart-rate
  sensors. The individual controllers still require driver integration.


## 2026-11-25 — S3NRN82 NFC responds in normal mode

- Confirmed on the handset that the Samsung post-enable wake signal
  is required by the tested startup sequence. The chip replied twice
  to a configuration-preserving NCI reset.
- Prepared a Linux NCI class transport for the board and kept the
  reset diagnostic out of the normal boot.


## 2026-11-25 — Native Linux NFC on the SM-G955N

- Enabled the S3NRN82 through the standard kernel NFC class. Fixed an
  early receive before the first I²C command was accepted.
- Verified device-up, discovery start and stop, and device-down on
  the handset after both s2idle and an ordinary reboot.


## 2026-11-25 — ADPD143 optical sensor identification

- Read the optical supply configuration and identified the installed
  device without enabling its emitters or capturing a biosignal.
