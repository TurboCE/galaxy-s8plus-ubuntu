/* Minimal Android 9 property-service v2, for an explicitly isolated bring-up
 * namespace. Uses real Bionic shared property areas and futex notifications.
 * No Android init, HAL autostart, synthetic ready state or vendor writes.
 * Protocol/API reference: pinned aosp-bionic.git sys/_system_properties.h and
 * bionic/system_property_set.cpp. This is diagnostic scaffolding, not a full
 * Android property permission/type-policy implementation.
 */
#include <stddef.h>
#include <stdint.h>

extern int open(const char *, int, ...), close(int), unlink(const char *), access(const char *, int);
extern long read(int, void *, size_t), write(int, const void *, size_t), readlink(const char *, char *, size_t);
extern int fflush(void *);
extern int printf(const char *, ...), puts(const char *), strcmp(const char *, const char *), strncmp(const char *, const char *, size_t);
extern char *strchr(const char *, int), *strstr(const char *, const char *), *getenv(const char *);
extern size_t strlen(const char *);
extern void *malloc(size_t), *memset(void *, int, size_t);
extern void free(void *);
extern unsigned int getuid(void);
extern int getpid(void);
extern int *__errno(void), fork(void), execv(const char *, char *const []), kill(int, int), waitpid(int, int *, int);
extern int setenv(const char *, const char *, int);
extern void _exit(int);
typedef void (*signal_handler)(int);
extern signal_handler signal(int, signal_handler);
struct runtime_time { long sec, nsec; };
extern int clock_gettime(int, struct runtime_time *), nanosleep(const struct runtime_time *, struct runtime_time *);
struct runtime_pollfd { int fd; short events, revents; };
extern int poll(struct runtime_pollfd *, unsigned int, int);
struct runtime_sockaddr_un { unsigned short family; char path[108]; };
struct runtime_ucred { int pid; unsigned int uid, gid; };
struct runtime_timeval { long sec, usec; };
extern int socket(int, int, int), bind(int, const void *, unsigned int), listen(int, int), accept4(int, void *, void *, int);
extern int chmod(const char *, unsigned int), getsockopt(int, int, int, void *, unsigned int *), setsockopt(int, int, int, const void *, unsigned int);
typedef struct prop_info prop_info;
extern int __system_property_area_init(void), __system_property_add(const char *, unsigned int, const char *, unsigned int);
extern int __system_property_update(prop_info *, const char *, unsigned int), __system_property_get(const char *, char *);
extern const prop_info *__system_property_find(const char *);
extern uint32_t __system_property_area_serial(void);

#define PROP_MSG_SETPROP2 0x00020001u
#define PROP_SUCCESS 0u
#define PROP_ERROR_READ_DATA 0x0008u
#define PROP_ERROR_READ_ONLY_PROPERTY 0x000Bu
#define PROP_ERROR_INVALID_NAME 0x0010u
#define PROP_ERROR_INVALID_VALUE 0x0014u
#define PROP_ERROR_PERMISSION_DENIED 0x0018u
#define PROP_ERROR_INVALID_CMD 0x001Bu
#define PROP_ERROR_SET_FAILED 0x0024u
#define MAX_PROPERTY_NAME 127
#define MAX_PROPERTY_VALUE 91
#define O_CLOEXEC 0x80000
#define SIGTERM 15
#define SIGKILL 9
static volatile int stopping;
static int ready_observed;
static void stop(int signal_number) { (void)signal_number; stopping = 1; }
static void ignore_signal(int signal_number) { (void)signal_number; }

static char *read_text(const char *path, size_t limit) {
    int fd = open(path, O_CLOEXEC);
    if (fd < 0) return NULL;
    char *data = malloc(limit + 1);
    if (!data) { close(fd); return NULL; }
    size_t total = 0;
    while (total < limit) {
        long n = read(fd, data + total, limit - total);
        if (n < 0 && *__errno() == 4) continue;
        if (n < 0) { free(data); close(fd); return NULL; }
        if (!n) break;
        total += (size_t)n;
    }
    char extra;
    long more = read(fd, &extra, 1);
    close(fd);
    if (more != 0) { free(data); return NULL; }
    data[total] = 0;
    return data;
}

static int private_namespace(void) {
    char pid_ns[128] = {0}, mount_ns[128] = {0};
    const char *original_pid = getenv("G955N_PARENT_PID_NS");
    const char *original_mount = getenv("G955N_PARENT_MOUNT_NS");
    if (getuid() || getpid() != 1 || !getenv("G955N_ANDROID_PRIVATE_RUNTIME") ||
        strcmp(getenv("G955N_ANDROID_PRIVATE_RUNTIME"), "1") || !original_pid || !original_mount) return 0;
    long a = readlink("/proc/self/ns/pid", pid_ns, sizeof(pid_ns) - 1);
    long b = readlink("/proc/self/ns/mnt", mount_ns, sizeof(mount_ns) - 1);
    if (a <= 0 || b <= 0 || !strcmp(pid_ns, original_pid) || !strcmp(mount_ns, original_mount)) return 0;
    char *mounts = read_text("/proc/self/mountinfo", 262144);
    if (!mounts) return 0;
    int dev = 0, props = 0, sockets = 0, fresh_proc = 0;
    for (char *line = mounts; line && *line;) {
        char *next = strchr(line, '\n');
        if (next) *next++ = 0;
        if (strstr(line, " /proc ro") && strstr(line, " - proc ")) fresh_proc = 1;
        if (strstr(line, " - tmpfs ")) {
            if (strstr(line, " /dev ")) dev = 1;
            if (strstr(line, " /dev/__properties__ ")) props = 1;
            if (strstr(line, " /dev/socket ")) sockets = 1;
        }
        line = next;
    }
    free(mounts);
    return fresh_proc && (dev || (props && sockets));
}


/* All callers first prove PID1/private tmpfs dev; these are never host paths.
 * Android property areas are originally created 0444. The outer supervisor's
 * intentional umask077 must not make shared read-only data root-only (0400).
 */
static int publish_private_property_read_access(void) {
    return chmod("/dev/__properties__/properties_serial", 0444) ||
           chmod("/dev/__properties__/u:object_r:default_prop:s0", 0444);
}

int android_property_permissions_selftest(void) {
    if (!private_namespace() || __system_property_area_serial() != UINT32_MAX) return 1;
    __system_property_area_init();
    if (__system_property_area_serial() == UINT32_MAX || publish_private_property_read_access()) return 1;
    /* No property values, readiness, socket listener, manager or HAL is seeded. */
    int child = fork();
    if (child < 0) return 1;
    if (!child) {
        extern int setgroups(unsigned long, const unsigned int *), setgid(unsigned int), setuid(unsigned int);
        extern int execl(const char *, const char *, ...);
        const unsigned int groups[] = {1026};
        if (setgroups(1, groups) || setgid(1003) || setuid(1000)) _exit(125);
        execl("/usr/bin/python3", "python3", "-c",
              "import os,stat,json,pathlib; "
              "paths=['/','/android','/data','/run','/dev','/dev/socket','/dev/__properties__',"
              "'/dev/__properties__/property_info','/dev/__properties__/properties_serial',"
              "'/dev/__properties__/u:object_r:default_prop:s0']; "
              "modes={p:oct(stat.S_IMODE(os.stat(p).st_mode)) for p in paths}; "
              "checks={'root':modes['/']=='0o755','properties_dir':modes['/dev/__properties__']=='0o711',"
              "'areas_readonly':all(modes[p]=='0o444' for p in paths[-2:]),"
              "'properties_readable':all(os.access(p,os.R_OK) for p in paths[-3:]),"
              "'exec_access':all(os.access(p,os.X_OK) for p in ['/vendor/bin/hw/android.hardware.graphics.allocator@2.0-service','/system/bin/linker64']),"
              "'std_binder_rw':all(os.access(p,os.R_OK|os.W_OK) for p in ['/dev/null','/dev/hwbinder'])}; "
              "print(json.dumps(dict(uid=os.getuid(),gid=os.getgid(),groups=os.getgroups(),modes=modes,checks=checks,"
              "device_modes={p:dict(mode=oct(stat.S_IMODE(os.stat(p).st_mode)),uid=os.stat(p).st_uid,gid=os.stat(p).st_gid) for p in ['/dev/null','/dev/hwbinder']})),flush=True); "
              "assert all(checks.values()); "
              "payloads={p:len(pathlib.Path(p).read_bytes()[:128]) for p in paths[-3:]}; "
              "print(json.dumps(dict(uid=os.getuid(),gid=os.getgid(),groups=os.getgroups(),modes=modes,read_lengths=payloads,"
              "original_allocator_exec_access=True,hal_executed=False,manager_started=False),sort_keys=True))",
              (char *)0);
        _exit(126);
    }
    int status = 0;
    if (waitpid(child, &status, 0) != child || status != 0) return 1;
    puts("Private property/exec-permissions selftest passed; no manager/HAL/hardware device opened");
    return 0;
}

int android_property_namespace_selftest(void) {
    if (!private_namespace()) return 1;
    if (__system_property_area_serial() != UINT32_MAX) return 1;
    const char *forbidden[] = {"/efs", "/dev/block", "/dev/snd", "/dev/mali0", "/dev/ion", "/dev/fb0", "/proc/1/root/efs"};
    for (unsigned int i = 0; i < sizeof(forbidden) / sizeof(forbidden[0]); i++) {
        if (!access(forbidden[i], 0) || *__errno() != 2) return 1;
    }
    puts("Native Bionic namespace selftest passed: PID1, fresh read-only proc, private PID/mount/dev; no EFS/block/audio/GPU nodes; property area not initialized");
    return 0;
}

static int valid_name(const char *name) {
    size_t n = strlen(name);
    if (!n || n > MAX_PROPERTY_NAME || name[0] == '.' || name[n - 1] == '.' || strstr(name, "..")) return 0;
    for (size_t i = 0; i < n; i++) {
        char c = name[i];
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '.' || c == '_' || c == '-')) return 0;
    }
    return 1;
}
static uint32_t set_property(const char *name, const char *value) {
    if (!valid_name(name)) return PROP_ERROR_INVALID_NAME;
    size_t length = strlen(value);
    if (length > MAX_PROPERTY_VALUE) return PROP_ERROR_INVALID_VALUE;
    const prop_info *existing = __system_property_find(name);
    if (existing && !strncmp(name, "ro.", 3)) return PROP_ERROR_READ_ONLY_PROPERTY;
    int result = existing ? __system_property_update((prop_info *)existing, value, (unsigned int)length)
                          : __system_property_add(name, (unsigned int)strlen(name), value, (unsigned int)length);
    return result ? PROP_ERROR_SET_FAILED : PROP_SUCCESS;
}
static void seed_file(const char *path) {
    char *data = read_text(path, 524288);
    if (!data) { printf("Optional stock property file unavailable: %s\n", path); return; }
    unsigned int imported = 0;
    for (char *line = data; line;) {
        char *next = strchr(line, '\n');
        if (next) *next++ = 0;
        size_t len = strlen(line);
        if (len && line[len - 1] == '\r') line[--len] = 0;
        char *value = strchr(line, '=');
        if (value) {
            *value++ = 0;
            if (!strncmp(line, "ro.", 3) && strcmp(line, "ro.property_service.version") &&
                !__system_property_find(line) && !set_property(line, value)) imported++;
        }
        line = next;
    }
    printf("Imported %u read-only stock properties from %s\n", imported, path);
    free(data);
}
static int receive_all(int fd, void *buffer, size_t size) {
    size_t total = 0;
    while (total < size) {
        long count = read(fd, (char *)buffer + total, size - total);
        if (count < 0 && *__errno() == 4 && !stopping) continue;
        if (count <= 0) return 0;
        total += (size_t)count;
    }
    return 1;
}
static uint32_t client_request(int fd, int manager_pid) {
    struct runtime_ucred peer = {0};
    unsigned int peer_size = sizeof(peer);
    struct runtime_timeval timeout = {2, 0};
    if (setsockopt(fd, 1, 20, &timeout, sizeof(timeout))) return PROP_ERROR_READ_DATA;
    if (getsockopt(fd, 1, 17, &peer, &peer_size) || peer_size != sizeof(peer) || peer.uid) return PROP_ERROR_PERMISSION_DENIED;
    uint32_t command = 0, name_size = 0, value_size = 0;
    char name[MAX_PROPERTY_NAME + 1] = {0}, value[MAX_PROPERTY_VALUE + 1] = {0};
    if (!receive_all(fd, &command, sizeof(command))) return PROP_ERROR_READ_DATA;
    if (command != PROP_MSG_SETPROP2) return PROP_ERROR_INVALID_CMD;
    if (!receive_all(fd, &name_size, sizeof(name_size)) || !name_size || name_size > MAX_PROPERTY_NAME ||
        !receive_all(fd, name, name_size) || !receive_all(fd, &value_size, sizeof(value_size)) ||
        value_size > MAX_PROPERTY_VALUE || !receive_all(fd, value, value_size)) return PROP_ERROR_READ_DATA;
    if (strlen(name) != name_size || strlen(value) != value_size) return PROP_ERROR_INVALID_VALUE;
    /* Only the actual supervised hwservicemanager may publish readiness. */
    if (peer.pid != manager_pid || strcmp(name, "hwservicemanager.ready") ||
        (strcmp(value, "true") && strcmp(value, "false"))) {
        printf("Rejected property request: pid=%d name=%s\n", peer.pid, name);
        return PROP_ERROR_PERMISSION_DENIED;
    }
    uint32_t result = set_property(name, value);
    char actual[92] = {0};
    __system_property_get(name, actual);
    if (!result && strcmp(actual, value)) result = PROP_ERROR_SET_FAILED;
    if (!result && !strcmp(value, "true")) ready_observed = 1;
    printf("Real hwservicemanager readiness request committed: success=%s peer_pid=%d supervised_pid=%d serial=%u\n", result ? "no" : "yes", peer.pid, manager_pid, __system_property_area_serial());
    fflush(NULL);
    return result;
}

int android_property_serve(int argc, char **argv) {
    if (argc != 4 || strcmp(argv[2], "/system/bin/hwservicemanager") || !private_namespace()) {
        puts("Requires an explicit private tmpfs /dev mount namespace, root, and stock hwservicemanager path");
        return 2;
    }
    unsigned int duration = 0;
    for (const char *p = argv[3]; *p; p++) {
        if (*p < '0' || *p > '9' || duration > 300) return 2;
        duration = duration * 10 + (unsigned int)(*p - '0');
    }
    if (!duration || duration > 300) return 2;
    int initialized = __system_property_area_init();
    printf("Real Bionic property area serial after init: %u\n", __system_property_area_serial());
    if (__system_property_area_serial() == UINT32_MAX) {
        puts("Bionic property area initialization failed");
        return 1;
    }
    if (initialized) puts("Property area exists with failed security-label setup; namespace is diagnostic only");
    if (publish_private_property_read_access()) {
        puts("Private read-only property area permissions failed");
        return 1;
    }
    seed_file("/system/build.prop");
    seed_file("/vendor/build.prop");
    if (set_property("ro.property_service.version", "2")) return 1;
    char version[92] = {0};
    if (__system_property_get("ro.property_service.version", version) != 1 || strcmp(version, "2")) return 1;
    /* No hwservicemanager.ready value is seeded. */
    struct runtime_sockaddr_un address = {.family = 1, .path = "/dev/socket/property_service"};
    int listener = socket(1, 1 | O_CLOEXEC, 0);
    if (listener < 0) return 1;
    if (bind(listener, &address, sizeof(address)) || chmod(address.path, 0600) || listen(listener, 8)) {
        close(listener);
        puts("Property-service socket initialization failed");
        return 1;
    }
    signal(13, ignore_signal);  /* A disconnected property client must not orphan the child. */
    signal(SIGTERM, stop);
    signal(2, stop);
    int manager = fork();
    if (manager < 0) { close(listener); unlink(address.path); return 1; }
    if (!manager) {
        close(listener);
        setenv("LD_LIBRARY_PATH", "/system/lib64:/vendor/lib64", 1);
        setenv("ANDROID_ROOT", "/system", 1);
        setenv("ANDROID_DATA", "/data", 1);
        char *args[] = {argv[2], NULL};
        execv(args[0], args);
        _exit(127);
    }
    printf("Property-service namespace process running, supervised manager pid=%d\n", manager);
    fflush(NULL);
    struct runtime_time start, now;
    if (clock_gettime(1, &start)) stopping = 1;
    int result = 0, reaped = 0;
    while (!stopping) {
        int status = 0;
        if (waitpid(manager, &status, 1) == manager) {
            printf("hwservicemanager exited: raw_status=%d\n", status);
            reaped = 1; result = 1; break;
        }
        if (clock_gettime(1, &now) || (now.sec - start.sec) + (now.nsec - start.nsec) / 1e9 >= duration) break;
        struct runtime_pollfd event = {.fd = listener, .events = 1, .revents = 0};
        int count = poll(&event, 1, 200);
        if (count < 0 && *__errno() == 4) continue;
        if (count < 0) { result = 1; break; }
        if (count > 0 && (event.revents & 1)) {
            int client = accept4(listener, NULL, NULL, O_CLOEXEC);
            if (client >= 0) {
                uint32_t reply = client_request(client, manager);
                if (write(client, &reply, sizeof(reply)) != (long)sizeof(reply)) result = 1;
                close(client);
            }
        }
    }
    close(listener);
    unlink(address.path);
    if (!reaped) {
        kill(manager, SIGTERM);
        struct runtime_time delay = {0, 100000000};
        for (int attempt = 0; attempt < 10; attempt++) {
            if (waitpid(manager, NULL, 1) == manager) { reaped = 1; break; }
            nanosleep(&delay, NULL);
        }
        if (!reaped) { kill(manager, SIGKILL); waitpid(manager, NULL, 0); }
    }
    /* Publish shutdown from the actual supervised process state, never readiness. */
    if (__system_property_find("hwservicemanager.ready")) set_property("hwservicemanager.ready", "false");
    if (!ready_observed) { puts("hwservicemanager never published verified readiness"); result = 1; }
    puts("Supervised Android property-service trial finished");
    return result;
}
