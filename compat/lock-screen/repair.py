#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build a pinned GNOME 46 keyboard safety overlay; native routing is retained."""
import argparse
import hashlib
from pathlib import Path

SOURCE_SHA256 = 'ca04df3bd982c4034e35c1fdb83a2744be03bf41ac04db3eb98e4129f79af575'
ACTOR_GUARD = '''        const actor = global.stage.get_event_actor(event);
        // Resume/cancel events can have no surviving actor to forward to.
        if (!actor)
            return false;
'''


def build(source):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('Unreviewed GNOME keyboard resource')
    text = source.decode()
    actor = '        const actor = global.stage.get_event_actor(event);\n'
    auto = '        let autoEnabled = this._seat.get_touch_mode() && this._lastDeviceIsTouchscreen();'
    if text.count(actor) != 1 or text.count(auto) != 1:
        raise ValueError('Unexpected GNOME keyboard structure')
    text = text.replace(actor, ACTOR_GUARD)
    # A forced accessibility keyboard needs no auto-detection. The old last
    # device can already be disposed during X11 device disable/resume.
    return text.replace(auto,
        '        let autoEnabled = !enableKeyboard && this._seat.get_touch_mode() && this._lastDeviceIsTouchscreen();')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(build(args.source.read_bytes()))
