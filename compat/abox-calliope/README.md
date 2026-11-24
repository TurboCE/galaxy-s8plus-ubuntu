# SM-G955N Calliope bring-up

This out-of-tree Linux 6.18 test uses the audio device's existing Exynos
System MMU domain. It validates the firmware files, stages the vendor DRAM
and IVA images at their fixed addresses, checks the translations, and
releases the mappings. The stage uses firmware from the handset's own
read-only SYSTEM partition. Use the provisioning script with `--with-dsm`
to include the six additional files listed by Samsung's Exynos8895 DT.

Build against the matching running kernel with the Makefile in this
directory. A successful one-shot stage prints its receipt and returns
`ECANCELED` from module initialization so that the module does not remain
loaded.

The explicit `try_boot=1` diagnostic requires idle native playback and
capture. It loads the SRAM image, asserts the firmware's DRAM request,
starts CA7, and checks the vendor SRAM mailbox for BOOT_DONE or a fault.
After BOOT_DONE it can send the system RESUME request and check whether
firmware clears the TX acknowledgment. It shuts down CA7 before reclaiming
its buffers. An unconfirmed shutdown retains the mappings until reboot.

The boot option exercises the Samsung nonsecure-GIC handoff available on
the tested silicon revision. A complete IRQ handler, audio stream and DSM
parameter IPC, and the secure-GIC path are outstanding. The module is a
diagnostic with no boot-time service or automatic loading.
