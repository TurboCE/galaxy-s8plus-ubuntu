/* Optional lazy-loaded Android9 EGLImage/FBO test. Never creates a window or
 * opens HWC/display nodes. The caller retains its imported mapper buffer until
 * this function has destroyed all EGL/GL objects and released buffer refs.
 */
#include <nativebase/nativebase.h>
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#include <cstdio>
#include <cstddef>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <new>
#include <unistd.h>
#define EGL_FUNCTIONS(X) X(eglGetDisplay) X(eglInitialize) X(eglBindAPI) X(eglChooseConfig) X(eglCreatePbufferSurface) X(eglCreateContext) X(eglMakeCurrent) X(eglGetProcAddress) X(eglQueryString) X(eglGetError) X(eglDestroyContext) X(eglDestroySurface) X(eglTerminate)
#define GL_FUNCTIONS(X) X(glGetString) X(glGetError) X(glGenTextures) X(glBindTexture) X(glTexParameteri) X(glDeleteTextures) X(glGenFramebuffers) X(glBindFramebuffer) X(glFramebufferTexture2D) X(glCheckFramebufferStatus) X(glDeleteFramebuffers) X(glCreateShader) X(glShaderSource) X(glCompileShader) X(glGetShaderiv) X(glDeleteShader) X(glCreateProgram) X(glAttachShader) X(glBindAttribLocation) X(glLinkProgram) X(glGetProgramiv) X(glUseProgram) X(glDeleteProgram) X(glGenBuffers) X(glBindBuffer) X(glBufferData) X(glDeleteBuffers) X(glVertexAttribPointer) X(glEnableVertexAttribArray) X(glGetUniformLocation) X(glUniform4f) X(glViewport) X(glDrawArrays) X(glFinish) X(glReadPixels)
struct Api {
#define FIELD(name) decltype(&name) name=nullptr;
    EGL_FUNCTIONS(FIELD) GL_FUNCTIONS(FIELD)
#undef FIELD
};
struct TrackedBuffer { ANativeWindowBuffer buffer; int refs=1; };
static_assert(offsetof(TrackedBuffer,buffer)==0,"Native buffer must be first");
static_assert(offsetof(ANativeWindowBuffer,common)==0,"Public Android native ABI");
static_assert(sizeof(ANativeWindowBuffer)==168,"Pinned Android9 AArch64 native buffer layout");
static void retain(android_native_base_t *base){__atomic_add_fetch(&reinterpret_cast<TrackedBuffer *>(base)->refs,1,__ATOMIC_RELAXED);}
static void release(android_native_base_t *base){__atomic_sub_fetch(&reinterpret_cast<TrackedBuffer *>(base)->refs,1,__ATOMIC_RELAXED);}
static GLuint make_shader(Api &a,GLenum type,const char *text){
    GLuint shader=a.glCreateShader(type); a.glShaderSource(shader,1,&text,nullptr);a.glCompileShader(shader);
    GLint ok=0;a.glGetShaderiv(shader,GL_COMPILE_STATUS,&ok);
    if(!ok){a.glDeleteShader(shader);return 0;}return shader;
}
extern "C" int g955n_test_native_buffer(const native_handle_t *handle,uint32_t width,uint32_t height,uint32_t stride,uint64_t usage){
    if(!handle||width!=64||height!=64||stride<width||stride>4096)return 2;
    void *driver=dlopen("/vendor/lib64/egl/libGLES_mali.so",RTLD_NOW|RTLD_LOCAL);
    if(!driver){fprintf(stderr,"Mali driver load failed: %s\n",dlerror());return 3;}
    Api a;
#define LOAD(name) a.name=reinterpret_cast<decltype(a.name)>(dlsym(driver,#name));if(!a.name)return 4;
    EGL_FUNCTIONS(LOAD) GL_FUNCTIONS(LOAD)
#undef LOAD
    auto createImage=reinterpret_cast<PFNEGLCREATEIMAGEKHRPROC>(a.eglGetProcAddress("eglCreateImageKHR"));
    auto destroyImage=reinterpret_cast<PFNEGLDESTROYIMAGEKHRPROC>(a.eglGetProcAddress("eglDestroyImageKHR"));
    auto imageTarget=reinterpret_cast<PFNGLEGLIMAGETARGETTEXTURE2DOESPROC>(a.eglGetProcAddress("glEGLImageTargetTexture2DOES"));
    if(!createImage||!destroyImage||!imageTarget)return 5;
    auto *native=new(std::nothrow)TrackedBuffer;
    if(!native)return 6;
    auto &b=native->buffer;
    b.common.incRef=retain;b.common.decRef=release;
    b.width=width;b.height=height;b.stride=stride;b.format=1;b.layerCount=1;
    b.usage_deprecated=static_cast<int>(usage);b.usage=usage;b.handle=handle;
    memset(b.reserved,0,sizeof(b.reserved));memset(b.reserved_proc,0,sizeof(b.reserved_proc));
    EGLDisplay display=EGL_NO_DISPLAY;EGLContext context=EGL_NO_CONTEXT;EGLSurface surface=EGL_NO_SURFACE;EGLImageKHR image=EGL_NO_IMAGE_KHR;
    GLuint texture=0,fbo=0,vertex=0,fragment=0,program=0,vbo=0;
    int result=7;bool initialized=false,current=false;
    do{
        display=a.eglGetDisplay(EGL_DEFAULT_DISPLAY);
        EGLint major=0,minor=0;
        if(display==EGL_NO_DISPLAY||!a.eglInitialize(display,&major,&minor))break;
        initialized=true;
        const char *extensions=a.eglQueryString(display,EGL_EXTENSIONS);
        if(!extensions||!strstr(extensions,"EGL_ANDROID_image_native_buffer")||!a.eglBindAPI(EGL_OPENGL_ES_API))break;
        const EGLint attrs[]={EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,EGL_OPENGL_ES2_BIT,EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,8,EGL_NONE};
        EGLConfig config;EGLint count=0;
        if(!a.eglChooseConfig(display,attrs,&config,1,&count)||count!=1)break;
        const EGLint size[]={EGL_WIDTH,1,EGL_HEIGHT,1,EGL_NONE};
        surface=a.eglCreatePbufferSurface(display,config,size);
        const EGLint version[]={EGL_CONTEXT_CLIENT_VERSION,2,EGL_NONE};
        context=a.eglCreateContext(display,config,EGL_NO_CONTEXT,version);
        if(surface==EGL_NO_SURFACE||context==EGL_NO_CONTEXT||!a.eglMakeCurrent(display,surface,surface,context))break;
        current=true;
        const char *renderer=reinterpret_cast<const char *>(a.glGetString(GL_RENDERER));
        printf("native_buffer_GL_RENDERER=%s\n",renderer ? renderer:"null");
        if(!renderer||!strstr(renderer,"Mali")||strstr(renderer,"llvmpipe"))break;
        const EGLint imageAttrs[]={EGL_IMAGE_PRESERVED_KHR,EGL_TRUE,EGL_NONE};
        image=createImage(display,EGL_NO_CONTEXT,EGL_NATIVE_BUFFER_ANDROID,reinterpret_cast<EGLClientBuffer>(&b),imageAttrs);
        if(image==EGL_NO_IMAGE_KHR)break;
        a.glGenTextures(1,&texture);a.glBindTexture(GL_TEXTURE_2D,texture);
        a.glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);a.glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
        imageTarget(GL_TEXTURE_2D,reinterpret_cast<GLeglImageOES>(image));
        a.glGenFramebuffers(1,&fbo);a.glBindFramebuffer(GL_FRAMEBUFFER,fbo);a.glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,texture,0);
        if(a.glGetError()!=GL_NO_ERROR||a.glCheckFramebufferStatus(GL_FRAMEBUFFER)!=GL_FRAMEBUFFER_COMPLETE)break;
        vertex=make_shader(a,GL_VERTEX_SHADER,"attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}");
        fragment=make_shader(a,GL_FRAGMENT_SHADER,"precision mediump float;uniform vec4 color;void main(){gl_FragColor=color;}");
        if(!vertex||!fragment)break;
        program=a.glCreateProgram();a.glAttachShader(program,vertex);a.glAttachShader(program,fragment);a.glBindAttribLocation(program,0,"p");a.glLinkProgram(program);
        GLint linked=0;a.glGetProgramiv(program,GL_LINK_STATUS,&linked);if(!linked)break;
        a.glUseProgram(program);GLfloat vertices[]={-1,-1,3,-1,-1,3};
        a.glGenBuffers(1,&vbo);a.glBindBuffer(GL_ARRAY_BUFFER,vbo);a.glBufferData(GL_ARRAY_BUFFER,sizeof(vertices),vertices,GL_STATIC_DRAW);
        a.glVertexAttribPointer(0,2,GL_FLOAT,GL_FALSE,0,nullptr);a.glEnableVertexAttribArray(0);a.glViewport(0,0,width,height);
        GLint color=a.glGetUniformLocation(program,"color");
        bool verified=true;
        for(int frame=0;frame<3;++frame){
            const int red=frame==1 ? 191:64;
            a.glUniform4f(color,frame==1 ? .75f:.25f,.5f,.75f,1.f);a.glDrawArrays(GL_TRIANGLES,0,3);a.glFinish();
            unsigned char pixel[4]={};a.glReadPixels(width/2,height/2,1,1,GL_RGBA,GL_UNSIGNED_BYTE,pixel);
            if(a.glGetError()!=GL_NO_ERROR||abs(pixel[0]-red)>2||abs(pixel[1]-128)>2||abs(pixel[2]-191)>2||pixel[3]!=255){verified=false;break;}
        }
        if(verified)result=0;
    }while(false);
    if(current){
        a.glFinish();
        if(vbo)a.glDeleteBuffers(1,&vbo);if(program)a.glDeleteProgram(program);
        if(vertex)a.glDeleteShader(vertex);if(fragment)a.glDeleteShader(fragment);
        if(fbo)a.glDeleteFramebuffers(1,&fbo);if(texture)a.glDeleteTextures(1,&texture);
        a.glFinish();
    }
    if(image!=EGL_NO_IMAGE_KHR&&!destroyImage(display,image))result=8;
    if(initialized){
        if(!a.eglMakeCurrent(display,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT))result=8;
        if(context!=EGL_NO_CONTEXT&&!a.eglDestroyContext(display,context))result=8;
        if(surface!=EGL_NO_SURFACE&&!a.eglDestroySurface(display,surface))result=8;
        if(!a.eglTerminate(display))result=8;
    }
    if(result==8 || __atomic_load_n(&native->refs,__ATOMIC_RELAXED)!=1){
        // Do not free an imported handle/native wrapper still retained by the
        // driver. Process exit closes all FDs/mappings without a dangling stack
        // object or reusing a supposedly freed ION buffer.
        fprintf(stderr,"EGL cleanup failure or unreleased native-buffer refs; process cleanup required\n");
        _exit(20);
    }
    delete native;
    printf("native_buffer_GLES_exit=%d frames=3 no_window_or_present=yes\n",result);
    return result;
}
