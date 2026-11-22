// SPDX-License-Identifier: GPL-2.0-or-later
import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as AppDisplay from 'resource:///org/gnome/shell/ui/appDisplay.js';

export default class AppGrid extends Extension {
    enable() {
        this._settings = this.getSettings();
        this._icons = new Map();
        this._pending = new Map();
        this._sources = new Set();
        this._budget = 160;
        this._capture = global.stage.connect('captured-event', (_stage, event) => {
            this._event(event);
            return Clutter.EVENT_PROPAGATE;
        });
        this._overview = Main.overview.connect('shown', () => {
            let source = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 800, () => {
                this._sources.delete(source);
                this._geometry();
                return GLib.SOURCE_REMOVE;
            });
            this._sources.add(source);
        });
        console.log('G955N_APP_GRID enabled');
    }

    _geometry() {
        const visit = actor => {
            if (actor instanceof AppDisplay.AppIcon &&
                ['org.gnome.Settings.desktop', 'org.gnome.SystemMonitor.desktop'].includes(actor.app.get_id())) {
                const [x, y] = actor.get_transformed_position();
                const [width, height] = actor.get_transformed_size();
                this._report(`${actor.app.get_id()} geometry=${x},${y},${width},${height} mapped=${actor.mapped}`);
            }
            for (const child of actor.get_children())
                visit(child);
        };
        visit(global.stage);
    }

    _report(text) {
        if (this._settings.get_boolean('diagnostic-enabled') && this._budget-- > 0)
            console.log(`G955N_APP_GRID ${text}`);
    }

    _icon(actor) {
        for (let node = actor; node; node = node.get_parent()) {
            if (node instanceof AppDisplay.AppIcon)
                return node;
        }
        return null;
    }

    _watch(icon) {
        if (this._icons.has(icon))
            return this._icons.get(icon);
        const state = {serial: 0, signals: []};
        state.signals.push(icon.connect('clicked', () => {
            state.serial++;
            this._report(`${icon.app.get_id()} clicked serial=${state.serial}`);
        }));
        state.signals.push(icon.connect('notify::pressed', () =>
            this._report(`${icon.app.get_id()} pressed=${icon.pressed}`)));
        state.signals.push(icon.connect('destroy', () => {
            this._icons.delete(icon);
            for (const [device, press] of this._pending) {
                if (press.icon === icon)
                    this._pending.delete(device);
            }
        }));
        this._icons.set(icon, state);
        return state;
    }

    _event(event) {
        const type = event.type();
        const interesting = [Clutter.EventType.BUTTON_PRESS, Clutter.EventType.BUTTON_RELEASE,
            Clutter.EventType.TOUCH_BEGIN, Clutter.EventType.TOUCH_END,
            Clutter.EventType.TOUCH_CANCEL, Clutter.EventType.ENTER, Clutter.EventType.LEAVE];
        if (!interesting.includes(type))
            return;
        const device = event.get_device();
        const icon = this._icon(global.stage.get_event_actor(event));
        const pending = this._pending.get(device);
        if (icon) {
            this._watch(icon);
            const [x, y] = event.get_coords();
            this._report(`${icon.app.get_id()} event=${type} pressed=${icon.pressed} point=${Math.round(x)},${Math.round(y)}`);
        }
        if (type === Clutter.EventType.BUTTON_PRESS && event.get_button() === 1) {
            this._pending.delete(device);
            if (icon) {
                const [x, y] = event.get_coords();
                this._pending.set(device, {icon, x, y, time: event.get_time(),
                    serial: this._watch(icon).serial});
            }
        } else if (type === Clutter.EventType.TOUCH_CANCEL) {
            this._pending.delete(device);
        } else if (type === Clutter.EventType.BUTTON_RELEASE && event.get_button() === 1 && pending) {
            this._pending.delete(device);
            const [x, y] = event.get_coords();
            const elapsed = (event.get_time() - pending.time) >>> 0;
            let source = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
                this._sources.delete(source);
                const state = this._icons.get(pending.icon);
                if (!state)
                    return GLib.SOURCE_REMOVE;
                this._report(`${pending.icon.app.get_id()} after-release pressed=${pending.icon.pressed} clicks=${state.serial - pending.serial} drag=${pending.icon._dragging ?? false} elapsed=${elapsed}`);
                return GLib.SOURCE_REMOVE;
            });
            this._sources.add(source);
        }
    }

    disable() {
        if (this._overview)
            Main.overview.disconnect(this._overview);
        if (this._capture)
            global.stage.disconnect(this._capture);
        for (const id of this._sources ?? [])
            GLib.source_remove(id);
        for (const [icon, state] of this._icons ?? []) {
            for (const id of state.signals)
                icon.disconnect(id);
        }
        this._icons?.clear();
        this._pending?.clear();
        this._settings = null;
    }
}
