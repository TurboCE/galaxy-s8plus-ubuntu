#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <EGL/egl.h>
#include <GLES2/gl2.h>
EGLBoolean eglMakeCurrent(EGLDisplay d,EGLSurface a,EGLSurface b,EGLContext c){
 EGLBoolean(*f)(EGLDisplay,EGLSurface,EGLSurface,EGLContext)=dlsym(RTLD_NEXT,"eglMakeCurrent");
 EGLBoolean r=f(d,a,b,c); const GLubyte*(*s)(GLenum)=dlsym(RTLD_NEXT,"glGetString");
 fprintf(stderr,"TRACE eglMakeCurrent=%u renderer=%s\n",r,r?(const char*)s(GL_RENDERER):"failed");return r;
}
static EGLContext trace_context(void){EGLContext(*f)(void)=dlsym(RTLD_NEXT,"eglGetCurrentContext");return f();}
GLuint glCreateShader(GLenum type){GLuint(*f)(GLenum)=dlsym(RTLD_NEXT,"glCreateShader");GLuint r=f(type);fprintf(stderr,"TRACE glCreateShader type=%x shader=%u\n",type,r);fprintf(stderr,"TRACE after create context=%p\n",trace_context());return r;}
void glCompileShader(GLuint shader){void(*f)(GLuint)=dlsym(RTLD_NEXT,"glCompileShader");fprintf(stderr,"TRACE glCompileShader %u\n",shader);fprintf(stderr,"TRACE before compile context=%p\n",trace_context());f(shader);fprintf(stderr,"TRACE after compile context=%p\n",trace_context());}
void glGetShaderiv(GLuint shader,GLenum name,GLint*v){void(*f)(GLuint,GLenum,GLint*)=dlsym(RTLD_NEXT,"glGetShaderiv");f(shader,name,v);fprintf(stderr,"TRACE glGetShaderiv shader=%u name=%x value=%d\n",shader,name,*v);}
void glShaderSource(GLuint shader,GLsizei count,const GLchar*const*source,const GLint*length){void(*f)(GLuint,GLsizei,const GLchar*const*,const GLint*)=dlsym(RTLD_NEXT,"glShaderSource");fprintf(stderr,"TRACE glShaderSource shader=%u count=%d text=%.160s\n",shader,count,count>0?source[0]:"");f(shader,count,source,length);}
EGLBoolean eglSwapBuffers(EGLDisplay d,EGLSurface s){
 EGLBoolean(*f)(EGLDisplay,EGLSurface)=dlsym(RTLD_NEXT,"eglSwapBuffers");
 EGLContext(*current)(void)=dlsym(RTLD_NEXT,"eglGetCurrentContext");
 fprintf(stderr,"TRACE eglSwapBuffers display=%p surface=%p current=%p\n",d,s,current());
 EGLBoolean r=f(d,s);fprintf(stderr,"TRACE eglSwapBuffers returned=%u\n",r);return r;
}
EGLBoolean eglQuerySurface(EGLDisplay d,EGLSurface s,EGLint name,EGLint*value){
 EGLBoolean(*f)(EGLDisplay,EGLSurface,EGLint,EGLint*)=dlsym(RTLD_NEXT,"eglQuerySurface");
 EGLContext(*current)(void)=dlsym(RTLD_NEXT,"eglGetCurrentContext");
 fprintf(stderr,"TRACE eglQuerySurface name=%x current=%p caller=%p\n",name,current(),__builtin_return_address(0));
 EGLBoolean r=f(d,s,name,value);fprintf(stderr,"TRACE eglQuerySurface returned=%u value=%d\n",r,r?*value:0);return r;
}
void glClear(GLbitfield mask){
 void(*f)(GLbitfield)=dlsym(RTLD_NEXT,"glClear");EGLContext(*current)(void)=dlsym(RTLD_NEXT,"eglGetCurrentContext");
 fprintf(stderr,"TRACE glClear mask=%x current=%p\n",mask,current());f(mask);fprintf(stderr,"TRACE glClear done\n");
}
void glViewport(GLint x,GLint y,GLsizei w,GLsizei h){
 void(*f)(GLint,GLint,GLsizei,GLsizei)=dlsym(RTLD_NEXT,"glViewport");EGLContext(*current)(void)=dlsym(RTLD_NEXT,"eglGetCurrentContext");
 fprintf(stderr,"TRACE glViewport %dx%d current=%p\n",w,h,current());f(x,y,w,h);fprintf(stderr,"TRACE glViewport done\n");
}
