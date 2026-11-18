/* Native G955N offscreen shader/readback probe. Does not qualify desktop scanout. */
#include <EGL/egl.h>
#include <GLES2/gl2.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/utsname.h>
#include <time.h>

#ifndef GPU_WIDTH
#define GPU_WIDTH 64
#endif
#ifndef GPU_HEIGHT
#define GPU_HEIGHT 64
#endif
#ifndef GPU_FRAMES
#define GPU_FRAMES 300
#endif

#define EGL_CHECK(test) do { if (!(test)) { fprintf(stderr, "EGL failed at line %d: 0x%x\n", __LINE__, eglGetError()); return 1; } } while (0)
static GLuint shader(GLenum type, const char *source) {
    GLuint object = glCreateShader(type);
    glShaderSource(object, 1, &source, NULL);
    glCompileShader(object);
    GLint ok = 0;
    glGetShaderiv(object, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[2048];
        glGetShaderInfoLog(object, sizeof(log), NULL, log);
        fprintf(stderr, "Shader failed: %s\n", log);
        exit(1);
    }
    return object;
}
int main(void) {
    char model[256] = {0};
    FILE *file = fopen("/proc/device-tree/model", "r");
    struct utsname identity;
    if (!file) return 2;
    size_t model_bytes = fread(model, 1, sizeof(model) - 1, file);
    fclose(file);
    if (!model_bytes || !strstr(model, "SM-G955N") || uname(&identity) || !strstr(identity.release, "g955n-ubuntu")) return 2;
    EGLDisplay display = eglGetDisplay(EGL_DEFAULT_DISPLAY);
    EGLint major, minor;
    EGL_CHECK(display != EGL_NO_DISPLAY && eglInitialize(display, &major, &minor));
    EGL_CHECK(eglBindAPI(EGL_OPENGL_ES_API));
    EGLint attributes[] = {EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
                          EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_ALPHA_SIZE, 8, EGL_NONE};
    EGLConfig config;
    EGLint count;
    EGL_CHECK(eglChooseConfig(display, attributes, &config, 1, &count) && count > 0);
    EGLint dimensions[] = {EGL_WIDTH, GPU_WIDTH, EGL_HEIGHT, GPU_HEIGHT, EGL_NONE};
    EGLSurface surface = eglCreatePbufferSurface(display, config, dimensions);
    EGLint context_attributes[] = {EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE};
    EGLContext context = eglCreateContext(display, config, EGL_NO_CONTEXT, context_attributes);
    EGL_CHECK(surface != EGL_NO_SURFACE && context != EGL_NO_CONTEXT);
    EGL_CHECK(eglMakeCurrent(display, surface, surface, context));
    const char *renderer = (const char *)glGetString(GL_RENDERER);
    printf("GL_VENDOR=%s\nGL_RENDERER=%s\nGL_VERSION=%s\n", glGetString(GL_VENDOR), renderer, glGetString(GL_VERSION));
    if (!renderer || !strstr(renderer, "Mali") || strstr(renderer, "llvmpipe")) return 3;
    GLuint program = glCreateProgram();
    GLuint vertex = shader(GL_VERTEX_SHADER, "attribute vec2 position; void main() { gl_Position=vec4(position,0.,1.); }");
    GLuint fragment = shader(GL_FRAGMENT_SHADER, "precision mediump float; uniform vec4 color; void main() { gl_FragColor=color; }");
    glAttachShader(program, vertex);
    glAttachShader(program, fragment);
    glBindAttribLocation(program, 0, "position");
    glLinkProgram(program);
    GLint linked = 0;
    glGetProgramiv(program, GL_LINK_STATUS, &linked);
    if (!linked) return 4;
    glUseProgram(program);
    GLfloat triangle[] = {-1,-1, 3,-1, -1,3};
    GLuint buffer;
    glGenBuffers(1, &buffer);
    glBindBuffer(GL_ARRAY_BUFFER, buffer);
    glBufferData(GL_ARRAY_BUFFER, sizeof(triangle), triangle, GL_STATIC_DRAW);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, NULL);
    glEnableVertexAttribArray(0);
    GLint uniform = glGetUniformLocation(program, "color");
    glViewport(0, 0, GPU_WIDTH, GPU_HEIGHT);
    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);
    for (int frame = 0; frame < GPU_FRAMES; frame++) {
        int expected_red = frame % 2 ? 191 : 64;
        glUniform4f(uniform, frame % 2 ? .75f : .25f, .5f, .75f, 1.f);
        glDrawArrays(GL_TRIANGLES, 0, 3);
        glFinish();
        unsigned char pixel[4] = {0};
        glReadPixels(GPU_WIDTH / 2, GPU_HEIGHT / 2, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel);
        GLenum error = glGetError();
        if (error != GL_NO_ERROR || abs(pixel[0]-expected_red)>2 || abs(pixel[1]-128)>2 || abs(pixel[2]-191)>2 || pixel[3]!=255) {
            fprintf(stderr, "Frame %d failed: GL=0x%x RGBA=%u,%u,%u,%u\n", frame,error,pixel[0],pixel[1],pixel[2],pixel[3]);
            return 5;
        }
    }
    clock_gettime(CLOCK_MONOTONIC, &end);
    printf("PASS: %d shader frames at %dx%d with alternating verified readback, %.3f seconds; offscreen only\n", GPU_FRAMES, GPU_WIDTH, GPU_HEIGHT, (end.tv_sec-start.tv_sec)+(end.tv_nsec-start.tv_nsec)/1e9);
    glDeleteBuffers(1, &buffer);
    glDeleteProgram(program);
    glDeleteShader(vertex);
    glDeleteShader(fragment);
    eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
    eglDestroyContext(display, context);
    eglDestroySurface(display, surface);
    eglTerminate(display);
    return 0;
}
