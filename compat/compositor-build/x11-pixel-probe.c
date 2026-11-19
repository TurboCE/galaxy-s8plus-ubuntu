/* SM-G955N private X11/EGL pixel and ownership fixture. No operation by default. */
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <EGL/egl.h>
#include <GLES2/gl2.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#define REQUIRE(test) do { if (!(test)) { fprintf(stderr,"X11 pixel failure line=%d EGL=%x GL=%x\n",__LINE__,eglGetError(),glGetError());exit(20); } } while(0)
static int read_text(const char *path,char *out,size_t length){FILE *f=fopen(path,"r");if(!f)return 0;size_t n=fread(out,1,length-1,f);out[n]=0;fclose(f);while(n&&out[n-1]=='\n')out[--n]=0;return 1;}
static unsigned channel(unsigned long pixel,unsigned long mask){REQUIRE(mask);unsigned shift=__builtin_ctzl(mask);unsigned long maximum=mask>>shift;return (unsigned)(((pixel&mask)>>shift)*255/maximum);}
static void verify(Display *display,Window window,unsigned width,unsigned height,const unsigned color[3]){
 XImage *image=XGetImage(display,window,0,0,width,height,AllPlanes,ZPixmap);REQUIRE(image);
 for(unsigned y=0;y<height;y++)for(unsigned x=0;x<width;x++){
  unsigned long p=XGetPixel(image,x,y);unsigned actual[3]={channel(p,image->red_mask),channel(p,image->green_mask),channel(p,image->blue_mask)};
  for(int c=0;c<3;c++)if(abs((int)actual[c]-(int)color[c])>1){fprintf(stderr,"X11 pixel mismatch (%u,%u) channel=%d actual=%u expected=%u\n",x,y,c,actual[c],color[c]);exit(21);}
 }
 XDestroyImage(image);
}
static void draw(EGLDisplay egl, EGLSurface surface,Display *display,Window window,unsigned width,unsigned height,unsigned index,int check){
 static const unsigned colors[][3]={{64,0,0},{0,128,0},{0,0,191},{64,128,191},{191,64,128},{128,191,64}};
 const unsigned *color=colors[index%6];glViewport(0,0,width,height);glClearColor(color[0]/255.0f,color[1]/255.0f,color[2]/255.0f,1.0f);glClear(GL_COLOR_BUFFER_BIT);glFinish();REQUIRE(glGetError()==GL_NO_ERROR);
 REQUIRE(eglSwapBuffers(egl,surface));XSync(display,False);if(check)verify(display,window,width,height,color);usleep(16000);
}
int main(int argc,char **argv){
 if(argc!=3||strcmp(argv[1],"--run-x11-pixel-trial")){puts("Explicit --run-x11-pixel-trial BOOT_ID required; no display opened");return 0;}
 char text[512];const char *private=getenv("G955N_ANDROID_PRIVATE_RUNTIME"),*target=getenv("DISPLAY");
 if(!private||strcmp(private,"1")||!target||strcmp(target,":77")||!read_text("/proc/device-tree/model",text,sizeof(text))||!strstr(text,"SM-G955N"))return 2;
 if(!read_text("/proc/sys/kernel/random/boot_id",text,sizeof(text))||strcmp(text,argv[2]))return 2;
 Display *display=XOpenDisplay(NULL);if(!display)return 3;unsigned frames=0;
 for(unsigned cycle=0;cycle<2;cycle++){
  EGLDisplay egl=eglGetDisplay((EGLNativeDisplayType)display);REQUIRE(egl!=EGL_NO_DISPLAY);REQUIRE(eglInitialize(egl,NULL,NULL));REQUIRE(eglBindAPI(EGL_OPENGL_ES_API));
  const EGLint attributes[]={EGL_SURFACE_TYPE,EGL_WINDOW_BIT,EGL_RENDERABLE_TYPE,EGL_OPENGL_ES2_BIT,EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,0,EGL_NONE};EGLConfig config;EGLint count=0,visual=0;
  REQUIRE(eglChooseConfig(egl,attributes,&config,1,&count)&&count==1);REQUIRE(eglGetConfigAttrib(egl,config,EGL_NATIVE_VISUAL_ID,&visual));
  XVisualInfo pattern={.visualid=(VisualID)visual,.screen=DefaultScreen(display)};int found=0;XVisualInfo *info=XGetVisualInfo(display,VisualIDMask|VisualScreenMask,&pattern,&found);REQUIRE(info&&found>0);
  unsigned width=96,height=64;Colormap map=XCreateColormap(display,RootWindow(display,info->screen),info->visual,AllocNone);
  XSetWindowAttributes wa={.colormap=map,.event_mask=StructureNotifyMask};Window window=XCreateWindow(display,RootWindow(display,info->screen),0,0,width,height,0,info->depth,InputOutput,info->visual,CWColormap|CWEventMask,&wa);XFree(info);XMapWindow(display,window);XSync(display,False);
  const EGLint context_attributes[]={EGL_CONTEXT_CLIENT_VERSION,2,EGL_NONE};EGLContext context=eglCreateContext(egl,config,EGL_NO_CONTEXT,context_attributes);REQUIRE(context!=EGL_NO_CONTEXT);
  EGLSurface surface=eglCreateWindowSurface(egl,config,(EGLNativeWindowType)window,NULL);REQUIRE(surface!=EGL_NO_SURFACE);REQUIRE(eglMakeCurrent(egl,surface,surface,context));
  const char *renderer=(const char *)glGetString(GL_RENDERER);REQUIRE(renderer&&strstr(renderer,"Mali-G71")&&!strstr(renderer,"llvmpipe"));printf("X11 actual GL_RENDERER=%s cycle=%u\n",renderer,cycle);fflush(stdout);
  for(unsigned f=0;f<12;f++){draw(egl,surface,display,window,width,height,f,1);frames++;}
  width=128;height=96;XResizeWindow(display,window,width,height);XSync(display,False);
  for(unsigned f=0;f<2;f++)draw(egl,surface,display,window,width,height,f,0);
  for(unsigned f=0;f<12;f++){draw(egl,surface,display,window,width,height,f,1);frames++;}
  REQUIRE(eglMakeCurrent(egl,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT));REQUIRE(eglDestroySurface(egl,surface));REQUIRE(eglDestroyContext(egl,context));REQUIRE(eglTerminate(egl));
  XDestroyWindow(display,window);XFreeColormap(display,map);XSync(display,False);
 }
 XCloseDisplay(display);printf("G955N_X11_PIXEL_PASS frames=%u resize=passed repeated_egl=passed teardown=passed\n",frames);return 0;
}
