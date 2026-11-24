# SM-G955N Calliope bring-up

This out-of-tree Linux 6.18 test uses the audio device's existing Exynos
System MMU domain. It validates the firmware files, stages the vendor DRAM and IVA images at their fixed addresses, checks the translations,
and releases the mappings. It maps the stock VSS address window to
private, zeroed memory for the diagnostic. The modem's memory is
outside that mapping. The stage uses firmware from the handset's own
read-only SYSTEM partition. Use the provisioning script with `--with-dsm`
to include the six additional files listed by Samsung's Exynos8895 DT.

Build against the matching running kernel with the Makefile in this
directory. A successful one-shot stage prints its receipt and returns
`ECANCELED` from module initialization so that the module does not remain
loaded.

The explicit `try_boot=1` diagnostic requires idle native playback and
capture. It loads the SRAM image, asserts the firmware's DRAM request,
starts CA7, and checks the vendor SRAM mailbox for BOOT_DONE or a fault.
Entering the boot test holds the runtime PM reference that powers
the audio IOMMU. With no PCM open, the software mappings alone do not
activate the hardware page-table walker. Boot observation validates
component descriptors in SRAM or DRAM and acknowledges the reports.
An unsupported request ends the diagnostic.
The separate `try_resume=1` option sends system RESUME only after
BOOT_DONE and checks whether firmware clears the TX acknowledgment. It shuts down CA7 before reclaiming
its buffers. An unconfirmed shutdown retains the mappings until reboot.

Use `try_boot=1 try_resume=1 try_dsm_read=1` for the read-only DSM query.
It checks the inherited CA7 boot clock and responds to the boot gear
request with the actual CA7 rate. It reports the number of returned words
and the DSM enable flag. The query runs with both ALSA streams idle and
does not change calibration or start a stream.

The boot option exercises the Samsung nonsecure-GIC handoff available on
the tested silicon revision. A complete IRQ handler, audio stream and DSM
parameter IPC, and the secure-GIC path are outstanding. The module is a
diagnostic with no boot-time service or automatic loading.

On the handset qualification run, powering the audio IOMMU made the CA7
read the correct DRAM data. Starting the stock image with that fix was
followed by a device hang, including with RESUME disabled. Keep the boot
options out of unattended startup. The default staging-only path has
no CA7 start or doorbell write.

The receive-only boot trial left a pstore record reporting a write fault
at 0xa0570000. That address falls inside the stock six MiB VSS window.
With private backing for that window, the handset remained responsive and
Calliope reported two components, sent BOOT_DONE, and acknowledged RESUME.
The DSM query returned 146 words with enable=1 at idle. Playback through
DSM and microphone capture remain unverified.
