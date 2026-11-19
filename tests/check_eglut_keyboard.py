#!/usr/bin/env python3
"""Exercise the actual patched Mesa capability callback without a display."""
import argparse
from pathlib import Path
import subprocess
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();s=a.source.read_text();start=s.index('static void\nseat_capabilities(');opening=s.index('{',start);depth=1;end=opening+1
while depth:
 depth+=(s[end]=='{')-(s[end]=='}');end+=1
function=s[start:end]
code=r'''
#include <assert.h>
#include <stddef.h>
#define WL_SEAT_CAPABILITY_KEYBOARD 2
#define CLOCK_MONOTONIC 1
#define TFD_CLOEXEC 1
#define TFD_NONBLOCK 2
struct wl_keyboard {int alive;};struct wl_seat {int unused;};
enum wl_seat_capability { NONE=0, KEYBOARD=2 };
struct display {struct {struct wl_keyboard *keyboard;int key_repeat_fd;} seat;};
static struct wl_keyboard keyboard;static int created,destroyed,opened,closed;
static const int keyboard_listener=1;
static struct wl_keyboard *wl_seat_get_keyboard(struct wl_seat *s){(void)s;assert(!keyboard.alive);keyboard.alive=1;++created;return &keyboard;}
static void wl_keyboard_add_listener(struct wl_keyboard *k,const int *l,void *data){assert(k&&l&&data);}
static void wl_keyboard_destroy(struct wl_keyboard *k){assert(k&&k->alive);k->alive=0;++destroyed;}
static int timerfd_create(int clock,int flags){assert(clock==1&&flags==3);++opened;return 100+opened;}
static int close(int fd){assert(fd>=101);++closed;return 0;}
'''+function+r'''
int main(void){
 struct display d={.seat={.key_repeat_fd=-1}};struct wl_seat seat={0};
 seat_capabilities(&d,&seat,NONE);assert(!created&&!destroyed&&!opened&&!closed);
 seat_capabilities(&d,&seat,KEYBOARD);seat_capabilities(&d,&seat,KEYBOARD);
 assert(created==1&&opened==1&&closed==0);
 seat_capabilities(&d,&seat,NONE);seat_capabilities(&d,&seat,NONE);
 assert(d.seat.keyboard==NULL&&d.seat.key_repeat_fd==-1&&destroyed==1&&closed==1);
 seat_capabilities(&d,&seat,KEYBOARD);seat_capabilities(&d,&seat,NONE);
 assert(created==2&&destroyed==2&&opened==2&&closed==2);return 0;
}
'''
a.output.mkdir(parents=True,exist_ok=True);source=a.output/'model.c';source.write_text(code);binary=a.output/'model'
subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(source),'-o',str(binary)],check=True)
subprocess.run([str(binary)],check=True);print('Actual callback passed initial no-keyboard, repeated grants/removals and timer ownership')
