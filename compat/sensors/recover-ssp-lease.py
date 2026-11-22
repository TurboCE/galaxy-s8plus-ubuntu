#!/usr/bin/python3
"""Recover only journalled native SSP claims after SensorProxy has stopped.

No action without --recover. Must run after process exit, with the same exclusive
controller lock. Failed restoration keeps its journal and blocks a new claim.
"""
import argparse
import configparser
import fcntl
import os
from pathlib import Path
import re
import stat

DIRECTORY = Path('/run/g955n-ssp-leases')
ATTRIBUTES = ('scan_elements/in_timestamp_en', 'buffer/length', 'buffer/enable', 'poll_delay')
NAMES = {0: 'accelerometer_sensor', 7: 'proximity_sensor', 9: 'light_sensor', 17: 'rotation_vector_sensor'}


def trusted(path, directory=False):
    info = path.lstat()
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if not kind(info.st_mode) or info.st_uid or info.st_mode & 0o077:
        raise RuntimeError('Untrusted SSP journal')
    if not directory and info.st_nlink != 1:
        raise RuntimeError('Unexpected journal hard link')


def read_record(path, boot, devices):
    trusted(path)
    if path.stat().st_size > 4096:
        raise RuntimeError('Oversized SSP journal')
    record = configparser.ConfigParser(interpolation=None, strict=True)
    record.read_string(path.read_text())
    if record.sections() != ['sensor']:
        raise RuntimeError('Unexpected journal sections')
    data = record['sensor']
    if set(data) != {'boot', 'path', 'bit', 'saved0', 'saved1', 'saved2', 'saved3'}:
        raise RuntimeError('Unexpected journal fields')
    if data['boot'] != boot or data['bit'] not in {str(bit) for bit in NAMES}:
        raise RuntimeError('Journal belongs to another boot or sensor')
    bit = int(data['bit'])
    if path.name != f'{bit}.ini':
        raise RuntimeError('Mismatched sensor journal name')
    node = Path(data['path']).resolve(strict=True)
    if devices.get(NAMES[bit]) != node:
        raise RuntimeError('Journal does not refer to the selected native IIO sensor')
    saved = [data[f'saved{i}'] for i in range(4)]
    if any(not re.fullmatch(r'[0-9]{1,19}', x) for x in saved):
        raise RuntimeError('Unexpected saved SSP settings')
    if saved[0] not in ('0', '1') or saved[2] != '0' or not 1 <= int(saved[1]) <= 1048576 or int(saved[3]) > 2**63-1:
        raise RuntimeError('Unreviewed saved SSP settings')
    return bit, node, saved


def restore_record(path, boot, devices, enable):
    bit, node, saved = read_record(path, boot, devices)
    mask = int(enable.read_text().strip())
    wanted = mask & ~(1 << bit)
    if mask != wanted:
        enable.write_text(str(wanted))
        if int(enable.read_text().strip()) != wanted:
            raise RuntimeError('SSP claim restoration was not acknowledged')
    # FIFO must stop before scan/length/poll changes. Original buffer was off.
    (node / ATTRIBUTES[2]).write_text(saved[2])
    for index in (3, 1, 0):
        (node / ATTRIBUTES[index]).write_text(saved[index])
    if any((node / name).read_text().strip() != value for name, value in zip(ATTRIBUTES, saved)):
        raise RuntimeError('SSP settings restoration did not match the journal')
    path.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recover', action='store_true')
    args = parser.parse_args()
    if not args.recover:
        parser.error('explicit --recover required')
    if os.geteuid() or not Path('/proc/device-tree/model').read_bytes().startswith(b'Samsung SM-G955N '):
        raise RuntimeError('Root on the selected SM-G955N required')
    if not DIRECTORY.exists():
        return
    trusted(DIRECTORY, directory=True)
    records = list(DIRECTORY.iterdir())
    if any(p.name not in {f'{bit}.ini' for bit in NAMES} for p in records):
        raise RuntimeError('Unexpected file in the native SSP journal directory')
    fd = os.open('/run/g955n-ssp.lock', os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid or info.st_mode & 0o077:
            raise RuntimeError('Untrusted SSP controller lock')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        devices = {}
        for node in Path('/sys/bus/iio/devices').glob('iio:device*'):
            name = (node / 'name').read_text().strip()
            if name in NAMES.values():
                if name in devices:
                    raise RuntimeError('Duplicate native IIO sensor')
                devices[name] = node.resolve(strict=True)
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        enable = Path('/sys/class/sensors/ssp_sensor/enable')
        # Validate every record before the first device write.
        for path in records:
            read_record(path, boot, devices)
        for path in records:
            restore_record(path, boot, devices, enable)
        print(f'Recovered {len(records)} journalled native SSP claims')
    finally:
        os.close(fd)


if __name__ == '__main__':
    main()
