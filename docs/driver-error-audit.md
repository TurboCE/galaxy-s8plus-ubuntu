# Driver error audit: current kernel 15 versus unqualified fixes

This audit is read-only. It changes no kernel, phone configuration, service,
radio or GPU library. Source corrections and log classification do not establish
hardware stability or an error-free boot.

## Evidence boundary

The current-window source is the private
`inventory/desktop-console-bootloop/kernel15-after-reconnect-cpu.raw.txt`:
62,510 lines, monotonic 17785.570811–19455.928146 seconds (27m50s). It starts
inside a register dump, not at boot. There are 60,508 priority-prefixed entries:
49,964 priority 4; 9,267 priority 6; 1,273 priority 3; four priority 7. A parser
that treats every priority-3/4 line as a new driver failure produces misleading
results. Raw evidence is retained; the counts below do not delete or conceal it.

`artifacts/kernel-audio-proc/vmlinux` identifies the matching build as
`4.4.111-g955n-ubuntu-experimental #15`, built 2026-11-18 18:19:19 UTC.
Its saved configuration enables BCM4361, Mali r16p0/kbase, Exynos ION,
Mali DVFS/runtime PM and verbose ALSA procfs; DRM is disabled. It also enables
SEC_DEBUG, last_kmsg and PANIC_ON_OOPS, with PANIC_TIMEOUT=5. Disabling diagnostic
or panic facilities is not a repair for the observed faults.

The newer `artifacts/kernel-request-locking/build-record.json` records patches
0001–0020 and explicitly `deployed=false`, `hardware_qualified=false`. Do not
attribute those candidate fixes to the phone still running #15. Source/config
build success and actual deployment are separate facts.

## Current-window classification

| Cluster | Observed count | Meaning and action |
| --- | ---: | --- |
| PCIe clock enable, ret=0 | 252 PCIe + 252 PHY | Actual successful calls logged with `dev_err`, not clock failures. Preserve execution/return checking; a future logging correction should store the return first, log nonzero as error and success at debug/info. |
| L1SS enabled | 252 | Successful power-management path logged at error priority. No evidence here of its failure. |
| ACK OK / Enter_L23_READY received | 251 each | Successful suspend handshake. Do not confuse these with the separate timeout branches. |
| keyctl add_key succeeded(0) | 15 | Successful key creation logged unconditionally with KERN_ERR. All 1,273 priority-3 messages are these successful-path categories; none is an observed failure return in this window. |
| Native optional-syscall register dumps | 1,904 printed syscall headers | 291/statx:1259, 439/faccessat2:551, 436/close_range:35, 435/clone3:57, 441/epoll_pwait2:2. Vendor `do_ni_syscall` prints registers while returning ENOSYS. Patch 0016 handles precisely these native feature negotiations, retaining the unsupported result and other fault diagnostics. It is not active in this window. |
| Firmware event_log_get ret=-25 | 49 | Real NOTREADY response from a diagnostic firmware-log request, not UNSUPPORTED (-23). Appears after intentional link-down/runtime-PM transitions. Readiness/flush ordering remains worth fixing; this alone does not establish packet loss or association failure. |
| New panic/oops/BUG/WARNING header | 0 matched in this window | Narrow observation only: boot-start data is missing, and printed task dumps already carry sticky `Tainted: ... W`. The whole boot is not warning-free. |

Source anchors for the successful priority-3 messages are
`drivers/pci/host/pci-exynos.c:759,1473,1513,1786,1803` and
`security/keys/keyctl.c:142–147`. The PCIe success and timeout messages are distinct
branches. In particular, never simply remove a logging macro that currently
contains the clock-enable function call as an argument.

`arch/arm64/kernel/traps.c:586–609` explains the unsupported-call register dumps;
patches 0006/0016 preserve ENOSYS instead of pretending to implement new syscalls.
These dumps occupy the ring buffer and can evict real boot failures, so a
truthful diagnostic correction is useful but is not a driver-function fix.

For `event_log_get`, `bcmdhd4361/include/bcmutils.h:380,382` defines -23/-25.
`wl_cfg80211.c:24987–25012` sends the log-preserve request and merely reports
its failure; several disconnect/error paths call it. The first captured -25 at
19022.583909 seconds follows link-down and “Runtime PM Disabled”. Proposed next
source investigation: attribute each caller, verify the firmware/bus-ready state
under the existing driver's appropriate lock/wake reference, and skip/defer an
optional diagnostic flush only when it cannot legally run. Preserve real
connect/scan/data errors and avoid adding unbounded retries. No PM or firmware
state patch was made in this audit.

## Genuine driver defects remain higher priority

The private previous-boot `kernel15-unexpected-last-kmsg.bin` contains an actual
Abox SysMMU WRITE PAGE FAULT at 0x0a400080 followed by “Unrecoverable System MMU
Fault” panic. That is materially different from register dumps for ENOSYS.
The fault address must not be equated with WDMA4's mapped 0x82400000 IOVA without
additional proof. The independent ABOX review has identified real source defects:

- Patch 0017 checks shared VTS/L2 SRAM acquisition before continuing CALL PCM
  initialization and separates per-endpoint CPU votes.
- Patch 0018 prevents mapping more fixed PCM memory than was actually allocated,
  checks mapping failure and keeps preallocation changes from invalidating IOVA.
- Patch 0019 checks CPU request-table bounds before writes and propagates failure.
- Patch 0020 serializes request-table access and L2 control/shutdown snapshots.

Their existence does not prove the panic is resolved. Firmware ACK/timeout
recovery and teardown ownership remain acceptance items. The scoped userspace
ALSA candidate can prevent unqualified PCM probing, but containment does not
replace repairing kernel memory/resource ownership. Do not reproduce broad
CALL/VTS/capture/realtime enumeration on the old kernel to obtain cleaner logs.

The saved #15 first-boot log also reports absent `/etc/wifi/filter_ie` once at
8.321407 seconds. The pinned driver explicitly calls filter-IE configuration
nonfatal (`bcmdhd4361/dhd_linux.c:12159–12161`). No such event is in the later
window. Do not fabricate an empty vendor filter file or silently call optional
configuration mandatory without actual filtering requirements.

MFC unknown-format warnings are separately addressed by candidate patch 0015's
six missing format descriptions. This corrects enum metadata while retaining
warnings for genuinely unknown formats; it does not validate video decoding,
encoding or cameras. Patch number 0015 is unrelated to running build number #15.

## Acceptance and sequencing

First preserve full boot/previous-panic evidence and deploy only a reviewed
kernel with a recovery path. After deployment, establish the actual build/config
identity and collect a fresh boot-start log before normal probes fill the ring.
Qualify the bounded normal speaker path and GPU allocator/presentation paths
separately; keep unqualified endpoints excluded until driver ownership fixes
are checked. Repeat already-successful network tests only after relevant driver
changes or new evidence. Whole-system suspend, thermal behavior, overnight
stability and physical audio/microphone acceptance remain distinct tests.

A cleaner console, zero failed systemd units, successful reconnects or one
quiet interval cannot establish “all features work without kernel errors”.
