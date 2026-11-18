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



def version_is_reviewed(raw):
    # The driver reads at most 35 bytes into a zero-initialized array; a
    # short file is terminated by the remaining zeros. A full read needs an
    # in-record NUL before any driver string operation. No exact file length
    # is required by the driver.
    record = raw[:35]
    if not record or (len(record) == 35 and b'\0' not in record):
        return False
    try:
        text = record.split(b'\0', 1)[0].decode('ascii')
    except UnicodeError:
        return False
    return re.fullmatch(r'170427\.[0-9a-fA-F]+', text) is not None


def panel_color():
    # Match the driver's first-eight-byte read, first-space token and u8
    # hexadecimal parser. Do not leak panel bytes through parse exceptions.
    record = Path('/sys/class/lcd/panel/window_type').read_bytes()[:8]
    if not record or (len(record) == 8 and not any(c in record for c in (0, 32))):
        raise RuntimeError('Invalid panel calibration variant record')
    try:
        token = record.split(b'\0', 1)[0].split(b' ', 1)[0].decode('ascii')
        if token.endswith('\n'):
            token = token[:-1]
        if not re.fullmatch(r'\+?(?:0[xX])?[0-9a-fA-F]+', token):
            raise ValueError
        value = int(token, 16)
        if not 0 <= value <= 255:
            raise ValueError
    except (UnicodeError, ValueError):
        raise RuntimeError('Invalid panel calibration variant record') from None
    color = value & 15
    if color not in (0, 1):
        raise RuntimeError('Unreviewed panel calibration variant')
    return color


def validate_coefficients(raw):
    # The driver requires exactly 65 bytes and parses seven signed32 values,
    # three unsigned32 thresholds and a signed32 checksum. It uses comma or
    # newline delimiters. Require an in-record NUL for bounded C parsing.
    if len(raw) != 65 or b'\0' not in raw:
        raise RuntimeError('Unexpected original coefficient record size or termination')
    try:
        text = raw.split(b'\0', 1)[0].decode('ascii')
        tokens = re.split(r'[,\n]', text)
        if text.endswith('\n'):
            tokens.pop()
        if len(tokens) != 11:
            raise ValueError
        values = []
        for index, token in enumerate(tokens):
            unsigned = 7 <= index <= 9
            pattern = r'\+?[0-9]+' if unsigned else r'[+-]?[0-9]+'
            if not re.fullmatch(pattern, token):
                raise ValueError
            value = int(token, 10)
            lower, upper = (0, 2**32 - 1) if unsigned else (-2**31, 2**31 - 1)
            if not lower <= value <= upper:
                raise ValueError
            values.append(value)
        # Signed additions precede the first unsigned threshold in C. Reject
        # records that would overflow those intermediate signed operations.
        signed_order = [values[i] for i in (1, 2, 3, 4, 0, 5, 6)]
        total = signed_order[0]
        for value in signed_order[1:]:
            total += value
            if not -2**31 <= total <= 2**31 - 1:
                raise ValueError
        checksum = (total + sum(values[7:10])) & 0xffffffff
        if checksum != (values[10] & 0xffffffff):
            raise ValueError
    except (UnicodeError, ValueError):
        raise RuntimeError('Original calibration record or checksum invalid') from None


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
    if not version_is_reviewed(raw_version):
        raise RuntimeError('Unreviewed original calibration version')
    color = panel_color()
    coefficients = Path('/efs/FactoryApp') / ('predefine' + str(color))
    raw_coefficients = coefficients.read_bytes()
    validate_coefficients(raw_coefficients)
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
