#!/usr/bin/env python3
"""Exercise the actual gralloc1 release branch with ASan-owned handles."""
import argparse
from pathlib import Path
import subprocess
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
s=a.source.read_text();start=s.index('    ) else if GRALLOC1(',s.index('int hybris_gralloc_release('))+len('    ) else if GRALLOC1(');end=s.index('    ) else if GRALLOC0(',start);body=s[start:end]
assert 'ret == 0 && !gralloc1_release_implies_delete && !was_allocated' in body
prefix=r'''
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
struct handle {int alive,allocated;};typedef struct handle *buffer_handle_t;typedef struct handle native_handle_t;
static int gralloc1_release_implies_delete,fail_release,vendor_frees,manual_closes,manual_frees;static void *gralloc1_device;
static int gralloc1_release(void *device,buffer_handle_t handle){(void)device;if(fail_release)return -5;if(handle->allocated||gralloc1_release_implies_delete){++vendor_frees;free(handle);}return 0;}
static __attribute__((noinline)) void native_handle_close(native_handle_t *handle){assert(handle->alive);++manual_closes;}
static __attribute__((noinline)) void native_handle_delete(native_handle_t *handle){assert(handle->alive);++manual_frees;free(handle);}
'''
code=prefix+'static int release(buffer_handle_t handle,int was_allocated){int ret=-1;'+body+'return ret;}\n'+r'''
int main(int argc,char **argv){(void)argv;
 for(int allocated=0;allocated<=1;allocated++)for(int capability=0;capability<=1;capability++)for(int failure=0;failure<=1;failure++){
  struct handle *handle=malloc(sizeof(*handle));assert(handle);*handle=(struct handle){1,allocated};
  gralloc1_release_implies_delete=capability;fail_release=failure;vendor_frees=manual_closes=manual_frees=0;
  int result=release(handle,allocated);
  if(failure){assert(result==-5&&vendor_frees==0&&manual_closes==0&&manual_frees==0&&handle->alive);free(handle);}
  else {assert(!result);assert(vendor_frees==!!(allocated||capability));assert(manual_frees==(!allocated&&!capability));assert(manual_closes==manual_frees);}
 }
 puts("Actual gralloc1 release passed allocated/imported, capability and error ownership cases");return argc>2;
}
'''
a.output.mkdir(parents=True,exist_ok=True);src=a.output/'model.c';src.write_text(code);binary=a.output/'model'
flags=['cc','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer']
subprocess.run([*flags,str(src),'-o',str(binary)],check=True);subprocess.run([str(binary)],check=True)
legacy=code.replace('ret == 0 && !gralloc1_release_implies_delete && !was_allocated','!gralloc1_release_implies_delete');src=a.output/'legacy.c';src.write_text(legacy);binary=a.output/'legacy'
subprocess.run([*flags,str(src),'-o',str(binary)],check=True);result=subprocess.run([str(binary)],capture_output=True,text=True);(a.output/'legacy-result.txt').write_text(result.stderr)
# The original also frees on an error; test the actual local-buffer UAF separately.
legacy=legacy.replace('for(int failure=0;failure<=1;failure++)','for(int failure=0;failure<=0;failure++)');src.write_text(legacy);subprocess.run([*flags,str(src),'-o',str(binary)],check=True);result=subprocess.run([str(binary)],capture_output=True,text=True);(a.output/'legacy-uaf.txt').write_text(result.stderr)
if result.returncode==0 or 'heap-use-after-free' not in result.stderr:raise SystemExit('Original local-handle ownership did not reproduce ASan UAF')
print('Original release counterfactual rejected with real ASan heap-use-after-free')
