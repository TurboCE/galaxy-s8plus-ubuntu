# GDM account-tile pointer re-entry repair

This GDM overlay is retained for historical comparison. The
[Mutter input fix](../mutter-x11-touch/README.md) has passed normal touch
login with the stock GDM resources on the SM-G955N.

The stock installed GNOME Shell 46 login resource is pinned by SHA256. Build
`repair.py --source ORIGINAL_LOGIN_RESOURCE --output OUTPUT` on the host, then
syntax-check the generated module with Node. No GNOME resource or vendor binary
is redistributed here. The transformed resource retains its upstream GPL notice.

The owner reproduced a failed account tap. Account-only diagnostics recorded a
primary button press, pressed true/false/true while the pointer left and
re-entered, and a release without a clicked signal. GNOME 46 St.Button clears
its remembered device on leave and reuses that cleared device on re-entry;
release from the actual device then fails its device check.
[Upstream source](https://gitlab.gnome.org/GNOME/gnome-shell/-/blob/46.0/src/st/st-button.c).

The repair tracks an account tile's primary press. It first allows the normal
release handler to run. Only a still-pressed button with no emitted native click
can recover: same device, release inside the mapped/reactive tile and at most
three seconds after the press. A recovery clears the stuck button and emits
its ordinary clicked signal. Password verification and GDM authentication are
unchanged. Keyboard activation is unchanged. No polling Return key or autologin.

`tests/check_greeter_repair.py` executes the actual generated methods for ten
success, cancellation, duplicate, outside, device, timeout and visibility cases.
These fixtures are not a substitute for physical touchscreen/reboot acceptance.

`install.py --install --payload FILE --sha256 HASH` explicitly installs only a
root-owned GDM resource overlay and GDM-specific shell desktop entry, preserving
previous files under `/var/lib/g955n/greeter-backups`. It checks model, installed
source hash, ownership and absence of an authenticated desktop. It does not
restart GDM, flash, reboot or change authentication. Restart GDM separately after
checking installation. Remove the GDM-specific desktop entry to use stock code.

`instrument.py` is an optional build-only account-tile diagnostic. It never hooks
password actors, keyboard events or the authentication prompt. Do not leave it
installed instead of the release repair.
