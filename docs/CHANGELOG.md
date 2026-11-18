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
