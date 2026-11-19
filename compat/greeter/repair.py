#!/usr/bin/env python3
"""Build a pinned GDM account-tile pointer re-entry repair. Does not authenticate."""
import argparse
import hashlib
from pathlib import Path

SOURCE_SHA256 = '2b49f11ebe3dbbcc8ca32f8e81d0b69e254c196e80bfa4d8eb4e4f13838de196'
METHODS = '''    vfunc_button_press_event(event) {
        // Track only a real primary press on this account tile.
        if (event.get_button() === 1) {
            this._g955nPress = {
                device: event.get_device(),
                time: event.get_time(),
            };
        }
        return super.vfunc_button_press_event(event);
    }

    vfunc_button_release_event(event) {
        const press = this._g955nPress;
        this._g955nPress = null;
        const serial = this._g955nClickSerial ?? 0;
        const result = super.vfunc_button_release_event(event);
        // St.Button 46 clears its device when a held pointer leaves, then
        // re-enters with a NULL device. Its release consequently stays pressed.
        // Repair only this stuck state; retain native successful clicks/cancels.
        if (!press || event.get_button() !== 1 ||
            press.device !== event.get_device() || !this.pressed ||
            (this._g955nClickSerial ?? 0) !== serial)
            return result;
        const elapsed = (event.get_time() - press.time) >>> 0;
        const [x, y] = event.get_coords();
        const [left, top] = this.get_transformed_position();
        const [width, height] = this.get_transformed_size();
        this.fake_release();
        if (elapsed <= 3000 && this.mapped && this.reactive &&
            x >= left && y >= top && x < left + width && y < top + height) {
            this.emit('clicked', 1);
            return Clutter.EVENT_STOP;
        }
        return result;
    }

'''

def build(source):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('Unreviewed installed GNOME login resource')
    text = source.decode()
    needle = "    vfunc_clicked() {\n        this.emit('activate');\n    }"
    if text.count(needle) != 1:
        raise ValueError('Unexpected account tile class')
    return text.replace(needle, METHODS + needle.replace("        this.emit", "        this._g955nClickSerial = (this._g955nClickSerial ?? 0) + 1;\n        this.emit"))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    a.output.write_text(build(a.source.read_bytes()))
