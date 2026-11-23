#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Restore the Ubuntu Clutter library on a previously modified SM-G955N."""
import argparse
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import tempfile

LIBRARY = Path('/usr/lib/aarch64-linux-gnu/mutter-14/libmutter-clutter-14.so.0.0.0')
VERSION = '46.2-1ubuntu0.24.04.18'
STOCK_SHA = 'ea04958bb942c9e470b354012a6e2fde0ed977570add06fad6b07a5eb3ef59c8'
BACKUPS = Path('/var/lib/g955n/mutter-x11-touch')
BACKUP = BACKUPS / (LIBRARY.name + '.stock')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trusted(path):
    for entry in (path, *path.parents):
        metadata = entry.lstat()
        if metadata.st_uid or metadata.st_mode & 0o022 or stat.S_ISLNK(metadata.st_mode):
            raise RuntimeError(f'Untrusted system path: {entry}')


def replace(target, source):
    fd, temporary = tempfile.mkstemp(dir=target.parent, prefix='.g955n-clutter-')
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), 0o644)
            stream.write(source)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore', action='store_true', required=True)
    parser.add_argument('--sha256', required=True, help='SHA256 of the installed reviewed patch')
    args = parser.parse_args()
    if os.geteuid() or b'SM-G955N' not in Path('/proc/device-tree/model').read_bytes():
        raise SystemExit('Expected root on SM-G955N')
    version = subprocess.check_output(
        ['dpkg-query', '-W', '-f=${Version}', 'libmutter-14-0:arm64'], text=True)
    if version != VERSION:
        raise SystemExit('Review this change against the installed Mutter version')
    trusted(LIBRARY)
    present = digest(LIBRARY)
    if present == STOCK_SHA:
        print('Ubuntu Clutter library already verified')
        return
    trusted(BACKUP)
    if present != args.sha256 or digest(BACKUP) != STOCK_SHA:
        raise SystemExit('Unexpected installed library or stock backup')
    replace(LIBRARY, BACKUP.read_bytes())
    if digest(LIBRARY) != STOCK_SHA:
        raise RuntimeError('Stock restore readback failed')
    print('Clutter library readback verified. Apply with a new graphical session.')


if __name__ == '__main__':
    main()
