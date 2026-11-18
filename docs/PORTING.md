# Engineering notes

## Native boot reference audit

roufsweb/galaxy-s8 targets **G950N**, not G955N. Its public guide identifies
USERDATA as sda15 while its builder falls back to sda24. Never copy numbered
partition paths; resolve by-name against this specific phone and verify sizes.
Its kernel/ directory is ignored, so the AP builder alone does not reproduce
the claimed kernel. Its llvmpipe demonstration is CPU rendering, not evidence
of Mali acceleration. BOOT+RECOVERY replacement in the reference is not adopted.

## Korean S8+ source

ace2nutzer/Samsung_dreamlte_Kernel contains
arch/arm64/configs/exynos8895-dream2ltekor_defconfig and Korean dream2lte DTs
for hardware revisions 6, 7, 9 and 10. The revision-10 DT explicitly names
SM-G955N. Its baseline configuration enables DEFEX, RKP/CFP and SELinux;
it is not an Ubuntu-ready configuration. Audit build scripts and actual config
overrides rather than assuming the defconfig describes released custom kernels.

## Graphics integration

The connected stock phone reports /dev/mali0, EGL Bifrost r16p0-01rel0,
libGLES_mali.so (32/64 bit), gralloc.default.so, hwcomposer.exynos5.so and
android.hardware.graphics.composer@2.1-impl.so. Preserve private copies and hashes
for ABI/dependency analysis; do not publish proprietary binaries.

First check candidate kernel Mali ABI versus r16p0, Android/Bionic dependencies,
gralloc/ION and fence interfaces, and Halium compatibility before selecting a
rootfs/Android base. A libhybris GLES demo is an initial milestone, not proof of
GNOME desktop OpenGL/GLX, browser or external display acceleration. Mainline
Panfrost is a separate strategy, not a drop-in user-space replacement for kbase.

## Device write gates

No flash/format/reboot has been performed. ADB shell is unprivileged. EFS,
RADIO and BOOT backup attempts requiring privilege have not been performed.
Need matching stock restore materials, verified private backups and an exact
write plan before installation. Do not modify the connected S9+ Linux device.
