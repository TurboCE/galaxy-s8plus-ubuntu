# Reference-generation compiler comparison

The pinned kernel's own HOW-TO-BUILD recommends Linaro GCC7.5 (2019.12) on an
x86_64 host and Make4.2.1 or older. Earlier porting builds used GCC13.3.
A compiler incompatibility is a diagnostic hypothesis, not an established
cause of the scheduler/RCU corruption.

`build/Dockerfile.gcc7-reference` prepares an AMD64 Ubuntu18.04 host with
Ubuntu's ARM64 GCC7.5 cross compiler and native GCC7/Make4.1. This compares the
recommended compiler **generation**; it is not falsely labeled the exact
Linaro toolchain. Package installation uses authenticated Ubuntu metadata.
There are no handset tools, vendor images or credentials in the image.

The kernel builder records the actual compiler version, immutable builder-image
ID and explicit build number. Kernel29 selects the same source proposals,
normal-idle config and core build flags as kernel28 but uses this compiler image.
A strict post-olddefconfig comparison must still pass; configuration differences
must not be silently accepted as a compiler-only trial. Hardware qualification
is separate from build success. Packed ramdisk/DT and protected partitions must
be checked again before any future deployment.

An initial ARM64-hosted compiler image ran under emulation on the AMD64 Docker
host. Its build was explicitly stopped (exit137), never packaged or installed.
The native-host cross-compiler build uses a separate fresh output/volume, so that
aborted attempt cannot be mistaken for a passing or source-compilation failure.

Public source/patch notices remain intact. Proprietary device firmware and
compiled images remain private; this comparison does not publish those inputs.


## Build checkpoint

The native-host cross-compiler kernel29 build completed successfully with actual
GCC7.5.0. Its config and exact source-patch hashes match kernel28. Both packed
ramdisk and DTBH are byte-identical to kernel28, and the completed image fits
the existing BOOT partition. Build29 is not deployed or hardware-qualified.
Kernel28 is also packed but not deployed: the prior staging attempt lost the
connection before any BOOT write. The last confirmed running kernel remains27.
Private full images/receipts are under artifacts/ondemand-safety.

At the latest check neither SSH nor the selected G955N USB console responds.
Interrupting the agent's console foreground command and toggling its standard
USB serial carrier did not recover a prompt. No raw USB vendor command, partition
write, or alternate-device operation was attempted for recovery. Further
handset verification needs a genuine reconnection; host source/build work is
not being counted as hardware acceptance.


## Later runtime correction

Kernel28 was subsequently installed and failed extended DPMS testing after
bounded passes. Kernel29 was then installed but reboot-looped before Ubuntu:
the GCC7 builder lacked lz4, so the builtin archive was silently gzip despite its
.lz4 filename and disabled gzip decompressor. The earlier pack check only covered
the external ramdisk. Therefore29 is a failed build-input validation case, not a
GCC7 runtime comparison. Known-booting28 was restored through TWRP. Actual builtin
codec guards and the corrected liblz4-tool builder are now used for fresh30.
See builtin-initramfs-boot-failure.md for evidence and preserved calibration.
