#!/usr/bin/env python3
"""Bounded native SSP/IIO data capture, restoring every temporary enable setting."""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import select
import signal
import struct
import time


def interrupted(_signal, _frame):
    raise KeyboardInterrupt('Sensor probe interrupted; restoring settings')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, default=10)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 60:
        raise SystemExit('Choose a bounded 1..60 second trial')
    if os.geteuid() or 'g955n-ubuntu' not in platform.release() or 'SM-G955N' not in Path('/proc/device-tree/model').read_text():
        raise SystemExit('Requires root on the native G955N')
    enable = Path('/sys/class/sensors/ssp_sensor/enable')
    original_mask = int(enable.read_text())
    if original_mask:
        raise SystemExit('Existing sensor consumer active; refusing to change its mask')
    firmware = Path('/sys/class/sensors/ssp_sensor/mcu_rev').read_text().strip().split(',')
    if len(firmware) != 2 or not re.fullmatch(r'BR\d+', firmware[0]) or firmware[0] != firmware[1]:
        raise SystemExit('Sensor MCU firmware not ready')
    wanted = {'accelerometer_sensor': 0, 'gyro_sensor': 1, 'light_sensor': 9}
    nodes = {}
    for node in Path('/sys/bus/iio/devices').glob('iio:device*'):
        name = (node / 'name').read_text().strip()
        if name in wanted:
            nodes[name] = node
    if set(nodes) != set(wanted):
        raise SystemExit('Expected three distinct native IIO devices')
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
            fd = os.open('/dev/' + node.name, os.O_RDONLY | os.O_NONBLOCK)
            fds[fd] = name
            records[name] = bytearray()
        mask = original_mask
        # The vendor sysfs handler handles only one changed bit per write.
        for bit in (0, 1, 9):
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
        for bit in (9, 1, 0):
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
    if report.get('error') or not report['restored'] or any(row['samples'] < 2 or not row['monotonic_timestamps'] for row in report['records'].values()) or len(report['records']) != 3:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
