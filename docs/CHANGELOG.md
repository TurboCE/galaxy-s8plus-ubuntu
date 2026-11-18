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
