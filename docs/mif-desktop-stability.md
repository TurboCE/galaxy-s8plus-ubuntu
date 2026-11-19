# Native GNOME MIF power-transition investigation

## Actual comparison

Kernel30 uses the corrected GCC7 builder. Its actual linked builtin archive
is legacy-LZ4, and its config/source patch hashes and external ramdisk/DTBH
match28. It boots Ubuntu, authenticates through real GDM PAM, and passes three
ordinary Mali/Exynos/private-EGL composition/popup tests without swrast.

Without a diagnostic floor, nine DPMS off/on cycles completed; the tenth off
operation stopped the transport. The owner confirmed **automatic** reboot into
GDM. Matching retained30 logs show a kernel paging exception while calling
request end_io from blk_finish_request, in a UFS/SCSI completion stack. The
indirect target points into request-associated data rather than kernel text.
Relocation is verified against the matching Image/System.map and recorded boot
offset. This identifies a corruption symptom; it does not identify the writer,
prove a UFS hardware defect, or justify ignoring/replacing the callback.

Previously, restored28 passed100 actual DPMS off/on cycles under a bounded
421000kHz PM_QOS_BUS_THROUGHPUT vote; no-floor28 failed its extended trial. The
same bounded condition also passed100 cycles on30. Actual runtime panel states,
DPMS state, boot identity and taint are checked per cycle. The temporary vote
closes on completion. min_freq remains208000kHz; no OPP or calibration is edited.
A failed direct min_freq write returned EACCES and changed nothing.

## Explicit mitigation candidate

compat/native-gnome/hold-mif-qos.py is an opt-in, model/device-checked holder for
the tested421000kHz operating point using the supported kernel QoS character
device. The matching systemd unit waits for READY after kernel acknowledgement
and can start before GDM. A process lease prevents duplicate holders; ordinary
termination and SIGKILL release the fd-owned request. It neither edits driver
minima nor caps higher performance frequencies. The unit was installed and started after that bounded comparison; ten further five-second off/on cycles passed, including measured421000kHz
off samples. Its display-manager requirement is now enabled; reboot persistence
is under test. An actual lifecycle test on30 confirmed normal service
stop removes one QoS request, a separately launched holder adds exactly one,
SIGKILL returns to the baseline request count, and restarting the service adds
exactly one again. Driver min_freq remains208000. Merely running without
--hold does not change state.

This policy avoids the lowest memory-bus points while active. It may increase
idle power. It is a reversible stability mitigation, **not** a proven repair of
the initiating corruption, deep-suspend qualification, or completion of the
owner's CPU power-saving requirement. CPU idle/governors are not disabled.
Further controlled long screen-off and repeated transition tests, callback
lifetime inspection and sensor/audio/modem/rotation work remain required.

Private evidence is under artifacts/ondemand-safety, including kernel30-session,
kernel30-power100, kernel30-failed-last-kmsg, kernel30-failed-decoded and
mif-qos30-power100 records. Raw logs/addresses remain private.


## Later bounded results and holder CPU behavior

30 with the installed policy completed three60-second off/five-second on cycles
with measured offMIF421000kHz, real panel suspended/active, same boot and taint0.
Long-on variants encountered policy-driven DPMS off while the machine remained
responsive; Mutter idle reset alone did not prevent the already-locked screen's
blank policy. They are recorded as state-assertion failures, not hardware hangs
or long-on passes. The later short-on test measures recovery before automatic
reblanking and does not override authentication.

31 adds only reviewed ABOX fixes17..20 to30's source selection and boots with
matched config/ramdisk/DTBH. Three ordinary Mali GNOME tests pass and the owner
confirmed touch password/desktop entry. The holder now blocks in sigwait rather
than polling: actual /proc wait state is do_sigtimedwait and consumed CPU ticks
were zero over a five-second observation. Actual normal termination exits0 and
releases its vote; SIGKILL releases it too. A second temporary guard vote kept
the tested floor throughout that lifecycle experiment and was released after
the service was ready again. GDM was deliberately restarted for this test.

A MIF QoS floor also affects coupled INT constraints and whether aggregate QoS
changes reach the notifier path. The pinned table maps421000MIF to178000INT,
versus107000INT for the lowest MIF points. Therefore these bounded passes do
not isolate DRAM speed alone as the cause or identify a corrupting writer.
