#!/usr/bin/env python3
"""Bounded native SSP/IIO data capture, restoring every temporary enable setting."""
import argparse
import fcntl
import stat
import json
import os
from pathlib import Path
import platform
import re
import select
import signal
import struct
import time



# Public Samsung SSP sensor_list.h/ssp.h/ssp_iio.c, pinned kernel source.
# Tuple: enable bit, exact payload+timestamp record bytes, reporting mode.
SENSORS = {
    'accelerometer_sensor': (0, 14, 'continuous'),
    'gyro_sensor': (1, 20, 'continuous'),
    'geomagnetic_sensor': (4, 16, 'continuous'),
    'light_sensor': (9, 26, 'on-change'),
    'step_cnt_sensor': (18, 16, 'on-change'),
}


def decode_record(name, sample):
    if name not in SENSORS or len(sample) != SENSORS[name][1]:
        raise ValueError('Unexpected native SSP record')
    out = {'timestamp_ns': struct.unpack_from('<Q', sample, len(sample)-8)[0]}
    if name == 'accelerometer_sensor':
        out['raw_xyz'] = list(struct.unpack_from('<3h', sample))
    elif name == 'gyro_sensor':
        out['raw_xyz'] = list(struct.unpack_from('<3i', sample))
    elif name == 'geomagnetic_sensor':
        out['raw_xyz'] = list(struct.unpack_from('<3h', sample))
        out['accuracy'] = sample[6]
        out['overflow'] = sample[7]
    elif name == 'light_sensor':
        # CONFIG_SENSORS_SSP_LIGHT_REPORT_LUX=y: lux precedes raw channels.
        out['mcu_lux'] = struct.unpack_from('<I', sample)[0]
    else:
        # IIO reports the kernel's u64 accumulated total, not the MCU u32 diff.
        out['step_total'] = struct.unpack_from('<Q', sample)[0]
    return out


def stream_status(name, samples):
    if not samples:
        return 'not-observed' if SENSORS[name][2] == 'on-change' else 'missing-continuous-stream'
    timestamps = [decode_record(name, sample)['timestamp_ns'] for sample in samples]
    if any(t == 0 for t in timestamps) or any(a >= b for a, b in zip(timestamps, timestamps[1:])):
        return 'invalid-timestamps'
    if SENSORS[name][2] == 'continuous' and len(samples) < 2:
        return 'insufficient-continuous-stream'
    return 'records-observed'


def interrupted(_signal, _frame):
    raise KeyboardInterrupt('Sensor probe interrupted; restoring settings')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, default=10)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sensors', nargs='+', choices=tuple(SENSORS),
                        default=['accelerometer_sensor', 'gyro_sensor', 'light_sensor'])
    args = parser.parse_args()
    if not 1 <= args.seconds <= 60:
        raise SystemExit('Choose a bounded 1..60 second trial')
    if os.geteuid() or 'g955n-ubuntu' not in platform.release() or 'SM-G955N' not in Path('/proc/device-tree/model').read_text():
        raise SystemExit('Requires root on the native G955N')
    lock = os.open('/run/g955n-ssp.lock', os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    info = os.fstat(lock)
    if info.st_uid or not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise SystemExit('Untrusted SSP ownership lock')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    enable = Path('/sys/class/sensors/ssp_sensor/enable')
    original_mask = int(enable.read_text())
    if original_mask:
        raise SystemExit('Existing sensor consumer active; refusing to change its mask')
    firmware = Path('/sys/class/sensors/ssp_sensor/mcu_rev').read_text().strip().split(',')
    if len(firmware) != 2 or not re.fullmatch(r'BR\d+', firmware[0]) or firmware[0] != firmware[1]:
        raise SystemExit('Sensor MCU firmware not ready')
    wanted = {name: SENSORS[name][0] for name in dict.fromkeys(args.sensors)}
    nodes = {}
    for node in Path('/sys/bus/iio/devices').glob('iio:device*'):
        name = (node / 'name').read_text().strip()
        if name in wanted:
            nodes[name] = node
    if set(nodes) != set(wanted):
        raise SystemExit('Expected selected distinct native IIO devices')
    snapshots, fds, records, strides, masks = [], {}, {}, {}, []
    report = dict(kernel=platform.release(), firmware_ready=True, records={}, restored=False,
                  physical_response_verified=False)
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    mask = original_mask
    try:
        for name, node in nodes.items():
            if (node / 'buffer/enable').read_text().strip() != '0':
                raise SystemExit('Existing IIO buffer consumer active')
            for relative, value in [('scan_elements/in_timestamp_en', '1'), ('buffer/length', '128'), ('buffer/enable', '1')]:
                path = node / relative
                snapshots.append((path, path.read_text().strip()))
                path.write_text(value)
            layout = (node / 'scan_elements/in_timestamp_type').read_text().strip()
            match = re.fullmatch(r'le:s(\d+)/(\d+)>>0', layout)
            if not match or match[1] != match[2] or int(match[1]) % 8:
                raise SystemExit('Unexpected SSP packed record layout')
            strides[name] = int(match[1]) // 8
            if strides[name] != SENSORS[name][1]:
                raise SystemExit('Record layout differs from the pinned Samsung protocol')
            fd = os.open('/dev/' + node.name, os.O_RDONLY | os.O_NONBLOCK)
            fds[fd] = name
            records[name] = bytearray()
        mask = original_mask
        # The vendor sysfs handler handles only one changed bit per write.
        for bit in sorted(wanted.values()):
            mask |= 1 << bit
            enable.write_text(str(mask))
            masks.append(mask)
        deadline = time.monotonic() + args.seconds
        print('Sensor sampling active', flush=True)
        while time.monotonic() < deadline:
            ready, _, _ = select.select(list(fds), [], [], min(.2, max(0, deadline-time.monotonic())))
            for fd in ready:
                try:
                    chunk = os.read(fd, 65536)
                except BlockingIOError:
                    continue
                if chunk:
                    records[fds[fd]].extend(chunk)
        for name, data in records.items():
            size = strides[name]
            if len(data) % size:
                raise ValueError('IIO capture did not contain complete packed records')
            samples = [bytes(data[i:i+size]) for i in range(0,len(data),size)]
            payloads = [sample[:-8] for sample in samples]
            timestamps = [struct.unpack('<Q',sample[-8:])[0] for sample in samples]
            report['records'][name] = dict(record_bytes=size, samples=len(samples),
                reporting_mode=SENSORS[name][2], stream_status=stream_status(name, samples),
                first_decoded=decode_record(name, samples[0]) if samples else None,
                last_decoded=decode_record(name, samples[-1]) if samples else None,
                distinct_payloads=len(set(payloads)), monotonic_timestamps=all(a < b for a,b in zip(timestamps,timestamps[1:])),
                first_payload=payloads[0].hex() if payloads else None,
                last_payload=payloads[-1].hex() if payloads else None)
    except (Exception, KeyboardInterrupt) as error:
        report['error'] = str(error)
    finally:
        restore_errors = []
        try:
            mask = int(enable.read_text())
        except OSError as error:
            restore_errors.append(str(error))
        for bit in sorted(wanted.values(), reverse=True):
            if mask & (1 << bit):
                mask &= ~(1 << bit)
                try:
                    enable.write_text(str(mask))
                except OSError as error:
                    restore_errors.append(str(error))
        for fd in fds:
            try:
                os.close(fd)
            except OSError as error:
                restore_errors.append(str(error))
        for path, value in reversed(snapshots):
            try:
                path.write_text(value)
                if path.read_text().strip() != value:
                    restore_errors.append('Readback mismatch: ' + str(path))
            except OSError as error:
                restore_errors.append(str(error))
        try:
            if int(enable.read_text()) != original_mask:
                restore_errors.append('Sensor enable mask was not restored')
        except OSError as error:
            restore_errors.append(str(error))
        report['restore_errors'] = restore_errors
        report['restored'] = not restore_errors
        args.output.write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report), flush=True)
    os.close(lock)
    if report.get('error') or not report['restored'] or len(report['records']) != len(wanted):
        raise SystemExit(1)
    statuses = {row['stream_status'] for row in report['records'].values()}
    if statuses - {'records-observed', 'not-observed'}:
        raise SystemExit(1)
    if 'not-observed' in statuses:
        # No step/light event while stationary is incomplete evidence, not a
        # fabricated success or a broken continuous stream.
        raise SystemExit(2)



if __name__ == '__main__':
    main()
