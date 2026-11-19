#!/usr/bin/env python3
"""Compile actual Hybris key hooks with real Linux pthreads; never access hardware."""
import argparse
from pathlib import Path
import re
import subprocess
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();s=a.source.read_text();functions=[]
for name in ['pthread_key_create','pthread_key_delete','pthread_setspecific','pthread_getspecific']:
 match=re.search(r'static (?:int|void\*)\s+_hybris_hook_'+name+r'\(',s);assert match,name
 start=match.start();opening=s.index('{',start);end=opening+1;depth=1
 while depth:
  depth+=(s[end]=='{')-(s[end]=='}');end+=1
 functions.append(s[start:end])
code=r'''
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <inttypes.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>
#define TRACE_HOOK(...) ((void)0)
'''+ '\n'.join(functions)+r'''
static pthread_key_t key;static pthread_barrier_t barrier;static atomic_int destructors;static int values[3];
static void destroy(void *p){assert(p==&values[1]||p==&values[2]);atomic_fetch_add(&destructors,1);}
static void *thread(void *p){assert(!_hybris_hook_pthread_setspecific(key,p));pthread_barrier_wait(&barrier);assert(_hybris_hook_pthread_getspecific(key)==p);return NULL;}
int main(int argc,char **argv){
 pthread_key_t host=999;
 if(argc==2&&!strcmp(argv[1],"--legacy")){
  assert(!pthread_key_create(&host,NULL)&&host==0);assert(!pthread_setspecific(host,&values[0]));
  assert(pthread_getspecific(host)==&values[0]);assert(_hybris_hook_pthread_getspecific(host)==NULL);
  puts("Original direct-create/get-hook mismatch reproduced on a valid glibc zero key");return 0;
 }
 int occupied=argc==2&&!strcmp(argv[1],"--host-zero");
 if(occupied){assert(!pthread_key_create(&host,NULL)&&host==0);assert(!pthread_setspecific(host,&values[0]));}
 assert(_hybris_hook_pthread_getspecific(0)==NULL);
 assert(_hybris_hook_pthread_setspecific(0,&values[2])==EINVAL);
 assert(_hybris_hook_pthread_key_delete(0)==EINVAL);
 assert(!_hybris_hook_pthread_key_create(&key,destroy)&&key!=0);
 assert(!_hybris_hook_pthread_setspecific(key,&values[0]));assert(_hybris_hook_pthread_getspecific(key)==&values[0]);
 pthread_t first,second;assert(!pthread_barrier_init(&barrier,NULL,3));
 assert(!pthread_create(&first,NULL,thread,&values[1]));assert(!pthread_create(&second,NULL,thread,&values[2]));
 pthread_barrier_wait(&barrier);assert(!pthread_join(first,NULL)&&!pthread_join(second,NULL));
 assert(atomic_load(&destructors)==2&&_hybris_hook_pthread_getspecific(key)==&values[0]);
 assert(!_hybris_hook_pthread_key_delete(key));
 for(int n=0;n<128;n++){assert(!_hybris_hook_pthread_key_create(&key,NULL)&&key!=0);assert(!_hybris_hook_pthread_key_delete(key));}
 if(occupied){assert(pthread_getspecific(host)==&values[0]);assert(!pthread_key_delete(host));}
 puts("Actual hooks passed zero-key reservation, host-zero preservation, thread isolation/destructors and 128 reuse cycles");return 0;
}
'''
a.output.mkdir(parents=True,exist_ok=True);src=a.output/'model.c';src.write_text(code);binary=a.output/'model'
subprocess.run(['cc','-O1','-Wall','-Wextra','-Werror','-pthread',str(src),'-o',str(binary)],check=True)
for args in [[],['--host-zero'],['--legacy']]:subprocess.run([str(binary),*args],check=True)
