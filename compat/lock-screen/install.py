#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Install a reviewed SM-G955N keyboard overlay, without restarting GNOME."""
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
RESOURCE = PREFIX / 'direct-shell/ui/keyboard.js'
UNLOCK_RESOURCE = RESOURCE.with_name('unlockDialog.js')
LAUNCHER = PREFIX / 'session.py'
MANIFEST = PREFIX / 'manifest.json'
DEFAULT = Path('/var/lib/g955n/direct-panel-trial/enabled-default.json')
SOURCE_SHA256 = 'ca04df3bd982c4034e35c1fdb83a2744be03bf41ac04db3eb98e4129f79af575'
OVERLAY = '/org/gnome/shell/ui=' + str(RESOURCE.parent)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def trusted(path):
    for item in (path, *path.parents):
        s = item.lstat()
        if s.st_uid or s.st_mode & 0o022 or stat.S_ISLNK(s.st_mode):
            raise RuntimeError('Untrusted installation path: ' + str(item))


def replace(path, data, mode):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.lock-screen-')
    try:
        with os.fdopen(fd, 'wb') as output:
            os.fchmod(output.fileno(), mode)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--restore-stock-unlock', action='store_true',
                        help='Remove only the matching earlier G955N unlock-dialog trial')
    args = parser.parse_args()
    if not args.install or os.geteuid() or b'SM-G955N' not in Path('/proc/device-tree/model').read_bytes():
        raise SystemExit('Explicit root installation on SM-G955N required')
    original = subprocess.check_output(['gresource', 'extract',
        '/usr/lib/gnome-shell/libshell-14.so', '/org/gnome/shell/ui/keyboard.js'])
    if digest(original) != SOURCE_SHA256:
        raise RuntimeError('Installed GNOME keyboard version changed')
    payload = args.payload.read_bytes()
    if digest(payload) != args.sha256:
        raise RuntimeError('Reviewed keyboard payload hash mismatch')
    for p in (LAUNCHER, MANIFEST, DEFAULT):
        trusted(p)
    expected = json.loads(DEFAULT.read_text())
    if not all(digest((PREFIX / name).read_bytes()) == sha for name, sha in expected.items()):
        raise RuntimeError('Existing default GPU files changed')
    manifest = json.loads(MANIFEST.read_text())
    if manifest['target'] != 'SM-G955N':
        raise RuntimeError('Wrong GPU prefix target')
    for name, record in manifest['files'].items():
        p = PREFIX / name
        if not p.resolve().is_relative_to(PREFIX):
            raise RuntimeError('Escaping manifest path')
        trusted(p)
        if digest(p.read_bytes()) != record['sha256']:
            raise RuntimeError('Existing GPU manifest mismatch')
    launcher = LAUNCHER.read_text()
    marker = " 'GSK_RENDERER':'gl','GNOME_SHELL_SESSION_MODE':'ubuntu',"
    addition = "\n 'G_RESOURCE_OVERLAYS':" + repr(OVERLAY) + ','
    if addition not in launcher:
        if launcher.count(marker) != 1 or 'G_RESOURCE_OVERLAYS' in launcher:
            raise RuntimeError('Unexpected launcher overlay configuration')
        launcher = launcher.replace(marker, marker + addition)
    resource_guard = """ # Pinned lock resources must be reviewed again after a GNOME update.
 for resource, expected_source in manifest.get('gnome_lock_sources', {}).items():
  source = subprocess.check_output(['gresource','extract','/usr/lib/gnome-shell/libshell-14.so',resource])
  if hashlib.sha256(source).hexdigest()!=expected_source:raise RuntimeError('GNOME lock resource changed; regenerate reviewed overlay')
"""
    marker = " for name in ('ion','mali0'):\n"
    if 'gnome_lock_sources' not in launcher:
        if launcher.count(marker) != 1:
            raise RuntimeError('Unexpected launcher verification structure')
        launcher = launcher.replace(marker, resource_guard + marker)
    sources = manifest.setdefault('gnome_lock_sources', {})
    sources['/org/gnome/shell/ui/keyboard.js'] = SOURCE_SHA256
    remove_unlock = False
    if args.restore_stock_unlock:
        key = str(UNLOCK_RESOURCE.relative_to(PREFIX))
        source = '/org/gnome/shell/ui/unlockDialog.js'
        if UNLOCK_RESOURCE.exists():
            if (key not in manifest['files'] or sources.get(source) !=
                    'd456126f998cd0fb2d4e3e70cd58bde7c5bfbd326623c8ee1a4ab79d6e47ecdb'):
                raise RuntimeError('Unlock overlay is not the reviewed G955N trial')
            remove_unlock = True
            del manifest['files'][key]
        sources.pop(source, None)
    compile(launcher, str(LAUNCHER), 'exec')
    RESOURCE.parent.mkdir(parents=True, exist_ok=True)
    trusted(RESOURCE.parent)
    for p in (RESOURCE, UNLOCK_RESOURCE):
        if p.exists():
            trusted(p)
    key = str(RESOURCE.relative_to(PREFIX))
    manifest['files'][key] = {'sha256': digest(payload),
                              'license': 'GPL-2.0-or-later; generated from installed GNOME Shell'}
    targets = {RESOURCE: (payload, 0o644), LAUNCHER: (launcher.encode(), 0o755),
               MANIFEST: (json.dumps(manifest, indent=2).encode(), 0o644)}
    if remove_unlock:
        targets[UNLOCK_RESOURCE] = (None, None)
    updated = {}
    for name, sha in expected.items():
        target = PREFIX / name
        if target in targets:
            data = targets[target][0]
            if data is None:
                continue
            sha = digest(data)
        updated[name] = sha
    targets[DEFAULT] = (json.dumps(updated, indent=2).encode(), 0o600)
    originals = {p: (p.read_bytes(), stat.S_IMODE(p.stat().st_mode)) if p.exists()
                 else None for p in targets}
    backup = Path('/var/lib/g955n/lock-screen-backups')
    backup.mkdir(mode=0o700, exist_ok=True)
    trusted(backup)
    backup = Path(tempfile.mkdtemp(prefix=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S-'), dir=backup))
    for i, (p, old) in enumerate(originals.items()):
        if old is not None:
            (backup / str(i)).write_bytes(old[0])
    (backup/'paths.json').write_text(json.dumps({str(i): str(p) for i,p in enumerate(originals)}))
    try:
        for p, (data, mode) in targets.items():
            if data is None:
                p.unlink(missing_ok=True)
            else:
                replace(p, data, mode)
        if digest(RESOURCE.read_bytes()) != args.sha256 or remove_unlock and UNLOCK_RESOURCE.exists():
            raise RuntimeError('Keyboard resource readback failed')
        if not all(digest((PREFIX/name).read_bytes()) == sha for name,sha in updated.items()):
            raise RuntimeError('Default file verification failed')
    except BaseException:
        for p, old in originals.items():
            if old is None:
                p.unlink(missing_ok=True)
            else:
                replace(p, *old)
        raise
    print('Keyboard safety overlay and GPU startup hashes installed; GNOME not restarted')


if __name__ == '__main__':
    main()
