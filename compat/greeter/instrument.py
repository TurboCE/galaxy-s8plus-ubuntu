#!/usr/bin/env python3
"""Build-only account-tile event diagnostics; never logs password-entry events."""
import argparse
import hashlib
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--source-sha256',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
s=a.source.read_text()
if hashlib.sha256(a.source.read_bytes()).hexdigest()!=a.source_sha256:raise SystemExit('Unreviewed installed login source')
needle='''        this.user = user;
        this.user.connectObject('changed', this._onUserChanged.bind(this), this);'''
if s.count(needle)!=1 or 'class UserListItem extends St.Button' not in s:raise SystemExit('Unexpected GNOME source layout')
replacement=needle+'''
        // Diagnostics are restricted to the account tile. Never connect to
        // the authentication prompt, keyboard, or password-entry actors.
        let budget = 24;
        const report = (kind, event = null) => {
            if (budget-- <= 0)
                return;
            const [x, y] = this.get_transformed_position();
            const [width, height] = this.get_transformed_size();
            const point = event ? event.get_coords().join(',') : '-';
            const device = event?.get_device()?.get_device_name() ?? '-';
            console.log(`G955N_ACCOUNT_TILE ${kind} pressed=${this.pressed} hover=${this.hover} box=${x},${y},${width},${height} point=${point} device=${device}`);
        };
        this.connect('captured-event', (_actor, event) => {
            const type = event.type();
            if ([Clutter.EventType.TOUCH_BEGIN, Clutter.EventType.TOUCH_END,
                Clutter.EventType.TOUCH_CANCEL, Clutter.EventType.BUTTON_PRESS,
                Clutter.EventType.BUTTON_RELEASE].includes(type))
                report(`event=${type}`, event);
            return Clutter.EVENT_PROPAGATE;
        });
        this.connect('notify::pressed', () => report('pressed'));
        this.connect('clicked', () => report('clicked'));
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1500, () => {
            report('geometry');
            return GLib.SOURCE_REMOVE;
        });'''
s=s.replace(needle,replacement);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(s)
print('Account-tile-only diagnostic resource built; no authentication behavior changed')
