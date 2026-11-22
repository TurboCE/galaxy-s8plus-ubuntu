#!/usr/bin/env python3
"""Exercise the actual pinned title method, including keyboard/menu accessibility."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('app_repair', root / 'compat/app-grid/repair.py')
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)
raw = args.source.read_bytes()
patched = repair.build(raw)
try:
    repair.build(raw + b'\n')
except ValueError:
    pass
else:
    raise AssertionError('Changed upstream source was accepted')


def method(text):
    start = text.index('    _updateMultiline() {')
    end = text.index('    _onHover() {', start)
    return text[start:end]


script = '''const assert = require('node:assert/strict');
const Pango = {WrapMode: {WORD_CHAR: 1, NONE: 0}, EllipsizeMode: {NONE: 0, END: 1}};
const Clutter = {ModifierType: {BUTTON1_MASK: 1, BUTTON2_MASK: 2, BUTTON3_MASK: 4}};
let buttons = 0;
global.get_pointer = () => [0, 0, buttons];
const APP_ICON_TITLE_EXPAND_TIME = 200, APP_ICON_TITLE_COLLAPSE_TIME = 100;
class Fixture {
 constructor(options={}) {
  Object.assign(this, {_expandTitleOnHover: true, hover: true, _forcedHighlight: false,
   focused: false, pressed: false, long: true, allocations: 0, lineWrap: false}, options);
  this.icon = {label: {remove_transition() {}, connect: () => 1,
   save_easing_state() {}, set_easing_duration() {},
   clutterText: {get_layout: () => ({is_wrapped: () => false, is_ellipsized: () => this.long}),
    set: props => {
     if (this.lineWrap !== props.line_wrap) this.allocations++;
     this.lineWrap = props.line_wrap;
    }}}};
 }
 has_key_focus() {return this.focused;}
}
''' + 'class Original extends Fixture {\n' + method(raw.decode()) + '}\n' + \
    'class Repaired extends Fixture {\n' + method(patched) + '}\n' + '''
const old = new Original();old._updateMultiline();
assert.equal(old.lineWrap, true);assert.equal(old.allocations, 1);
const fixed = new Repaired();fixed._updateMultiline();
assert.equal(fixed.lineWrap, false);assert.equal(fixed.allocations, 0);
for (const opts of [{focused:true}, {_forcedHighlight:true}]) {
 const t=new Repaired(opts);t._updateMultiline();
 assert.equal(t.lineWrap,true);assert.equal(t.allocations,1);
}
for (const opts of [{long:false}, {_expandTitleOnHover:false}, {hover:false}]) {
 const t=new Repaired(opts);t._updateMultiline();assert.equal(t.allocations,0);
}
const held=new Repaired({focused:true,pressed:true});held._updateMultiline();
assert.equal(held.allocations,0);
for (const mask of [1,2,4]) {
 buttons=mask;const t=new Repaired({focused:true});t._updateMultiline();
 assert.equal(t.allocations,0);
}
buttons=0;const released=new Repaired({focused:true});released._updateMultiline();
assert.equal(released.lineWrap,true);
console.log('Pinned source guard; original hover reallocation reproduced; stable touch title, keyboard focus, menu highlight and short labels passed');
'''
icon = patched.split('export const AppIcon = GObject.registerClass', 1)[1]
event_methods = icon[icon.index('    vfunc_leave_event(event) {'):icon.index('    vfunc_touch_event(event) {')]
assert ".emit('clicked'" not in event_methods
script += '''
const device={};
Clutter.EVENT_PROPAGATE=false;Clutter.EVENT_STOP=true;
class NativeButton {
 constructor(opts={}) {Object.assign(this,{pressed:false,mapped:true,reactive:true,
  _dragging:false,_menu:null,clicks:0,left:10,top:10},opts);}
 vfunc_button_press_event() {this.pressed=true;return true;}
 vfunc_button_release_event() {if(this.pressed)this.clicks++;this.pressed=false;return true;}
 vfunc_leave_event() {this.pressed=false;return false;}
 fake_release() {this.pressed=false;}
 get_transformed_position() {return [this.left,this.top];}
 get_transformed_size() {return [100,100];}
 _removeMenuTimeout() {}
 _setPopupTimeout() {}
}
class Icon extends NativeButton {
''' + event_methods + '''}
const event=(opts={})=>({get_button:()=>opts.button??1,get_device:()=>opts.device??device,
 get_time:()=>opts.time??100,get_coords:()=>opts.point??[30,30]});
function crossing(opts={},leave={}) {
 const t=new Icon();t.vfunc_button_press_event(event());Object.assign(t,opts);
 t.vfunc_leave_event(event(leave));t.vfunc_button_release_event(event({time:300}));
 assert.equal(t._g955nPress,null);return t;
}
assert.equal(crossing().clicks,1); // synthetic grab crossing inside the same tile
for(const [opts,leave] of [
 [{},{point:[200,30]}],[{},{device:{}}],[{},{time:900}],
 [{mapped:false},{}],[{reactive:false},{}],[{_dragging:true},{}],
 [{_menu:{isOpen:true}},{}],[{left:300,top:300},{}]])
 assert.equal(crossing(opts,leave).clicks,0);
const keyboard=new Icon({pressed:true});keyboard.vfunc_leave_event(event());
assert.equal(keyboard.pressed,false);assert.equal(keyboard.clicks,0);
const once=crossing();once.vfunc_button_release_event(event());assert.equal(once.clicks,1);
console.log('Actual icon event methods: real release retained; outside, device, timeout, visibility, drag, menu, moved tile, keyboard and duplicate cancellation passed');
'''
with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary) / 'fixture.cjs'
    path.write_text(script)
    subprocess.run(['node', str(path)], check=True)
    module = Path(temporary) / 'appDisplay.mjs'
    module.write_text(patched)
    subprocess.run(['node', '--check', str(module)], check=True)
