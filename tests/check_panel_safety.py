#!/usr/bin/env python3
"""Run actual DPP timer/copy and native-pan code against lifetime/power races."""
import argparse
from pathlib import Path
import subprocess
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--before',type=Path,required=True);p.add_argument('--after',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
relative=Path('drivers/video/fbdev/exynos/dpu')
def fn(text,name):
 marker=text.index(name+'(');start=text.rfind('\n',0,marker)+1;brace=text.index('{',marker);depth=1;end=brace+1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
flags=['clang','-O1','-g','-fsanitize=address,undefined','-fsanitize-address-use-after-return=always','-fno-omit-frame-pointer']
for variant,root in [('fixed',a.after),('borrowed',a.before)]:
 source=(root/relative/'dpp_drv.c').read_text();timer=fn(source,'dpp_op_timer_handler')
 pointer=variant=='borrowed'
 prefix=r'''
#include <stdio.h>
#include <assert.h>
struct decon_win_config {int compression;struct {int comp_src;} dpp_parm;};
'''+('struct dpp_device {int id;struct decon_win_config *config;};\n' if pointer else 'struct dpp_device {int id;struct decon_win_config config;};\n')+r'''
#define DPP_COMP_SRC_G2D 0
#define dpp_info(...) printf(__VA_ARGS__)
'''
 copy='static void dpp_copy_config(struct dpp_device *dpp,const struct decon_win_config *arg){dpp->config = (struct decon_win_config *)arg;}' if pointer else fn(source,'dpp_copy_config')
 code=prefix+copy+'\n'+timer+r'''
__attribute__((noinline)) static void submit(struct dpp_device *dpp){
 struct decon_win_config config={.compression=1,.dpp_parm={.comp_src=DPP_COMP_SRC_G2D}};
 dpp_copy_config(dpp,&config);
}
int main(void){struct dpp_device dpp={.id=1};submit(&dpp);dpp_op_timer_handler((unsigned long)&dpp);return 0;}
'''
 c=a.output/(variant+'-timer.c');c.write_text(code);exe=c.with_suffix('');subprocess.run([*flags,str(c),'-o',str(exe)],check=True);r=subprocess.run([str(exe)],text=True,capture_output=True);(a.output/(variant+'-timer.log')).write_text(r.stdout+r.stderr)
 if pointer:
  if r.returncode==0 or 'stack-use-after-return' not in r.stderr:raise SystemExit('Borrowed caller stack did not reproduce deferred UAR')
 elif r.returncode:raise SystemExit(r.stderr)
print('Actual DPP timer: owned metadata passed; original borrowed stack reproduced ASan stack-use-after-return')
pre=r'''
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
typedef unsigned int u32;
#define DECON_OUT_DSI 1
#define DECON_PIXEL_FORMAT_RGB_565 1
#define DECON_PIXEL_FORMAT_ABGR_8888 2
#define DPP_WIN_CONFIG 1
#define PANEL_IOC_DISP_ON 2
#define PANEL_DISPLAY_OFF 0
#define VSYNC_TIMEOUT_MSEC 50
#define SHADOW_UPDATE_TIMEOUT 50
struct frame {unsigned x,y,w,h,f_w,f_h;};
struct decon_win_config {int format;struct {unsigned long addr[1];} dpp_parm;struct frame src,dst;};
struct panel_state {int disp_on;};struct v4l2_subdev {int unused;};struct decon_mode_info {int unused;};
struct decon_device {int id,state,lock;struct {int out_type,dft_idma,dft_win;} dt;unsigned long cur_using_dpp,prev_used_dpp,dpp_err_stat;struct v4l2_subdev *dpp_sd[1],*panel_sd;struct panel_state *panel_state;};
struct decon_win {struct decon_device *decon;int dpp_id;};
struct fb_var_screeninfo {unsigned bits_per_pixel,xoffset,yoffset,xres,yres;};struct fb_info {struct decon_win *par;struct {unsigned long smem_start;} fix;};
static struct decon_device *active;static int blank_at_lock,blocks,locks,hardware;
static int check_decon_state(struct decon_device*d){return d->state==1;}
static void mutex_lock(int*p){(void)p;locks++;if(blank_at_lock)active->state=0;}
static void mutex_unlock(int*p){(void)p;locks--;}
static void decon_hiber_block_exit(struct decon_device*d){(void)d;blocks++;}
static void decon_hiber_unblock(struct decon_device*d){(void)d;blocks--;}
static int decon_set_par(struct fb_info*i){(void)i;return 0;}
static int decon_set_win_info(struct fb_info*i){(void)i;assert(active->state==1);hardware++;return 0;}
static void set_bit(int n,unsigned long*p){*p|=1UL<<n;}
static void clear_bit(int n,unsigned long*p){*p&=~(1UL<<n);}
static int invoke(int cmd,void*p){(void)cmd;(void)p;assert(active->state==1);hardware++;return 0;}
#define v4l2_subdev_call(sd,ops,method,cmd,arg) invoke(cmd,arg)
#define decon_warn(...) printf(__VA_ARGS__)
#define decon_err(...) printf(__VA_ARGS__)
static void decon_reg_update_req_window(int id,int w){(void)id;(void)w;assert(active->state==1);hardware++;}
static void decon_to_psr_info(struct decon_device*d,struct decon_mode_info*p){(void)d;(void)p;}
static void decon_reg_start(int id,struct decon_mode_info*p){(void)id;(void)p;assert(active->state==1);hardware++;}
static int decon_wait_for_vsync(struct decon_device*d,int t){(void)d;(void)t;return 0;}
static int decon_reg_wait_update_done_and_mask(int id,struct decon_mode_info*p,int t){(void)id;(void)p;(void)t;return 0;}
'''
main=r'''
int main(void){
 struct panel_state panel={.disp_on=1};struct decon_device d={.state=1,.dt={.out_type=DECON_OUT_DSI},.panel_state=&panel};struct decon_win w={.decon=&d};struct fb_info info={.par=&w};struct fb_var_screeninfo v={.bits_per_pixel=32,.xres=1440,.yres=2960};active=&d;
 blank_at_lock=1;assert(decon_pan_display(&v,&info)==0);assert(hardware==0&&blocks==0&&locks==0);
 blank_at_lock=0;d.state=1;assert(decon_pan_display(&v,&info)==0);assert(hardware>0&&blocks==0&&locks==0);
 return 0;
}
'''
for variant,root in [('fixed',a.after),('racy',a.before)]:
 source=(root/relative/'decon_dsi.c').read_text();c=a.output/(variant+'-pan.c');c.write_text(pre+fn(source,'decon_pan_display')+main);exe=c.with_suffix('');subprocess.run([*flags,str(c),'-o',str(exe)],check=True);r=subprocess.run([str(exe)],text=True,capture_output=True);(a.output/(variant+'-pan.log')).write_text(r.stdout+r.stderr)
 if variant=='fixed' and r.returncode:raise SystemExit(r.stderr)
 if variant=='racy' and r.returncode==0:raise SystemExit('Old pan path accepted register access after concurrent power-down')
print('Actual native pan: blank-at-lock suppressed MMIO and balanced ownership; original failed power-state assertion')
