# L2/SRAM timeout recovery: design review only

Status: not an applicable patch; excluded from `patches/*.patch`. No native
operations, error injection, reset or firmware change has been performed.
This does not establish the cause or resolution of the captured MMU fault.

## Confirmed source defects

After 0017 and 0020, `__abox_control_l2c()` still ignores the return from
`abox_request_ipc()` and its wait result. Enable timeout nevertheless records
`l2c_enabled = true`, so synchronous callers can proceed without an acknowledged
L2 transition. Disable timeout nevertheless releases shared VTS SRAM and
records disabled, although ABOX may still be using that SRAM.

The IPC transport has two different acknowledgements. `abox_request_ipc()`
forces synchronous transport acknowledgement, and may return `-EIO` after its
transport timeout. `ABOX_END_L2C_CONTROL` is a separate operation completion.
The current completion handler only sets one boolean; it does not validate an
enable/disable value, request generation or firmware epoch. The checked-in IPC
header does not document such an echo contract. A timed-out request can therefore
complete late, and a subsequent request can mistake that event for its own ACK.
A mutex prevents concurrent submissions, but cannot disambiguate a late ACK.

## Required state and error contract

A correct implementation must separately track:

- confirmed disabled, confirmed enabled, or unknown firmware L2 state;
- whether the host owns the shared SRAM lease;
- whether a control transaction is pending, failed or acknowledged;
- the recoverable transaction/firmware epoch used to reject stale ACKs.

An acquisition failure before sending an IPC leaves the old confirmed state and
never grants ownership. A transport timeout or completion timeout leaves an
unknown state, returns an explicit error to synchronous callers, and retains
SRAM until a proven completion or hardware quiescence fence. It must not claim
that a host-side work item completing means firmware is ready.

Unknown state cannot be solved by setting `enabled = false`, releasing SRAM,
retrying until one uncorrelated ACK arrives, or indefinitely leaking the lease.
The recovery must be bounded, observable and paired with a documented way to
re-establish a known firmware state before VTS or a new CALL can use the SRAM.

## Why no automatic recovery patch is supplied yet

`abox_cpu_power(false)` only writes the PMU configuration. It neither returns a
power-down result nor polls a power-down status. `abox_cpu_enable(false)` also
has no disable-side status wait; its status polling is enable-only. These
helpers therefore do not establish a checked DMA/L2 quiescence fence after
which releasing the lease is proven safe. Resetting firmware also affects
active PCM/VSS streams and its clock/power/IPC ordering must be specified.

Before this can enter the automatic patch chain, obtain either:

1. a verified stock-firmware completion contract providing correlation and a
   way to drain/cancel a timed-out operation, or
2. a documented Exynos 8895 ABOX/L2/DMA reset/power-down fence, with checked status,
   bounded failure handling and a known-state recovery path for the SRAM owner.

Then validate normal transitions plus acquisition busy, IPC failure, lost ACK,
late ACK after timeout, failed recovery and concurrent vote removal with a
fault-injection harness. Hardware validation requires an automated recovery
route before injecting faults. Merely silencing the current errors or holding
the SRAM forever is not a completed fix.

## Source locations in the pinned kernel

- `sound/soc/samsung/abox/abox.c`: `__abox_control_l2c`,
  `abox_system_ipc_handler` (`ABOX_END_L2C_CONTROL` case),
  `abox_start_ipc_transaction_atomic`, `abox_cpu_power`, `abox_cpu_enable`.
- `include/sound/samsung/abox_ipc.h`: `IPC_SYSTEM_MSG` and L2 control message IDs.
- `sound/soc/samsung/vts/vts.c`: `vts_acquire_sram`, `vts_release_sram`.

Pinned commit: `54feaea9870dd0e90ceced5623e0544d965b400b`.
