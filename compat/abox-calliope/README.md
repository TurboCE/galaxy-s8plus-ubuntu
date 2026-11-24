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
activate the hardware page-table walker. Boot observation ends on
unsupported firmware requests. It does not acknowledge those requests.
The separate `try_resume=1` option sends system RESUME only after
BOOT_DONE and checks whether firmware clears the TX acknowledgment. It shuts down CA7 before reclaiming
its buffers. An unconfirmed shutdown retains the mappings until reboot.

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
Calliope reached IPC 1:0xc0 (ABOX_REPORT_COMPONENT in the Samsung ABI).
The diagnostic powered the core off at that request. BOOT_DONE, DSM
playback, and microphone capture remain unverified.
