# Engineering notes

## First configuration run

Generated on a case-sensitive Linux Docker volume using the pinned kernel.
The actual upstream build script merges g950x_defconfig + g955x_kor_defconfig;
the port follows that combination then applies config/ubuntu-bringup.fragment.
Result retains MALI_TMIX_R16P0, CAMERA_DREAM2 and WLAN_REGION_CODE=200,
selecting dream2lte_kor_10.dtb.
Configuration SHA256: 673bedfb85a22640b9a043854acaaf28fd170127f00def16704d1584fff61661.
Configuration generation succeeded; compilation and hardware boot are separate.
First builder was the existing s9-g965n-builder:24.04.3 image
(sha256:f969dadedd09d3a2469549a204bb1ff45c42b2569931d6d3cdc086b00b379637),
used in a new isolated container with a G955N-only volume, without USB access.
The supplied Dockerfile documents a standalone builder for subsequent work.

macOS checkout has case-colliding Linux filenames. The builder uses git archive
from pinned committed objects and extracts into Linux storage. fetch_sources.py
now uses bare *.git repositories so fetching does not create case-collided
working files; existing checkouts are left untouched. The builder prefers the
bare pinned source when present. Use case-sensitive storage for source edits.
Build output is private.

## Graphics dependency audit

Read-only extraction and ELF inspection of the connected phone's 64-bit EGL,
gralloc and HWC libraries completed. Binaries remain private and Git-ignored.
Mali requires Android libnativewindow, libcutils, liblog and libion_exynos,
in addition to Bionic libc/libm/libdl and other dependencies. HWC additionally
requires libexynosdisplay, libmpp, allocator/mapper 2.0, libGrallocWrapper and
libExynosHWCService. This confirms that copying libGLES_mali.so into a glibc
rootfs alone is insufficient. The candidate kernel includes b_r16p0 with
MALI_RELEASE_NAME r16p0-01rel0, matching the observed version string; this is
a compatibility lead, not proof of full ABI or hardware compatibility.

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

The authorized initial RECOVERY bootstrap has now succeeded. TWRP 3.7.0 root
ADB and Knox 1 were observed; the RECOVERY prefix matches its approved image.
Seven partitions have independently matching raw device/host SHA256 and sizes.
The user additionally authorized initializing Android app data. No Ubuntu
BOOT/USERDATA write had occurred at this preparation checkpoint. Preserve the
working recovery and calibration partitions. Do not modify the S9+ Linux device.
