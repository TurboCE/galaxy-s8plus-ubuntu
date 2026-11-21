# Ordinary USB disconnection: existing-log audit

Audit date: 2026-11-21, Asia/Seoul. Target: SM-G955N only.

## Scope and outcome

This audit compared already retained macOS USB events and Ubuntu USB/sleep
receipts. It did not contact the handset, use SSH, rerun a modem/SIPC test,
change settings, reset USB, reboot, flash, clear logs, or alter the excluded
modem code/proposal work. The later report that reboot/reconnection restored
Mac USB and serial recognition is a reported status, not a new data-path test.

**An independent cause of the recent ordinary-use USB disconnection is not
established. No new device/configuration fix is justified by this evidence.**
The requested boundary is reached: an ordinary USB fault cannot be separated
from the other failure classes with these logs alone. Diagnosis stops here;
no blocked operation is bypassed or retried.

## macOS evidence

The read-only system-log query covered 08:14–09:12 KST on 2026-11-21. It returned
6,939 retained events.119 messages named the S8+; unrelated device events were
excluded from the conclusions. Raw records and identifiers remain in ignored,
private artifacts. The native S8+ repeatedly enumerated at480Mbps.

Selected native-S8 detach/re-enumeration pairs align with the retained controlled
sleep tests. These host gaps exclude preparation/settling overhead:

| Host detach KST | Host re-enumeration KST | Host gap | Existing device trial |
| --- | --- | --- | --- |
| 08:16:15 | 08:16:34 | 19.068s |20.30s timed cycle documented in VALIDATION |
| 08:18:56 | 08:19:40 | 43.934s |45.15s cycle; USB recovered, GNOME process lost |
| 08:29:19 | 08:30:03 | 43.597s |44.86s cycle; USB and GNOME retained |
| 08:31:47 | 08:34:46 | 178.928s |180.41s cycle; USB recovered, GNOME process lost |
| 08:39:57 | 08:42:56 | 178.233s |179.30s cycle; USB and GNOME retained |

Other reconnect pairs also exist, but no precise per-event cause is assigned
without matching ordinary-use device-side records. A recovery-mode transition
was excluded from the native Ubuntu sleep-gap pairs.

Thirty native-S8 transaction-error completions are recorded in this window.
They accompany USB disconnect activity; they do not by themselves establish a
bad cable/port or an uncommanded gadget failure. The words “hardware connection
lost” establish the host's loss of the link, not which side caused it.

Nineteen native-S8 user-client opens were denied for exclusive ownership shared
between Google Chrome and ChatGPT. This establishes host application access
contention. It does not establish that a failed open removed the CDC/serial
interfaces or caused the detach. No application was closed and no USB owner
was forcibly displaced on that basis.

## Ubuntu evidence and classification

The retained kernel55 receipts show successful USB quiesce/restart, unchanged
boot and zero new USB/kernel failure signatures in the saved45/180-second
comparisons. The later30.15-second power-key path likewise retained the boot,
USB, GNOME and lock. Actual USB SSH/serial checks are historical observations;
they were not repeated by this audit. Device-side CONFIGURED alone is not proof
of a working host connection.

A separate, deliberately induced kernel54 re-enumeration-during-sleep case
lost the Mac interfaces while Wi-Fi remained responsive. That is independent
USB-path failure evidence for that older controlled scenario. The existing
kernel55 sleep fix and bounded passes cannot be generalized into proof that
all ordinary-use USB failures are fixed.

| Candidate explanation | What can be concluded |
| --- | --- |
| Cable, connector or Mac port | Data-capable enumeration is observed; intermittent physical failure is neither proved nor excluded. No A/B cable/port comparison exists in this audit. |
| USB system-sleep recovery | Controlled detach/reconnect intervals and kernel55 successful recovery receipts align. These are not spontaneous ordinary-use failures. |
| Host application ownership | Exclusive-open denials are confirmed; a causal link to disconnect is not. |
| GNOME/session failure | Some trials lost GNOME while USB and the same boot survived. A frozen-looking desktop is not sufficient to diagnose a USB fault. |
| Whole-device hang | Prior reports combined USB, Wi-Fi and console loss with an unresponsive power button. USB observations alone cannot isolate or repair that failure. The excluded trial path is not retried. |
| Recent ordinary-use disconnect | Missing a correlated ordinary failure interval with independent device-liveness evidence; cause remains unresolved. |

## Disposition

No autosuspend policy, gadget configuration, desktop login, browser USB claim,
cable/port configuration or kernel was changed. Existing logs were preserved.
No new physical or remote test is claimed. Resolving the ordinary-use case
requires a correlated failure interval that distinguishes live Ubuntu with a
lost USB path from a stopped handset; that evidence is absent in this bounded
existing-log review.

See [the earlier USB sleep validation](VALIDATION.md#kernel55-usb-sleep-ownership-and-transport-recovery)
for the separately recorded kernel54/55 observations and their limitations.
