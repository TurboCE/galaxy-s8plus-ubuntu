/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <dlfcn.h>
#include <stdbool.h>
#include <stddef.h>
#include <hardware/gps.h>
#include <pthread.h>
#include <signal.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static volatile sig_atomic_t interrupted;
static _Atomic unsigned nmea_count, fixes, satellite_reports;
static _Atomic unsigned engine_status, assisted_location_requests;

struct G955NGpsCallbacks {
    GpsCallbacks standard;
    void (*request_location)(bool independent);
};

_Static_assert(offsetof(struct G955NGpsCallbacks, request_location) == 96,
               "Unexpected Android 9 AArch64 GPS callback layout");

static void on_signal(int sig) {
    (void)sig;
    interrupted = 1;
}

static void on_location(GpsLocation *location) {
    if (location && location->size >= sizeof(*location) &&
        (location->flags & GPS_LOCATION_HAS_LAT_LONG))
        ++fixes;
}

static void on_status(GpsStatus *status) {
    if (status && status->size >= sizeof(*status))
        engine_status = status->status;
}

static void on_legacy_sv(GpsSvStatus *report) {
    if (report && report->size >= sizeof(*report) && report->num_svs > 0)
        ++satellite_reports;
}

static void on_sv(GnssSvStatus *report) {
    if (report && report->size >= sizeof(*report) && report->num_svs > 0)
        ++satellite_reports;
}

static void on_nmea(GpsUtcTime stamp, const char *nmea, int length) {
    (void)stamp;
    if (nmea && length > 8 && length <= 1024 && nmea[0] == '$')
        ++nmea_count;
}

static void on_capabilities(uint32_t capability) { (void)capability; }
static void on_system_info(const GnssSystemInfo *info) { (void)info; }
static void on_wake(void) {}
static void on_time_request(void) {}
static void on_location_request(bool independent) {
    (void)independent;
    ++assisted_location_requests;
}

struct thread_start {
    void (*run)(void *);
    void *data;
};

static void *thread_main(void *raw) {
    struct thread_start start = *(struct thread_start *)raw;
    free(raw);
    start.run(start.data);
    return NULL;
}

static pthread_t on_thread(const char *name, void (*fn)(void *), void *arg) {
    (void)name;
    if (!fn)
        return 0;
    struct thread_start *start = malloc(sizeof(*start));
    if (!start)
        return 0;
    *start = (struct thread_start){fn, arg};
    pthread_t thread;
    if (pthread_create(&thread, NULL, thread_main, start)) {
        free(start);
        return 0;
    }
    return thread;
}

static struct G955NGpsCallbacks callbacks = {
    .standard = {
        .size = sizeof(struct G955NGpsCallbacks),
        .location_cb = on_location,
        .status_cb = on_status,
        .sv_status_cb = on_legacy_sv,
        .nmea_cb = on_nmea,
        .set_capabilities_cb = on_capabilities,
        .acquire_wakelock_cb = on_wake,
        .release_wakelock_cb = on_wake,
        .create_thread_cb = on_thread,
        .request_utc_time_cb = on_time_request,
        .set_system_info_cb = on_system_info,
        .gnss_sv_status_cb = on_sv,
    },
    .request_location = on_location_request,
};

int main(int argc, char **argv) {
    if (argc != 3 || strcmp(argv[1], "--test-standalone")) {
        fprintf(stderr, "Usage: %s --test-standalone SECONDS (1-90)\n", argv[0]);
        return 2;
    }
    char *end;
    long seconds = strtol(argv[2], &end, 10);
    if (end == argv[2] || *end || seconds < 1 || seconds > 90)
        return 2;
    signal(SIGTERM, on_signal);
    signal(SIGINT, on_signal);
    setvbuf(stdout, NULL, _IOLBF, 0);
    void *hal = dlopen("/vendor/lib64/hw/gps.default.so", RTLD_NOW | RTLD_LOCAL);
    if (!hal) {
        fprintf(stderr, "GNSS HAL loading failed: %s\n", dlerror());
        return 2;
    }

    hw_module_t *module = dlsym(hal, HAL_MODULE_INFO_SYM_AS_STR);
    if (!module || module->tag != HARDWARE_MODULE_TAG || !module->id ||
        strcmp(module->id, GPS_HARDWARE_MODULE_ID) || !module->methods ||
        !module->methods->open) {
        fprintf(stderr, "GNSS HAL metadata mismatch\n");
        return 2;
    }
    hw_device_t *dev = NULL;
    int rc = module->methods->open(module, GPS_HARDWARE_MODULE_ID, &dev);
    printf("GPS module open result=%d\n", rc);
    if (rc || !dev || dev->tag != HARDWARE_DEVICE_TAG)
        return 2;
    struct gps_device_t *gps = (struct gps_device_t *)dev;
    const GpsInterface *api = gps->get_gps_interface ? gps->get_gps_interface(gps) : NULL;
    if (!api || api->size < sizeof(*api) || !api->init || !api->start ||
        !api->stop || !api->cleanup || !api->set_position_mode)
        return 2;

    rc = api->init(&callbacks.standard);
    printf("GPS HAL initialize result=%d\n", rc);
    if (rc)
        return 2;
    if (rc || interrupted)
        goto cleanup;
    rc = api->set_position_mode(GPS_POSITION_MODE_STANDALONE,
            GPS_POSITION_RECURRENCE_PERIODIC, 1000, 0, 0);
    printf("GPS standalone mode result=%d\n", rc);
    if (rc || interrupted)
        goto cleanup;
    rc = api->start();
    printf("GPS start result=%d\n", rc);
    if (rc)
        goto cleanup;
    for (long i = 0; i < seconds && !interrupted; ++i)
        sleep(1);
    rc = api->stop();
    printf("GPS stop result=%d\n", rc);
cleanup:
    api->cleanup();
    if (dev->close)
        dev->close(dev);
    printf("GPS status=%u NMEA records=%u location callbacks=%u satellite reports=%u assisted location requests=%u\n",
           engine_status, nmea_count, fixes, satellite_reports, assisted_location_requests);
    return rc ? 2 : nmea_count ? 0 : 1;
}
