# GNOME 46 app-grid touch hit-area stability

This Shell overlay is retained for historical comparison. The SM-G955N uses
the [Mutter input fix](../mutter-x11-touch/README.md) with stock Shell resources.

The upstream implementations are GNOME Shell's
[appDisplay.js](https://gitlab.gnome.org/GNOME/gnome-shell/-/blob/46.0/js/ui/appDisplay.js)
and [St.Button](https://gitlab.gnome.org/GNOME/gnome-shell/-/blob/46.0/src/st/st-button.c).
The source pin below is the installed Ubuntu resource, not an assumed vanilla
upstream checksum. Generated resources retain their upstream content and license.

On the SM-G955N X11/GNOME session, a fresh touch on an ellipsized app title
could reallocate the icon while the touch was held. The normal app-icon leave
handler cleared the press, so no `clicked` signal or application launch followed.
Software & Updates reproduced this after moving the pointer away and reopening
the grid. Short titles did not reproduce the same failure. This is distinct from
an application that starts and then crashes, or a missing kernel touch event.

X11's DND grab/release also produced crossing events with the pointer still
inside the icon; title changes alone did not eliminate the lost clicks.
`repair.py` transforms the hash-pinned installed `appDisplay.js`. It retains a
real primary press across these synthetic leaves only for the same device,
within600ms, inside both the original and current mapped/reactive tile, and
outside a drag or open menu. A real leave, touch cancellation, drag, menu, or
button release clears that record. The standard native release still produces
the click; the repair does not emit a replacement click or launch an app itself.

Pointer hover no longer expands titles, and title allocation is frozen while
a button is held or the actor is pressed. Keyboard focus and explicit menu
highlighting can still expand titles outside a press. No timer-based activation,
authentication change or renderer override is added. Pointer-hover title
expansion is intentionally disabled on this dedicated handset, including a mouse;
the full accessible app name is retained.

Extract the installed source from `/usr/lib/gnome-shell/libshell-14.so`, resource
`/org/gnome/shell/ui/appDisplay.js`, into a private file. Build and check it:

```
python3 compat/app-grid/repair.py --source ORIGINAL --output REVIEWED.mjs
python3 tests/check_app_grid_repair.py --source ORIGINAL
```

The test executes the actual original/repaired title and generated icon event
methods. It checks the source pin, hover allocation, press protection, keyboard
focus, explicit highlighting, short titles and genuine cancellation conditions.
It also syntax-checks the entire generated module.
Hardware click/launch acceptance is separate; see `docs/VALIDATION.md`.

`install.py --install --payload REVIEWED.mjs --sha256 REVIEWED_SHA256` explicitly
installs only the root-owned resource, GPU manifest and default hash record on
SM-G955N. It verifies the installed source, existing GPU hashes and ownership,
keeps prior files under `/var/lib/g955n/app-grid-backups`, and verifies readback.
Replacing an already tracked, different overlay additionally requires its reviewed
`--replace-sha256`. The existing startup resource-source check is extended to
this module, so a GNOME update requires review/regeneration. The script never
restarts GNOME, authenticates, flashes, changes the kernel or changes graphics
libraries. A normal logout/login activates the resource; kernel replacement does
not remove this userspace fix.

To roll back, restore the resource (or its recorded absence), manifest and default
hash record from the same pre-install backup, then log out/in normally. Do not
restore only one hash record or overwrite a newer reviewed overlay.

`extension.js`, `metadata.json` and `schemas/` are a separate, opt-in diagnostic
extension (`g955n-app-grid@local`). Compile its schema before enabling it and set
`diagnostic-enabled` explicitly. It records a bounded set of app-icon events,
pressed transitions and native clicks; it does not hook password actors or keyboard
text and does not alter input or launch apps. Disable it after diagnosis. The
production resource fix does not require user extensions to be enabled.
