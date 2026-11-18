#!/usr/bin/env python3
"""Optional native-host cache warm-up for a foreign ARM64 Python rootfs.

Python bytecode is architecture-independent for matching bytecode magic.
This only compiles source; it does not execute target modules, skip maintainer
scripts, change dpkg state or waive package verification.
"""
import argparse
import compileall
import importlib.util
from pathlib import Path
import struct
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    if root.parent != Path('/work') or not root.name.startswith('rootfs') or not (root / 'var/lib/dpkg/status').exists():
        raise SystemExit('Requires a dedicated debootstrap staging root, never the host root')
    python = root / f'usr/bin/python{sys.version_info.major}.{sys.version_info.minor}'
    header = python.read_bytes()[:64]
    if header[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', header, 18)[0] != 183:
        raise SystemExit('Foreign interpreter is not the expected ARM64 Python version')
    tree = root / 'usr/lib/python3/dist-packages'
    sample = next(tree.rglob('*.pyc'))
    if sample.read_bytes()[:4] != importlib.util.MAGIC_NUMBER:
        raise SystemExit('Bytecode magic differs; refusing cross-version caches')
    if not compileall.compile_dir(str(tree), quiet=1, workers=2, optimize=0,
                                 stripdir=str(root), prependdir='/'):
        raise SystemExit('Python source compilation reported errors')
    print('Matching-magic ARM64 rootfs bytecode caches warmed; dpkg configuration is still mandatory')


if __name__ == '__main__':
    main()
