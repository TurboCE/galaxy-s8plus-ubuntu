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

Eleven boot/integrity/inhibitor tests exercise malformed input, actual pointer/packed argument layout,
positive return handling, transfer failure, verification-before-power ordering
and truncated replies:

```sh
python3 tests/test_cp_boot.py
python3 tests/test_sipc_status.py
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

## Experimental status-query boundary

`--boot-trial --query-status` adds a bounded FMT receiver and only two GETs:
phone power state and SIM status. A real packet must validate before queries
are sent. Fragmented/coalesced framing is length-bounded and reply type/sequence
must match; notifications are not reported as successful queries. Payloads,
identifiers and NV contents are never logged. The RFS endpoint is observed but
no request is answered, and no NV write/radio-enable/PIN command is implemented.
Five framing/correlation tests pass. The public older libsamsung-ipc reference
has no G955N/SS355 descriptor, so it is not installed as a ready-made backend.

The first status-query trial subsequently lost USB/Wi-Fi/serial responses.
Its failing stage/cause is unknown until the independently stored journal is
recovered. Do not qualify this feature or enable it automatically from the
successful earlier RAM-boot result. The default invocation remains validation
only and the default boot trial does not query status.

A follow-up correction holds an acknowledged logind sleep/idle inhibitor in
addition to the Android kernel wake lock, and closes its pipe on every exit.
Two real-child host tests cover readiness/EOF cleanup and failure-before-trial.
This has not yet been retried on the unreachable handset; it does not establish
that an idle suspend caused the connection loss. The original NV companion
checksum was separately verified using the public Samsung suffix and matched;
preflight now checks that as well as the original SHA256 backup pin.
