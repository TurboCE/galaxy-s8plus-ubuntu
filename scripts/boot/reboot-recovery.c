/* SPDX-License-Identifier: MIT
 * Explicit ARM64 recovery reboot helper for a native initramfs without Android
 * reboot tooling. Build-only source: compiling does not contact a device.
 * No libc or partition writes. Linux RESTART2 passes "recovery" to the SoC
 * restart handler. Invoke only after verifying the live target identity.
 */
void _start(void)
{
    register unsigned long arg0 __asm__("x0") = 0xfee1dead;
    register unsigned long arg1 __asm__("x1") = 672274793;
    register unsigned long arg2 __asm__("x2") = 0xa1b2c3d4;
    register const char *arg3 __asm__("x3") = "recovery";
    register unsigned long number __asm__("x8") = 142;
    __asm__ volatile("svc 0" : "+r"(arg0) : "r"(arg1), "r"(arg2),
                     "r"(arg3), "r"(number) : "memory");
    /* Failed reboot: exit with failure rather than executing arbitrary bytes. */
    arg0 = 1;
    number = 93;
    __asm__ volatile("svc 0" : : "r"(arg0), "r"(number) : "memory");
    for (;;) {}
}
