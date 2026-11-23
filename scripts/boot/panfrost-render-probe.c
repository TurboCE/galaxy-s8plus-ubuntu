// SPDX-License-Identifier: GPL-2.0-only
#include <stdbool.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <stdio.h>
#include <linux/dma-heap.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define EGL_NO_PLATFORM_SPECIFIC_TYPES
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl3.h>
#include <GLES2/gl2ext.h>
#include <drm/drm_fourcc.h>
#include <gbm.h>
#include <drm/panfrost_drm.h>

#define API(name) __typeof__(&name) name##_fn
#define LOAD(lib, name) do { \
    name##_fn = (__typeof__(name##_fn))dlsym(lib, #name); \
    if (!name##_fn) return fail(#name); \
} while (0)
#define GL(name) __typeof__(&name) name##_fn = \
    (__typeof__(&name))eglGetProcAddress_fn(#name); \
    if (!name##_fn) return fail(#name)

static int fail(const char *stage)
{
    fprintf(stderr, "Panfrost render probe failed at %s\n", stage);
    return 1;
}

static int probe_drm(int fd)
{
    struct drm_panfrost_get_param gpu = { .param = DRM_PANFROST_PARAM_GPU_PROD_ID };
    struct drm_panfrost_create_bo bo = { .size = 4096 };
    struct drm_gem_close close_bo = { 0 };

    if (ioctl(fd, DRM_IOCTL_PANFROST_GET_PARAM, &gpu) < 0) {
        perror("DRM_IOCTL_PANFROST_GET_PARAM");
        return fail("Panfrost GPU ID");
    }
    fprintf(stderr, "Panfrost probe: DRM reported model 0x%llx\n",
            (unsigned long long)gpu.value);
    if (ioctl(fd, DRM_IOCTL_PANFROST_CREATE_BO, &bo) < 0) {
        perror("DRM_IOCTL_PANFROST_CREATE_BO");
        return fail("Panfrost buffer allocation");
    }
    close_bo.handle = bo.handle;
    if (ioctl(fd, DRM_IOCTL_GEM_CLOSE, &close_bo) < 0) {
        perror("DRM_IOCTL_GEM_CLOSE");
        return fail("Panfrost buffer release");
    }
    fprintf(stderr, "Panfrost probe: DRM buffer allocated and released\n");
    return 0;
}

static int allocate_scanout_buffer(unsigned int pitch, unsigned int height)
{
    int heap = open("/dev/dma_heap/default_cma_region", O_RDWR | O_CLOEXEC);
    if (heap < 0)
        return -1;
    struct dma_heap_allocation_data alloc = {
        .len = (uint64_t)pitch * height,
        .fd_flags = O_RDWR | O_CLOEXEC,
    };
    int ret = ioctl(heap, DMA_HEAP_IOCTL_ALLOC, &alloc);
    close(heap);
    return ret < 0 ? -1 : (int)alloc.fd;
}

static int present_decon_buffer(int fd)
{
    int control = open("/sys/bus/platform/devices/12860000.decon-handoff/scanout_test",
                       O_WRONLY | O_CLOEXEC);
    if (control < 0) {
        perror("DECON scanout test control");
        return 1;
    }
    char arg[32];
    int len = snprintf(arg, sizeof(arg), "%d\n", fd);
    ssize_t written = write(control, arg, len);
    if (written != len)
        perror("DECON DMA-BUF scanout");
    close(control);
    return written != len;
}

/* Exercise the kind of linear image a separate KMS device can import. */
static EGLImage create_linear_image(void *gbm, void *egl, struct gbm_device *device,
                                    EGLDisplay display, int width, int height,
                                    bool cma_scanout, int *out_fd)
{
    API(gbm_bo_create);
    API(gbm_bo_get_fd);
    API(gbm_bo_get_stride);
    API(gbm_bo_get_offset);
    API(gbm_bo_get_modifier);
    API(gbm_bo_get_plane_count);
    API(gbm_bo_destroy);
    API(eglCreateImage);

    /* Unlike the main probe, this helper returns an EGLImage on failure. */
    gbm_bo_create_fn = dlsym(gbm, "gbm_bo_create");
    gbm_bo_get_fd_fn = dlsym(gbm, "gbm_bo_get_fd");
    gbm_bo_get_stride_fn = dlsym(gbm, "gbm_bo_get_stride");
    gbm_bo_get_offset_fn = dlsym(gbm, "gbm_bo_get_offset");
    gbm_bo_get_modifier_fn = dlsym(gbm, "gbm_bo_get_modifier");
    gbm_bo_get_plane_count_fn = dlsym(gbm, "gbm_bo_get_plane_count");
    gbm_bo_destroy_fn = dlsym(gbm, "gbm_bo_destroy");
    eglCreateImage_fn = dlsym(egl, "eglCreateImage");
    if (!gbm_bo_create_fn || !gbm_bo_get_fd_fn || !gbm_bo_get_stride_fn ||
        !gbm_bo_get_offset_fn || !gbm_bo_get_modifier_fn ||
        !gbm_bo_get_plane_count_fn || !gbm_bo_destroy_fn || !eglCreateImage_fn)
        return EGL_NO_IMAGE;

    struct gbm_bo *bo = NULL;
    EGLImage image = EGL_NO_IMAGE;
    unsigned int pitch = width * 4;
    unsigned int offset = 0;
    int dma_fd = -1;
    if (cma_scanout) {
        dma_fd = allocate_scanout_buffer(pitch, height);
    } else {
        bo = gbm_bo_create_fn(device, width, height, GBM_FORMAT_ARGB8888,
                             GBM_BO_USE_RENDERING | GBM_BO_USE_LINEAR);
        if (!bo)
            return EGL_NO_IMAGE;
        if (gbm_bo_get_plane_count_fn(bo) != 1 ||
            gbm_bo_get_modifier_fn(bo) != DRM_FORMAT_MOD_LINEAR)
            goto fail;
        dma_fd = gbm_bo_get_fd_fn(bo);
        pitch = gbm_bo_get_stride_fn(bo);
        offset = gbm_bo_get_offset_fn(bo, 0);
    }
    if (dma_fd < 0)
        goto fail;

    const EGLAttrib attrs[] = {
        EGL_WIDTH, width, EGL_HEIGHT, height,
        EGL_LINUX_DRM_FOURCC_EXT, DRM_FORMAT_ARGB8888,
        EGL_DMA_BUF_PLANE0_FD_EXT, dma_fd,
        EGL_DMA_BUF_PLANE0_OFFSET_EXT, offset,
        EGL_DMA_BUF_PLANE0_PITCH_EXT, pitch, EGL_NONE
    };
    image = eglCreateImage_fn(display, EGL_NO_CONTEXT, EGL_LINUX_DMA_BUF_EXT, NULL, attrs);
    if (image == EGL_NO_IMAGE)
        goto fail;

    fprintf(stderr, "Panfrost DMA-BUF: AR24 %dx%d pitch=%u offset=%u modifier=LINEAR\n",
            width, height, pitch, offset);
    *out_fd = dma_fd;
    if (bo)
        gbm_bo_destroy_fn(bo);
    return image;

fail:
    if (dma_fd >= 0)
        close(dma_fd);
    if (bo)
        gbm_bo_destroy_fn(bo);
    return EGL_NO_IMAGE;
}

static int verify_prime_import(const char *render_node, int dma_fd)
{
    int importer = open(render_node, O_RDWR | O_CLOEXEC);
    if (importer < 0)
        return fail("second DRM file");
    struct drm_prime_handle prime = { .fd = dma_fd };
    int ret = ioctl(importer, DRM_IOCTL_PRIME_FD_TO_HANDLE, &prime);
    if (ret < 0)
        perror("DRM_IOCTL_PRIME_FD_TO_HANDLE");
    close(importer);
    return ret < 0 ? fail("DMA-BUF reimport") : 0;
}

int main(int argc, char **argv)
{
    static const char *vertex =
        "#version 300 es\n"
        "void main() {\n"
        "  const vec2 p[3] = vec2[3](vec2(-.8,-.8),vec2(.8,-.8),vec2(0.,.8));\n"
        "  gl_Position = vec4(p[gl_VertexID],0.,1.);\n"
        "}\n";
    static const char *fragment =
        "#version 300 es\n"
        "precision mediump float; out vec4 color;\n"
        "void main() { color = vec4(1.,0.,0.,1.); }\n";
    static const EGLint config_attrs[] = {
        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT, EGL_NONE
    };
    static const EGLint context_attrs[] = {
        EGL_CONTEXT_CLIENT_VERSION, 3, EGL_NONE
    };
    API(gbm_create_device);
    API(eglGetPlatformDisplay);
    API(eglInitialize);
    API(eglBindAPI);
    API(eglChooseConfig);
    API(eglCreateContext);
    API(eglMakeCurrent);
    API(eglGetProcAddress);
    EGLConfig config;
    EGLint count;

    bool scanout = argc == 3 && strcmp(argv[2], "--decon-dmabuf") == 0;
    bool linear = scanout || (argc == 3 && strcmp(argv[2], "--linear-dmabuf") == 0);
    if (argc != 2 && !linear)
        return fail("render node argument");
    int width = linear ? 1440 : 16;
    int height = linear ? 2960 : 16;
    int fd = open(argv[1], O_RDWR | O_CLOEXEC);
    if (fd < 0) {
        perror("DRM render node");
        return fail("render node open");
    }
    fprintf(stderr, "Panfrost probe: render node open\n");
    if (probe_drm(fd))
        return 1;
    void *gbm = dlopen("libgbm.so.1", RTLD_NOW);
    void *egl = dlopen("libEGL.so.1", RTLD_NOW);
    if (!gbm || !egl)
        return fail("Mesa EGL and GBM libraries");
    LOAD(gbm, gbm_create_device);
    LOAD(egl, eglGetPlatformDisplay);
    LOAD(egl, eglInitialize);
    LOAD(egl, eglBindAPI);
    LOAD(egl, eglChooseConfig);
    LOAD(egl, eglCreateContext);
    LOAD(egl, eglMakeCurrent);
    LOAD(egl, eglGetProcAddress);
    fprintf(stderr, "Panfrost probe: EGL and GBM libraries loaded\n");

    struct gbm_device *device = gbm_create_device_fn(fd);
    if (!device)
        return fail("GBM device");
    fprintf(stderr, "Panfrost probe: GBM device created\n");
    EGLDisplay display = eglGetPlatformDisplay_fn(EGL_PLATFORM_GBM_KHR, device, NULL);
    if (display == EGL_NO_DISPLAY || !eglInitialize_fn(display, NULL, NULL) ||
        !eglBindAPI_fn(EGL_OPENGL_ES_API) ||
        !eglChooseConfig_fn(display, config_attrs, &config, 1, &count) || !count)
        return fail("GBM EGL initialization");
    EGLContext context = eglCreateContext_fn(display, config, EGL_NO_CONTEXT, context_attrs);
    if (context == EGL_NO_CONTEXT ||
        !eglMakeCurrent_fn(display, EGL_NO_SURFACE, EGL_NO_SURFACE, context))
        return fail("surfaceless GLES 3 context");
    fprintf(stderr, "Panfrost probe: GLES context current\n");

    GL(glGetString);
    GL(glGenTextures);
    GL(glBindTexture);
    GL(glTexStorage2D);
    GL(glGenFramebuffers);
    GL(glBindFramebuffer);
    GL(glFramebufferTexture2D);
    GL(glCheckFramebufferStatus);
    GL(glCreateShader);
    GL(glShaderSource);
    GL(glCompileShader);
    GL(glGetShaderiv);
    GL(glCreateProgram);
    GL(glAttachShader);
    GL(glLinkProgram);
    GL(glGetProgramiv);
    GL(glUseProgram);
    GL(glViewport);
    GL(glClearColor);
    GL(glClear);
    GL(glDrawArrays);
    GL(glReadPixels);
    GL(glGetError);
    GL(glFinish);

    const char *renderer = (const char *)glGetString_fn(GL_RENDERER);
    if (!renderer || !strstr(renderer, "Mali-G71"))
        return fail("Mali-G71 renderer selection");
    GLuint texture, framebuffer;
    glGenTextures_fn(1, &texture);
    glBindTexture_fn(GL_TEXTURE_2D, texture);
    int dma_fd = -1;
    if (linear) {
        API(eglDestroyImage);
        LOAD(egl, eglDestroyImage);
        PFNGLEGLIMAGETARGETTEXTURE2DOESPROC bind_image =
            (PFNGLEGLIMAGETARGETTEXTURE2DOESPROC)
            eglGetProcAddress_fn("glEGLImageTargetTexture2DOES");
        if (!bind_image)
            return fail("EGL image binding");
        EGLImage image = create_linear_image(gbm, egl, device, display, width, height,
                                             scanout, &dma_fd);
        if (image == EGL_NO_IMAGE)
            return fail("linear GBM DMA-BUF and EGL image");
        bind_image(GL_TEXTURE_2D, (GLeglImageOES)image);
        eglDestroyImage_fn(display, image);
    } else {
        glTexStorage2D_fn(GL_TEXTURE_2D, 1, GL_RGBA8, width, height);
    }
    glGenFramebuffers_fn(1, &framebuffer);
    glBindFramebuffer_fn(GL_FRAMEBUFFER, framebuffer);
    glFramebufferTexture2D_fn(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture, 0);
    if (glCheckFramebufferStatus_fn(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE)
        return fail("framebuffer");

    GLuint program = glCreateProgram_fn();
    const GLchar *sources[] = { vertex, fragment };
    const GLenum stages[] = { GL_VERTEX_SHADER, GL_FRAGMENT_SHADER };
    GLint status;
    for (unsigned int i = 0; i < 2; i++) {
        GLuint shader = glCreateShader_fn(stages[i]);
        glShaderSource_fn(shader, 1, &sources[i], NULL);
        glCompileShader_fn(shader);
        glGetShaderiv_fn(shader, GL_COMPILE_STATUS, &status);
        if (!status)
            return fail("shader compile");
        glAttachShader_fn(program, shader);
    }
    glLinkProgram_fn(program);
    glGetProgramiv_fn(program, GL_LINK_STATUS, &status);
    if (!status)
        return fail("shader link");

    glUseProgram_fn(program);
    glViewport_fn(0, 0, width, height);
    glClearColor_fn(0, 0, 1, 1);
    glClear_fn(GL_COLOR_BUFFER_BIT);
    glDrawArrays_fn(GL_TRIANGLES, 0, 3);
    if (scanout) {
        glFinish_fn();
        int ret = glGetError_fn() == GL_NO_ERROR ? present_decon_buffer(dma_fd) : 1;
        close(dma_fd);
        if (!ret)
            printf("Panfrost DMA-BUF drawn and presented on DECON: %s\n", renderer);
        return ret;
    }

    fprintf(stderr, "Panfrost probe: reading rendered pixels\n");
    GLubyte center[4] = {0}, corner[4] = {0};
    glReadPixels_fn(width / 2, height / 2, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, center);
    glReadPixels_fn(0, height - 1, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, corner);
    GLenum gl_error = glGetError_fn();
    if (gl_error != GL_NO_ERROR ||
        memcmp(center, (GLubyte[]){255, 0, 0, 255}, sizeof(center)) ||
        memcmp(corner, (GLubyte[]){0, 0, 255, 255}, sizeof(corner))) {
        fprintf(stderr, "Panfrost pixels: error=%#x center=%u,%u,%u,%u corner=%u,%u,%u,%u\n",
                gl_error, center[0], center[1], center[2], center[3],
                corner[0], corner[1], corner[2], corner[3]);
        return fail("GPU pixel verification");
    }
    if (linear) {
        int ret = verify_prime_import(argv[1], dma_fd);
        close(dma_fd);
        if (ret)
            return ret;
        puts("Panfrost linear DMA-BUF render, readback and PRIME reimport verified");
    }
    printf("Panfrost GPU draw and readback verified: %s\n", renderer);
    return 0;
}
