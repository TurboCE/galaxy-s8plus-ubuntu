#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Join the verified BCM4773 hub and relay its GNSS data through GeoClue."""
from contextlib import ExitStack
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import time

from run_probe import MODEL, check_vendor
from serve import stop

BASE = Path(__file__).resolve().parent
HUB = 'g955n-location-hub-mainline.service'
STATE = Path('/data/vendor/gps')
FIFO_NAMES = ('.pipe.gpsd_to_lhd.to_server', '.pipe.gpsd_to_lhd.to_client')
PROC = Path('/proc')


def command(*args):
    subprocess.run(args, check=True, timeout=8)


def hub_namespace():
    deadline = time.monotonic() + 15
    while True:
        pid = subprocess.check_output(
            ['systemctl', 'show', '--property=MainPID', '--value', HUB], text=True, timeout=5,
        ).strip()
        if not pid.isdecimal() or int(pid) < 2:
            raise RuntimeError('BCM4773 hub is not running')
        base = PROC / pid
        if os.readlink(base / 'exe') == '/android/system/vendor/bin/hw/lhd':
            return base / 'ns/mnt'
        if time.monotonic() >= deadline:
            raise RuntimeError('BCM4773 location hub did not finish starting')
        time.sleep(0.25)


def fifo_identity(path):
    entry = path.lstat()
    if not stat.S_ISFIFO(entry.st_mode) or entry.st_uid != 0:
        raise RuntimeError('Unexpected GNSS FIFO')
    return entry.st_dev, entry.st_ino


def wait_for_fifos(paths):
    deadline = time.monotonic() + 12
    while True:
        try:
            return {path.name: fifo_identity(path) for path in paths}
        except FileNotFoundError:
            if time.monotonic() >= deadline:
                raise RuntimeError('The location hub did not create both GNSS FIFOs')
            time.sleep(0.25)


def require_readonly(path):
    options = subprocess.check_output(
        ['findmnt', '-T', path, '-n', '-o', 'OPTIONS'], text=True, timeout=5,
    ).strip().split(',')
    if 'ro' not in options:
        raise RuntimeError(f'Read-only mount required for {path}')


def reset_signal(*_):
    raise SystemExit(0)


def serve_in_hub():
    check_vendor()
    require_readonly('/efs')
    require_readonly('/android/system')
    signal.signal(signal.SIGTERM, reset_signal)
    signal.signal(signal.SIGINT, reset_signal)
    if STATE.is_symlink() or STATE.stat().st_uid != 0:
        raise RuntimeError('Unexpected GNSS state directory')
    paths = [STATE / filename for filename in FIFO_NAMES]
    shared = wait_for_fifos(paths)

    with ExitStack() as cleanup:
        isolated = Path(cleanup.enter_context(
            tempfile.TemporaryDirectory(prefix='.g955n-gnss-session.', dir=STATE.parent)
        ))
        for path in paths:
            os.link(path, isolated / path.name, follow_symlinks=False)

        command('mount', '--bind', str(isolated), str(STATE))
        cleanup.callback(command, 'umount', str(STATE))
        if any(fifo_identity(path) != shared[path.name] for path in paths):
            raise RuntimeError('The GNSS FIFO mount did not preserve its inode')

        socket_dir = Path('/dev/socket')
        if not socket_dir.exists():
            socket_dir.mkdir(mode=0o700)
            cleanup.callback(socket_dir.rmdir)
        command('mount', '-t', 'tmpfs', '-o', 'mode=0700,nosuid,nodev,noexec',
                'tmpfs', str(socket_dir))
        cleanup.callback(command, 'umount', str(socket_dir))

        # Keep the shared root read-only inside this clone as well.
        command('mount', '-o', 'remount,bind,ro', '/')
        cleanup.callback(command, 'mount', '-o', 'remount,bind,rw', '/')
        child = subprocess.Popen([
            '/usr/bin/setpriv', '--bounding-set=-sys_admin', '--no-new-privs',
            sys.executable, str(BASE / 'serve.py'),
        ])
        try:
            return child.wait()
        finally:
            stop(child)


def main():
    if os.geteuid() or b'SM-G955N' not in MODEL.read_bytes():
        raise SystemExit('Requires root on the SM-G955N')
    if len(sys.argv) == 2 and sys.argv[1] == 'serve':
        return serve_in_hub()
    if len(sys.argv) != 1:
        raise SystemExit('Unexpected arguments')

    namespace = hub_namespace()
    os.execv('/usr/bin/nsenter', [
        '/usr/bin/nsenter', f'--mount={namespace}', '--',
        '/usr/bin/unshare', '--mount', '--propagation', 'private',
        sys.executable, str(BASE / 'serve-mainline.py'), 'serve',
    ])


if __name__ == '__main__':
    raise SystemExit(main())
