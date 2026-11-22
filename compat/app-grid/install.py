#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Explicitly install a reviewed app-grid resource; never restart or authenticate."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile

PREFIX = Path('/opt/g955n-native-gpu')
RESOURCE = PREFIX / 'direct-shell/ui/appDisplay.js'
MANIFEST = PREFIX / 'manifest.json'
DEFAULT = Path('/var/lib/g955n/direct-panel-trial/enabled-default.json')
SOURCE = '/org/gnome/shell/ui/appDisplay.js'
SOURCE_SHA256 = '4477ac78dcddbad84899a9bce69d7b5a99db3c0099c94a610c4c56dcc0fc6c0f'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def trusted(path):
    for item in (path, *path.parents):
        s = item.lstat()
        if s.st_uid or s.st_mode & 0o022 or stat.S_ISLNK(s.st_mode):
            raise RuntimeError('Untrusted installation path: ' + str(item))


def replace(path, data, mode):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.app-grid-')
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--replace-sha256', help='Explicitly reviewed existing overlay hash')
    args = parser.parse_args()
    if not args.install or os.geteuid() or b'SM-G955N' not in Path('/proc/device-tree/model').read_bytes():
        raise SystemExit('Explicit root installation on SM-G955N required')
    original = subprocess.check_output(['gresource', 'extract',
        '/usr/lib/gnome-shell/libshell-14.so', SOURCE])
    if digest(original) != SOURCE_SHA256:
        raise RuntimeError('Installed GNOME app-display version changed')
    payload = args.payload.read_bytes()
    if digest(payload) != args.sha256:
        raise RuntimeError('Reviewed app-display payload hash mismatch')
    for path in (MANIFEST, DEFAULT, PREFIX / 'session.py', RESOURCE.parent):
        trusted(path)
    launcher = (PREFIX / 'session.py').read_text()
    if 'gnome_lock_sources' not in launcher or 'G_RESOURCE_OVERLAYS' not in launcher:
        raise RuntimeError('Existing resource overlay/source verification unavailable')
    expected = json.loads(DEFAULT.read_text())
    if not all(digest((PREFIX / name).read_bytes()) == sha for name, sha in expected.items()):
        raise RuntimeError('Existing default GPU files changed')
    manifest = json.loads(MANIFEST.read_text())
    if manifest['target'] != 'SM-G955N':
        raise RuntimeError('Wrong GPU prefix target')
    for name, record in manifest['files'].items():
        path = PREFIX / name
        if not path.resolve().is_relative_to(PREFIX):
            raise RuntimeError('Escaping manifest path')
        trusted(path)
        if digest(path.read_bytes()) != record['sha256']:
            raise RuntimeError('Existing GPU manifest mismatch')
    if RESOURCE.exists():
        trusted(RESOURCE)
        if str(RESOURCE.relative_to(PREFIX)) not in manifest['files']:
            raise RuntimeError('Untracked app-display overlay already exists')
        if RESOURCE.read_bytes() != payload and digest(RESOURCE.read_bytes()) != args.replace_sha256:
            raise RuntimeError('Existing app-display overlay needs a separate review')
    key = str(RESOURCE.relative_to(PREFIX))
    manifest['files'][key] = {'sha256': digest(payload),
        'license': 'GPL-2.0-or-later; generated from installed GNOME Shell'}
    manifest.setdefault('gnome_lock_sources', {})[SOURCE] = SOURCE_SHA256
    encoded = (json.dumps(manifest, indent=2) + '\n').encode()
    expected[key] = digest(payload)
    expected['manifest.json'] = digest(encoded)
    targets = {RESOURCE: (payload, 0o644), MANIFEST: (encoded, 0o644),
        DEFAULT: ((json.dumps(expected, indent=2) + '\n').encode(), 0o600)}
    originals = {path: (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
        if path.exists() else None for path in targets}
    backup = Path('/var/lib/g955n/app-grid-backups')
    backup.mkdir(mode=0o700, exist_ok=True)
    trusted(backup)
    backup = Path(tempfile.mkdtemp(
        prefix=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S-'), dir=backup))
    for i, (path, old) in enumerate(originals.items()):
        if old:
            (backup / str(i)).write_bytes(old[0])
    (backup / 'paths.json').write_text(json.dumps({str(i): str(p) for i, p in enumerate(originals)}))
    try:
        for path, (data, mode) in targets.items():
            replace(path, data, mode)
        if not all(digest((PREFIX / name).read_bytes()) == sha for name, sha in expected.items()):
            raise RuntimeError('Installed app-grid/default readback mismatch')
    except BaseException:
        for path, old in originals.items():
            if old is None:
                path.unlink(missing_ok=True)
            else:
                replace(path, *old)
        raise
    print('App-grid touch repair/source hashes installed. GNOME not restarted.')


if __name__ == '__main__':
    main()
