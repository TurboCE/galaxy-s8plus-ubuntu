/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "panel-rotation.h"

#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <fcntl.h>

enum { PANEL_WIDTH = 1440, PANEL_HEIGHT = 2960, RGBX8888 = 2 };
typedef EGLBoolean (*Allocate)(EGLint, EGLint, EGLint, EGLint, EGLint *, EGLClientBuffer *);
typedef EGLBoolean (*GetHandle)(EGLDisplay, EGLClientBuffer, void **);

#define ROTATION_GL_FUNCTIONS(F) \
    F(PFNGLACTIVETEXTUREPROC, glActiveTexture) \
    F(PFNGLATTACHSHADERPROC, glAttachShader) \
    F(PFNGLBINDATTRIBLOCATIONPROC, glBindAttribLocation) \
    F(PFNGLBINDFRAMEBUFFERPROC, glBindFramebuffer) \
    F(PFNGLBINDTEXTUREPROC, glBindTexture) \
    F(PFNGLCHECKFRAMEBUFFERSTATUSPROC, glCheckFramebufferStatus) \
    F(PFNGLCOMPILESHADERPROC, glCompileShader) \
    F(PFNGLCREATEPROGRAMPROC, glCreateProgram) \
    F(PFNGLCREATESHADERPROC, glCreateShader) \
    F(PFNGLDELETESHADERPROC, glDeleteShader) \
    F(PFNGLDELETETEXTURESPROC, glDeleteTextures) \
    F(PFNGLDRAWARRAYSPROC, glDrawArrays) \
    F(PFNGLENABLEVERTEXATTRIBARRAYPROC, glEnableVertexAttribArray) \
    F(PFNGLFINISHPROC, glFinish) \
    F(PFNGLFRAMEBUFFERTEXTURE2DPROC, glFramebufferTexture2D) \
    F(PFNGLGENFRAMEBUFFERSPROC, glGenFramebuffers) \
    F(PFNGLGENTEXTURESPROC, glGenTextures) \
    F(PFNGLGETERRORPROC, glGetError) \
    F(PFNGLGETPROGRAMIVPROC, glGetProgramiv) \
    F(PFNGLGETSHADERIVPROC, glGetShaderiv) \
    F(PFNGLGETUNIFORMLOCATIONPROC, glGetUniformLocation) \
    F(PFNGLLINKPROGRAMPROC, glLinkProgram) \
    F(PFNGLSHADERSOURCEPROC, glShaderSource) \
    F(PFNGLTEXPARAMETERIPROC, glTexParameteri) \
    F(PFNGLUNIFORM1IPROC, glUniform1i) \
    F(PFNGLUNIFORMMATRIX3FVPROC, glUniformMatrix3fv) \
    F(PFNGLUSEPROGRAMPROC, glUseProgram) \
    F(PFNGLVERTEXATTRIBPOINTERPROC, glVertexAttribPointer) \
    F(PFNGLVIEWPORTPROC, glViewport) \
    F(PFNGLGETSTRINGPROC, glGetString)

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
    struct {
#define DECLARE_GL(type, name) type name;
        ROTATION_GL_FUNCTIONS(DECLARE_GL)
#undef DECLARE_GL
    } gl;
    Allocate allocate;
    GetHandle get_handle;
    PFNEGLCREATEIMAGEKHRPROC create_image;
    PFNEGLDESTROYIMAGEKHRPROC destroy_image;
    PFNGLEGLIMAGETARGETTEXTURE2DOESPROC image_texture;
    struct target targets[G955N_ROTATION_SLOTS];
} panel;

static bool egl_failure(const char *operation)
{
    fprintf(stderr, "G955N Mali rotation %s: EGL error 0x%04x\n",
            operation, eglGetError());
    return false;
}

static bool load_gl(void)
{
    /* GNOME can load the desktop GL dispatcher before this EGL backend.
     * Resolve against the current Mali EGL provider, not the process PLT. */
#define RESOLVE_GL(type, name) \
    panel.gl.name = (type)eglGetProcAddress(#name); \
    if (!panel.gl.name) \
        return false;
    ROTATION_GL_FUNCTIONS(RESOLVE_GL)
#undef RESOLVE_GL
    const char *renderer = (const char *)panel.gl.glGetString(GL_RENDERER);
    return renderer && strstr(renderer, "Mali-G71");
}

static GLuint shader(GLenum type, const char *code)
{
    GLuint id = panel.gl.glCreateShader(type);
    GLint valid = GL_FALSE;
    panel.gl.glShaderSource(id, 1, &code, NULL);
    panel.gl.glCompileShader(id);
    panel.gl.glGetShaderiv(id, GL_COMPILE_STATUS, &valid);
    if (valid)
        return id;
    panel.gl.glDeleteShader(id);
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
        panel.program = panel.gl.glCreateProgram();
        panel.gl.glAttachShader(panel.program, vs);
        panel.gl.glAttachShader(panel.program, fs);
        panel.gl.glBindAttribLocation(panel.program, 0, "vert");
        panel.gl.glLinkProgram(panel.program);
        panel.gl.glGetProgramiv(panel.program, GL_LINK_STATUS, &linked);
    }
    if (vs)
        panel.gl.glDeleteShader(vs);
    if (fs)
        panel.gl.glDeleteShader(fs);
    if (!linked)
        return false;
    panel.sampler = panel.gl.glGetUniformLocation(panel.program, "image");
    panel.transform = panel.gl.glGetUniformLocation(panel.program, "transform");
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
    panel.gl.glBindTexture(GL_TEXTURE_2D, texture);
    panel.gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    panel.gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    panel.gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    panel.gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
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
    panel.gl.glGenTextures(1, &target->texture);
    bind_image(target->texture, target->image);
    panel.gl.glGenFramebuffers(1, &target->fbo);
    panel.gl.glBindFramebuffer(GL_FRAMEBUFFER, target->fbo);
    panel.gl.glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, target->texture, 0);
    return panel.gl.glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE &&
           panel.gl.glGetError() == GL_NO_ERROR;
}

static bool draw(EGLClientBuffer input, struct target *target, const GLfloat *matrix)
{
    static const GLfloat quad[] = {-1, -1, 1, -1, -1, 1, 1, 1};
    EGLImageKHR src = create_image(input);
    if (src == EGL_NO_IMAGE_KHR)
        return egl_failure("source import");
    GLuint texture;
    panel.gl.glGenTextures(1, &texture);
    panel.gl.glActiveTexture(GL_TEXTURE0);
    bind_image(texture, src);
    panel.gl.glBindFramebuffer(GL_FRAMEBUFFER, target->fbo);
    panel.gl.glViewport(0, 0, PANEL_WIDTH, PANEL_HEIGHT);
    panel.gl.glUseProgram(panel.program);
    panel.gl.glUniform1i(panel.sampler, 0);
    panel.gl.glUniformMatrix3fv(panel.transform, 1, GL_FALSE, matrix);
    panel.gl.glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, quad);
    panel.gl.glEnableVertexAttribArray(0);
    panel.gl.glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
    panel.gl.glFinish();
    GLenum error = panel.gl.glGetError();
    if (error != GL_NO_ERROR)
        fprintf(stderr, "G955N Mali rotation draw: GL error 0x%04x\n", error);
    panel.gl.glDeleteTextures(1, &texture);
    return panel.destroy_image(panel.display, src) && error == GL_NO_ERROR;
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
        return egl_failure("missing current context");
    if (panel.display == EGL_NO_DISPLAY && !init_context(display))
        return egl_failure("create context");
    if (display != panel.display ||
        !eglMakeCurrent(display, panel.surface, panel.surface, panel.context))
        return egl_failure("bind context");

    struct target *target = &panel.targets[slot];
    bool program_ready = panel.program || (load_gl() && init_program());
    bool target_ready = program_ready && (target->fbo || init_target(target));
    if (!target_ready)
        egl_failure(program_ready ? "allocate scanout buffer" : "create program");
    bool ok = target_ready && draw(source, target, matrix);
    if (!eglMakeCurrent(display, draw_surface, read_surface, producer))
        return egl_failure("restore compositor context");
    if (!ok)
        return false;
    *dma_buf = target->dma_buf;
    if (destination)
        *destination = target->buffer;
    return true;
}
