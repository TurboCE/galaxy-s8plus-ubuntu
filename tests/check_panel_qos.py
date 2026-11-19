#!/usr/bin/env python3
"""Compile actual decon_blank bodies to check power/QoS ordering and rollback."""
import argparse
from pathlib import Path
import subprocess
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--before',type=Path,required=True);p.add_argument('--after',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
def function(text):
 start=text.index('static int decon_blank(');brace=text.index('{',start);end=brace+1;depth=1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
pre=r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdio.h>
#define FB_BLANK_UNBLANK 0
#define FB_BLANK_NORMAL 1
#define FB_BLANK_VSYNC_SUSPEND 2
#define FB_BLANK_HSYNC_SUSPEND 3
#define FB_BLANK_POWERDOWN 4
#define DECON_OUT_DSI 0
#define DECON_STATE_SHUTDOWN 9
#define DPU_EVENT_LOG(...) ((void)0)
#define decon_info(...) ((void)0)
#define decon_warn(...) ((void)0)
#define decon_err(...) ((void)0)
struct decon_device {int id,state;struct {int out_type;} dt;};
struct decon_win {struct decon_device *decon;};struct fb_info {struct decon_win *par;};
static bool is_suspend;static int decon_blank_qos_lock,locks,blocks,qos_calls,hardware,fail,disabled;
static void mutex_lock(int*p){(void)p;assert(locks==0);locks++;}
static void mutex_unlock(int*p){(void)p;assert(locks==1);locks--;}
static void decon_hiber_block_exit(struct decon_device*d){(void)d;blocks++;}
static void decon_hiber_unblock(struct decon_device*d){(void)d;blocks--;}
static void set_devfreq_pm_qos(void){qos_calls++;if(is_suspend)assert(disabled);}
static int decon_enable(struct decon_device*d){(void)d;assert(!is_suspend);hardware++;return fail;}
static int decon_disable(struct decon_device*d){(void)d;hardware++;if(!fail)disabled=1;return fail;}
'''
main=r'''
static void reset(int suspended){is_suspend=suspended;disabled=suspended;qos_calls=hardware=fail=locks=blocks=0;}
int main(void){
 struct decon_device d={.dt={.out_type=DECON_OUT_DSI}};struct decon_win w={.decon=&d};struct fb_info info={.par=&w};
 reset(1);assert(decon_blank(0,&info)==0);assert(!is_suspend&&qos_calls==1&&hardware==1&&!locks&&!blocks);
 reset(0);assert(decon_blank(4,&info)==0);assert(is_suspend&&disabled&&hardware==1&&!locks&&!blocks);
 reset(0);assert(decon_blank(3,&info)==-EINVAL);assert(!is_suspend&&!qos_calls&&!hardware);
 reset(0);fail=-EIO;assert(decon_blank(4,&info)==-EIO);assert(!is_suspend&&!locks&&!blocks);
 reset(1);fail=-EIO;assert(decon_blank(0,&info)==-EIO);assert(is_suspend&&!locks&&!blocks);
 reset(0);d.id=1;assert(decon_blank(4,&info)==0);assert(!is_suspend&&!qos_calls);
 reset(1);d.id=0;d.state=DECON_STATE_SHUTDOWN;assert(decon_blank(0,&info)==0);assert(is_suspend&&!qos_calls&&!hardware&&!locks&&!blocks);
 puts("7 actual blank/QoS ordering and rollback cases passed");return 0;
}
'''
for variant,path in [('fixed',a.after),('old',a.before)]:
 src=a.output/(variant+'.c');src.write_text(pre+function(path.read_text())+main);exe=src.with_suffix('')
 subprocess.run(['clang','-O1','-fsanitize=address,undefined',str(src),'-o',str(exe)],check=True)
 r=subprocess.run([str(exe)],capture_output=True,text=True);(a.output/(variant+'.log')).write_text(r.stdout+r.stderr)
 if variant=='fixed' and r.returncode:raise SystemExit(r.stderr)
 if variant=='old' and r.returncode==0:raise SystemExit('Original woke hardware at screen-off QoS without reproducing violation')
print('Fixed actual decon_blank passed; original reproduced pre-enable QoS violation')
