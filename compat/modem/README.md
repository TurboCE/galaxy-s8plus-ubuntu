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

Sixteen boot/integrity/inhibitor/read/cleanup tests exercise malformed input, actual pointer/packed argument layout,
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
Six framing/correlation/passive tests pass. The public older libsamsung-ipc reference
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


## Recovered freeze comparison

After a forced restart, protected firmware/calibration/recovery and original NV
still matched their private pins. PARAM was archived again as a separate current
snapshot. The earlier failed trial's retained userspace journal ended just after
unit start; it did not prove that a status GET had executed. The saved last_kmsg
had bootloader records and no usable matching Linux banner, so no panic address
was symbolized from it. A missing transient unit's default Result=success is
not acceptance: always retain LoadState. Use the explicit .service name when
recovering a previous unit's journal.

The buffered Python block-reader caused the kernel's illegal UFS TCGETS messages.
`partition_input()` uses explicit os.open/os.read with EINTR handling and no
terminal probe. Three actual validation passes had zero new TCGETS errors and
taint0. Sleep inhibition now covers the entire preflight, with a regression case
that fails the former ordering. The desktop's configured automatic system-sleep
actions were both nothing; no automatic-suspend cause is inferred.

A later no-query trial booted/offlined CP, passed six subsequent full preflights
and about60seconds of further observation without a reboot, with taint0. Another
trial used the new --observe-only mode, which sends no status request at all.
Actual FMT frames arrived, then all remote responses stopped again. Passive mode
is therefore NOT qualified and no further modem boots are enabled/repeated at
this checkpoint. Normal kernel55 remains installed; there is no persistent CP
service.

Stage output in these comparisons is fsynced to a private USERDATA log before
hardware actions. A host-monitor glob accidentally included an older completed
run and stopped its follower early; completion now also requires the current
unit to be inactive. That follower's partial capture cannot prove a later phase.
Recover the newest individual durable log after restart, rather than accepting
an older completion marker. Additional cleanup markers now distinguish reset
from power-off, and even a failed log stream cannot prevent attempted power-off
when reset fails. The later passive freeze's last durable stage still needs
recovery. None of these diagnostics establishes a freeze root cause or LTE data.


## Timer cancellation on kernel57

Proposal0055 replaces synchronous cancellation under the modem callback lock
with serialized nonblocking attempts. A running callback can take the lock and
finish before the next attempt. The regression fixture tests inactive, queued,
running and running/rearmed timers in the actual patched helper.

Kernel57 takes the kernel55 display, USB and power profile plus
`--modem-timer-cancel-locking`. The actual handset passed four passive starts
and three read-only GET trials on the same boot. Each returned the CP to
OFFLINE after reset, power-off, endpoint close and wake-lock release. The
modem emitted generic command replies and asynchronous status notifications.
These are recorded separately from a matching typed GET response. Two RFS
requests per trial were observed, with no RFS or NV writes. ModemManager
integration and real cellular service still require a supported control and
data path.
