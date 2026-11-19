# Kernel #22 stability investigation

Kernel #22 is not qualified for normal use. Three unexpected resets occurred;
the verified complete BOOT backup containing kernel #15 was restored while
preserving USERDATA and the recovery/calibration partitions. Recovery is a
mitigation, not a root-cause fix. No ION allocator or hardware GPU trial ran
during the affected boots.

## What the saved evidence establishes

The reserved last-kmsg buffer contains older boot sections as well as the most
recent one. Each incident must be separated at the fresh Linux boot banner and
subsequent bootloader boundary; repeated older traces are not new failures.

| Incident | First useful failure evidence | Interpretation and limits |
| --- | --- | --- |
| First | Workqueue invariants fail, then `process_one_work` dereferences a null `worker->pool`. Its worker argument points into its own kernel stack rather than the expected worker allocation. | A real kernel exception followed by panic/reset. The next queued callback resolves to `dbs_timer`, but was not entered: this does not establish a cpufreq callback bug. |
| Second | A new boot first faults in `_raw_spin_lock` called by `rcu_read_unlock_special` during pathname lookup. Later exceptions involve an invalid instruction target from `scheduler_tick` and a lock failure in `run_rebalance_domains`. | Broader pointer/state corruption is suspected. Later exceptions may follow from the first; they are not three independently established causes. The first incident's residual workqueue trace occurs before this boot and must be excluded. |
| Third | After a new Linux boot section, output ends without a new Linux Oops/panic traceback. The following bootloader identifies a watchdog reset and a safe-kernel-panic reason. | Another unexpected reset is established, but its failing instruction and initiating caller were not captured. The earlier RCU/scheduler traces in this dump belong to the second incident. |

WLAN runtime suspend/resume and display blank/unblank or missed-unblank messages
occur near parts of the captured activity. Temporal proximity does not identify
either driver as the corrupting writer. Kernel build #22 contains multiple
changes relative to #15, and the display presenter also changed during the
investigation. Neither change set has been isolated as causal.

The #15 and #22 saved kernel configurations are byte-identical, and both image
banners report the same GCC version. This does not establish identical object
code or compiler command lines. The pinned ARM64 suspend assembly has matching
callee-saved register save/restore offsets; no concrete context-restore defect
was found. Secure firmware register preservation remains a hypothesis, not a
verified fault.

## Minimal next diagnostics

1. Keep the recovered baseline and matching private BOOT/vmlinux/receipts.
   Compare generated code and available compiler command records for the fault
   paths, suspend/SMCCC boundary and changed objects before selecting a bisect.
2. Prepare a controlled patch-group bisect with the same presenter and userspace
   state. Keep audio auto-probing and GPU/ION experiments isolated. A short
   successful run cannot qualify an intermittent-corruption candidate.
3. Review the inactive ESS work-tail proposal before building a diagnostic
   candidate. It prints at most 32 existing work records per CPU at panic,
   without following recorded pointers or altering the normal workqueue path.
   Its extracted helper passed bounded-ring and fault-input ASan/UBSan checks,
   and the actual modified object compiled in an isolated copy. Full image
   integration and live persistence remain unverified. The ring is
   cleared on the next boot, so a post-reset read cannot recover it otherwise.
4. If a later controlled comparison specifically tests deep idle, first verify
   the actual state names and save all original disable values. Disabling only
   C2 on every CPU retains WFI and governors and excludes the driver's
   cluster/system-idle promotion path. This is reversible isolation, not a fix;
   it does not repair already-corrupted state. Do not substitute the vendor
   global idle mask, whose disabled path can return without WFI.

Full function/event tracing is absent from the current configuration. Enabling
it requires a separately reviewed diagnostic build. Public records omit device
identifiers and raw addresses; complete dumps remain private.
