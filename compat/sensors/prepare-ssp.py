#!/usr/bin/python3
"""Require genuine initialized SSP firmware and original calibration before claims."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if not args.prepare:
        parser.error('explicit --prepare required')
    if os.geteuid() or not Path('/proc/device-tree/model').read_bytes().startswith(b'Samsung SM-G955N '):
        raise RuntimeError('Root on the selected SM-G955N required')
    prefix = Path('/opt/g955n-sensors')
    for name in ('recover-ssp-lease.py', 'light-calibration-probe.py'):
        p = prefix / name
        info = p.stat()
        if info.st_uid or info.st_mode & 0o022 or not p.resolve().is_relative_to(prefix):
            raise RuntimeError('Untrusted native sensor preparation helper')
    deadline = time.monotonic() + 40
    while True:
        values = Path('/sys/class/sensors/ssp_sensor/mcu_rev').read_text().strip().split(',')
        if len(values) == 2 and values[0] == values[1] and re.fullmatch(r'BR0*[1-9][0-9]*', values[0]):
            break
        if time.monotonic() >= deadline:
            raise RuntimeError('Genuine sensor MCU firmware did not initialize')
        time.sleep(0.25)
    subprocess.run([str(prefix / 'recover-ssp-lease.py'), '--recover'], check=True, timeout=15)
    subprocess.run([str(prefix / 'light-calibration-probe.py'), '--initialize-runtime-calibration'], check=True, timeout=20)


if __name__ == '__main__':
    main()
