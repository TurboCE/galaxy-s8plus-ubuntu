#!/usr/bin/env python3
"""Explicit target installation of the pinned account-tile repair; no restart by default."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--install', action='store_true')
    p.add_argument('--payload', type=Path, required=True)
    p.add_argument('--sha256', required=True)
    a = p.parse_args()
    if not a.install:
        p.error('Explicit --install required')
    if os.getuid() != 0 or b'SM-G955N' not in Path('/proc/device-tree/model').read_bytes():
        raise SystemExit('Expected root on SM-G955N')
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            if (proc/'comm').read_text().strip() == 'gnome-shell' and proc.stat().st_uid != 105:
                raise SystemExit('Log out the desktop before changing the greeter')
        except (FileNotFoundError, ProcessLookupError):
            pass
    stock = subprocess.check_output(['gresource', 'extract', '/usr/lib/gnome-shell/libshell-14.so', '/org/gnome/shell/gdm/loginDialog.js'])
    if hashlib.sha256(stock).hexdigest() != '2b49f11ebe3dbbcc8ca32f8e81d0b69e254c196e80bfa4d8eb4e4f13838de196':
        raise SystemExit('GNOME resource version changed; review again')
    data = a.payload.read_bytes()
    if hashlib.sha256(data).hexdigest() != a.sha256:
        raise SystemExit('Payload checksum mismatch')
    desktop = Path('/usr/share/applications/org.gnome.Shell.desktop').read_text()
    original = 'Exec=/usr/bin/gnome-shell\n'
    if desktop.count(original) != 1:
        raise SystemExit('Unexpected shell desktop entry')
    desktop = desktop.replace(original, 'Exec=/usr/bin/env G_RESOURCE_OVERLAYS=/org/gnome/shell/gdm=/opt/g955n-greeter/gdm /usr/bin/gnome-shell\n')
    targets = [(Path('/opt/g955n-greeter/gdm/loginDialog.js'), data),
               (Path('/usr/share/gdm/greeter/autostart/org.gnome.Shell.desktop'), desktop.encode())]
    backup = Path('/var/lib/g955n/greeter-backups') / str(time.time_ns())
    backup.mkdir(parents=True, mode=0o700)
    for index, (target, content) in enumerate(targets):
        for parent in target.parents:
            if parent.exists() and (parent.is_symlink() or parent.stat().st_uid != 0 or parent.stat().st_mode & 0o022):
                raise SystemExit('Unsafe destination directory')
        if target.is_symlink() or (target.exists() and target.stat().st_uid != 0):
            raise SystemExit('Unsafe destination file')
        if target.exists():
            (backup/str(index)).write_bytes(target.read_bytes())
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix('.new')
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, 'wb') as f:
            f.write(content); f.flush(); os.fsync(f.fileno())
        os.replace(temp, target)
    print('Installed GDM-only account-tile repair; restart GDM explicitly when ready')

if __name__ == '__main__':
    main()
