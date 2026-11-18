/* Minimal AArch64 Android executable entry using Bionic's public CRT ABI.
 * ABI reference: pinned AOSP bionic libc/arch-common/bionic/crtbegin.c and
 * libc/bionic/libc_init_common.h (Android 9.0.0_r61). No vendor code included.
 * This C-only executable has no constructor/destructor arrays of its own.
 */
#if !defined(__aarch64__)
#error Build this entry only for AArch64
#endif
struct android_structors {
    void (**preinit_array)(void);
    void (**init_array)(void);
    void (**fini_array)(void);
};
extern int main(int, char **, char **);
extern __attribute__((noreturn)) void __libc_init(
    void *, void (*)(void), int (*)(int, char **, char **), const struct android_structors *);
__attribute__((used, visibility("hidden"), noreturn))
void android_cli_start(void *raw_args) {
    const struct android_structors arrays = {0, 0, 0};
    __libc_init(raw_args, 0, main, &arrays);
}
__asm__(".text; .global _start; .type _start,%function; _start: mov x0,sp; b android_cli_start; .size _start, .-_start");
