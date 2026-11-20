#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Execute candidate USB sleep methods with power/state fault injection."""
import argparse
from pathlib import Path
import subprocess
import tempfile


def function(source, name):
    start = source.index('int ' + name + '(')
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--kernel-dir', type=Path, required=True)
args = parser.parse_args()
directory = args.kernel_dir / 'drivers/usb/dwc3'
source = (directory / 'otg.c').read_text()
quiesce = function(source, 'dwc3_otg_quiesce_gadget')
# Use the actual serialized runner as well, including its second ready check.
runner = source[source.index('void dwc3_otg_run_sm('):]
runner = runner[:runner.index('\n}\n') + 3]
core = (directory / 'core.c').read_text()
suspend = core[core.index('static int dwc3_suspend('):core.index('static int dwc3_resume(')]
assert suspend.index('dwc3_otg_stop(dwc)') < suspend.index('dwc3_otg_quiesce_gadget(dwc)')
assert suspend.index('dwc3_otg_quiesce_gadget(dwc)') < suspend.index('dwc3_event_buffers_cleanup(dwc)')
assert 'samsung,quiesce-gadget-in-system-sleep' in suspend
gadget = function((directory / 'gadget.c').read_text(), 'dwc3_gadget_vbus_session')
assert gadget.rstrip().endswith('return ret;\n}')

shim = r'''
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#define OTG_STATE_B_PERIPHERAL 2
#define OTG_STATE_B_IDLE 1
#define OTG_STATE_A_HOST 3
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define dev_info(d,...) ((void)(d))
#define dev_err(d,...) ((void)(d))
struct usb_otg {int state; void *gadget;};
struct otg_fsm {int lock, id, b_sess_vld;};
struct dwc3_otg {struct usb_otg otg; struct otg_fsm fsm; int ready;};
struct dwc3 {struct dwc3_otg *dotg; int dev;};
static int locked, calls, restores, failure, powered=1, raced, runs;
static struct dwc3_otg *active;
static void mutex_lock(int *lock) {
    (void)lock; assert(!locked); locked=1;
    if (raced) active->ready=0;
}
static void mutex_unlock(int *lock) {(void)lock;assert(locked);locked=0;}
static int otg_start_gadget(struct otg_fsm *fsm,int on) {
    assert(locked && powered && !on && fsm->id && fsm->b_sess_vld);
    calls++;return failure;
}
static int usb_gadget_vbus_connect(void *gadget) {
    assert(locked && powered && gadget);restores++;return 0;
}
static int dwc3_otg_statemachine(struct otg_fsm *fsm) {
    (void)fsm;assert(locked && active->ready);runs++;return 0;
}
'''
main = r'''
int main(void) {
    struct dwc3_otg otg={.otg={OTG_STATE_B_PERIPHERAL,(void *)1},
                        .fsm={0,1,1},.ready=0};
    struct dwc3 core={&otg,0};active=&otg;
    assert(!dwc3_otg_quiesce_gadget(&core));
    assert(otg.otg.state==OTG_STATE_B_IDLE && calls==1 && !restores);
    assert(otg.fsm.id==1 && otg.fsm.b_sess_vld==1 && !locked);
    assert(!dwc3_otg_quiesce_gadget(&core) && calls==1);
    otg.otg.state=OTG_STATE_A_HOST;
    assert(!dwc3_otg_quiesce_gadget(&core) && calls==1);
    otg.otg.state=OTG_STATE_B_PERIPHERAL;failure=-110;
    assert(dwc3_otg_quiesce_gadget(&core)==-110);
    assert(otg.otg.state==OTG_STATE_B_PERIPHERAL && calls==2 && restores==1);
    assert(powered && !locked && otg.fsm.id && otg.fsm.b_sess_vld);
    otg.ready=1;raced=1;dwc3_otg_run_sm(&otg.fsm);
    assert(!runs && !locked);
    raced=0;otg.ready=1;dwc3_otg_run_sm(&otg.fsm);
    assert(runs==1 && !locked);
    puts("USB sleep: quiesce, unchanged VBUS/ID, failed-halt restore, host exclusion and stop race passed");
}
'''
with tempfile.TemporaryDirectory(prefix='g955n-usb-sleep-') as temp:
    fixture = Path(temp) / 'fixture.c'
    fixture.write_text(shim + quiesce + '\n' + runner + main)
    binary = Path(temp) / 'fixture'
    subprocess.run(['cc', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', str(fixture), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
