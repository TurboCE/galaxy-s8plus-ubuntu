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
