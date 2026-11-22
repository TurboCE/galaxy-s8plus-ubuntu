/* SPDX-License-Identifier: GPL-2.0-only */
#define _GNU_SOURCE
/* On-device GBM/EGL render and KMS scanout test. No CPU pixel access. */
#include "drm-output.h"

#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#include <fcntl.h>
#include <drm_fourcc.h>
#include <gbm.h>
#include <glob.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <xf86drm.h>

enum { WIDTH = 1440, HEIGHT = 2960, SLOT_COUNT = 3 };

struct slot {
    struct gbm_bo *bo;
    EGLImageKHR image;
    GLuint texture;
    GLuint framebuffer;
    struct g955n_panel_frame frame;
};

static int open_panfrost(void)
{
    glob_t nodes = {0};
    int fd = -1;

    if (!glob("/dev/dri/renderD*", 0, NULL, &nodes)) {
        for (size_t i = 0; i < nodes.gl_pathc; i++) {
            fd = open(nodes.gl_pathv[i], O_RDWR | O_CLOEXEC);
            if (fd < 0)
                continue;
            drmVersionPtr version = drmGetVersion(fd);
            bool supported = version && !strcmp(version->name, "panfrost");
            drmFreeVersion(version);
            if (supported)
                break;
            close(fd);
            fd = -1;
        }
    }
    globfree(&nodes);
    return fd;
}

static bool correct_device(void)
{
    char model[128] = {0};
    FILE *file = fopen("/proc/device-tree/model", "r");
    if (!file)
        return false;
    size_t length = fread(model, 1, sizeof(model) - 1, file);
    fclose(file);
    return length && strstr(model, "SM-G955N");
}

static bool build_slot(struct slot *slot, struct gbm_device *gbm,
                       uint32_t usage, EGLDisplay dpy,
                       PFNEGLCREATEIMAGEKHRPROC create_image,
                       PFNGLEGLIMAGETARGETTEXTURE2DOESPROC image_texture)
{
    slot->bo = gbm_bo_create(gbm, WIDTH, HEIGHT, GBM_FORMAT_ARGB8888,
                             usage);
    if (!slot->bo || gbm_bo_get_plane_count(slot->bo) != 1 ||
        gbm_bo_get_modifier(slot->bo) != DRM_FORMAT_MOD_LINEAR ||
        gbm_bo_get_offset(slot->bo, 0))
        return false;
    uint32_t pitch = gbm_bo_get_stride(slot->bo);
    if (pitch < WIDTH * 4 || pitch % 4 || pitch > 4096 * 4)
        return false;

    slot->frame = (struct g955n_panel_frame){
        .dma_buf = gbm_bo_get_fd(slot->bo), .acquire_fence = -1,
        .stride_pixels = pitch / 4, .allocation_height = HEIGHT,
        .format = G955N_DECON_BGRA8888,
    };
    if (slot->frame.dma_buf < 0)
        return false;
    const EGLint attrs[] = {
        EGL_WIDTH, WIDTH, EGL_HEIGHT, HEIGHT,
        EGL_LINUX_DRM_FOURCC_EXT, GBM_FORMAT_ARGB8888,
        EGL_DMA_BUF_PLANE0_FD_EXT, slot->frame.dma_buf,
        EGL_DMA_BUF_PLANE0_OFFSET_EXT, 0, EGL_DMA_BUF_PLANE0_PITCH_EXT, (EGLint)pitch,
        EGL_NONE,
    };
    slot->image = create_image(dpy, EGL_NO_CONTEXT, EGL_LINUX_DMA_BUF_EXT, NULL, attrs);
    if (slot->image == EGL_NO_IMAGE_KHR)
        return false;

    glGenTextures(1, &slot->texture);
    glBindTexture(GL_TEXTURE_2D, slot->texture);
    image_texture(GL_TEXTURE_2D, slot->image);
    glGenFramebuffers(1, &slot->framebuffer);
    glBindFramebuffer(GL_FRAMEBUFFER, slot->framebuffer);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D,
                           slot->texture, 0);
    return glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE &&
           glGetError() == GL_NO_ERROR;
}

static bool paint_slot(const struct slot *slot, unsigned int index)
{
    glBindFramebuffer(GL_FRAMEBUFFER, slot->framebuffer);
    glViewport(0, 0, WIDTH, HEIGHT);
    glClearColor(index == 0, index == 1, index == 2, 1);
    glClear(GL_COLOR_BUFFER_BIT);
    glFinish();
    return glGetError() == GL_NO_ERROR;
}

static bool present_frames(struct g955n_kms *output, struct slot *slots)
{
    for (unsigned int n = 0; n < 12; n++) {
        unsigned int index = n % SLOT_COUNT;
        struct slot *slot = &slots[index];
        if (!paint_slot(slot, index))
            return false;
        int submitted = 0;
        int result = g955n_kms_present(output, &slot->frame, &submitted);
        if (result || !submitted) {
            fprintf(stderr, "DECON frame %u failed: status=%d submitted=%d\n",
                    n, result, submitted);
            return false;
        }
        usleep(100000);
    }
    return true;
}

int main(int argc, char **argv)
{
    bool kms_gbm = argc == 2 && !strcmp(argv[1], "--check-kms-gbm");
    bool check = kms_gbm || (argc == 2 && !strcmp(argv[1], "--check"));
    if (argc != 2 || (!check && strcmp(argv[1], "--present-reviewed-sm-g955n"))) {
        fprintf(stderr, "Use --check, --check-kms-gbm or --present-reviewed-sm-g955n after vacating the panel\n");
        return 2;
    }
    if (!correct_device()) {
        fprintf(stderr, "Requires an SM-G955N\n");
        return 2;
    }

    int result = 1;
    struct g955n_kms *output = NULL;
    const int kms_error = g955n_kms_open(&output);
    if (kms_error) {
        fprintf(stderr, "DECON KMS preflight failed: %d\n", kms_error);
        return 1;
    }
    puts("DECON KMS supports native DSI and PRIME import");

    int fd = open_panfrost();
    if (fd < 0) {
        fprintf(stderr, "No accessible Panfrost DRM render node\n");
        g955n_kms_close(output);
        return 3;
    }

    const int gbm_fd = kms_gbm ? g955n_kms_fd(output) : fd;
    const uint32_t usage = GBM_BO_USE_RENDERING | GBM_BO_USE_LINEAR |
                           (kms_gbm ? GBM_BO_USE_SCANOUT : 0);
    printf("GBM device: %s\n", kms_gbm ? "DECON KMS card" : "Panfrost render node");
    struct gbm_device *gbm = gbm_create_device(gbm_fd);
    if (!gbm) {
        fprintf(stderr, "Could not create GBM device\n");
        goto close_devices;
    }

    EGLDisplay dpy = eglGetPlatformDisplay(EGL_PLATFORM_GBM_KHR, gbm, NULL);
    if (dpy == EGL_NO_DISPLAY || !eglInitialize(dpy, NULL, NULL)) {
        fprintf(stderr, "Could not initialize GBM EGL (error 0x%x)\n", eglGetError());
        goto close_devices;
    }

    EGLContext context = EGL_NO_CONTEXT;
    struct slot slots[SLOT_COUNT] = {0};
    for (size_t i = 0; i < SLOT_COUNT; i++)
        slots[i].frame.dma_buf = -1;
    const EGLint cfgattrs[] = {
        EGL_SURFACE_TYPE, EGL_DONT_CARE, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
        EGL_NONE,
    };
    const EGLint ctxattrs[] = {EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE};
    EGLConfig config;
    EGLint count;
    if (!eglBindAPI(EGL_OPENGL_ES_API) || !eglChooseConfig(dpy, cfgattrs, &config, 1, &count) ||
        count != 1)
        goto close_egl;
    context = eglCreateContext(dpy, config, EGL_NO_CONTEXT, ctxattrs);
    if (context == EGL_NO_CONTEXT || !eglMakeCurrent(dpy, EGL_NO_SURFACE, EGL_NO_SURFACE, context))
        goto close_egl;

    const char *renderer = (const char *)glGetString(GL_RENDERER);
    const char *vendor = eglQueryString(dpy, EGL_VENDOR);
    if (!renderer || !strstr(renderer, "Mali-G71") || !strstr(renderer, "Panfrost") ||
        !vendor || !strstr(vendor, "Mesa")) {
        fprintf(stderr, "Mesa Panfrost Mali-G71 required, got %s\n", renderer ? renderer : "(none)");
        goto close_egl;
    }
    printf("Mesa renderer: %s\n", renderer);

    PFNEGLCREATEIMAGEKHRPROC create_image = (PFNEGLCREATEIMAGEKHRPROC)eglGetProcAddress("eglCreateImageKHR");
    PFNEGLDESTROYIMAGEKHRPROC destroy_image = (PFNEGLDESTROYIMAGEKHRPROC)eglGetProcAddress("eglDestroyImageKHR");
    PFNGLEGLIMAGETARGETTEXTURE2DOESPROC image_texture =
        (PFNGLEGLIMAGETARGETTEXTURE2DOESPROC)eglGetProcAddress("glEGLImageTargetTexture2DOES");
    if (!create_image || !destroy_image || !image_texture)
        goto close_egl;

    bool ready = true;
    for (size_t i = 0; i < SLOT_COUNT && ready; i++)
        ready = build_slot(&slots[i], gbm, usage, dpy, create_image, image_texture) &&
                paint_slot(&slots[i], i);
    if (ready && (check || present_frames(output, slots))) {
        puts(kms_gbm ? "DECON GBM selected Panfrost and rendered to linear scanout buffers" :
             check ? "Panfrost GBM allocation and DMA-BUF EGL rendering ready" :
                     "12 Mesa/Panfrost DECON presentations completed");
        result = 0;
    } else if (!ready) {
        fprintf(stderr, "Could not create or render a linear, single-plane Panfrost target\n");
    }

    /* Presentation owns the KMS buffers. The KMS GBM check borrows its fd. */
    if (!kms_gbm) {
        g955n_kms_close(output);
        output = NULL;
    }
    for (size_t i = 0; i < SLOT_COUNT; i++) {
        struct slot *slot = &slots[i];
        glDeleteFramebuffers(1, &slot->framebuffer);
        glDeleteTextures(1, &slot->texture);
        if (slot->image != EGL_NO_IMAGE_KHR)
            destroy_image(dpy, slot->image);
        if (slot->frame.dma_buf >= 0)
            close(slot->frame.dma_buf);
        if (slot->bo)
            gbm_bo_destroy(slot->bo);
    }
close_egl:
    if (result)
        fprintf(stderr, "GBM/EGL test failed (EGL error 0x%x)\n", eglGetError());
    if (context != EGL_NO_CONTEXT) {
        eglMakeCurrent(dpy, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
        eglDestroyContext(dpy, context);
    }
    eglTerminate(dpy);
close_devices:
    if (gbm)
        gbm_device_destroy(gbm);
    close(fd);
    g955n_kms_close(output);
    return result;
}
