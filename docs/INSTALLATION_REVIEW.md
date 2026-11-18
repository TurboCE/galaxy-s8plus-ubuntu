# Initial privileged-access review — not an installer

After recovery bootstrap and irreversible Knox effects were explained, the
owner explicitly authorized proceeding with the permanent Knox change on
2026-11-18. This authorizes the reviewed initial recovery bootstrap, not data
formatting. General porting and Git updates are also authorized.

## Preparation completed

- Target ADB identity: SM-G955N / dream2lteks / G955NKSU5DZE1 / revision 10.
- Exact Samsung KTC restore package downloaded; ZIP CRC passed. AP tar.md5
  verified by samloader. Stock BOOT and RECOVERY extracted/decompressed privately.
- Stock ZIP SHA256: c9e3a1dd7b0b22a547457ebe1f7df7a6bcf50f2e83a76f3a6ed5a40f8f2e1e4a.
- Stock BOOT SHA256: 6de0f78b0f5f6476cf1ad91bc4871c32160769735847596c530401630e027862.
- Stock RECOVERY SHA256: 117c9ca4c1a259f624ba92c1b998b49f9fd8ae0e066e1f5e7ef0ed8aaa8aaf25.
- Official TeamWin dream2lte 3.7.0_9-0 downloaded and verified against its
  published SHA256: e21a11df7c33b9897d1eb7371906650c53595e50ea24f1138ba96bdfe81321db.
  Image is 40,546,304 bytes and has a valid Android boot-image header. It is
  the unified Exynos S8+ recovery; its embedded DT names G955F. This does not
  constitute G955N runtime qualification. Do not substitute a G965N recovery.
- Stock CSC includes DREAM2LTE_KOR_SINGLE.pit. It describes BOOT as 10,240
  and RECOVERY as 11,776 UFS blocks (nominal 40/46 MiB with 4096-byte UFS
  blocks). This is restore-package geometry, not a live PIT readback.
- Shared storage copied and private per-file SHA256 manifest generated.
  This is not app-private data, raw EFS/CPEFS/RADIO or partition backup.

## Proposed bootstrap after explicit user approval

1. Recheck ADB identity; enter Download Mode; independently confirm its model
   and current flash restrictions, and obtain the live PIT without repartitioning.
2. Review unified recovery compatibility and compare the live RECOVERY geometry
   before any payload. If blocked by RMM/KG/FRP, stop; no bootloader workaround.
3. Install only the reviewed TWRP RECOVERY payload. This explicitly needs an
   exception to the repository's RECOVERY-preservation rule for the initial
   privileged-access bootstrap. Stock recovery restore materials exist, but
   no raw readback backup is available before privileged recovery access.
4. Enter recovery, verify actual root ADB, keep filesystems read-only initially,
   and back up BOOT, EFS, CPEFS, RADIO and other required partitions with hashes.
5. Check encrypted data access and app-private backups before planning Ubuntu
   installation. Do not format /data solely to make TWRP mount it. No data wipe
   is included in this bootstrap proposal.

Never flash BL, CP, PIT, repartition, relock or downgrade as part of this plan.
Device-side restrictions and manual mode transitions may require the user.

## Irreversible effect and outstanding verification

Android currently reports Knox warranty_bit=0. Loading an unofficial kernel or
recovery can permanently trip it to 1, disabling services such as Samsung Pay
and Secure Folder even after stock restore. See Samsung's official explanation:
https://docs.samsungknox.com/admin/knox-platform-for-enterprise/faqs/faq-115013719548.htm/

Full hardware parity is still unproven. No Ubuntu boot, LTE call, GPU runtime,
GNSS fix, sensor motion, Bluetooth pairing, Wi-Fi traffic or suspend test has
passed. There is no readable Ubuntu kernel log to audit yet.

## First live attempt

Read-only live PIT retrieval succeeded. All 30 entries match the exact Korean
stock CSC PIT; RECOVERY is ID 8, 48,234,496 bytes. The reviewed TWRP image fits.
The first samloader 2.2.0 RECOVERY attempt then failed during ODIN handshake,
before any session or payload write. It did not establish flashing success.
The user was asked to re-enter Download Mode and report any on-screen errors;
no automatic write retry or device restriction workaround was attempted.
