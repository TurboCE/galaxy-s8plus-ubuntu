# Diagnostic proposal: existing ESS work ring

This is not an active kernel patch or a corruption fix. The adjacent patch stays
outside `patches/*.patch`. No device operation was performed for this review.

The actual added helper was extracted and compiled into a native C fault model
with AddressSanitizer and UndefinedBehaviorSanitizer. It passed strict patch
application and these cases: all eight CPUs with 2,057 ring writes and exactly
the last 32 records retained; empty ring; null log pointer; uninitialized item;
zero mapping size; mismatched mapping pointer; signed head values INT_MIN and
INT_MAX; invalid recorded pointers; nonterminated task names; and a second dump
call producing no extra output. These checks establish bounded indexing and
non-dereferencing of recorded pointers in the helper, not live panic persistence.
The actual `drivers/trace/exynos-ss.o` also compiled successfully using GCC
13.3.0 in a dedicated Docker volume copied from the current source/output. The
original build volume was mounted read-only. The final helper introduces no
compiler diagnostic; existing task/work `strncpy` warnings remain. An aligned
atomic64 once guard avoids the old atomic32 wrapper's GCC array-bounds warning.
Evidence and the reproducible extracted-helper model are under private
`artifacts/ess-tail-audit/`. No full kernel image was built, and there has been
no live panic persistence test.

Existing ESS work logging is present in minimized mode. `show_regs()` freezes
log_kevents before the panic notifier, so the later disabled message does not
prove that logging was disabled before the fault. The next boot clears the
work ring. Printing the bounded tail into the existing last-kmsg path could
preserve callback ownership evidence without function tracing. Concurrent
entries remain best-effort snapshots; they cannot prove which callback caused
corruption. Raw addresses and resulting panic evidence must remain private.

# CPU suspend hypothesis review

Kernel15 (`artifacts/kernel-audio-proc/kernel.config`) and kernel22
(`artifacts/kernel-pcie-clock-bounds/kernel.config`) configurations are identical:
SHA256 ac47c26e14b555536cc87abb0bf68bc4deff856566d3c3e26a9a842c979a4ddd.
Both Image banners identify GCC 13.3.0 Ubuntu 13.3.0-6ubuntu2~24.04.1. This does
not establish identical complete compiler command lines or generated code.

Pinned `arch/arm64/kernel/sleep.S` saves and restores x19 through x28 at matching
stack offsets +16 through +80 in both failure-return and resume paths. The saved
caller stack pointer uses CPU_CTX_SP consistently. No concrete mismatch was
found. PSCI calls arm_smccc_smc in `drivers/firmware/psci.c`; the assembly wrapper
and `arch/arm64/kernel/exynos-smc.S` rely on the firmware callee-saved register
contract. These facts do not demonstrate a firmware contract violation.

The Exynos DT supplies one c2 state after driver-provided WFI. In
`drivers/cpuidle/cpuidle-exynos64.c`, only nonzero state indexes enter cpu_pm and
exynos_cpu_pm_enter. `drivers/soc/samsung/exynos-powermode.c` may promote that
entry to CLUSTER_SLEEP or SYSTEM_IDLE. The menu governor skips each CPU's
states_usage.disable flag. Therefore, after independently checking actual state
names and preserving old values, disabling state1 on every CPU would be a
bounded diagnostic isolation of this deep-idle path while retaining WFI and
frequency governors. It cannot repair corruption already present or prevent a
transition already in progress. No such setting was changed in this review.

Do not substitute the vendor enable_mask=0 parameter: exynos_enter_idle returns
without even executing WFI when ENABLE_LPM is clear. The generic per-state
disable mechanism avoids that implementation trap. Any isolation result still
requires repeated observation and does not identify a root cause; rollback to
the previously observed stable kernel remains a separate recovery action.
