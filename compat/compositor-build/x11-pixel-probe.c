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
#include <dlfcn.h>
#include <sys/statvfs.h>
#include <sys/prctl.h>
#define REQUIRE(test) do { if (!(test)) { fprintf(stderr,"X11 pixel failure line=%d EGL=%x GL=%x\n",__LINE__,eglGetError(),glGetError());exit(20); } } while(0)
static int read_text(const char *path,char *out,size_t length){FILE *f=fopen(path,"r");if(!f)return 0;size_t n=fread(out,1,length-1,f);out[n]=0;fclose(f);while(n&&out[n-1]=='\n')out[--n]=0;return 1;}
static unsigned channel(unsigned long pixel,unsigned long mask){REQUIRE(mask);unsigned shift=__builtin_ctzl(mask);unsigned long maximum=mask>>shift;return (unsigned)(((pixel&mask)>>shift)*255/maximum);}
static int pixels_match(Display *display,Window window,int left,int top,unsigned width,unsigned height,const unsigned color[3]){
 XImage *image=XGetImage(display,window,left,top,width,height,AllPlanes,ZPixmap);REQUIRE(image);
 for(unsigned y=0;y<height;y++)for(unsigned x=0;x<width;x++){
  unsigned long p=XGetPixel(image,x,y);unsigned actual[3]={channel(p,image->red_mask),channel(p,image->green_mask),channel(p,image->blue_mask)};
  for(int c=0;c<3;c++)if(abs((int)actual[c]-(int)color[c])>1){XDestroyImage(image);return 0;}
 }
 XDestroyImage(image);return 1;
}
static void verify(Display *display,Window window,unsigned width,unsigned height,const unsigned color[3]){REQUIRE(pixels_match(display,window,0,0,width,height,color));}
static void draw(EGLDisplay egl, EGLSurface surface,Display *display,Window window,unsigned width,unsigned height,unsigned index,int check){
 static const unsigned colors[][3]={{64,0,0},{0,128,0},{0,0,191},{64,128,191},{191,64,128},{128,191,64}};
 const unsigned *color=colors[index%6];glViewport(0,0,width,height);glClearColor(color[0]/255.0f,color[1]/255.0f,color[2]/255.0f,1.0f);glClear(GL_COLOR_BUFFER_BIT);glFinish();REQUIRE(glGetError()==GL_NO_ERROR);
 REQUIRE(eglSwapBuffers(egl,surface));XSync(display,False);if(check)verify(display,window,width,height,color);usleep(16000);
}
static uint64_t popup_hash(Display *display,Window overlay,unsigned width){
 unsigned left=width>400?(width-400)/2:0,cols=width>400?400:width;
 XImage *image=XGetImage(display,overlay,left,70,cols,380,AllPlanes,ZPixmap);REQUIRE(image);
 uint64_t hash=1469598103934665603ULL;unsigned long mask=image->red_mask|image->green_mask|image->blue_mask;
 for(unsigned y=0;y<380;y++)for(unsigned x=0;x<cols;x++){hash^=XGetPixel(image,x,y)&mask;hash*=1099511628211ULL;}
 XDestroyImage(image);return hash;
}
static void calendar_key(Display *display,void *xtest){
 int (*key)(Display *,unsigned int,Bool,unsigned long)=dlsym(xtest,"XTestFakeKeyEvent");REQUIRE(key);
 unsigned int super=XKeysymToKeycode(display,0xffeb),v=XKeysymToKeycode(display,0x76);REQUIRE(super&&v);
 REQUIRE(key(display,super,True,0));REQUIRE(key(display,v,True,0));XSync(display,False);usleep(80000);
 REQUIRE(key(display,v,False,0));REQUIRE(key(display,super,False,0));XSync(display,False);
}
static void popup_check(Display *display,void *xtest,void *compositelib,int keyboard){
 Window (*get_overlay)(Display *,Window)=dlsym(compositelib,"XCompositeGetOverlayWindow");
 void (*release_overlay)(Display *,Window)=dlsym(compositelib,"XCompositeReleaseOverlayWindow");
 int (*motion)(Display *,int,int,int,unsigned long)=dlsym(xtest,"XTestFakeMotionEvent");
 int (*button)(Display *,unsigned int,Bool,unsigned long)=dlsym(xtest,"XTestFakeButtonEvent");
 REQUIRE(get_overlay&&release_overlay&&motion&&button);Window root=DefaultRootWindow(display),overlay=get_overlay(display,root);XWindowAttributes a;REQUIRE(XGetWindowAttributes(display,root,&a)&&a.width>=400&&a.height>=500);
 usleep(500000);uint64_t closed=popup_hash(display,overlay,a.width);
 if(keyboard)calendar_key(display,xtest);else{REQUIRE(motion(display,DefaultScreen(display),a.width/2,12,0));REQUIRE(button(display,1,True,0));XSync(display,False);usleep(80000);REQUIRE(button(display,1,False,0));XSync(display,False);}usleep(2500000);
 uint64_t opened=popup_hash(display,overlay,a.width);REQUIRE(opened!=closed);
 for(unsigned frame=0;frame<20;frame++){usleep(100000);uint64_t current=popup_hash(display,overlay,a.width);if(current!=opened){fprintf(stderr,"GNOME popup changed sample=%u hash=%llx expected=%llx closed=%llx\n",frame,(unsigned long long)current,(unsigned long long)opened,(unsigned long long)closed);exit(22);}}
 if(keyboard)calendar_key(display,xtest);else{REQUIRE(button(display,1,True,0));REQUIRE(button(display,1,False,0));XSync(display,False);}release_overlay(display,root);
 puts("G955N_GNOME_POPUP_PASS samples=20 stable=passed");
}
int main(int argc,char **argv){
 int session=argc==3&&!strcmp(argv[1],"--run-session-x11-composite-trial");
 int legacy=session||(argc==3&&!strcmp(argv[1],"--run-legacy-native-x11-pixel-trial"));
 int host_native=argc==3&&!strcmp(argv[1],"--run-host-native-x11-pixel-trial");
 int native=legacy||host_native||(argc==3&&!strcmp(argv[1],"--run-native-x11-pixel-trial"));
 int composite=session||(argc==3&&(!strcmp(argv[1],"--run-x11-composite-trial")||!strcmp(argv[1],"--run-x11-composite-no-popup-trial")));
 if(argc!=3||(!native&&!composite&&strcmp(argv[1],"--run-x11-pixel-trial"))){puts("Explicit --run-x11-pixel-trial BOOT_ID required; no display opened");return 0;}
 char text[512];const char *private=getenv(host_native?"G955N_NATIVE_COMPAT_RUNTIME":"G955N_ANDROID_PRIVATE_RUNTIME"),*target=getenv("DISPLAY");
 if((!legacy&&(!private||strcmp(private,"1")))||!target||(session?(target[0]!=':'||target[1]<'0'||target[1]>'9'||target[2]!=0):(native?strcmp(target,":0"):strcmp(target,":77")))||!read_text("/proc/device-tree/model",text,sizeof(text))||!strstr(text,"SM-G955N"))return 2;
 if(!read_text("/proc/sys/kernel/random/boot_id",text,sizeof(text))||strcmp(text,argv[2]))return 2;
 if(legacy){
  const char *setting=getenv("HYBRIS_FORCE_LEGACY_PROPERTIES");
  if(getuid()!=1000||getgid()!=1000||!setting||strcmp(setting,"1")||access("/dev/__properties__",F_OK)==0||prctl(PR_GET_NO_NEW_PRIVS,0,0,0,0)!=1)return 2;
  puts("G955N native legacy context uid=1000 gid=1000 Android_property_daemon=absent nnp=yes");fflush(stdout);
 }
 if(host_native){
  struct statvfs filesystem;
  if(getenv("G955N_ANDROID_PRIVATE_RUNTIME")||getuid()!=1000||getgid()!=1000||prctl(PR_GET_NO_NEW_PRIVS,0,0,0,0)!=1||statvfs("/dev/__properties__",&filesystem)||!(filesystem.f_flag&ST_RDONLY))return 2;
  if(!read_text("/proc/self/status",text,sizeof(text)))return 2;
  char *at=strstr(text,"NSpid:");if(!at)return 2;at+=6;unsigned count=0;
  while(*at&&*at!='\n'){if(*at==' '||*at=='\t'){at++;continue;}char *end;long value=strtol(at,&end,10);if(end==at||value<1)return 2;count++;at=end;}
  if(count!=1)return 2;
  puts("G955N native host context verified uid=1000 gid=1000 properties=read-only host_pid=yes nnp=yes");fflush(stdout);
 }
 void *xtest=NULL,*compositelib=NULL;Display *display=XOpenDisplay(NULL);if(!display)return 3;unsigned frames=0;
 if(composite){
  /* The separately created test session starts in GNOME overview. Use its
   * ordinary X11 keyboard path to leave that UI before pixel comparison.
   * This synthetic event is not physical touchscreen/input qualification. */
  xtest=dlopen("libXtst.so.6",RTLD_NOW|RTLD_LOCAL);REQUIRE(xtest);
  int (*key)(Display *,unsigned int,Bool,unsigned long)=dlsym(xtest,"XTestFakeKeyEvent");REQUIRE(key);
  unsigned int escape=XKeysymToKeycode(display,0xff1b);REQUIRE(escape);
  REQUIRE(key(display,escape,True,0));REQUIRE(key(display,escape,False,0));XSync(display,False);usleep(1000000);
 }
 for(unsigned cycle=0;cycle<(composite?1u:2u);cycle++){
  EGLDisplay egl=eglGetDisplay((EGLNativeDisplayType)display);REQUIRE(egl!=EGL_NO_DISPLAY);REQUIRE(eglInitialize(egl,NULL,NULL));REQUIRE(eglBindAPI(EGL_OPENGL_ES_API));
  const EGLint attributes[]={EGL_SURFACE_TYPE,EGL_WINDOW_BIT,EGL_RENDERABLE_TYPE,EGL_OPENGL_ES2_BIT,EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,0,EGL_NONE};EGLConfig config;EGLint count=0,visual=0;
  REQUIRE(eglChooseConfig(egl,attributes,&config,1,&count)&&count==1);REQUIRE(eglGetConfigAttrib(egl,config,EGL_NATIVE_VISUAL_ID,&visual));
  XVisualInfo pattern={.visualid=(VisualID)visual,.screen=DefaultScreen(display)};int found=0;XVisualInfo *info=XGetVisualInfo(display,VisualIDMask|VisualScreenMask,&pattern,&found);REQUIRE(info&&found>0);
  unsigned width=96,height=64;Colormap map=XCreateColormap(display,RootWindow(display,info->screen),info->visual,AllocNone);
  XSetWindowAttributes wa={.colormap=map,.event_mask=StructureNotifyMask,.override_redirect=composite||native};Window window=XCreateWindow(display,RootWindow(display,info->screen),composite?120:0,composite?160:0,width,height,0,info->depth,InputOutput,info->visual,CWColormap|CWEventMask|CWOverrideRedirect,&wa);XFree(info);XMapWindow(display,window);XSync(display,False);
  const EGLint context_attributes[]={EGL_CONTEXT_CLIENT_VERSION,2,EGL_NONE};EGLContext context=eglCreateContext(egl,config,EGL_NO_CONTEXT,context_attributes);REQUIRE(context!=EGL_NO_CONTEXT);
  EGLSurface surface=eglCreateWindowSurface(egl,config,(EGLNativeWindowType)window,NULL);REQUIRE(surface!=EGL_NO_SURFACE);REQUIRE(eglMakeCurrent(egl,surface,surface,context));
  const char *renderer=(const char *)glGetString(GL_RENDERER);REQUIRE(renderer&&strstr(renderer,"Mali-G71")&&!strstr(renderer,"llvmpipe"));printf("X11 actual GL_RENDERER=%s cycle=%u\n",renderer,cycle);fflush(stdout);
  if(composite){
   compositelib=dlopen("libXcomposite.so.1",RTLD_NOW|RTLD_LOCAL);REQUIRE(compositelib);
   Window (*get_overlay)(Display *,Window)=dlsym(compositelib,"XCompositeGetOverlayWindow");
   void (*release_overlay)(Display *,Window)=dlsym(compositelib,"XCompositeReleaseOverlayWindow");REQUIRE(get_overlay&&release_overlay);
   Window root=RootWindow(display,DefaultScreen(display)),overlay=get_overlay(display,root);REQUIRE(overlay);
   static const unsigned colors[][3]={{64,0,0},{0,128,0},{0,0,191},{64,128,191},{191,64,128},{128,191,64}};
   for(unsigned f=0;f<6;f++){
    draw(egl,surface,display,window,width,height,f,1);int left,top;Window child;
    REQUIRE(XTranslateCoordinates(display,window,root,0,0,&left,&top,&child));int matched=0;
    for(int wait=0;wait<20;wait++){usleep(50000);if(pixels_match(display,overlay,left,top,width,height,colors[f])){matched=1;break;}}
    if(!matched){
     XWindowAttributes a;REQUIRE(XGetWindowAttributes(display,overlay,&a));XImage *im=XGetImage(display,overlay,0,0,a.width,a.height,AllPlanes,ZPixmap);REQUIRE(im);
     unsigned matches=0;int minx=a.width,miny=a.height,maxx=-1,maxy=-1;
     for(int yy=0;yy<a.height;yy++)for(int xx=0;xx<a.width;xx++){
      unsigned long px=XGetPixel(im,xx,yy);if(abs((int)channel(px,im->red_mask)-(int)colors[f][0])<=1&&abs((int)channel(px,im->green_mask)-(int)colors[f][1])<=1&&abs((int)channel(px,im->blue_mask)-(int)colors[f][2])<=1){matches++;if(xx<minx)minx=xx;if(xx>maxx)maxx=xx;if(yy<miny)miny=yy;if(yy>maxy)maxy=yy;}}
     if(a.width<=2048&&a.height<=2048){FILE *out=fopen("/run/g955n-compositor/composite-failure.ppm","wb");if(out){fprintf(out,"P6\n%d %d\n255\n",a.width,a.height);for(int yy=0;yy<a.height;yy++)for(int xx=0;xx<a.width;xx++){unsigned long pp=XGetPixel(im,xx,yy);unsigned char rgb[3]={channel(pp,im->red_mask),channel(pp,im->green_mask),channel(pp,im->blue_mask)};fwrite(rgb,1,3,out);}fclose(out);}}
     unsigned long px=XGetPixel(im,left+width/2,top+height/2);
     fprintf(stderr,"Overlay mismatch frame=%u size=%dx%d window=%d,%d,%u,%u center=%u,%u,%u expected=%u,%u,%u total_matches=%u bbox=%d,%d..%d,%d\n",f,a.width,a.height,left,top,width,height,channel(px,im->red_mask),channel(px,im->green_mask),channel(px,im->blue_mask),colors[f][0],colors[f][1],colors[f][2],matches,minx,miny,maxx,maxy);XDestroyImage(im);
    }
    REQUIRE(matched);frames++;
   }
   release_overlay(display,root);
  }else{
  for(unsigned f=0;f<12;f++){draw(egl,surface,display,window,width,height,f,1);frames++;}
  width=128;height=96;XResizeWindow(display,window,width,height);XSync(display,False);
  for(unsigned f=0;f<2;f++)draw(egl,surface,display,window,width,height,f,0);
  for(unsigned f=0;f<12;f++){draw(egl,surface,display,window,width,height,f,1);frames++;}
  }
  REQUIRE(eglMakeCurrent(egl,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT));REQUIRE(eglDestroySurface(egl,surface));REQUIRE(eglDestroyContext(egl,context));REQUIRE(eglTerminate(egl));
  XDestroyWindow(display,window);XFreeColormap(display,map);XSync(display,False);
 }
 if(composite&&(session||!strcmp(argv[1],"--run-x11-composite-trial")))popup_check(display,xtest,compositelib,session);
 XCloseDisplay(display);if(compositelib)dlclose(compositelib);if(xtest)dlclose(xtest);if(composite){printf("G955N_X11_COMPOSITE_PASS frames=%u overlay_pixels=passed\n",frames);return 0;}printf("G955N_X11_PIXEL_PASS frames=%u resize=passed repeated_egl=passed teardown=passed\n",frames);return 0;
}
