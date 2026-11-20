#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Explicit SM-G955N USB peripheral/PHY reset, normally invoked over Wi-Fi."""
import argparse
from collections import Counter
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import time

GADGET = Path('/sys/class/android_usb/android0')
FSM = Path('/sys/devices/platform/10c00000.usb/10c00000.dwc3')
ONLINE = Path('/sys/class/power_supply/usb/online')


def reset_peripheral(gadget=GADGET, fsm=FSM, online=ONLINE, pause=time.sleep):
    read = lambda path: path.read_text().strip()
    if (read(gadget/'functions') != 'cdc_ethernet,acm'
            or read(gadget/'enable') != '1' or read(fsm/'id') != '1'
            or read(fsm/'b_sess') != '1' or read(online) != '1'
            or read(fsm/'state') != 'b_peripheral'):
        raise RuntimeError('Expected the enabled, powered SM-G955N USB peripheral')
    # A composite-only enable toggle does not reset a stuck PHY/core. The
    # driver's peripheral stop/start path owns power, clocks and runtime refs.
    try:
        (fsm/'b_sess').write_text('0')
        pause(.8)
    finally:
        # Never force a peripheral role after a real unplug or a host-role swap.
        if read(online) == '1' and read(fsm/'id') == '1':
            (fsm/'b_sess').write_text('1')
    return read(online) == '1' and read(fsm/'id') == '1'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reset-peripheral', action='store_true')
    args = parser.parse_args()
    if not args.reset_peripheral:
        parser.error('Requires explicit --reset-peripheral')
    if os.geteuid() or b'SM-G955N' not in Path('/proc/device-tree/model').read_bytes():
        raise RuntimeError('Requires root on SM-G955N')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text()
    taint = Path('/proc/sys/kernel/tainted').read_text()
    before = Counter(subprocess.check_output(['dmesg'], text=True).splitlines())
    # Invoke from a detached systemd unit if the command's SSH route uses USB.
    with open('/run/g955n-usb-recover.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        attached = reset_peripheral()
        deadline = time.monotonic() + 10
        while attached and time.monotonic() < deadline:
            if (GADGET/'state').read_text().strip() == 'CONFIGURED':
                break
            if ONLINE.read_text().strip() != '1' or (FSM/'id').read_text().strip() != '1':
                attached = False
                break
            time.sleep(.25)
    added = Counter(subprocess.check_output(['dmesg'], text=True).splitlines()) - before
    report = {
        'device_configured': attached and (GADGET/'state').read_text().strip() == 'CONFIGURED',
        'host_transport_verified': False,
        'same_boot': boot == Path('/proc/sys/kernel/random/boot_id').read_text(),
        'taint_unchanged': taint == Path('/proc/sys/kernel/tainted').read_text(),
        'new_usb_failures': sum(n for line, n in added.items()
            if 'dwc3' in line and re.search(r'timeout|error|failed', line, re.I)),
        'new_kernel_faults': sum(n for line, n in added.items()
            if re.search(r'WARNING:|BUG:|Call trace:|Kernel panic|Unable to handle', line)),
    }
    print(json.dumps(report, indent=2))
    return 0 if report['device_configured'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
