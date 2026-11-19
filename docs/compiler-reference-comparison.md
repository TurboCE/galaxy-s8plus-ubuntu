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
