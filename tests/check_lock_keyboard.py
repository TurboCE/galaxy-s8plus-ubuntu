#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Run the actual generated keyboard safety methods; no credentials involved."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import tempfile
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--resource',type=Path,required=True)
a=p.parse_args()
spec=importlib.util.spec_from_file_location('repair',Path(__file__).resolve().parents[1]/'compat/lock-screen/repair.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
text=a.resource.read_text()
assert m.ACTOR_GUARD in text
assert '_g955nTouches' not in text
assert "if (!Meta.is_wayland_compositor())\n                return Clutter.EVENT_PROPAGATE;" in text
methods=[]
for name in ('maybeHandleEvent','_syncEnabled'):
 start=text.index('    '+name+'(')
 end=text.index('\n    }',start)+len('\n    }')
 methods.append(text[start:end])
js='''const assert=require('node:assert/strict');
let actor=null,deliveries=[];
const global={stage:{get_event_actor:()=>actor}};
const Main={layoutManager:{keyboardBox:{contains:a=>{assert(a);return !!a.inside;}}}};
const SHOW_KEYBOARD='screen-keyboard-enabled';
class Controller {
 constructor(){this._keyboard={};this.forced=true;this._a11yApplicationsSettings={get_boolean:()=>this.forced};
 this._seat={get_touch_mode:()=>{throw Error('Forced keyboard inspected the old device');}};}
'''+'\n'.join(methods)+'''}
const c=new Controller();assert.equal(c.maybeHandleEvent({}),false);
actor={inside:true,event:(e,capture)=>deliveries.push(capture)};
assert.equal(c.maybeHandleEvent({}),true);assert.deepEqual(deliveries,[true,false]);
actor={inside:false};assert.equal(c.maybeHandleEvent({}),false);
actor={_extendedKeys:true,event:(e,capture)=>deliveries.push(capture)};assert.equal(c.maybeHandleEvent({}),true);
c._keyboard=null;assert.equal(c.maybeHandleEvent({}),false);c._keyboard={};
c._lastDeviceIsTouchscreen=()=>{throw Error('Disposed device accessed');};
c._syncEnabled();assert(c._keyboard);
c.forced=false;c._seat.get_touch_mode=()=>true;c._lastDeviceIsTouchscreen=()=>true;c._syncEnabled();assert(c._keyboard);
let destroyed=0;c._seat.get_touch_mode=()=>false;c._bottomDragAction={enabled:false};
c._keyboard={setCursorLocation:x=>assert.equal(x,null),destroy:()=>destroyed++};c._syncEnabled();
assert.equal(destroyed,1);assert.equal(c._keyboard,null);assert.equal(c._bottomDragAction.enabled,true);
console.log('Generated null-actor, native forwarding and forced-keyboard device-lifetime guards passed');
'''
try:m.build(b'not the reviewed resource')
except ValueError:pass
else:raise AssertionError('Unpinned source accepted')
with tempfile.NamedTemporaryFile(suffix='.cjs',mode='w') as f:
 f.write(js);f.flush();subprocess.run(['node',f.name],check=True)
