# Matched panic decoding and safe-fault recovery checkpoint

## Offline decoding

`scripts/decode_kernel_panic.py` reads a retained log and a completed matching
SM-G955N build directory. It verifies the vmlinux/System.map hashes from the
build plan and the AArch64 ELF type, extracts the compiled full Linux banner,
and refuses a different or damaged latest intact banner. It excludes older
boot sections and subsequent bootloader messages. Multiple later bootloader
sections are rejected because a newer kernel banner may be damaged.

KASLR displacement requires an explicit boot-offset record or agreement between
both named PC/LR symbols, printed function offsets and raw addresses. Missing,
unaligned or conflicting evidence is not guessed. A stack-protector message
contains a return address: the decoder subtracts relocation and four bytes to
resolve the AArch64 call instruction. This avoids misidentifying the next
function at a symbol boundary. A decoded caller is not a proven corrupting
writer or hardware acceptance.

Output is an atomic mode0600 private JSON file. The tool refuses to replace the
raw capture or write into the matching build directory. It does not access a
handset or run firmware. Keep reports, addresses and raw logs out of Git.

Fourteen decoder cases cover mismatched/damaged banners, residual boot sections,
conflicting relocation, missing symbols, call-boundary attribution and input
preservation. On the actual kernel27 retained buffer it verifies relocation and
resolves the stack-check caller to exynos_ss_panic_handler_safe. The damaged
kernel26 buffer is rejected rather than automatically symbolized against weak
evidence. The earlier manual kernel26 interpretation remains explicitly partial.
The parser cannot reconstruct arbitrarily corrupted or missing boot boundaries;
manual scope validation of damaged buffers remains required.

Example (use private paths and the matching build):

```
python3 scripts/decode_kernel_panic.py --log PRIVATE_LAST_KMSG \
  --kernel-dir PRIVATE_COMPLETED_BUILD --output PRIVATE_REPORT.json
```

## Recovery defect found during source review

The ARM64 __do_kernel_fault_safe caller invokes
exynos_ss_panic_handler_safe, then waits indefinitely with WFI. The callback
formerly returned immediately when optional snapshot logging was disabled,
skipping its existing watchdog reset request. This is a concrete missing-recovery
path. It is not evidence that optional logging was disabled in an observed hang,
and it is not the initiating memory-corruption fix.

Proposal32 routes that disabled-logging path to the existing watchdog request.
The enabled-logging path, its ordering, and raw watchdog count100 stay unchanged.
That number is a hardware counter value, **not seconds**. The watchdog driver
must have initialized successfully for its request to work. No normal execution
path is changed and no fault is deliberately triggered by the check.

An extracted actual-function sanitizer fixture verifies the disabled case and
all eight enabled CPU paths; the original fails the missing-reset assertion.
The actual patched trace translation unit also compiles as AArch64 with GCC7.5
against the read-only kernel29 source/output volume, using its saved compiler
command with only source/output/dependency destinations redirected privately.
The parent source/image is unchanged. The object receipt is private.

Proposal32 is inactive: it is not in kernel28/29, no full boot image containing
it was installed, and no on-device watchdog recovery pass is claimed. The full
76-test host tooling suite is separate from these actual-function fixtures and
from all phone hardware acceptance.
