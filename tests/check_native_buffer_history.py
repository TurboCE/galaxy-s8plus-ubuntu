#!/usr/bin/env python3
"""Actual scene history selection with two native frames behind one swap token.

The pixel sink is a model, not a GPU or physical panel qualification.
"""
import argparse
from pathlib import Path
import re
import subprocess
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--scene',type=Path,required=True);p.add_argument('--android',type=Path,required=True)
p.add_argument('--original-scene',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
s=a.scene.read_text();start=s.index('\tint renderer_buffer_age =');end=s.index('\n\trender_data.render_pass =',start);selection=s[start:end]
assert 'renderer_buffer_age' not in a.original_scene.read_text()
assert 'wlr_swapchain_acquire(output->swapchain, &buffer_age)' in a.original_scene.read_text()
t=a.android.read_text();part=t[t.index('static int android_get_buffer_age'):];match=re.search(r'return (buffer->buffer_age[^;]*);',part);assert match
getter=match[1]
base=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define wlr_log(...) ((void)0)
struct renderer {int native;};struct output {struct renderer *renderer;};
static int wlr_renderer_get_buffer_age(struct renderer *renderer,void *buffer){(void)buffer;return renderer->native;}
static int choose(int buffer_age,int native){struct renderer renderer={native};struct output owner={&renderer},*output=&owner;void *buffer=0;
SELECTION
return buffer_age;}
static int actual_android_age(int native){struct {int buffer_age;} state={native},*buffer=&state;return GETTER;}
static int pixel_case(void){
 unsigned char slots[2][64]={{0}},scene[64]={0};scene[18]=scene[19]=scene[26]=scene[27]=255;
 for(int frame=0;frame<8;frame++){
  int age=choose(1,0);unsigned char *current=slots[frame%2];
  if(age==0)memcpy(current,scene,sizeof(scene));
  else if(frame==0){current[18]=current[19]=current[26]=current[27]=255;}
  if(memcmp(current,scene,sizeof(scene)))return frame+1;
 }
 return 0;
}
int main(void){
#ifdef ORIGINAL
 if(pixel_case()!=2)return 9;puts("Original swapchain-only history reproduced background/popup alternation on second native frame");
#else
 assert(choose(3,-1)==3);assert(choose(1,0)==0);assert(choose(1,2)==2);
 assert(actual_android_age(-1)==0&&actual_android_age(0)==0&&actual_android_age(1)==1&&actual_android_age(2)==2);
 assert(pixel_case()==0);puts("Actual native history selection passed zero/known/unavailable ages and eight alternating native frames");
#endif
}
'''
for original in [False,True]:
 code=base.replace('SELECTION','' if original else selection).replace('GETTER',getter)
 name='original' if original else 'current';source=a.output/(name+'.c');binary=a.output/name;source.write_text(code)
 subprocess.run(['cc','-std=c11','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',*(['-DORIGINAL'] if original else []),str(source),'-o',str(binary)],check=True)
 subprocess.run([str(binary)],check=True)
