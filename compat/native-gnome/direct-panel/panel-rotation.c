/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "panel-rotation.h"

#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>

enum { PANEL_WIDTH = 1440, PANEL_HEIGHT = 2960, RGBX8888 = 2 };
typedef EGLBoolean (*Allocate)(EGLint, EGLint, EGLint, EGLint, EGLint *, EGLClientBuffer *);
typedef EGLBoolean (*GetHandle)(EGLDisplay, EGLClientBuffer, void **);

struct target {
    EGLClientBuffer buffer;
    EGLImageKHR image;
    GLuint texture, fbo;
    int dma_buf;
};

/* This state belongs to the one GNOME direct panel renderer. Its context
 * and at most three native scanout buffers share the renderer's lifetime. */
static struct {
    EGLDisplay display;
    EGLContext context;
    EGLSurface surface;
    GLuint program;
    GLint sampler, transform;
    Allocate allocate;
    GetHandle get_handle;
    PFNEGLCREATEIMAGEKHRPROC create_image;
    PFNEGLDESTROYIMAGEKHRPROC destroy_image;
    PFNGLEGLIMAGETARGETTEXTURE2DOESPROC image_texture;
    struct target targets[G955N_ROTATION_SLOTS];
} panel;

static GLuint shader(GLenum type, const char *code)
{
    GLuint id = glCreateShader(type);
    GLint valid = GL_FALSE;
    glShaderSource(id, 1, &code, NULL);
    glCompileShader(id);
    glGetShaderiv(id, GL_COMPILE_STATUS, &valid);
    if (valid)
        return id;
    glDeleteShader(id);
    return 0;
}

static bool init_program(void)
{
    const GLuint vs = shader(GL_VERTEX_SHADER,
        "attribute vec2 vert; varying vec2 uv; void main() {"
        "gl_Position=vec4(vert,0.0,1.0); uv=vert*0.5+0.5; }");
    const GLuint fs = shader(GL_FRAGMENT_SHADER,
        "precision highp float; varying vec2 uv; uniform sampler2D image;"
        "uniform mat3 transform; void main() {"
        "gl_FragColor=texture2D(image,(transform*vec3(uv,1.0)).xy); }");
    GLint linked = GL_FALSE;
    if (vs && fs) {
        panel.program = glCreateProgram();
        glAttachShader(panel.program, vs);
        glAttachShader(panel.program, fs);
        glBindAttribLocation(panel.program, 0, "vert");
        glLinkProgram(panel.program);
        glGetProgramiv(panel.program, GL_LINK_STATUS, &linked);
    }
    if (vs)
        glDeleteShader(vs);
    if (fs)
        glDeleteShader(fs);
    if (!linked)
        return false;
    panel.sampler = glGetUniformLocation(panel.program, "image");
    panel.transform = glGetUniformLocation(panel.program, "transform");
    return panel.sampler >= 0 && panel.transform >= 0;
}

static bool init_context(EGLDisplay display)
{
    const EGLint config_attrs[] = {
        EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
        EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_NONE,
    };
    const EGLint context_attrs[] = {EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE};
    const EGLint surface_attrs[] = {EGL_WIDTH, 1, EGL_HEIGHT, 1, EGL_NONE};
    EGLConfig config;
    EGLint count = 0;

    panel.allocate = (Allocate)eglGetProcAddress("eglHybrisCreateNativeBuffer");
    panel.get_handle = (GetHandle)eglGetProcAddress("eglHybrisNativeBufferHandle");
    panel.create_image = (PFNEGLCREATEIMAGEKHRPROC)eglGetProcAddress("eglCreateImageKHR");
    panel.destroy_image = (PFNEGLDESTROYIMAGEKHRPROC)eglGetProcAddress("eglDestroyImageKHR");
    panel.image_texture = (PFNGLEGLIMAGETARGETTEXTURE2DOESPROC)eglGetProcAddress("glEGLImageTargetTexture2DOES");
    if (!panel.allocate || !panel.get_handle || !panel.create_image ||
        !panel.destroy_image || !panel.image_texture ||
        eglQueryAPI() != EGL_OPENGL_ES_API ||
        !eglChooseConfig(display, config_attrs, &config, 1, &count) || count != 1)
        return false;
    panel.display = display;
    panel.context = eglCreateContext(display, config, EGL_NO_CONTEXT, context_attrs);
    panel.surface = eglCreatePbufferSurface(display, config, surface_attrs);
    return panel.context != EGL_NO_CONTEXT && panel.surface != EGL_NO_SURFACE;
}

static EGLImageKHR create_image(EGLClientBuffer buffer)
{
    const EGLint attributes[] = {EGL_IMAGE_PRESERVED_KHR, EGL_TRUE, EGL_NONE};
    return panel.create_image(panel.display, EGL_NO_CONTEXT, EGL_NATIVE_BUFFER_ANDROID, buffer, attributes);
}

static void bind_image(GLuint texture, EGLImageKHR image)
{
    glBindTexture(GL_TEXTURE_2D, texture);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    panel.image_texture(GL_TEXTURE_2D, (GLeglImageOES)image);
}

static bool init_target(struct target *target)
{
    const EGLint render_texture_usage = 0x200 | 0x100; /* Android 9 HW_RENDER | HW_TEXTURE */
    EGLint stride = 0;
    void *handle = NULL;
    if (!panel.allocate(PANEL_WIDTH, PANEL_HEIGHT, render_texture_usage, RGBX8888,
                        &stride, &target->buffer) || stride != PANEL_WIDTH ||
        !panel.get_handle(panel.display, target->buffer, &handle) || !handle)
        return false;

    const int *fields = handle;
    if (fields[0] != 3 * sizeof(int) || fields[1] != 1 || fields[2] != 46)
        return false;
    uint32_t magic;
    uint64_t internal;
    memcpy(&magic, (const unsigned char *)handle + 24, sizeof(magic));
    memcpy(&internal, (const unsigned char *)handle + 56, sizeof(internal));
    if (magic != 0x03141592 || internal != RGBX8888 || fcntl(fields[3], F_GETFD) < 0)
        return false;

    target->dma_buf = fields[3];
    target->image = create_image(target->buffer);
    if (target->image == EGL_NO_IMAGE_KHR)
        return false;
    glGenTextures(1, &target->texture);
    bind_image(target->texture, target->image);
    glGenFramebuffers(1, &target->fbo);
    glBindFramebuffer(GL_FRAMEBUFFER, target->fbo);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, target->texture, 0);
    return glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE &&
           glGetError() == GL_NO_ERROR;
}

static bool draw(EGLClientBuffer input, struct target *target, const GLfloat *matrix)
{
    static const GLfloat quad[] = {-1, -1, 1, -1, -1, 1, 1, 1};
    EGLImageKHR src = create_image(input);
    if (src == EGL_NO_IMAGE_KHR)
        return false;
    GLuint texture;
    glGenTextures(1, &texture);
    glActiveTexture(GL_TEXTURE0);
    bind_image(texture, src);
    glBindFramebuffer(GL_FRAMEBUFFER, target->fbo);
    glViewport(0, 0, PANEL_WIDTH, PANEL_HEIGHT);
    glUseProgram(panel.program);
    glUniform1i(panel.sampler, 0);
    glUniformMatrix3fv(panel.transform, 1, GL_FALSE, matrix);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, quad);
    glEnableVertexAttribArray(0);
    glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
    glFinish();
    bool ok = glGetError() == GL_NO_ERROR;
    glDeleteTextures(1, &texture);
    return panel.destroy_image(panel.display, src) && ok;
}

bool g955n_rotate_panel_buffer(EGLClientBuffer source, unsigned int degrees,
                              unsigned int slot, int *dma_buf,
                              EGLClientBuffer *destination)
{
    /* Column-major maps from logical UV to source texture sampling UV. */
    static const GLfloat left[] = {0,-1,0, 1,0,0, 0,1,1};
    static const GLfloat inverted[] = {-1,0,0, 0,-1,0, 1,1,1};
    static const GLfloat right[] = {0,1,0, -1,0,0, 1,0,1};
    const GLfloat *matrix = degrees == 90 ? left :
                            degrees == 180 ? inverted :
                            degrees == 270 ? right : NULL;
    if (!source || !matrix || slot >= G955N_ROTATION_SLOTS || !dma_buf)
        return false;

    EGLDisplay display = eglGetCurrentDisplay();
    EGLContext producer = eglGetCurrentContext();
    EGLSurface draw_surface = eglGetCurrentSurface(EGL_DRAW);
    EGLSurface read_surface = eglGetCurrentSurface(EGL_READ);
    if (display == EGL_NO_DISPLAY || producer == EGL_NO_CONTEXT)
        return false;
    if (panel.display == EGL_NO_DISPLAY && !init_context(display))
        return false;
    if (display != panel.display ||
        !eglMakeCurrent(display, panel.surface, panel.surface, panel.context))
        return false;

    struct target *target = &panel.targets[slot];
    bool ok = (panel.program || init_program()) &&
              (target->fbo || init_target(target)) &&
              draw(source, target, matrix);
    if (!eglMakeCurrent(display, draw_surface, read_surface, producer) || !ok)
        return false;
    *dma_buf = target->dma_buf;
    if (destination)
        *destination = target->buffer;
    return true;
}
