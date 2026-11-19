# PCIe clock enable/rollback: excluded design proposal

Status: no applicable patch and no phone fault injection. Active patch 0025 only
fixes clock lookup indexing/count bounds; it does not repair the enable state
machine below. The build runner does not apply this directory.

## Confirmed defects in the pinned source

Both clock-enable helpers overwrite `ret` on each iteration and inspect it only
after the loop. An earlier failure can be hidden by a later success, diagnostics
report i==count rather than the failing slot, and successfully enabled clocks
before/after a failure retain references. `CONFIG_SEC_PANIC_PCIE_ERR` currently
only sees the final return, so it can also miss the earlier failure.

A helper-only transactional rollback is unsafe: callers currently assume all
clocks were acquired. `poweron_fail` forces STATE_LINK_UP and calls poweroff even
when failure was before clock acquisition (including pinctrl failure). Poweroff
then disables an IRQ that was not enabled by this attempt, accesses controller/
PHY MMIO, sends PME and disables every clock. If a corrected helper already
unwinds a prefix, that path would double-disable or access hardware without
required clocks. A simple `if (ret) goto poweron_fail` is therefore not a fix.

The void `assert_phy_reset` and `resumed_phydown` also discard failure. Their
callers span establish_link retries, initial probe, noirq resume and LPA_EXIT.
`resume_noirq` ignores establish_link's existing result and proceeds to L1SS
MMIO. Missing error propagation is not confined to the loop.

## Required ownership contract before an active patch

Track the resources actually acquired by the operation, separately from the
public link state: pinctrl selection, QoS/idle/wakeup updates, controller clock
references, PHY clock references, PHY/MMIO validity and IRQ enabled state.
Determine whether each resume path retains old clock references before changing
repeated-enable semantics; do not substitute a single guessed boolean.

- Each enable attempt must stop on the first failure and preserve its errno and
  exact index. Unwind only that attempt's successful prefix in reverse order.
  Never disable the failed clock: clk_prepare_enable already unwinds its own
  failed prepare/enable attempt. Do not consume references held before this call.
- Preserve the configured panic policy for real clock failures, with correct
  failed-index diagnostics; do not remove BUG_ON under the enabled option merely
  to make an injected test return. Test the nonpanic return and enabled-panic
  branch with mocked BUG handling, without a live panic.
- A failure before controller clocks may restore pinctrl/QoS/idle/wakeup state,
  but must not use ELBI/DBI/PHY MMIO, send PME, disable an unowned IRQ or disable
  unacquired clock references.
- A PHY failure with controller clocks held needs a separate error path that
  only touches registers whose clock requirements are established. Establish
  whether phy_config's earlier MMIO requires those PHY clocks on this SoC.
- Make reset/phydown return int, consume it in probe, noirq resume, link retries
  and LPA notifier using each API's actual error contract. Do not force LINK_UP
  simply to reuse poweroff; separate rollback from a real linked shutdown.
- Clock lookup references (`of_clk_get`/clk_put) and prepared/enabled references
  are different ownership. Probe failure still needs a complete accounting of
  successful earlier lookup references; index correction alone does not free
  them.

Pinned contexts: pci-exynos.c clock helpers 395/420; reset 750; phydown 1468;
poweron 1549/1675; poweroff 1683; noirq resume 1872; LPA_EXIT 1967. Line numbers
refer to the unpatched source; patch 0024 shifts later contexts without fixing
these control-flow defects.

## Required fault-injection acceptance

Use extracted production functions with mocked CCF, MMIO, IRQ, pinctrl, regmap,
QoS and notifier operations. For both clock groups cover first, every middle,
and last failure; success; zero clocks; and initially held references. Assert
reverse prefix order, no failed-clock disable, no later enable after failure,
exact errno/index and unchanged held references. With panic configured verify
the intended panic notification; without it verify safe propagation.

Inject at controller enable, PHY enable on each retry, probe phydown, noirq/LPA
resume and the pre-clock pinctrl phase. Require zero forbidden MMIO/PME/IRQ
operations and balanced ownership on every failure. Only after the complete
caller-level tests pass should this become an active patch and receive a
recoverable on-device qualification. Current host tests cover the narrower
active 0025 lookup fix, not this unimplemented state-machine repair.
