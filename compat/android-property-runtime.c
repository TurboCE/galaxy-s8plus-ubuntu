/* Native Android/Bionic bring-up helper, not Android init.
 * Uses real stock Bionic property APIs; no ready-state fabrication.
 * Minimal declarations avoid accidentally linking glibc ABI/header wrappers.
 */
#include <stddef.h>
#include <stdint.h>

extern int open(const char *, int, ...);
extern long read(int, void *, size_t);
extern long write(int, const void *, size_t);
extern int close(int);
extern unsigned int getuid(void);
extern int getpid(void);
extern int printf(const char *, ...);
extern int puts(const char *);
extern int strcmp(const char *, const char *);
extern char *strstr(const char *, const char *);
extern int *__errno(void);
struct bionic_timespec { long tv_sec; long tv_nsec; };
extern int clock_gettime(int, struct bionic_timespec *);
extern uint32_t __system_property_area_serial(void);
extern int __system_property_get(const char *, char *);
extern int android_property_serve(int, char **);
extern int android_property_namespace_selftest(void);

static int file_contains(const char *path, const char *expected) {
    char buffer[512] = {0};
    int fd = open(path, 0);
    if (fd < 0) return 0;
    long count = read(fd, buffer, sizeof(buffer) - 1);
    close(fd);
    return count > 0 && strstr(buffer, expected) != NULL;
}

int main(int argc, char **argv, char **environment) {
    (void)environment;
    if ((!file_contains("/proc/device-tree/model", "SM-G955N") &&
         !file_contains("/sys/firmware/devicetree/base/model", "SM-G955N")) ||
        !file_contains("/proc/sys/kernel/osrelease", "g955n-ubuntu")) return 2;
    if (argc == 3 && !strcmp(argv[1], "--read-property")) {
        if (strcmp(argv[2], "hwservicemanager.ready") && strcmp(argv[2], "ro.property_service.version")) return 2;
        char value[92] = {0};
        int length = __system_property_get(argv[2], value);
        printf("Real shared property: name=%s value=%s serial=%u\n", argv[2], value, __system_property_area_serial());
        return length > 0 ? 0 : 1;
    }
    if (argc == 2 && !strcmp(argv[1], "--namespace-selftest")) return android_property_namespace_selftest();
    if (argc >= 2 && !strcmp(argv[1], "--serve")) return android_property_serve(argc, argv);
    if (argc != 2 || strcmp(argv[1], "--abi-selftest")) {
        puts("Usage: android-property-runtime --abi-selftest | --namespace-selftest | --serve /system/bin/hwservicemanager SECONDS");
        return 2;
    }
    struct bionic_timespec time;
    if (clock_gettime(1, &time)) return 1;
    int result = close(-1);
    if (result != -1 || *__errno() != 9) return 1;
    printf("Bionic executable ABI/TLS selftest passed: uid=%u pid=%d monotonic=%ld.%09ld\n",
           getuid(), getpid(), time.tv_sec, time.tv_nsec);
    printf("Existing Android property serial: %u (UINT32_MAX means no area)\n",
           __system_property_area_serial());
    return 0;
}
