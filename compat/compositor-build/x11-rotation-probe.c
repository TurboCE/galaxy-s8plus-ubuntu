/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Exercise the Mali rotation pass between two full-size gralloc buffers. */
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#include <X11/Xlib.h>
#include <fcntl.h>
#include <stdbool.h>
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

static CreateBuffer create_buffer;
static ReleaseBuffer release_buffer;
static GetHandle get_handle;
static PFNEGLCREATEIMAGEKHRPROC create_image;
static PFNEGLDESTROYIMAGEKHRPROC destroy_image;
static PFNGLEGLIMAGETARGETTEXTURE2DOESPROC image_texture;

static struct target make_target(EGLDisplay display, int width, int height)
{
    struct target target = {.width = width, .height = height};
    const EGLint rgbx8888 = 2; /* Android 9 HAL_PIXEL_FORMAT_RGBX_8888 */
    const EGLint gpu_usage = 0x100 | 0x200; /* HW_TEXTURE | HW_RENDER */
    EGLint stride;
    REQUIRE(create_buffer(width, height, gpu_usage, rgbx8888, &stride, &target.buffer));
    REQUIRE(stride == width);
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

static void destroy_target(EGLDisplay display, const struct target *target)
{
    glDeleteFramebuffers(1, &target->framebuffer);
    glDeleteTextures(1, &target->texture);
    REQUIRE(destroy_image(display, target->image));
    REQUIRE(release_buffer(target->buffer));
}

static GLuint compile_shader(GLenum type, const char *source)
{
    GLuint shader = glCreateShader(type);
    glShaderSource(shader, 1, &source, NULL);
    glCompileShader(shader);
    GLint compiled;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &compiled);
    REQUIRE(compiled);
    return shader;
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

static void rotate_and_verify(GLuint program, const struct target *src, const struct target *dst,
                              bool clockwise, const unsigned int colors[4][3])
{
    static const GLfloat quad[] = {-1, -1, 1, -1, -1, 1, 1, 1};
    static const int corner_map[][4] = {{2, 0, 3, 1}, {1, 3, 0, 2}};
    glBindFramebuffer(GL_FRAMEBUFFER, dst->framebuffer);
    glViewport(0, 0, dst->width, dst->height);
    glUseProgram(program);
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, src->texture);
    glUniform1i(glGetUniformLocation(program, "source"), 0);
    glUniform1i(glGetUniformLocation(program, "clockwise"), clockwise);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, quad);
    glEnableVertexAttribArray(0);
    glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
    glFinish();

    /* Diagnostic readback only. The rotation pass itself does not map either
     * gralloc buffer and the destination remains a native DMA-BUF. */
    for (int corner = 0; corner < 4; corner++) {
        unsigned char pixel[4] = {0};
        glReadPixels((1 + 2 * (corner % 2)) * dst->width / 4,
                     (1 + 2 * (corner / 2)) * dst->height / 4,
                     1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel);
        REQUIRE(glGetError() == GL_NO_ERROR);
        for (int k = 0; k < 3; k++)
            REQUIRE(pixel[k] == colors[corner_map[clockwise][corner]][k]);
    }
}

int main(int argc, char **argv)
{
    REQUIRE(argc == 2 && !strcmp(argv[1], "--run-sm-g955n-rotation-probe"));
    FILE *model = fopen("/proc/device-tree/model", "r");
    char name[128] = {0};
    REQUIRE(model && fgets(name, sizeof(name), model) && strstr(name, "SM-G955N"));
    fclose(model);
    REQUIRE(getuid() == 1000);
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

    const struct target src = make_target(dpy, 2960, 1440);
    const struct target dst = make_target(dpy, 1440, 2960);
    REQUIRE(src.fd != dst.fd);
    printf("Source and destination are full-size native RGBX gralloc buffers\n");
    const unsigned int colors[][3] = {{255, 0, 0}, {0, 255, 0}, {0, 0, 255}, {255, 255, 0}};
    const GLuint vertex = compile_shader(GL_VERTEX_SHADER,
        "attribute vec2 vertex; varying vec2 uv; void main() {"
        "gl_Position=vec4(vertex,0.0,1.0); uv=vertex*0.5+0.5; }");
    const GLuint fragment = compile_shader(GL_FRAGMENT_SHADER,
        "precision highp float; varying vec2 uv; uniform sampler2D source; uniform bool clockwise;"
        "void main() { vec2 st = clockwise ? vec2(1.0-uv.y,uv.x) : vec2(uv.y,1.0-uv.x);"
        "gl_FragColor=texture2D(source,st); }");
    const GLuint program = glCreateProgram();
    glAttachShader(program, vertex);
    glAttachShader(program, fragment);
    glBindAttribLocation(program, 0, "vertex");
    glLinkProgram(program);
    GLint linked;
    glGetProgramiv(program, GL_LINK_STATUS, &linked);
    REQUIRE(linked);
    fill_source(&src, colors);
    rotate_and_verify(program, &src, &dst, false, colors);
    rotate_and_verify(program, &src, &dst, true, colors);
    puts("Clockwise and counterclockwise native-buffer pixels verified");
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    glBindTexture(GL_TEXTURE_2D, 0);
    glUseProgram(0);
    glDeleteProgram(program);
    glDeleteShader(vertex);
    glDeleteShader(fragment);
    glFinish();
    destroy_target(dpy, &dst);
    destroy_target(dpy, &src);
    REQUIRE(eglMakeCurrent(dpy, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT));
    REQUIRE(eglDestroySurface(dpy, surface));
    REQUIRE(eglDestroyContext(dpy, context));
    REQUIRE(eglTerminate(dpy));
    XCloseDisplay(x11);
}
