import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

export default class DirectPanel extends Extension {
    enable() {
        if (GLib.getenv('G955N_DIRECT_PANEL_TRIAL') !== '1')
            return;

        Meta.disable_unredirect_for_display(global.display);
        this._inhibited = true;
        console.log('G955N direct panel: fullscreen X11 composition enabled');
    }

    disable() {
        if (!this._inhibited)
            return;

        Meta.enable_unredirect_for_display(global.display);
        this._inhibited = false;
    }
}
