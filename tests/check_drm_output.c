/* SPDX-License-Identifier: GPL-2.0-only */
/* Run the production presenter against a fake KMS endpoint. No device access. */
#define open fake_open
#define close fake_close
#define lseek fake_lseek
#define poll fake_poll
#define clock_gettime fake_clock
#define drmIoctl fake_ioctl
#define drmGetVersion fake_version
#define drmFreeVersion fake_free_version
#define drmGetCap fake_cap
#define drmModeGetResources fake_resources
#define drmModeFreeResources fake_free_resources
#define drmModeGetConnector fake_connector
#define drmModeFreeConnector fake_free_connector
#define drmModeGetEncoder fake_encoder
#define drmModeFreeEncoder fake_free_encoder
#define drmPrimeFDToHandle fake_prime
#define drmModeAddFB2 fake_addfb
#define drmModeRmFB fake_rmfb
#define drmIsMaster fake_is_master
#define drmSetMaster fake_master
#define drmModeSetCrtc fake_modeset
#define drmModePageFlip fake_flip
#define drmHandleEvent fake_event
#define drmModeObjectGetProperties fake_properties
#define drmModeFreeObjectProperties fake_free_properties
#define drmModeGetProperty fake_property
#define drmModeFreeProperty fake_free_property
#include "../compat/native-gnome/direct-panel/drm-output.c"
#include <assert.h>
#include <stdarg.h>

static unsigned allocations, flips, reads, closed, removed;
static uint32_t active_fb, queued_fb, next_fb = 100, last_format;
static int flip_failure, poll_failure, event_failure, prime_failure, blank_timeout, resume_timeout;
static int powered_timeout;
static int suspend_timeout;
static uint64_t fake_ms;
static uint64_t fake_sleep_ms;
static int simulated_power=DRM_MODE_DPMS_ON;
static struct g955n_kms *pending;
static uint32_t exported[128];
int fake_open(const char *p, int flags, ...) { (void)p; (void)flags; errno=ENOENT; return -1; }
int fake_close(int fd) { assert(fd == 55); closed++; return 0; }
off_t fake_lseek(int fd, off_t off, int whence) { assert(fd>=0 && off==0 && whence==SEEK_END); return 32*1024*1024; }
int fake_clock(clockid_t id,struct timespec *t) {
    assert(id==CLOCK_MONOTONIC || id==CLOCK_BOOTTIME);
    uint64_t now=fake_ms+(id==CLOCK_BOOTTIME ? fake_sleep_ms : 0);
    t->tv_sec=now/1000;t->tv_nsec=(now%1000)*1000000;return 0;
}
int fake_poll(struct pollfd *p, nfds_t n, int timeout) {
    assert(n==1 && timeout>0); reads++;
    if (blank_timeout) {
        blank_timeout=0;simulated_power=DRM_MODE_DPMS_OFF;fake_ms+=timeout;return 0;
    }
    if (powered_timeout) {fake_ms+=timeout;return 0;}
    if (suspend_timeout) {suspend_timeout=0;fake_sleep_ms+=180000;return 0;}
    if (resume_timeout) {resume_timeout--;fake_ms+=20000;return 0;}
    p->revents = poll_failure ? POLLERR : POLLIN;
    return 1;
}
int fake_ioctl(int fd, unsigned long request, void *arg) {
    assert(fd==55 && request==DRM_IOCTL_GEM_CLOSE);
    struct drm_gem_close *c=arg; assert(c->handle<128); exported[c->handle]=0; return 0;
}
drmVersionPtr fake_version(int fd) { (void)fd; abort(); }
void fake_free_version(drmVersionPtr p) { (void)p; abort(); }
int fake_cap(int fd, uint64_t c, uint64_t *v) { (void)fd;(void)c;(void)v;abort(); }
drmModeResPtr fake_resources(int fd) { (void)fd;abort(); }
void fake_free_resources(drmModeResPtr p) { (void)p;abort(); }
drmModeConnectorPtr fake_connector(int fd,uint32_t id) { (void)fd;(void)id;abort(); }
void fake_free_connector(drmModeConnectorPtr p) { (void)p;abort(); }
drmModeEncoderPtr fake_encoder(int fd,uint32_t id) { (void)fd;(void)id;abort(); }
void fake_free_encoder(drmModeEncoderPtr p) { (void)p;abort(); }
int fake_prime(int fd,int buf,uint32_t *handle) {
    assert(fd==55 && buf<128);
    if (prime_failure) { errno=EINVAL;return -1; }
    /* Different fd numbers can describe the same DMA-BUF. */
    *handle=buf==21 ? 20 : (uint32_t)buf;
    return 0;
}
int fake_addfb(int fd,uint32_t w,uint32_t h,uint32_t fmt,const uint32_t handles[4],
               const uint32_t pitches[4],const uint32_t offsets[4],uint32_t *id,uint32_t flags) {
    assert(fd==55 && w==1440 && h==2960 && pitches[0]==5760 && !offsets[0] && !flags);
    *id=++next_fb;exported[handles[0]]=*id;last_format=fmt;allocations++;return 0;
}
int fake_rmfb(int fd,uint32_t id) { assert(fd==55 && id!=active_fb);removed++;return 0; }
int fake_is_master(int fd) { assert(fd==55);return 1; }
int fake_master(int fd) { assert(fd==55);return 0; }
int fake_modeset(int fd,uint32_t crtc,uint32_t fb,uint32_t x,uint32_t y,
                 uint32_t *connectors,int count,drmModeModeInfoPtr mode) {
    assert(fd==55 && crtc==1 && !x && !y && *connectors==2 && count==1 && mode);
    active_fb=fb;return 0;
}
int fake_flip(int fd,uint32_t crtc,uint32_t fb,uint32_t flags,void *data) {
    assert(fd==55 && crtc==1 && flags==DRM_MODE_PAGE_FLIP_EVENT);
    if (flip_failure) {errno=EBUSY;return -1;}
    queued_fb=fb;pending=data;flips++;return 0;
}
int fake_event(int fd,drmEventContextPtr event) {
    assert(fd==55 && pending && event->version==2);
    if(event_failure){errno=EIO;return -1;}
    active_fb=queued_fb;
    event->page_flip_handler(fd,1,0,0,pending);pending=NULL;return 0;
}

drmModeObjectPropertiesPtr fake_properties(int fd,uint32_t id,uint32_t type) {
    assert(fd==55 && id==2 && type==DRM_MODE_OBJECT_CONNECTOR);
    static uint32_t ids[]={42};static uint64_t values[]={DRM_MODE_DPMS_OFF};
    static drmModeObjectProperties properties={1,ids,values};
    values[0]=simulated_power;
    return &properties;
}
void fake_free_properties(drmModeObjectPropertiesPtr p) {assert(p);}
drmModePropertyPtr fake_property(int fd,uint32_t id) {(void)fd;(void)id;abort();}
void fake_free_property(drmModePropertyPtr p) {(void)p;abort();}

int main(void) {
    struct g955n_kms output={.fd=55,.crtc=1,.connector=2,.dpms_property=42};
    struct g955n_panel_frame frame={20,-1,1440,2960,G955N_DECON_RGBX8888};
    int submitted=-1;
    assert(g955n_kms_present(&output,&frame,&submitted)==0 && submitted==1);
    assert(last_format==DRM_FORMAT_XBGR8888 && allocations==1 && !flips && !reads);
    uint32_t first=active_fb;
    frame.dma_buf=21;
    assert(g955n_kms_present(&output,&frame,&submitted)==0);
    assert(allocations==1 && flips==1 && reads==1 && output.current_fb==first);
    frame.dma_buf=22;
    assert(g955n_kms_present(&output,&frame,&submitted)==0);
    assert(allocations==2 && output.current_fb==active_fb && active_fb!=first);
    /* Repeated wraps must retain the active scanout and bound framebuffer IDs. */
    for(int i=30;i<70;++i) {
        frame.dma_buf=i;
        assert(g955n_kms_present(&output,&frame,&submitted)==0);
        assert(output.current_fb==active_fb);
    }
    assert(removed==allocations-CACHE_SIZE);
    /* The panel goes off after the flip has been accepted. Keep both buffers
     * and return to GNOME instead of waiting on a flip that requires wake. */
    blank_timeout=1;frame.dma_buf=70;
    unsigned previous_reads=reads;
    uint32_t original_fb=output.current_fb;
    assert(g955n_kms_present(&output,&frame,&submitted)==G955N_KMS_DEFERRED && submitted==1);
    assert(reads==previous_reads+1 && pending && output.pending_fb==queued_fb);
    assert(output.current_fb==original_fb && active_fb==original_fb);
    frame.dma_buf=75;
    assert(g955n_kms_progress(&output)==G955N_KMS_DEFERRED && reads==previous_reads+1);
    assert(g955n_kms_present(&output,&frame,&submitted)==-EBUSY && !submitted);
    assert(output.pending_fb!=0 && output.current_fb==original_fb);
    simulated_power=DRM_MODE_DPMS_ON;
    assert(g955n_kms_progress(&output)==0);
    assert(reads==previous_reads+2 && !pending && !output.pending_fb && output.current_fb==active_fb);

    /* Already blank: drop the new composition without importing or submitting it. */
    simulated_power=DRM_MODE_DPMS_OFF;
    unsigned previous_allocations=allocations;
    assert(g955n_kms_present(&output,&frame,&submitted)==G955N_KMS_DEFERRED && !submitted);
    assert(allocations==previous_allocations && !pending && !output.pending_fb);
    /* Normal MONOTONIC excludes the sleep interval: no late-clock condition
     * or previously sampled OFF property tells userspace that it just thawed. */
    simulated_power=DRM_MODE_DPMS_ON;suspend_timeout=1;frame.dma_buf=76;
    previous_reads=reads;
    assert(g955n_kms_present(&output,&frame,&submitted)==0);
    assert(reads==previous_reads+2 && !pending && output.current_fb==active_fb);
    simulated_power=DRM_MODE_DPMS_ON;resume_timeout=1;frame.dma_buf=71;
    previous_reads=reads;
    assert(g955n_kms_present(&output,&frame,&submitted)==0 && reads==previous_reads+2);
    assert(!pending && output.current_fb==active_fb);
    uint32_t held=output.current_fb;
    powered_timeout=1;frame.dma_buf=74;
    uint64_t started=fake_ms;
    assert(g955n_kms_present(&output,&frame,&submitted)==-ETIMEDOUT && submitted==1);
    assert(fake_ms-started==FLIP_TIMEOUT_MS && output.pending_fb==queued_fb);
    assert(output.current_fb==held && active_fb==held);
    powered_timeout=0;pending=NULL;output.pending_fb=0;

    frame.dma_buf=73;flip_failure=1;
    assert(g955n_kms_present(&output,&frame,&submitted)==-EBUSY && submitted==1);
    assert(output.current_fb==held && active_fb==held);
    flip_failure=0;poll_failure=1;
    assert(g955n_kms_present(&output,&frame,&submitted)==-EIO && submitted==1);
    assert(output.current_fb==held && active_fb==held);
    poll_failure=0;pending=NULL;output.pending_fb=0;
    prime_failure=1;frame.dma_buf=72;
    assert(g955n_kms_present(&output,&frame,&submitted)==-EINVAL && submitted==0);
    assert(output.current_fb==held);
    prime_failure=0;frame.stride_pixels=100;
    assert(g955n_kms_present(&output,&frame,&submitted)==-EINVAL && submitted==0);
    assert(pixel_format(G955N_DECON_RGBA8888)==DRM_FORMAT_ABGR8888);
    assert(pixel_format(G955N_DECON_BGRA8888)==DRM_FORMAT_ARGB8888);
    struct g955n_kms *missing=(void *)1;
    assert(g955n_kms_open(&missing)==-ENODEV && !missing);
    puts("KMS presenter: DMA-BUF identity, bounded cache, real event retirement and ambiguous-error retention passed");
}
