#!/usr/bin/env python3
"""Sanitize actual gralloc deinit/release code with late EGL-owned buffers."""
import argparse
from pathlib import Path
import subprocess
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();source=a.source.read_text()
def function(name):
 start=source.index('void '+name+'(void)\n{');brace=source.index('{',start);depth=1;end=brace+1
 while depth:
  depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[start:end]
deinit=function('hybris_gralloc_deinitialize')
start=source.index('int hybris_gralloc_release(');end=source.index('int hybris_gralloc_import_buffer(',start);release=source[start:end]
left=release.index('    ) else if GRALLOC1(')+len('    ) else if GRALLOC1(');right=release.index('    ) else if GRALLOC0(',left)
body=release[left:right];tail=release[release.index('    if (ret == 0 && __atomic_load_n'):release.rindex('}')]
prefix=r'''
#include <stdlib.h>
#include <assert.h>
#include <stdio.h>
#define HAS_GRALLOC1_HEADER 1
struct module {void *dso;};struct handle {int alive;};
typedef struct handle *buffer_handle_t;typedef struct handle native_handle_t;
static struct module module;static struct module *gralloc_hardware_module;
static void *framebuffer_device,*gralloc0_alloc;static int *gralloc1_device;
static int live_buffer_references,deferred_deinitialize,closed,unloaded,fail_release;
static int gralloc1_release_implies_delete;
static void framebuffer_close(void*p){(void)p;abort();}static void gralloc_close(void*p){(void)p;abort();}
static void gralloc1_close(int*p){assert(*p==1);free(p);++closed;}
static void android_dlclose(void*p){assert(p==&module);++unloaded;}
static int gralloc1_release(int*device,buffer_handle_t h){assert(*device==1&&h->alive);if(fail_release)return -5;free(h);return 0;}
static void native_handle_close(native_handle_t*h){(void)h;abort();}static void native_handle_delete(native_handle_t*h){(void)h;abort();}
'''
code=prefix+deinit+'\nstatic int release(buffer_handle_t handle,int was_allocated){int ret=-1;'+body+tail+'}\n'+r'''
int main(void){
 gralloc1_device=malloc(sizeof(int));*gralloc1_device=1;module.dso=&module;gralloc_hardware_module=&module;
 buffer_handle_t first=malloc(sizeof(*first)),last=malloc(sizeof(*last));first->alive=last->alive=1;
 live_buffer_references=2;hybris_gralloc_deinitialize();assert(deferred_deinitialize&&closed==0&&unloaded==0);
 assert(release(first,1)==0&&live_buffer_references==1&&closed==0);
 fail_release=1;assert(release(last,1)==-5&&live_buffer_references==1&&closed==0&&last->alive);
 fail_release=0;assert(release(last,1)==0&&live_buffer_references==0&&closed==1&&unloaded==1);
 hybris_gralloc_deinitialize();assert(closed==1&&unloaded==1);
 puts("Actual gralloc delayed exit: buffers outlive deinit, failed release retains ownership, final release closes exactly once");return 0;
}
'''
a.output.mkdir(parents=True,exist_ok=True)
flags=['cc','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer']
for label,text in [('fixed',code),('early-close',code.replace('    if (__atomic_load_n(&live_buffer_references, __ATOMIC_ACQUIRE) > 0) {\n        __atomic_store_n(&deferred_deinitialize, 1, __ATOMIC_RELEASE);\n        return;\n    }\n',''))]:
 path=a.output/(label+'.c');path.write_text(text);binary=a.output/label;subprocess.run([*flags,str(path),'-o',str(binary)],check=True)
 r=subprocess.run([str(binary)],text=True,capture_output=True);(a.output/(label+'.log')).write_text(r.stdout+r.stderr)
 if label=='fixed':
  if r.returncode:raise SystemExit(r.stderr)
  print(r.stdout.strip())
 elif r.returncode==0:raise SystemExit('Old early-close unexpectedly accepted')
print('Early-close counterfactual rejected; hardware GNOME helper separately verifies genuine shutdown')
