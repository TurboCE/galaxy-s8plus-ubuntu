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
