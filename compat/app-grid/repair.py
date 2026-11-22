#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build the reviewed GNOME 46 app-grid pointer repair; no handset operations."""
import argparse
import hashlib
from pathlib import Path

SOURCE_SHA256 = '4477ac78dcddbad84899a9bce69d7b5a99db3c0099c94a610c4c56dcc0fc6c0f'
GUARD_POINT = '''        if (!this._expandTitleOnHover || !this.icon.label)
            return;'''
PRESS_GUARD = '''        // Focus/hover notifications can arrive between the press and its
        // release. Never change the label allocation during that transaction.
        const buttons = Clutter.ModifierType.BUTTON1_MASK |
            Clutter.ModifierType.BUTTON2_MASK | Clutter.ModifierType.BUTTON3_MASK;
        if (this.pressed || (global.get_pointer()[2] & buttons))
            return;

'''
ORIGINAL = '        const expand = this._forcedHighlight || this.hover || this.has_key_focus();'
REPLACEMENT = '''        // A touchscreen's emulated hover arrives with the press. Expanding
        // an ellipsized title then reallocates the tile under that press and
        // AppIcon's leave handler cancels it before release. Keep the hit area
        // stable; keyboard focus and explicit menu highlighting still expand.
        const expand = this._forcedHighlight || this.has_key_focus();'''

LEAVE_GUARD = '''        const press = this._g955nPress;
        if (press && this.pressed && press.device === event.get_device() &&
            !this._dragging && !this._menu?.isOpen &&
            ((event.get_time() - press.time) >>> 0) <= 600) {
            const [x, y] = event.get_coords();
            const [left, top] = this.get_transformed_position();
            const [width, height] = this.get_transformed_size();
            // X11's DND grab can synthesize a leave without pointer motion.
            // It must not cancel a real press still inside the same tile.
            if (this.mapped && this.reactive &&
                x >= left && y >= top && x < left + width && y < top + height &&
                x >= press.left && y >= press.top &&
                x < press.left + press.width && y < press.top + press.height)
                return Clutter.EVENT_PROPAGATE;
        }
        this._g955nPress = null;
'''
PRESS_TRACK = '''        const button = event.get_button();
        this._g955nPress = null;
        if (button === 1) {
            const [left, top] = this.get_transformed_position();
            const [width, height] = this.get_transformed_size();
            this._g955nPress = {device: event.get_device(), time: event.get_time(),
                left, top, width, height};
        }
        const ret = super.vfunc_button_press_event(event);'''
RELEASE_METHOD = '''    vfunc_button_release_event(event) {
        try {
            return super.vfunc_button_release_event(event);
        } finally {
            this._g955nPress = null;
        }
    }

'''


def build(source):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('Unreviewed installed GNOME app-display resource')
    text = source.decode()
    if text.count(ORIGINAL) != 1 or text.count(GUARD_POINT) != 1:
        raise ValueError('Unexpected GNOME title expansion implementation')
    text = text.replace(GUARD_POINT, PRESS_GUARD + GUARD_POINT).replace(ORIGINAL, REPLACEMENT)
    prefix, icon = text.split('export const AppIcon = GObject.registerClass', 1)
    replacements = [
        ('    vfunc_leave_event(event) {\n', '    vfunc_leave_event(event) {\n' + LEAVE_GUARD),
        ('''        const ret = super.vfunc_button_press_event(event);
        const button = event.get_button();''', PRESS_TRACK),
        ('    vfunc_touch_event(event) {\n', RELEASE_METHOD + '''    vfunc_touch_event(event) {
        if (event.type() === Clutter.EventType.TOUCH_CANCEL)
            this._g955nPress = null;
'''),
        ('    _onDragBegin() {\n', '    _onDragBegin() {\n        this._g955nPress = null;\n'),
        ('    popupMenu(side = St.Side.LEFT) {\n', '    popupMenu(side = St.Side.LEFT) {\n        this._g955nPress = null;\n'),
    ]
    for before, after in replacements:
        if icon.count(before) != 1:
            raise ValueError('Unexpected GNOME app-icon event implementation')
        icon = icon.replace(before, after)
    return prefix + 'export const AppIcon = GObject.registerClass' + icon


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(build(args.source.read_bytes()))
