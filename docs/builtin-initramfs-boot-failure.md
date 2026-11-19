# Builtin initramfs failure and build/pack guard

## Actual failure

After owner-assisted recovery, kernel28 booted and the owner logged in by touch.
The normal Mali GNOME verifier passed three composition/popup trials. Twenty
DPMS cycles passed, then the next longer trial lost responses during its second
off operation. The extra trial also read MIF frequency; it is a valid negative
stability result, not proof of the original corrupting writer. The unavailable
alternate-governor test stopped at its precondition before any writes: this
kernel advertises only ondemand.

The following kernel29 GCC7 candidate immediately reboot-looped. Its matching
retained banner and repeated panic say: compression method gzip not configured.
It did **not** reach native Ubuntu or qualify the GCC7 runtime comparison.

The external ramdisk was correctly legacy-LZ4, identical to28. The overlooked
part was the builtin archive inside Image: the GCC7 builder lacked lz4. The
pinned scripts/gen_initramfs_list.sh defaults to gzip and silently retains it
when the requested .lz4 suffix has no corresponding executable. The resulting
file is named usr/initramfs_data.cpio.lz4 but starts with gzip bytes. The kernel
config has RD_LZ4/DECOMPRESS_LZ4 and no gzip decompressor. The previous builder
had lz4, so its builtin archive was genuinely legacy-LZ4.

This is a build-environment/validation error, not evidence of a GCC7 generated
code runtime defect. It caused an avoidable recovery operation. Kernel28 was
restored from a verified full BOOT backup in the exact matching root TWRP,
with full readback and unchanged recovery/protected data during restoration.
Kernel29 packed images are quarantined privately; original build files are
retained as negative regression inputs.

## Prevention

* The GCC7 image installs Ubuntu18.04's liblz4-tool package (which supplies lz4).
* Diagnostic and normal kernel builders preflight the required compressor.
* scripts/verify_kernel_initramfs.py verifies the matching embedded config and
  actual builtin archive bytes in ARM64 Image using its System.map start/size
  symbols. It checks linked bounds and enabled decompressor; filenames do not
  supply codec evidence. Empty/raw newc, gzip and legacy-LZ4 are distinguished;
  modern LZ4 frames and unsupported streams fail closed for this pinned kernel.
* The diagnostic build records the codec check and returns failure on rejection.
  The normal image builder also runs the guard. pack_boot repeats the check
  before creating an output image and records the result in its manifest.

Nine guard cases pass. The actual failing29 Image is rejected before any boot
image is created. The actual booting28 Image passes and repacks to exactly the
same boot-image bytes. The complete host suite is85 tests; none is hardware
stability acceptance. Kernel30 is rebuilding the same source patches/config
with GCC7 and the corrected builder. Deployment/boot/power testing remain pending
at this checkpoint.

## Calibration preservation check

A raw EFS hash differed after recovery entry, before any restore write. The
current EFS was independently saved; original EFS matches its earlier native
pre29 hash. Read-only debugfs extraction of both saved images compared118 file/
link entries: no changed, added or removed contents. This is content-level
preservation evidence; it is not a claim that filesystem/journal metadata is
byte-identical. No EFS write or calibration rollback was performed. The BOOT
restore preserved the current full protected hashes, including EFS, PARAM and
MISC, and wrote no USERDATA through the restore command.

Private evidence: artifacts/ondemand-safety/{kernel28-returned-*,kernel29-recovery-*,
recovery29-to28-receipt.json,bad29-pack-rejection.log,good28-pack-guard.log},
artifacts/quarantine/kernel29-gzip-builtin, artifacts/efs-returned-audit and the
independent backups. No calibration values, identifiers or raw images enter Git.
