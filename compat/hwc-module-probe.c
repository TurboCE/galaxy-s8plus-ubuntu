/* G955N own-device HAL metadata/vtable probe; no vendor code is redistributed.
 * Default mode only loads module metadata. --open-hwc2 can initialize hardware
 * and must be coordinated with the active display owner before use.
 */
#include <hardware/hardware.h>
#include <hardware/hwcomposer2.h>
#include <hybris/common/dlfcn.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/utsname.h>
#include <stdatomic.h>
#include <inttypes.h>
#include <time.h>


struct hotplug_state {
    atomic_int connected;
    atomic_uint_fast64_t display;
};
static struct hotplug_state hotplug;

static void on_hotplug(hwc2_callback_data_t data, hwc2_display_t display,
                       int32_t connection) {
    struct hotplug_state *state = data;
    if (connection == HWC2_CONNECTION_CONNECTED) {
        atomic_store_explicit(&state->display, display, memory_order_relaxed);
        atomic_store_explicit(&state->connected, 1, memory_order_release);
    } else if (atomic_load_explicit(&state->display, memory_order_relaxed) == display) {
        atomic_store_explicit(&state->connected, 0, memory_order_release);
    }
}
static void on_refresh(hwc2_callback_data_t data, hwc2_display_t display) {
    (void)data;
    (void)display;
}
static void on_vsync(hwc2_callback_data_t data, hwc2_display_t display,
                     int64_t timestamp) {
    (void)data;
    (void)display;
    (void)timestamp;
}

static int display_metadata(hwc2_device_t *device) {
    /* HWC2 defines getFunction as an erased function pointer. Copy its
     * representation into each exact API type; no call uses the erased type. */
#define LOAD_FUNCTION(type, name, descriptor) \
    type name; \
    do { \
        hwc2_function_pointer_t erased = device->getFunction(device, descriptor); \
        _Static_assert(sizeof(name) == sizeof(erased), "HWC2 function pointer ABI"); \
        memcpy(&name, &erased, sizeof(name)); \
    } while (0)
    LOAD_FUNCTION(HWC2_PFN_REGISTER_CALLBACK, callback, HWC2_FUNCTION_REGISTER_CALLBACK);
    LOAD_FUNCTION(HWC2_PFN_GET_DISPLAY_CONFIGS, configs, HWC2_FUNCTION_GET_DISPLAY_CONFIGS);
    LOAD_FUNCTION(HWC2_PFN_GET_DISPLAY_ATTRIBUTE, attribute, HWC2_FUNCTION_GET_DISPLAY_ATTRIBUTE);
    LOAD_FUNCTION(HWC2_PFN_GET_ACTIVE_CONFIG, active_config, HWC2_FUNCTION_GET_ACTIVE_CONFIG);
#undef LOAD_FUNCTION
    if (!callback || !configs || !attribute || !active_config) return 1;
    int32_t error = callback(device, HWC2_CALLBACK_REFRESH, &hotplug,
                            (hwc2_function_pointer_t)on_refresh);
    if (!error) error = callback(device, HWC2_CALLBACK_VSYNC, &hotplug,
                                (hwc2_function_pointer_t)on_vsync);
    if (!error) error = callback(device, HWC2_CALLBACK_HOTPLUG, &hotplug,
                                (hwc2_function_pointer_t)on_hotplug);
    if (error) {
        fprintf(stderr, "Callback registration failed: %d\n", error);
        return 1;
    }
    struct timespec start, now, pause = { .tv_sec = 0, .tv_nsec = 10000000 };
    if (clock_gettime(CLOCK_MONOTONIC, &start)) return 1;
    while (!atomic_load_explicit(&hotplug.connected, memory_order_acquire)) {
        if (clock_gettime(CLOCK_MONOTONIC, &now)) return 1;
        if ((now.tv_sec - start.tv_sec) + (now.tv_nsec - start.tv_nsec) / 1e9 >= 5.0) {
            fputs("No connected display hotplug within five seconds\n", stderr);
            return 1;
        }
        nanosleep(&pause, NULL);
    }
    hwc2_display_t display = atomic_load_explicit(&hotplug.display, memory_order_relaxed);
    uint32_t count = 0;
    error = configs(device, display, &count, NULL);
    if (error || !count || count > 128) {
        fprintf(stderr, "Display config count failed: error=%d count=%u\n", error, count);
        return 1;
    }
    hwc2_config_t ids[128] = {0}, active = 0;
    uint32_t capacity = count;
    error = configs(device, display, &capacity, ids);
    if (error || !capacity || capacity > count) return 1;
    error = active_config(device, display, &active);
    if (error) return 1;
    printf("hotplug_display=%" PRIu64 " configs=%u active=%u\n", display, capacity, active);
    for (uint32_t i = 0; i < capacity; i++) {
        int32_t width = 0, height = 0, period = 0;
        error = attribute(device, display, ids[i], HWC2_ATTRIBUTE_WIDTH, &width);
        if (!error) error = attribute(device, display, ids[i], HWC2_ATTRIBUTE_HEIGHT, &height);
        if (!error) error = attribute(device, display, ids[i], HWC2_ATTRIBUTE_VSYNC_PERIOD, &period);
        if (error || width <= 0 || height <= 0 || width > 16384 || height > 16384 || period <= 0) {
            fprintf(stderr, "Config %u query failed: %d\n", ids[i], error);
            return 1;
        }
        printf("config=%u width=%d height=%d vsync_ns=%d\n", ids[i], width, height, period);
    }
    return 0;
}

static int identity_ok(void) {
    struct utsname name;
    char model[256] = {0};
    FILE *file = fopen("/proc/device-tree/model", "r");
    if (!file) return 0;
    size_t bytes = fread(model, 1, sizeof(model) - 1, file);
    fclose(file);
    return bytes && strstr(model, "SM-G955N") && !uname(&name) &&
           strstr(name.release, "g955n-ubuntu");
}

static int metadata(const char *id, const hw_module_t **module, const char *fallback) {
    int error = hw_get_module(id, module);
    if ((error || !*module) && fallback) {
        /* Android init normally supplies ro.hardware.* properties. This
         * process-local fallback uses the observed own-device module path;
         * it does not write properties or alter the global loader paths. */
        void *handle = hybris_dlopen(fallback, RTLD_NOW | RTLD_LOCAL);
        if (!handle) {
            fprintf(stderr, "%s direct module load failed: %s\n", id, hybris_dlerror());
            return 1;
        }
        *module = hybris_dlsym(handle, HAL_MODULE_INFO_SYM_AS_STR);
        if (*module) {
            ((hw_module_t *)*module)->dso = handle;
            error = 0;
            printf("module_source=%s\n", fallback);
        }
    }
    if (error || !*module) {
        fprintf(stderr, "%s module load failed: %d\n", id, error);
        return 1;
    }
    const hw_module_t *m = *module;
    if (m->tag != HARDWARE_MODULE_TAG || !m->id || strcmp(m->id, id)) {
        fprintf(stderr, "%s module header mismatch\n", id);
        return 1;
    }
    printf("module=%s name=%s module_api=0x%04x hal_api=0x%04x open=%s\n",
           m->id, m->name ? m->name : "(none)", (unsigned)m->module_api_version,
           (unsigned)m->hal_api_version,
           m->methods && m->methods->open ? "available" : "missing");
    return 0;
}

int main(int argc, char **argv) {
    int open_hwc2 = argc == 2 && !strcmp(argv[1], "--open-hwc2");
    if (argc > 2 || (argc == 2 && strcmp(argv[1], "--metadata") && !open_hwc2)) {
        fprintf(stderr, "Usage: %s [--metadata | --open-hwc2]\n", argv[0]);
        return 2;
    }
    if (!identity_ok()) {
        fputs("Requires native SM-G955N Ubuntu\n", stderr);
        return 2;
    }
    setvbuf(stdout, NULL, _IOLBF, 0);
    const hw_module_t *gralloc = NULL, *composer = NULL;
    int failed = metadata("gralloc", &gralloc, NULL);
    failed |= metadata(HWC_HARDWARE_MODULE_ID, &composer, "/vendor/lib64/hw/hwcomposer.exynos5.so");
    if (failed) return 1;
    if (!open_hwc2) {
        puts("Metadata only: no device open, layer, power, buffer or present calls");
        return 0;
    }
    if (!composer->methods || !composer->methods->open) return 1;
    hw_device_t *raw = NULL;
    int error = composer->methods->open(composer, HWC_HARDWARE_COMPOSER, &raw);
    if (error || !raw) {
        fprintf(stderr, "composer open failed: %d\n", error);
        return 1;
    }
    printf("device_api=0x%08x\n", raw->version);
    int result = 1;
    if ((raw->version & HARDWARE_API_VERSION_2_MAJ_MIN_MASK) !=
        (HWC_DEVICE_API_VERSION_2_0 & HARDWARE_API_VERSION_2_MAJ_MIN_MASK)) {
        fputs("Not an HWC2.0 device; no HWC2 vtable calls attempted\n", stderr);
        goto close;
    }
    hwc2_device_t *device = (hwc2_device_t *)raw;
    if (!device->getCapabilities || !device->getFunction) goto close;
    uint32_t count = 0;
    device->getCapabilities(device, &count, NULL);
    if (count > 64) goto close;
    int32_t capabilities[64] = {0};
    uint32_t capacity = count;
    if (count) device->getCapabilities(device, &capacity, capabilities);
    if (capacity > count) goto close;
    printf("capabilities=%u", capacity);
    for (uint32_t i = 0; i < capacity; i++) printf(" %d", capabilities[i]);
    putchar('\n');
    const struct { const char *name; int32_t descriptor; } functions[] = {
        {"registerCallback", HWC2_FUNCTION_REGISTER_CALLBACK},
        {"getDisplayConfigs", HWC2_FUNCTION_GET_DISPLAY_CONFIGS},
        {"getActiveConfig", HWC2_FUNCTION_GET_ACTIVE_CONFIG},
        {"getDisplayAttribute", HWC2_FUNCTION_GET_DISPLAY_ATTRIBUTE},
        {"createLayer", HWC2_FUNCTION_CREATE_LAYER},
        {"setClientTarget", HWC2_FUNCTION_SET_CLIENT_TARGET},
        {"validateDisplay", HWC2_FUNCTION_VALIDATE_DISPLAY},
        {"acceptDisplayChanges", HWC2_FUNCTION_ACCEPT_DISPLAY_CHANGES},
        {"presentDisplay", HWC2_FUNCTION_PRESENT_DISPLAY},
        {"getReleaseFences", HWC2_FUNCTION_GET_RELEASE_FENCES},
        {"setPowerMode", HWC2_FUNCTION_SET_POWER_MODE},
        {"setVsyncEnabled", HWC2_FUNCTION_SET_VSYNC_ENABLED},
    };
    result = 0;
    for (size_t i = 0; i < sizeof(functions) / sizeof(functions[0]); i++) {
        int present = device->getFunction(device, functions[i].descriptor) != NULL;
        printf("function=%s available=%s\n", functions[i].name, present ? "yes" : "no");
        if (!present) result = 1;
    }
    if (!result) result = display_metadata(device);
    puts("No layer, power, buffer or present calls; callback/config inspection only");
close:
    if (!raw->close || raw->close(raw)) {
        fputs("Device close failed or unavailable\n", stderr);
        return 1;
    }
    return result;
}
