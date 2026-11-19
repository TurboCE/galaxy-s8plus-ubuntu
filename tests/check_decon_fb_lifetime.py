#!/usr/bin/env python3
"""Extract actual proposed ownership helpers into an ASan/UBSan lifetime model."""
import argparse
from pathlib import Path
import subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source-root',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
s=(a.source_root/'drivers/video/fbdev/exynos/dpu/decon_core.c').read_text()
def function(name):
    start=s.index('static void '+name+'('); opening=s.index('{',start);depth=1;pos=opening+1
    while depth:
        depth+=(s[pos]=='{')-(s[pos]=='}');pos+=1
    return s[start:pos]
code=r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#define IS_ENABLED(x) native_console
struct dma_buf { unsigned char bytes[16384]; };
struct decon_dma_buf_data { uintptr_t dma_addr; struct dma_buf *dma_buf; };
struct fb_info { void *screen_base; struct {uintptr_t smem_start;size_t smem_len;} fix;void *par; };
struct decon_win { struct fb_info *fbinfo;void *decon;struct decon_dma_buf_data dma_buf_data[3];struct decon_dma_buf_data fb_dma_buf_data;int plane_cnt; };
static int native_console=1,registered=1,legacy=0,native_frees=0,frame_frees=0;
static uintptr_t native_address;
static struct decon_dma_buf_data allocation(void){
 struct dma_buf *buffer=calloc(1,sizeof(*buffer));assert(buffer);
 return (struct decon_dma_buf_data){(uintptr_t)buffer,buffer};
}
static void decon_free_dma_buf(void *device,struct decon_dma_buf_data *data){
 (void)device;
 if(!data->dma_addr)return;
 if(data->dma_addr==native_address){assert(!registered||legacy);++native_frees;}
 else ++frame_frees;
 free(data->dma_buf);memset(data,0,sizeof(*data));
}
static void framebuffer_release(struct fb_info *fb){free(fb->par);free(fb);}
'''
mmap_source=(a.source_root/'drivers/video/fbdev/exynos/dpu/decon_dsi.c').read_text()
start=mmap_source.index('\tbuf = win->fb_dma_buf_data.dma_buf ?')
end=mmap_source.index(';',start)+1
selection=mmap_source[start:end]
assert '\tif (!buf)\n\t\treturn -ENODEV;' in mmap_source
code+='static struct dma_buf *fb_buffer(struct decon_win *win){struct dma_buf *buf;'+selection+'return buf;}\n'
code+=function('decon_keep_native_fb')+'\n'+function('decon_release_windows')+'\n'
code+=r'''
static struct decon_win *window(void){
 struct decon_win *win=calloc(1,sizeof(*win));assert(win);
 win->fbinfo=calloc(1,sizeof(*win->fbinfo));assert(win->fbinfo);win->fbinfo->par=win;
 win->dma_buf_data[0]=allocation();win->plane_cnt=1;
 native_address=win->dma_buf_data[0].dma_addr;
 win->fbinfo->screen_base=win->dma_buf_data[0].dma_buf->bytes;
 win->fbinfo->fix.smem_start=native_address;win->fbinfo->fix.smem_len=16384;
 return win;
}
int main(int argc,char **argv){
 legacy=argc==2&&!strcmp(argv[1],"--legacy");
 struct decon_win *win=window();
 if(!legacy)decon_keep_native_fb(win);
 if(!legacy){assert(win->plane_cnt==0);assert(!win->dma_buf_data[0].dma_addr);assert(win->fb_dma_buf_data.dma_addr==native_address);}
 for(int frame=0;frame<128;++frame){
  struct decon_dma_buf_data old[3];int count=win->plane_cnt;
  memcpy(old,win->dma_buf_data,sizeof(old));
  for(int plane=0;plane<3;++plane)win->dma_buf_data[plane]=allocation();
  win->plane_cnt=3;
  for(int plane=0;plane<count;++plane)decon_free_dma_buf(NULL,&old[plane]);
  /* Counterfactual old driver reaches a real ASan UAF here after frame one. */
  unsigned char *screen=win->fbinfo->screen_base;screen[0]=0x5a;assert(screen[0]==0x5a);
  assert(win->fbinfo->fix.smem_start==native_address);
  assert(win->fb_dma_buf_data.dma_addr==native_address);assert(fb_buffer(win)==win->fb_dma_buf_data.dma_buf);
 }
 assert(native_frees==0);
 for(int plane=0;plane<3;++plane)decon_free_dma_buf(NULL,&win->dma_buf_data[plane]);
 assert(frame_frees==128*3);registered=0;decon_release_windows(win);assert(native_frees==1);
 decon_release_windows(NULL);
 /* Failed allocation/probe unwind has no persistent owner to release. */
 win=calloc(1,sizeof(*win));win->fbinfo=calloc(1,sizeof(*win->fbinfo));win->fbinfo->par=win;decon_release_windows(win);assert(native_frees==1);
 /* Non-console path keeps the existing per-frame ownership behavior. */
 native_console=0;win=window();decon_keep_native_fb(win);assert(win->plane_cnt==1);assert(!win->fb_dma_buf_data.dma_addr);assert(fb_buffer(win)==win->dma_buf_data[0].dma_buf);
 decon_free_dma_buf(NULL,&win->dma_buf_data[0]);decon_release_windows(win);assert(native_frees==2);
 puts("Actual helper ownership model passed 128 three-plane handoffs, stable native mapping, teardown and non-console/probe cases");return 0;
}
'''
a.output.mkdir(parents=True,exist_ok=True);(a.output/'model.c').write_text(code)
subprocess.run(['gcc','-g','-O1','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(a.output/'model.c'),'-o',str(a.output/'model')],check=True)
subprocess.run([str(a.output/'model')],check=True)
failed=subprocess.run([str(a.output/'model'),'--legacy'],capture_output=True,text=True)
(a.output/'legacy-counterfactual.txt').write_text(failed.stderr)
if failed.returncode==0 or 'heap-use-after-free' not in failed.stderr:raise SystemExit('Counterfactual did not detect original lifetime bug')
print('Unmodified-lifetime counterfactual rejected with actual ASan heap-use-after-free')
