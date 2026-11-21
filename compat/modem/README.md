# Native CP RAM boot checkpoint

`cp_boot.py` implements a bounded native Linux boot trial for SM-G955N's
SS355AP, using the SS310AP driver ABI and SIPC5 SHMEM boot protocol. It does not
install a cellular service, create an AT modem, or qualify LTE data/calls.
The ordinary ModemManager service still has no supported control transport.

The default invocation validates only. An explicit `--boot-trial` loads the
phone's own BOOT/MAIN/VSS and existing NV into reserved CP RAM, requires the
normal signed BOOT/MAIN verification, exchanges actual boot/final-stage
responses and waits for the kernel's real init completion. It observes the CP
for five seconds and resets/powers it off in cleanup. SIGINT/SIGTERM also take
that cleanup path. No status IOCTL is used: that older IOCTL clears SIM-change
or NV-rebuild state. No crash/dump/panic/reboot command, NV creation, firmware
flashing, full Android init or RFS file write is implemented.

The tool requires a private inventory with verified raw backups/current byte
counts and hashes for RADIO, EFS, CPEFS, RECOVERY and PARAM, and a hash of the
existing `/efs/nv_data.bin`. Keep that file, all backup images and all vendor
inputs out of Git. Verify the model, stock recovery material and private backup
files on the host before any trial. EFS must already be mounted read-only;
the current DT must identify SS355AP with a128MiB CP boot region. Preflight
rejects an active modem or competing open clients. The actual invocation used
a bounded, independently supervised systemd unit; it was not enabled at boot.

Public references are pinned in sources.json. Modern cpboot's mode7/12 TOC/VSS
verification must not be copied into this older kernel: shm_ipc.c only maps
normal, dump and reinit parameters. The implementation uses its legacy SIPC
path, with packed28-byte firmware and16-byte security arguments. It rejects
unexpected TOCs, CRC failures, incomplete NV, overlapping/out-of-range sections,
positive IOCTL failures and incomplete handshake frames before reporting success.

Eight tests exercise malformed input, actual pointer/packed argument layout,
positive return handling, transfer failure, verification-before-power ordering
and truncated replies:

```sh
python3 tests/test_cp_boot.py
```

On kernel55 the first actual trial reached `ONLINE`, stayed there during the
bounded observation and returned to `OFFLINE` without reboot, taint or storage
hash changes. Both signed verification and actual CP_START/INIT_END occurred.
The ordinary GNOME hashes/default path stayed valid, failed-session UI was
absent and a subsequent standard speaker/mic duplex trial passed its transport
and tone checks. Its pre-existing cold-capture transient remains open.

Next work is native SIPC/RFS ownership and a compatible Ubuntu modem-control
backend. Do not enable an unattended modem boot service until those consumers
and crash/recovery/power behavior have been tested. A SIM has not been supplied;
registration, mobile-only traffic, calls/SMS/VoLTE and modem suspend/reconnect
remain unverified. Merely reaching ONLINE does not establish those functions.
