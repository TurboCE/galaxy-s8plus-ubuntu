# GNOME 46 keyboard safety overlay

This version-pinned overlay adds two guards to the SM-G955N native GNOME
session. An event without a surviving actor is not forwarded to the keyboard.
When the accessibility keyboard is explicitly enabled, automatic touchscreen
detection is skipped, avoiding access to a disposed last-input device on X11.
Native event routing, the unlock dialog and PAM authentication are retained.
The patch contains no credentials, input logging or automatic unlocking.

Generate from the installed original keyboard resource:

```
gresource extract /usr/lib/gnome-shell/libshell-14.so /org/gnome/shell/ui/keyboard.js > ORIGINAL_KEYBOARD
python3 compat/lock-screen/repair.py --source ORIGINAL_KEYBOARD --output KEYBOARD
node --check --input-type=module < KEYBOARD
python3 tests/check_lock_keyboard.py --resource KEYBOARD
```

The original resource's exact hash is required. Generated files retain upstream
content and licensing; the full module is not redistributed here. See the
[GNOME Shell keyboard source](https://gitlab.gnome.org/GNOME/gnome-shell/-/blob/46.0/js/ui/keyboard.js).

After identity, recovery and backup verification, `install.py --install
--payload KEYBOARD --sha256 HASH` installs as root on SM-G955N only. It checks
the existing GPU files and original GNOME resource, backs up changed files,
updates the launcher/manifest/startup hashes and rolls back failed writes.
The optional `--restore-stock-unlock` removes only the matching earlier G955N
unlock-dialog trial. Runtime source pins reject an overlay after a GNOME update
until its source has been reviewed again.

Activate through normal logout/login. The installer does not restart GNOME.
Forcing the Shell service to restart while locked previously activated GNOME's
failed-session target; recovery required a fresh normal session.

The handler fixture executes the generated methods to check absent actors,
native event forwarding and device lifetime under a forced keyboard. Device
acceptance additionally waits for the actual prepared keyboard and protected
entry focus, checks one character per touch without reading password contents,
and verifies normal PAM unlock. Earlier blind coordinate/timing trials were
inconclusive and are not acceptance evidence. See VALIDATION.md for physical
device results and remaining limits.
