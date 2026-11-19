#!/usr/bin/env python3
"""Exercise actual X11 submission/cancel/present bodies with a fake fence/X sink.

Checks ownership and call ordering, not a hardware fence or GPU qualification.
The original dequeue-order source is a required counterfactual input.
"""
import argparse
from pathlib import Path
import subprocess
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True)
p.add_argument('--original',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
def methods(source):
 text=source.read_text();parts=[]
 for name in ['finishSwap','queueBuffer','cancelBuffer']:
  start=text.index(('void' if name=='finishSwap' else 'int')+' X11NativeWindow::'+name+'(')
  end=text.index('\n}\n',start)+3;parts.append(text[start:end])
 return '\n'.join(parts)
header=r'''
#include <cassert>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <list>
#include <deque>
#include <vector>
#include <unistd.h>
#define ANDROID_VERSION_MAJOR 9
#define ANDROID_VERSION_MINOR 0
#define NO_ERROR 0
#define HYBRIS_TRACE_BEGIN(...)
#define HYBRIS_TRACE_END(...)
#define HYBRIS_TRACE_COUNTER(...)
#define HYBRIS_ERROR(...) fprintf(stderr,"model ownership/fence rejection\n")
#define xcb_present_pixmap(...) abort()
#define xcb_flush(...) abort()
#define hybris_dump_buffer_to_file(...) abort()
using EGLint=int;
static int waited,closed,fail_fence;
static int sync_wait(int fd,int ms){assert(fd==42&&ms==1000);waited++;return fail_fence?-1:0;}
static int fake_close(int fd){assert(fd==42);closed++;return 0;}
#define close fake_close
struct X11NativeWindowBuffer {
 int id,busy=0,youngest=0,pixmap=0;
 void pixmap_from_buffer(int,int){abort();}
 void *getNativeBuffer(){return this;}
};
using BaseNativeWindowBuffer=X11NativeWindowBuffer;
static int debugenvchecked=0;
struct X11NativeWindow {
 std::list<X11NativeWindowBuffer *> m_bufList;
 std::deque<X11NativeWindowBuffer *> queue;
 X11NativeWindowBuffer *m_lastBuffer=nullptr;
 std::vector<int> shown;
 bool m_haveDRIHybris=false,locked=false;
 int m_freeBufs=2,m_connection=0,m_window=0,m_damage_n_rects=0;
 EGLint *m_damage_rects=nullptr;
 void lock(){assert(!locked);locked=true;}
 void unlock(){assert(locked);locked=false;}
 void copyToX11(X11NativeWindowBuffer *b){shown.push_back(b->id);}
 void borrow(X11NativeWindowBuffer *b){assert(!b->busy);b->busy=1;m_freeBufs--;
#ifdef LEGACY
 queue.push_back(b);
#endif
 }
 void finishSwap();int queueBuffer(BaseNativeWindowBuffer *,int);int cancelBuffer(BaseNativeWindowBuffer *,int);
};
'''
main=r'''
int main(){
 X11NativeWindow w;X11NativeWindowBuffer first{1},second{2},foreign{3};w.m_bufList={&first,&second};
 w.borrow(&first);w.borrow(&second);assert(w.m_freeBufs==0);
 assert(w.queueBuffer(&second,42)==0);assert(waited==1&&closed==1);
#ifndef LEGACY
 assert(w.queueBuffer(&second,-1)==-EINVAL);
#endif
 w.finishSwap();
 if(w.shown.size()!=1||w.shown[0]!=2){puts("Rejected original: presented dequeued buffer before its real submission");return 23;}
 assert(w.m_freeBufs==1&&second.busy==0&&first.busy==1);
 assert(w.cancelBuffer(&first,42)==0);assert(waited==2&&closed==2&&w.m_freeBufs==2);
 assert(w.queueBuffer(&foreign,-1)==-EINVAL);assert(w.cancelBuffer(&foreign,-1)==-EINVAL);
 assert(w.queueBuffer(&first,-1)==-EINVAL);
 w.borrow(&first);assert(w.queueBuffer(&first,-1)==0);assert(w.cancelBuffer(&first,-1)==-EINVAL);
 assert(w.m_freeBufs==1);w.finishSwap();assert(w.m_freeBufs==2&&w.shown.back()==1);
 w.borrow(&first);size_t before=w.shown.size();w.finishSwap();assert(w.shown.size()==before&&first.busy==1);
 assert(w.cancelBuffer(&first,-1)==0);assert(w.m_freeBufs==2&&w.queue.empty());
 puts("Actual X11 callbacks passed out-of-order submission, cancellation, duplicate/foreign ownership and no-submit retention");
}
'''
for legacy,path in [(False,a.source),(True,a.original)]:
 name='original' if legacy else 'current';source=a.output/(name+'.cpp');binary=a.output/name
 source.write_text(header+methods(path)+main)
 command=['c++','-std=c++17','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer']
 if legacy:command+=['-DLEGACY']
 subprocess.run([*command,str(source),'-o',str(binary)],check=True)
 result=subprocess.run([str(binary)],capture_output=True,text=True)
 (a.output/(name+'.log')).write_text(result.stdout+result.stderr)
 if result.returncode!=(23 if legacy else 0):raise SystemExit(name+' ownership scenario failed: '+result.stdout+result.stderr)
 print(result.stdout.strip())
