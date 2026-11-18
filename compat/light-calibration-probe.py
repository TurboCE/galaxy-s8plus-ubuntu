#!/usr/bin/env python3
"""Validate original G955N light calibration; optionally initialize MCU RAM.

Default mode reads only. The explicit initialization mode calls the stock
hidden-hole hook with EFS mounted read-only/no journal replay and compares the
whole protected partition before/after. This is not a physical light-response,
coefficient readback, calibrated-unit or desktop integration acceptance test.
No original calibration values or identifiers are printed or copied.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess


def whole_hash(path):
    with path.open('rb', buffering=0) as source:
        return hashlib.file_digest(source, 'sha256').digest()


def validate():
    if (os.geteuid() != 0 or 'g955n-ubuntu' not in platform.release()
            or 'SM-G955N' not in Path('/proc/device-tree/model').read_text()):
        raise RuntimeError('Requires root on the native SM-G955N Ubuntu kernel')
    node = Path('/dev/block/by-name/EFS').resolve(strict=True)
    if not stat.S_ISBLK(node.stat().st_mode):
        raise RuntimeError('EFS is not a block device')
    uevent = Path('/sys/class/block') / node.name / 'uevent'
    if 'PARTNAME=EFS' not in uevent.read_text().splitlines():
        raise RuntimeError('Unexpected protected partition identity')
    mount = json.loads(subprocess.check_output(
        ['findmnt', '--json', '--target', '/efs', '--output',
         'TARGET,SOURCE,FSTYPE,OPTIONS'], text=True, timeout=5))['filesystems']
    if len(mount) != 1:
        raise RuntimeError('Ambiguous EFS mount')
    entry = mount[0]
    options = set(entry['options'].split(','))
    if (entry['target'] != '/efs' or entry['fstype'] != 'ext4'
            or Path(entry['source']).resolve(strict=True) != node
            or 'ro' not in options or not options & {'noload', 'norecovery'}):
        raise RuntimeError('Original EFS must be mounted read-only without replay')
    version = Path('/efs/FactoryApp/version')
    raw_version = version.read_bytes()
    text = raw_version.split(b'\0', 1)[0].decode('ascii').strip()
    if not re.fullmatch(r'170427\.[0-9a-fA-F]+', text):
        raise RuntimeError('Unreviewed original calibration version')
    color = int(Path('/sys/class/lcd/panel/window_type').read_text().split()[0], 16) & 15
    if color not in (0, 1):
        raise RuntimeError('Unreviewed panel calibration variant')
    coefficients = Path('/efs/FactoryApp') / ('predefine' + str(color))
    raw_coefficients = coefficients.read_bytes()
    if len(raw_coefficients) != 65:
        raise RuntimeError('Unexpected original coefficient record size')
    values = list(map(int, raw_coefficients.split(b'\0', 1)[0].decode('ascii').strip().split(',')))
    if len(values) != 11 or sum(values[:10]) != values[10]:
        raise RuntimeError('Original calibration checksum invalid')
    return node, version, raw_version, coefficients, raw_coefficients


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--initialize-runtime-calibration', action='store_true',
                        help='Explicitly request the original driver runtime hook')
    args = parser.parse_args()
    node, version, raw_version, coefficients, raw_coefficients = validate()
    result = dict(version_valid=True, calibration_checksum_valid=True,
                  runtime_initialization_requested=False,
                  physical_response_verified=False)
    if args.initialize_runtime_calibration:
        before = whole_hash(node)
        try:
            Path('/sys/class/sensors/hidden_hole/hh_check_coef').write_text('1')
            result['runtime_initialization_requested'] = True
        finally:
            unchanged = (whole_hash(node) == before
                         and version.read_bytes() == raw_version
                         and coefficients.read_bytes() == raw_coefficients)
            result['original_calibration_unchanged'] = unchanged
            if not unchanged:
                raise RuntimeError('Protected EFS contents changed; stop further trials')
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
