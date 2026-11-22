/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <dlfcn.h>
#include <errno.h>
#include <math.h>
#include <time.h>
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
static _Atomic bool utc_requested, location_requested;
static bool serving;
static FILE *receipt;

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

static int hex_digit(unsigned char c) {
    if (c >= '0' && c <= '9')
        return c - '0';
    if (c >= 'A' && c <= 'F')
        return c - 'A' + 10;
    if (c >= 'a' && c <= 'f')
        return c - 'a' + 10;
    return -1;
}

static void on_nmea(GpsUtcTime stamp, const char *nmea, int length) {
    (void)stamp;
    if (!nmea || length < 9 || length > 1022 || nmea[0] != '$')
        return;
    while (length > 0 && (nmea[length - 1] == '\r' || nmea[length - 1] == '\n'))
        --length;
    if (length < 9 || nmea[length - 3] != '*')
        return;
    int high = hex_digit(nmea[length - 2]), low = hex_digit(nmea[length - 1]);
    if (high < 0 || low < 0)
        return;
    unsigned checksum = 0;
    for (int i = 1; i < length - 3; ++i) {
        unsigned char c = nmea[i];
        if (c < ' ' || c > '~' || c == '$' || c == '*')
            return;
        checksum ^= c;
    }
    if (checksum != (unsigned)(16 * high + low))
        return;
    ++nmea_count;
    if (!serving)
        return;
    char sentence[1024];
    memcpy(sentence, nmea, length);
    sentence[length] = '\r';
    sentence[length + 1] = '\n';
    /* A sentence fits in PIPE_BUF. A full relay pipe drops that sample. */
    ssize_t size = write(STDOUT_FILENO, sentence, length + 2);
    if (size < 0 && errno == EPIPE)
        interrupted = 1;
}

static void on_capabilities(uint32_t capability) { (void)capability; }
static void on_system_info(const GnssSystemInfo *info) { (void)info; }
static void on_wake(void) {}
static void on_time_request(void) { utc_requested = true; }
static void on_location_request(bool independent) {
    (void)independent;
    ++assisted_location_requests;
    location_requested = true;
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

static int64_t milliseconds(const struct timespec *value) {
    return (int64_t)value->tv_sec * 1000 + value->tv_nsec / 1000000;
}

static void provide_utc(const GpsInterface *gps) {
    if (!getenv("G955N_GNSS_SYNCED_CLOCK") || !gps->inject_time)
        return;
    struct timespec before, utc, after;
    if (clock_gettime(CLOCK_BOOTTIME, &before) || clock_gettime(CLOCK_REALTIME, &utc)
        || clock_gettime(CLOCK_BOOTTIME, &after) || utc.tv_sec < 1704067200)
        return;
    int64_t span = milliseconds(&after) - milliseconds(&before);
    if (span < 0 || span > 100)
        return;
    int result = gps->inject_time(milliseconds(&utc), milliseconds(&before) + span / 2, 1000);
    fprintf(receipt, "GPS UTC injection result=%d\n", result);
}

static void provide_seed(const GpsInterface *gps) {
    const char *path = getenv("G955N_GNSS_SEED");
    if (!path || !gps->inject_location)
        return;
    FILE *input = fopen(path, "r");
    if (!input)
        return;
    double latitude, longitude, accuracy, stamp;
    char extra;
    int fields = fscanf(input, "%lf %lf %lf %lf %c", &latitude, &longitude, &accuracy, &stamp, &extra);
    fclose(input);
    struct timespec now;
    if (fields != 4 || clock_gettime(CLOCK_REALTIME, &now) ||
        !isfinite(latitude) || !isfinite(longitude) || !isfinite(accuracy) || !isfinite(stamp) ||
        latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180 ||
        accuracy < 1 || accuracy > 100000 || stamp <= 0)
        return;
    double age = now.tv_sec + now.tv_nsec / 1e9 - stamp;
    if (age < 0 || age > 300 || accuracy + 100 * age > 100000)
        return;
    int result = gps->inject_location(latitude, longitude, (float)(accuracy + 100 * age));
    fprintf(receipt, "GPS coarse position injection result=%d\n", result);
}

static void xtra_requested(void) {}

static void provide_lto(const GpsInterface *gps) {
    const char *path = getenv("G955N_GNSS_LTO");
    if (!path || !gps->get_extension)
        return;
    const GpsXtraInterface *xtra = gps->get_extension(GPS_XTRA_INTERFACE);
    if (!xtra || xtra->size < sizeof(*xtra) || !xtra->init || !xtra->inject_xtra_data) {
        fprintf(receipt, "GPS XTRA interface unavailable\n");
        return;
    }
    FILE *input = fopen(path, "rb");
    if (!input)
        return;
    const size_t limit = 512 * 1024;
    char *data = malloc(limit + 1);
    if (!data) {
        fclose(input);
        return;
    }
    size_t length = fread(data, 1, limit + 1, input);
    bool valid = !ferror(input) && length > 512 && length <= limit;
    fclose(input);
    if (valid) {
        static GpsXtraCallbacks callbacks = {
            .download_request_cb = xtra_requested, .create_thread_cb = on_thread,
        };
        int result = xtra->init(&callbacks);
        fprintf(receipt, "GPS XTRA initialize result=%d\n", result);
        if (!result) {
            result = xtra->inject_xtra_data(data, (int)length);
            fprintf(receipt, "GPS XTRA injection result=%d bytes=%zu\n", result, length);
        }
    }
    free(data);
}

int main(int argc, char **argv) {
    serving = argc == 2 && !strcmp(argv[1], "--serve");
    if (!serving && (argc != 3 || strcmp(argv[1], "--test-standalone"))) {
        fprintf(stderr, "Usage: %s --test-standalone SECONDS (1-90)\n", argv[0]);
        return 2;
    }
    long seconds = 0;
    if (!serving) {
        char *end;
        seconds = strtol(argv[2], &end, 10);
        if (end == argv[2] || *end || seconds < 1 || seconds > 90)
            return 2;
    }
    receipt = serving ? stderr : stdout;
    signal(SIGPIPE, SIG_IGN);
    signal(SIGTERM, on_signal);
    signal(SIGINT, on_signal);
    setvbuf(receipt, NULL, _IOLBF, 0);
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
    fprintf(receipt, "GPS module open result=%d\n", rc);
    if (rc || !dev || dev->tag != HARDWARE_DEVICE_TAG)
        return 2;
    struct gps_device_t *gps = (struct gps_device_t *)dev;
    const GpsInterface *api = gps->get_gps_interface ? gps->get_gps_interface(gps) : NULL;
    if (!api || api->size < sizeof(*api) || !api->init || !api->start ||
        !api->stop || !api->cleanup || !api->set_position_mode)
        return 2;

    rc = api->init(&callbacks.standard);
    fprintf(receipt, "GPS HAL initialize result=%d\n", rc);
    if (rc)
        return 2;
    if (interrupted)
        goto cleanup;
    rc = api->set_position_mode(GPS_POSITION_MODE_STANDALONE,
            GPS_POSITION_RECURRENCE_PERIODIC, 1000, 0, 0);
    fprintf(receipt, "GPS standalone mode result=%d\n", rc);
    if (rc || interrupted)
        goto cleanup;
    provide_utc(api);
    provide_seed(api);
    provide_lto(api);
    rc = api->start();
    fprintf(receipt, "GPS start result=%d\n", rc);
    if (rc)
        goto cleanup;
    for (long i = 0; !interrupted && (serving || i < seconds); ++i) {
        if (atomic_exchange(&utc_requested, false))
            provide_utc(api);
        if (atomic_exchange(&location_requested, false))
            provide_seed(api);
        sleep(1);
    }
    rc = api->stop();
    fprintf(receipt, "GPS stop result=%d\n", rc);
cleanup:
    api->cleanup();
    if (dev->close)
        dev->close(dev);
    fprintf(receipt, "GPS status=%u NMEA records=%u location callbacks=%u satellite reports=%u assisted location requests=%u\n",
           engine_status, nmea_count, fixes, satellite_reports, assisted_location_requests);
    return rc ? 2 : nmea_count ? 0 : 1;
}
