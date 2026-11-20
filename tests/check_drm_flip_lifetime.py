#!/usr/bin/env python3
"""Run the actual DRM flip/defer/cancel callbacks against a fake panel.

This verifies event and buffer lifetime, not kernel locking or hardware timing.
"""
from pathlib import Path
import argparse,subprocess
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
text=(Path(__file__).resolve().parents[1]/'compat/drm-kms/decon_drm.c').read_text()
names=('decon_complete_event','decon_flip_work','decon_cancel_pending','decon_drm_power_state')
parts=[]
for name in names:
 start=text.index(('void ' if name=='decon_drm_power_state' else 'static void ')+name+'(')
 end=text.index('\n}\n',start)+3
 parts.append(text[start:end])
header=r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
#define container_of(ptr,type,member) ((type *)((char *)(ptr)-offsetof(type,member)))
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,y) ((x)=(y))
#define DRM_ERROR(...) ((void)0)
#define DECON_STATE_OFF 0
#define DRM_MODE_DPMS_ON 0
#define DRM_MODE_DPMS_OFF 3
#define spin_lock_irqsave(lock,flags) do {(void)(lock);(flags)=0;} while(0)
#define spin_unlock_irqrestore(lock,flags) do {(void)(lock);(void)(flags);} while(0)
#define rcu_read_lock() ((void)0)
#define rcu_read_unlock() ((void)0)
#define rcu_dereference(x) (x)
struct work_struct {int unused;};
struct drm_file {int event_space,event_wait;bool is_master;};
struct drm_pending_vblank_event {struct {struct drm_file *file_priv;} base;int event;};
struct drm_framebuffer {int refs;};
struct drm_device {int event_lock;struct {void *dpms_property;} mode_config;};
struct decon_drm;
struct decon_device {bool drm_owned;int state;struct decon_drm *native_drm;};
struct decon_drm {
 struct drm_device *drm;struct decon_device *decon;
 struct work_struct flip_work;int commit_lock,pending_lock,workqueue;
 struct drm_framebuffer *scanout_fb,*pending;
 struct drm_pending_vblank_event *event;
 struct {int base;} connector;
 bool stopping,deferred;int error;
};
static int completed,puts,queued,wakes,commit_result,power_state;
static struct decon_drm *observed;
static void mutex_lock(int *lock){assert(!*lock);*lock=1;}
static void mutex_unlock(int *lock){assert(*lock);*lock=0;}
static int decon_commit_frame(struct decon_drm *display,struct drm_framebuffer *fb){assert(display->commit_lock&&fb);return commit_result;}
static void drm_framebuffer_unreference(struct drm_framebuffer *fb){assert(fb->refs>0);fb->refs--;}
static void drm_send_vblank_event(struct drm_device *dev,int pipe,struct drm_pending_vblank_event *event){assert(dev&&pipe==0&&observed->pending==NULL);completed++;free(event);}
static void drm_vblank_put(struct drm_device *dev,int pipe){assert(dev&&pipe==0);puts++;}
static void wake_up_interruptible(int *q){(void)q;wakes++;}
static void kfree(void *p){free(p);}
static void queue_work(int w,struct work_struct *work){(void)w;assert(work);queued++;}
static void drm_object_property_set_value(int *base,void *prop,int value){(void)base;(void)prop;power_state=value;}
'''
main=r'''
static struct drm_pending_vblank_event *event_for(struct drm_file *file){struct drm_pending_vblank_event *e=calloc(1,sizeof(*e));assert(e);e->base.file_priv=file;return e;}
int main(void){
 struct drm_device drm={0};struct decon_device parent={.drm_owned=true,.state=DECON_STATE_OFF};
 struct drm_file owner={.is_master=true},other={0};struct drm_framebuffer old={1},next={1};
 struct decon_drm display={.drm=&drm,.decon=&parent,.scanout_fb=&old,.pending=&next};
 observed=&display;parent.native_drm=&display;display.event=event_for(&owner);
 commit_result=-EAGAIN;decon_flip_work(&display.flip_work);
 assert(display.deferred&&display.pending==&next&&next.refs==1&&old.refs==1);
 assert(completed==0&&puts==0&&!display.error&&display.event);
 parent.state=1;decon_drm_power_state(&parent,true);
 assert(queued==1&&power_state==DRM_MODE_DPMS_ON&&completed==0);
 commit_result=0;decon_flip_work(&display.flip_work);
 assert(!display.deferred&&!display.pending&&!display.event&&display.scanout_fb==&next);
 assert(completed==1&&puts==1&&next.refs==1&&old.refs==0);
 /* Close a different file cannot cancel the owner's deferred flip. */
 struct drm_framebuffer another={1};parent.state=0;display.pending=&another;display.event=event_for(&owner);
 commit_result=-EAGAIN;decon_flip_work(&display.flip_work);
 decon_cancel_pending(&display,&other);assert(display.pending==&another&&another.refs==1);
 decon_cancel_pending(&display,&owner);
 assert(!display.pending&&!display.event&&!display.deferred&&another.refs==0);
 assert(completed==1&&puts==2&&wakes==1&&owner.event_space==sizeof(int));
 /* Work queued concurrently with close must not use the cancelled buffer. */
 decon_flip_work(&display.flip_work);assert(puts==2&&completed==1);
 struct drm_framebuffer failed={1};display.pending=&failed;display.event=event_for(&owner);parent.state=1;
 commit_result=-EIO;decon_flip_work(&display.flip_work);
 assert(display.error==-EIO&&!display.pending&&!display.event&&failed.refs==0);
 assert(completed==1&&puts==3&&wakes==2&&display.scanout_fb==&next&&next.refs==1);
 /* Unblank may complete between the hardware check and worker return. */
 struct drm_framebuffer raced={1};display.error=0;display.pending=&raced;display.event=event_for(&owner);
 parent.state=1;commit_result=-EAGAIN;int queued_before=queued;
 decon_flip_work(&display.flip_work);
 assert(display.deferred&&display.pending==&raced&&!display.error&&queued==queued_before+1);
 assert(completed==1&&raced.refs==1);
 commit_result=0;decon_flip_work(&display.flip_work);
 assert(completed==2&&puts==4&&raced.refs==1&&next.refs==0&&!display.pending);
 printf("Actual DRM callbacks: off-panel deferral, real completion, close cancellation and failed-flip retention passed\n");
}
'''
# Avoid the standard puts() name in this isolated fixture.
source=a.output/'drm-flip.c';source.write_text((header+'\n'.join(parts)+main).replace('puts','vblank_puts'))
subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror',str(source),'-o',str(a.output/'drm-flip')],check=True)
subprocess.run([str(a.output/'drm-flip')],check=True)
