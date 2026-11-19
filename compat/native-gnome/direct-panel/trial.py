#!/usr/bin/env python3
"""Bounded trial of direct output in the ordinary SM-G955N GNOME session."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

PREFIX = Path('/opt/g955n-native-gpu')
KEY = 'lib/libhybris/eglplatform_x11.so'
LIBRARY = PREFIX / KEY
MANIFEST = PREFIX / 'manifest.json'
LAUNCHER = PREFIX / 'session.py'
FILES = (LIBRARY, MANIFEST, LAUNCHER)
BACKUP = Path('/var/lib/g955n/direct-panel-trial')
LEASE = Path('/run/lock/g955n-direct-panel-trial')
TIMER = 'g955n-direct-panel-rollback'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def replace(path, data):
    mode = stat.S_IMODE(path.stat().st_mode)
    fd, name = tempfile.mkstemp(prefix='.direct-output-', dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            os.fchmod(stream.fileno(), mode)
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def ctl(*args):
    subprocess.run(['systemctl', *args], check=True, timeout=45)


def restore():
    if not BACKUP.exists():
        return
    ctl('stop', 'gdm.service')
    LEASE.unlink(missing_ok=True)
    for path in FILES:
        replace(path, (BACKUP / path.name).read_bytes())
    ctl('restart', 'g955n-fb-display.service')
    ctl('start', 'gdm.service')
    for path in FILES:
        (BACKUP / path.name).unlink()
    BACKUP.rmdir()


def run(candidate, expected):
    if LEASE.exists() or BACKUP.exists():
        raise RuntimeError('A previous trial still has state; restore it before staging another')
    if b'pan_with_trial_lease' not in Path('/usr/local/sbin/g955n-fb-display').read_bytes():
        raise RuntimeError('The installed framebuffer service does not honor the trial lease')
    ctl('is-active', 'g955n-fb-display.service', 'gdm.service')
    data = candidate.read_bytes()
    if digest(data) != expected:
        raise RuntimeError('Candidate checksum mismatch')
    original = {path: path.read_bytes() for path in FILES}
    manifest = json.loads(original[MANIFEST])
    if manifest['target'] != 'SM-G955N' or digest(original[LIBRARY]) != manifest['files'][KEY]['sha256']:
        raise RuntimeError('The installed GPU prefix does not match its manifest')
    marker = b' original=dict(os.environ);env=environment(original)'
    if original[LAUNCHER].count(marker) != 1 or b'G955N_DIRECT_PANEL_TRIAL' in original[LAUNCHER]:
        raise RuntimeError('Unexpected GNOME launcher')
    BACKUP.mkdir(mode=0o700)
    for path, content in original.items():
        (BACKUP / path.name).write_bytes(content)

    # Schedule recovery on the phone before interrupting its desktop.
    try:
        subprocess.run(['systemd-run', f'--unit={TIMER}', '--on-active=150s',
                        sys.executable, str(Path(__file__).resolve()), '--restore'],
                       check=True, timeout=15)
    except (subprocess.SubprocessError, OSError):
        for path in FILES:
            (BACKUP / path.name).unlink()
        BACKUP.rmdir()
        raise
    try:
        ctl('stop', 'gdm.service')
        fd = os.open(LEASE, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o644)
        os.close(fd)
        # Reopen the legacy presenter while GDM is stopped. All future pans
        # will go through the lease, including the next greeter.
        ctl('restart', 'g955n-fb-display.service')
        manifest['files'][KEY]['sha256'] = expected
        replace(LIBRARY, data)
        replace(MANIFEST, json.dumps(manifest, indent=2).encode())
        replace(LAUNCHER, original[LAUNCHER].replace(
            marker, marker + b";env['G955N_DIRECT_PANEL_TRIAL']='1'"))
        ctl('start', 'gdm.service')
    except (subprocess.SubprocessError, OSError):
        restore()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--candidate', type=Path)
    mode.add_argument('--restore', action='store_true')
    parser.add_argument('--sha256')
    args = parser.parse_args()
    if os.getuid() or b'SM-G955N' not in Path('/proc/device-tree/model').read_bytes():
        raise RuntimeError('Requires root on the SM-G955N')
    if args.restore:
        restore()
        return
    if '#32 ' not in subprocess.check_output(['uname', '-v'], text=True):
        raise RuntimeError('The trial is qualified only against the kernel32 ABI')
    if Path('/proc/sys/kernel/tainted').read_text().strip() != '0':
        raise RuntimeError('Expected an untainted kernel before the trial')
    # The delayed root recovery must invoke a trusted copy of this file.
    own_file = Path(__file__).resolve()
    for path in (own_file, *own_file.parents):
        info = path.stat()
        if info.st_uid or info.st_mode & 0o022:
            raise RuntimeError('Install the trial controller under a root-owned prefix')
    run(args.candidate, args.sha256)


if __name__ == '__main__':
    main()
