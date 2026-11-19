#!/usr/bin/env python3
"""Exercise the actual generated account-tile release methods with event fixtures."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
spec = importlib.util.spec_from_file_location('repair', Path(__file__).resolve().parents[1]/'compat/greeter/repair.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
js = '''const assert = require('node:assert/strict');
const Clutter = {EVENT_STOP: true};
class Native {
 vfunc_button_press_event(e) {this.pressed=true;return true;}
 vfunc_button_release_event(e) {
  if(this.nativeSuccess){this.pressed=false;this.emit('clicked',1);}
  if(this.cancelled)this.pressed=false;
  return true;
 }
 fake_release(){this.pressed=false;}
 get_transformed_position(){return [10,10];}
 get_transformed_size(){return [100,50];}
 emit(name){if(name==='clicked'){this.clicks++;this._g955nClickSerial=(this._g955nClickSerial??0)+1;}}
}
class Tile extends Native {
 constructor(){super();this.clicks=0;this.mapped=true;this.reactive=true;}
''' + m.METHODS + '''}
const device={};
const event=(o={})=>({get_button:()=>o.button??1,get_device:()=>o.device??device,
 get_time:()=>o.time??100,get_coords:()=>o.coords??[30,30]});
function trial(opts,release,expected){const t=new Tile();Object.assign(t,opts);
 t.vfunc_button_press_event(event());t.vfunc_button_release_event(event(release));
 assert.equal(t.clicks,expected);return t;}
trial({}, {time:200},1); // observed stuck release
trial({nativeSuccess:true},{time:200},1); // never duplicate native click
trial({cancelled:true},{time:200},0);
trial({}, {coords:[200,30]},0);
trial({}, {device:{}},0);
trial({}, {time:5000},0);
trial({}, {button:3},0);
trial({mapped:false},{},0);
const t=new Tile();t.pressed=true;t.vfunc_button_release_event(event());assert.equal(t.clicks,0);
const repeat=trial({}, {},1);repeat.vfunc_button_release_event(event());assert.equal(repeat.clicks,1);
console.log('10 account-tile event cases passed');
'''
with tempfile.NamedTemporaryFile(suffix='.cjs',mode='w') as f:
    f.write(js);f.flush();subprocess.run(['node',f.name],check=True)
