#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Install or restore only the reviewed Clutter library on the SM-G955N."""
import argparse
import hashlib
import os
from pathlib import Path
import re
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


def elf_interface(path):
    header = subprocess.check_output(['readelf', '-hW', str(path)], text=True)
    if 'AArch64' not in header or 'ELF64' not in header:
        raise RuntimeError('Expected an ARM64 library')
    dynamic = subprocess.check_output(['readelf', '-dW', str(path)], text=True)
    tags = sorted(re.findall(r'\((NEEDED|SONAME|RPATH|RUNPATH)\).*?\[([^\]]+)\]', dynamic))
    # Keep existing defined public symbol types and versions. Their addresses
    # and sizes naturally change when the implementation is rebuilt.
    exports = set()
    for line in subprocess.check_output(['readelf', '--dyn-syms', '--wide', str(path)], text=True).splitlines():
        fields = line.split()
        if len(fields) >= 8 and fields[0].endswith(':') and fields[6] != 'UND':
            if fields[4] in {'GLOBAL', 'WEAK'} and fields[5] in {'DEFAULT', 'PROTECTED'}:
                exports.add((fields[3], fields[4], fields[5], fields[7]))
    return tags, exports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--install', type=Path, metavar='REVIEWED_LIBRARY')
    action.add_argument('--restore', action='store_true')
    parser.add_argument('--sha256', required=True, help='Reviewed library SHA256')
    args = parser.parse_args()
    if os.geteuid() or b'SM-G955N' not in Path('/proc/device-tree/model').read_bytes():
        raise SystemExit('Expected root on SM-G955N')
    version = subprocess.check_output(
        ['dpkg-query', '-W', '-f=${Version}', 'libmutter-14-0:arm64'], text=True)
    if version != VERSION:
        raise SystemExit('Review this change against the installed Mutter version')
    trusted(LIBRARY)
    present = digest(LIBRARY)
    if args.install:
        if present not in {STOCK_SHA, args.sha256} or digest(args.install) != args.sha256:
            raise SystemExit('Unexpected installed or candidate library')
        if present == args.sha256:
            print('Reviewed Clutter library already installed')
            return
        # Read the candidate as data. Do not load it into this root process.
        candidate = args.install.read_bytes()
        if hashlib.sha256(candidate).hexdigest() != args.sha256:
            raise RuntimeError('Candidate changed during read')
        with tempfile.NamedTemporaryFile() as reviewed:
            reviewed.write(candidate)
            reviewed.flush()
            if elf_interface(LIBRARY) != elf_interface(Path(reviewed.name)):
                raise RuntimeError('Clutter public ELF interface mismatch')
        trusted(BACKUPS.parent)
        BACKUPS.mkdir(mode=0o700, exist_ok=True)
        trusted(BACKUPS)
        if not BACKUP.exists():
            replace(BACKUP, LIBRARY.read_bytes())
        trusted(BACKUP)
        if digest(BACKUP) != STOCK_SHA:
            raise RuntimeError('Missing matching stock backup')
        replace(LIBRARY, candidate)
        if digest(LIBRARY) != args.sha256:
            replace(LIBRARY, BACKUP.read_bytes())
            raise RuntimeError('Install readback failed; restored stock')
    else:
        trusted(BACKUP)
        if present != args.sha256 or digest(BACKUP) != STOCK_SHA:
            raise SystemExit('Unexpected installed library or stock backup')
        replace(LIBRARY, BACKUP.read_bytes())
        if digest(LIBRARY) != STOCK_SHA:
            raise RuntimeError('Stock restore readback failed')
    print('Clutter library readback verified. Apply with a new graphical session.')


if __name__ == '__main__':
    main()
