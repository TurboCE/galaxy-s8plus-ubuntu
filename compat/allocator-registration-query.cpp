/* Exact-instance Android 9 HWBinder registration query. No allocation, service
 * activation, passthrough manager, debug() or graphics/audio device operation.
 * Builds against public generated HIDL headers and the owner's stock libraries.
 */
#include <android/hidl/manager/1.0/IServiceManager.h>
#include <hidl/ServiceManagement.h>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <initializer_list>
#include <sys/prctl.h>
#include <sys/statvfs.h>
#include <sys/system_properties.h>
#include <unistd.h>

static constexpr const char *descriptor = "android.hardware.graphics.allocator@2.0::IAllocator";
static constexpr const char *fqinstance = "android.hardware.graphics.allocator@2.0::IAllocator/default";
static constexpr const char *allocator = "/vendor/bin/hw/android.hardware.graphics.allocator@2.0-service";

static bool contains(const char *path, const char *value) {
    char text[1024] = {};
    const int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) return false;
    const ssize_t n = read(fd, text, sizeof(text) - 1);
    close(fd);
    return n > 0 && strstr(text, value);
}

static bool readonly(const char *path) {
    struct statvfs fs;
    return statvfs(path, &fs) == 0 && (fs.f_flag & ST_RDONLY);
}

static bool namespace_guard(int pid) {
    const char *marker = getenv("G955N_ANDROID_PRIVATE_RUNTIME");
    const char *parent_pid = getenv("G955N_PARENT_PID_NS");
    const char *parent_mount = getenv("G955N_PARENT_MOUNT_NS");
    if (!marker || strcmp(marker, "1") || !parent_pid || !parent_mount) return false;
    char ns[128] = {};
    ssize_t n = readlink("/proc/self/ns/pid", ns, sizeof(ns) - 1);
    if (n < 0 || !strcmp(ns, parent_pid)) return false;
    memset(ns, 0, sizeof(ns));
    n = readlink("/proc/self/ns/mnt", ns, sizeof(ns) - 1);
    if (n < 0 || !strcmp(ns, parent_mount)) return false;
    if (!readonly("/proc") || !readonly("/sys") || prctl(PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0) != 1) return false;
    // Linux capability indices: SYS_MODULE, RAWIO, ADMIN, BOOT, MKNOD.
    for (int cap : {16, 17, 21, 22, 27})
        if (prctl(PR_CAPBSET_READ, cap, 0, 0, 0) != 0) return false;
    for (const char *path : {"/efs", "/proc/1/root/efs", "/dev/block", "/dev/snd", "/dev/ion",
                            "/dev/mali0", "/dev/fb0", "/dev/graphics/fb0", "/dev/sw_sync"})
        if (access(path, F_OK) == 0 || errno != ENOENT) return false;
    char property[PROP_VALUE_MAX] = {};
    if (__system_property_get("hwservicemanager.ready", property) <= 0 || strcmp(property, "true")) return false;
    if (pid == 0) return true; // list-only absence check; never get an interface.
    char path[64], command[512] = {};
    snprintf(path, sizeof(path), "/proc/%d/cmdline", pid);
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) return false;
    const ssize_t count = read(fd, command, sizeof(command) - 1);
    close(fd);
    return count > 0 && !strcmp(command, allocator);
}

int main(int argc, char **argv) {
    if ((!contains("/proc/device-tree/model", "SM-G955N") &&
         !contains("/sys/firmware/devicetree/base/model", "SM-G955N")) ||
        !contains("/proc/sys/kernel/osrelease", "g955n-ubuntu")) return 2;
    if (argc == 2 && !strcmp(argv[1], "--abi-selftest")) {
        // Exercise real Bionic TLS, libc++, and HIDL string/vector ownership.
        // No service-manager getter or Binder operation is reached in this mode.
        android::hardware::hidl_vec<android::hardware::hidl_string> values;
        values.resize(1);
        values[0] = fqinstance;
        if (close(-1) != -1 || errno != EBADF || strcmp(values[0].c_str(), fqinstance)) return 1;
        printf("Bionic C++/HIDL ABI selftest passed: pid=%d values=%zu no_service_query=yes\n", getpid(), values.size());
        return 0;
    }
    const bool absence_only = argc == 2 && !strcmp(argv[1], "--expect-allocator-absent");
    if (!absence_only && (argc != 3 || strcmp(argv[1], "--query-allocator"))) return 2;
    char *end = nullptr;
    errno = 0;
    const long expected = absence_only ? 0 : strtol(argv[2], &end, 10);
    if (errno || (!absence_only && (!end || *end || expected <= 1 || expected > 2147483647)) ||
        !namespace_guard(static_cast<int>(expected))) {
        puts("allocator_registration=refused guard_failed=yes");
        return 2;
    }
    alarm(5); // Default SIGALRM: bound all synchronous manager/base transactions.
    auto manager = android::hardware::defaultServiceManager();
    if (!manager) return 5;
    bool listed = false;
    auto list = manager->list([&](const auto &names) {
        for (const auto &name : names)
            if (!strcmp(name.c_str(), fqinstance)) listed = true;
    });
    if (!list.isOk()) return 5;
    if (!listed) {
        puts("allocator_registration=absent");
        return absence_only ? 0 : 3;
    }
    if (absence_only) {
        puts("allocator_registration=unexpected_existing");
        return 4;
    }
    // Unlike a service's getDebugInfo(), the manager's debugDump PID is the
    // actual registration caller PID recorded from Binder credentials. Stock
    // user-build IBase::getDebugInfo is allowed to return NO_PID (-1).
    int registration_pid = -1;
    auto dump = manager->debugDump([&](const auto &entries) {
        for (const auto &entry : entries)
            if (!strcmp(entry.interfaceName.c_str(), descriptor) && !strcmp(entry.instanceName.c_str(), "default"))
                registration_pid = entry.pid;
    });
    if (!dump.isOk()) return 5;
    // get only after list reports the exact existing instance. No getService,
    // passthrough fallback, lazy-service wait, ctl write or service-start ACK.
    auto got = manager->get(descriptor, "default");
    if (!got.isOk()) return 5;
    android::sp<android::hidl::base::V1_0::IBase> service = got;
    if (!service || !service->isRemote()) return 5;
    int registered_pid = -1;
    auto info = service->getDebugInfo([&](const auto &value) { registered_pid = value.pid; });
    if (!info.isOk()) return 5;
    const bool match = registration_pid == expected && (registered_pid == expected || registered_pid == -1);
    printf("allocator_registration=%s namespace_pid=%d expected_pid=%ld transport=hwbinder debug_pid=%d pid_source=manager_registration\n",
           match ? "present" : "pid_mismatch", registration_pid, expected, registered_pid);
    return match ? 0 : 4;
}
