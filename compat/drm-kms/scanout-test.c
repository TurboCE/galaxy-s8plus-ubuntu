/* SPDX-License-Identifier: GPL-2.0-only */
/* Hardware fixture only: CPU fills three solid-color test buffers once.
 * Production GNOME presentation never maps or fills these buffers. */
#define _GNU_SOURCE
#include "drm-output.h"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <xf86drm.h>
#include <xf86drmMode.h>

int main(void)
{
    struct g955n_panel_frame frames[3];
    const uint32_t colors[3] = {0xffff0000, 0xff00ff00, 0xff0000ff};
    FILE *model = fopen("/proc/device-tree/model", "r");
    char name[256] = {0};
    assert(model && fread(name, 1, sizeof(name)-1, model)>0);
    fclose(model);
    assert(strstr(name, "SM-G955N"));
    int fd = open("/dev/dri/card0", O_RDWR | O_CLOEXEC);
    assert(fd>=0);
    drmVersionPtr version = drmGetVersion(fd);
    assert(version && !strcmp(version->name, "g955n-decon"));
    drmFreeVersion(version);
    for (unsigned i=0; i<3; ++i) {
        struct drm_mode_create_dumb create = {.width=1440,.height=2960,.bpp=32};
        assert(drmIoctl(fd, DRM_IOCTL_MODE_CREATE_DUMB, &create)==0);
        struct drm_mode_map_dumb map = {.handle=create.handle};
        assert(drmIoctl(fd, DRM_IOCTL_MODE_MAP_DUMB, &map)==0);
        uint32_t *pixels = mmap(NULL, create.size, PROT_READ|PROT_WRITE, MAP_SHARED, fd, map.offset);
        assert(pixels!=MAP_FAILED);
        for (uint64_t p=0; p<create.size/4; ++p) pixels[p]=colors[i];
        assert(munmap(pixels,create.size)==0);
        int buffer=-1;
        assert(drmPrimeHandleToFD(fd, create.handle, DRM_CLOEXEC, &buffer)==0);
        frames[i]=(struct g955n_panel_frame){buffer,-1,create.pitch/4,2960,G955N_DECON_BGRA8888};
    }
    close(fd);
    struct g955n_kms *output=NULL;
    int result = g955n_kms_open(&output);
    if (result) {fprintf(stderr,"KMS open: %d\n",result);return 1;}
    for (unsigned n=0; n<90; ++n) {
        int submitted=0;
        result=g955n_kms_present(output,&frames[n%3],&submitted);
        if (result) {fprintf(stderr,"KMS frame %u: %d submitted=%d\n",n,result,submitted);return 2;}
        usleep(16000);
    }
    g955n_kms_close(output);
    for(unsigned i=0;i<3;++i)close(frames[i].dma_buf);
    puts("KMS/PRIME: 90 native panel presentations completed and fbdev restored");
}
