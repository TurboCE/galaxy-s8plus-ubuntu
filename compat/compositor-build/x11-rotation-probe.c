/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Exercise the Mali rotation pass between two full-size gralloc buffers. */
#include "../native-gnome/direct-panel/panel-rotation.h"
#ifdef G955N_ROTATION_PROBE_KMS
#include "../native-gnome/direct-panel/drm-output.h"
#endif
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#include <X11/Xlib.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define REQUIRE(condition) do { \
    if (!(condition)) { \
        fprintf(stderr, "rotation probe: %s failed at line %d\n", #condition, __LINE__); \
        _exit(1); \
    } \
} while (0)

typedef EGLBoolean (*CreateBuffer)(EGLint, EGLint, EGLint, EGLint, EGLint *, EGLClientBuffer *);
typedef EGLBoolean (*ReleaseBuffer)(EGLClientBuffer);
typedef EGLBoolean (*GetHandle)(EGLDisplay, EGLClientBuffer, void **);

struct target {
    EGLClientBuffer buffer;
    EGLImageKHR image;
    GLuint texture;
    GLuint framebuffer;
    int fd;
    int width;
    int height;
};

#ifdef G955N_ROTATION_PROBE_KMS
static struct g955n_kms *kms;

static void verify_scanout(int fd, unsigned int angle)
{
    if (!kms)
        return;
    const struct g955n_panel_frame frame = {
        .dma_buf = fd, .acquire_fence = -1, .stride_pixels = 1440,
        .allocation_height = 2960, .format = G955N_DECON_RGBX8888,
    };
    int submitted;
    int error = g955n_kms_present(kms, &frame, &submitted);
    if (error)
        fprintf(stderr, "KMS present failed: %d (submitted=%d)\n", error, submitted);
    REQUIRE(!error && submitted);
    printf("KMS presented Mali DMA-BUF at %u degrees\n", angle);
    fflush(stdout);
}
#endif

static CreateBuffer create_buffer;
static ReleaseBuffer release_buffer;
static GetHandle get_handle;
static PFNEGLCREATEIMAGEKHRPROC create_image;
static PFNEGLDESTROYIMAGEKHRPROC destroy_image;
static PFNGLEGLIMAGETARGETTEXTURE2DOESPROC image_texture;

static struct target import_target(EGLDisplay display, EGLClientBuffer buffer, int width, int height)
{
    struct target target = {.width = width, .height = height, .buffer = buffer};
    const EGLint rgbx8888 = 2; /* Android 9 HAL_PIXEL_FORMAT_RGBX_8888 */
    void *handle = NULL;
    REQUIRE(get_handle(display, target.buffer, &handle) && handle);
    /* Android native_handle_t starts with version, numFds and numInts.
     * This phone's RGBX buffer ABI carries one linear DMA-BUF fd. */
    const int *fields = handle;
    REQUIRE(fields[0] == 3 * sizeof(int) && fields[1] == 1 && fields[2] == 46);
    uint32_t magic;
    uint64_t internal;
    memcpy(&magic, (const unsigned char *)handle + 24, sizeof(magic));
    memcpy(&internal, (const unsigned char *)handle + 56, sizeof(internal));
    REQUIRE(magic == 0x03141592 && internal == (uint64_t)rgbx8888);
    target.fd = fields[3];
    REQUIRE(fcntl(target.fd, F_GETFD) >= 0);
    const EGLint attrs[] = {EGL_IMAGE_PRESERVED_KHR, EGL_TRUE, EGL_NONE};
    target.image = create_image(display, EGL_NO_CONTEXT, EGL_NATIVE_BUFFER_ANDROID, target.buffer, attrs);
    REQUIRE(target.image != EGL_NO_IMAGE_KHR);
    glGenTextures(1, &target.texture);
    glBindTexture(GL_TEXTURE_2D, target.texture);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    image_texture(GL_TEXTURE_2D, (GLeglImageOES)target.image);
    glGenFramebuffers(1, &target.framebuffer);
    glBindFramebuffer(GL_FRAMEBUFFER, target.framebuffer);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, target.texture, 0);
    REQUIRE(glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE);
    REQUIRE(glGetError() == GL_NO_ERROR);
    return target;
}

static struct target make_source(EGLDisplay display, int width, int height)
{
    const EGLint rgbx8888 = 2;
    const EGLint gpu_usage = 0x100 | 0x200;
    EGLint stride;
    EGLClientBuffer buffer;
    REQUIRE(create_buffer(width, height, gpu_usage, rgbx8888, &stride, &buffer));
    REQUIRE(stride == width);
    return import_target(display, buffer, width, height);
}

static void destroy_target(EGLDisplay display, const struct target *target)
{
    glDeleteFramebuffers(1, &target->framebuffer);
    glDeleteTextures(1, &target->texture);
    REQUIRE(destroy_image(display, target->image));
}

static void fill_source(const struct target *src, const unsigned int colors[4][3])
{
    glBindFramebuffer(GL_FRAMEBUFFER, src->framebuffer);
    glEnable(GL_SCISSOR_TEST);
    for (int i = 0; i < 4; i++) {
        glScissor((i % 2) * src->width / 2, (i / 2) * src->height / 2,
                  src->width / 2, src->height / 2);
        glClearColor(colors[i][0] / 255.0f, colors[i][1] / 255.0f,
                     colors[i][2] / 255.0f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT);
    }
    glDisable(GL_SCISSOR_TEST);
}

static void rotate_and_verify(EGLDisplay display, const struct target *src,
                              unsigned int angle, unsigned int slot,
                              const int mapping[4], const unsigned int colors[4][3])
{
    EGLContext context = eglGetCurrentContext();
    EGLSurface surface = eglGetCurrentSurface(EGL_DRAW);
    EGLClientBuffer output;
    int fd;
    glFinish();
    REQUIRE(g955n_rotate_panel_buffer(src->buffer, angle, slot, &fd, &output));
    REQUIRE(eglGetCurrentContext() == context && eglGetCurrentSurface(EGL_DRAW) == surface);
    struct target dst = import_target(display, output, 1440, 2960);
    REQUIRE(fd == dst.fd && src->fd != dst.fd);
    for (int corner = 0; corner < 4; corner++) {
        unsigned char pixel[4] = {0};
        glReadPixels((1 + 2 * (corner % 2)) * dst.width / 4,
                     (1 + 2 * (corner / 2)) * dst.height / 4,
                     1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel);
        REQUIRE(glGetError() == GL_NO_ERROR);
        for (int k = 0; k < 3; k++)
            REQUIRE(pixel[k] == colors[mapping[corner]][k]);
    }
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    glBindTexture(GL_TEXTURE_2D, 0);
    destroy_target(display, &dst);
#ifdef G955N_ROTATION_PROBE_KMS
    verify_scanout(fd, angle);
#endif
}

int main(int argc, char **argv)
{
    REQUIRE(argc == 2);
#ifdef G955N_ROTATION_PROBE_KMS
    int scanout = !strcmp(argv[1], "--present-sm-g955n-rotation-probe");
    REQUIRE(scanout || !strcmp(argv[1], "--run-sm-g955n-rotation-probe"));
#else
    REQUIRE(!strcmp(argv[1], "--run-sm-g955n-rotation-probe"));
#endif
    FILE *model = fopen("/proc/device-tree/model", "r");
    char name[128] = {0};
    REQUIRE(model && fgets(name, sizeof(name), model) && strstr(name, "SM-G955N"));
    fclose(model);
    REQUIRE(getuid() == 1000);
#ifdef G955N_ROTATION_PROBE_KMS
    if (scanout) {
        int error = g955n_kms_open(&kms);
        if (error)
            fprintf(stderr, "KMS open failed: %d\n", error);
        REQUIRE(!error);
    }
#endif
    Display *x11 = XOpenDisplay(NULL);
    REQUIRE(x11);
    EGLDisplay dpy = eglGetDisplay((EGLNativeDisplayType)x11);
    REQUIRE(dpy != EGL_NO_DISPLAY && eglInitialize(dpy, NULL, NULL));
    REQUIRE(eglBindAPI(EGL_OPENGL_ES_API));
    const EGLint config_attrs[] = {
        EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
        EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_NONE,
    };
    EGLConfig config;
    EGLint count;
    REQUIRE(eglChooseConfig(dpy, config_attrs, &config, 1, &count) && count == 1);
    const EGLint context_attrs[] = {EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE};
    const EGLint surface_attrs[] = {EGL_WIDTH, 1, EGL_HEIGHT, 1, EGL_NONE};
    EGLContext context = eglCreateContext(dpy, config, EGL_NO_CONTEXT, context_attrs);
    EGLSurface surface = eglCreatePbufferSurface(dpy, config, surface_attrs);
    REQUIRE(context != EGL_NO_CONTEXT && surface != EGL_NO_SURFACE);
    REQUIRE(eglMakeCurrent(dpy, surface, surface, context));
    const char *renderer = (const char *)glGetString(GL_RENDERER);
    REQUIRE(renderer && strstr(renderer, "Mali-G71"));
    printf("Rotation probe renderer: %s\n", renderer);
    fflush(stdout);
    create_buffer = (CreateBuffer)eglGetProcAddress("eglHybrisCreateNativeBuffer");
    release_buffer = (ReleaseBuffer)eglGetProcAddress("eglHybrisReleaseNativeBuffer");
    get_handle = (GetHandle)eglGetProcAddress("eglHybrisNativeBufferHandle");
    create_image = (PFNEGLCREATEIMAGEKHRPROC)eglGetProcAddress("eglCreateImageKHR");
    destroy_image = (PFNEGLDESTROYIMAGEKHRPROC)eglGetProcAddress("eglDestroyImageKHR");
    image_texture = (PFNGLEGLIMAGETARGETTEXTURE2DOESPROC)eglGetProcAddress("glEGLImageTargetTexture2DOES");
    REQUIRE(create_buffer && release_buffer && get_handle && create_image && destroy_image && image_texture);

    const unsigned int colors[][3] = {{255, 0, 0}, {0, 255, 0}, {0, 0, 255}, {255, 255, 0}};
    const int left[] = {2, 0, 3, 1}, inverted[] = {3, 2, 1, 0}, right[] = {1, 3, 0, 2};
    const struct target landscape = make_source(dpy, 2960, 1440);
    fill_source(&landscape, colors);
    rotate_and_verify(dpy, &landscape, 90, 0, left, colors);
    rotate_and_verify(dpy, &landscape, 270, 1, right, colors);
    destroy_target(dpy, &landscape);
    REQUIRE(release_buffer(landscape.buffer));
    const struct target portrait = make_source(dpy, 1440, 2960);
    fill_source(&portrait, colors);
    rotate_and_verify(dpy, &portrait, 180, 2, inverted, colors);
    rotate_and_verify(dpy, &portrait, 180, 0, inverted, colors);
    destroy_target(dpy, &portrait);
    REQUIRE(release_buffer(portrait.buffer));
    puts("90, 180 and 270 degree native-buffer pixels verified; producer EGL binding restored");
#ifdef G955N_ROTATION_PROBE_KMS
    g955n_kms_close(kms);
#endif
    REQUIRE(eglMakeCurrent(dpy, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT));
    REQUIRE(eglDestroySurface(dpy, surface));
    REQUIRE(eglDestroyContext(dpy, context));
    REQUIRE(eglTerminate(dpy));
    XCloseDisplay(x11);
}
