#!/usr/bin/env python3
"""Read-only SSH capture after G955N Ubuntu boot. Not an automated feature pass."""
import argparse
import datetime
import json
import os
import shlex
from pathlib import Path
import subprocess
from kernel_log_audit import audit
from serial_shell import SerialShell

ROOT = Path(__file__).resolve().parents[1]
CHECKS = {
    'dmesg': 'dmesg --raw',
    'journal_kernel': 'journalctl -k -b --no-pager',
    'taint': 'cat /proc/sys/kernel/tainted',
    'pid1': 'cat /proc/1/comm; readlink /proc/1/exe',
    'memory_storage': 'free -m; lsblk; findmnt /',
    'network': 'ip -brief address; ip route',
    'radio_services': 'systemctl is-active ModemManager ofono NetworkManager bluetooth gpsd',
    'gpu_nodes': 'ls -l /dev/mali* /dev/dri/* /dev/ion',
    'sensor_nodes': 'ls -l /sys/bus/iio/devices; cat /proc/bus/input/devices',
    'power': 'ls /sys/class/power_supply; cat /sys/power/state',
    'audio_camera': 'cat /proc/asound/cards; ls -l /dev/video*',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    transport = parser.add_mutually_exclusive_group(required=True)
    transport.add_argument('--host', help='SSH host or user@host; configure host key and authentication first')
    transport.add_argument('--serial-port', help='Explicit G955N USB console port for bring-up without host networking')
    parser.add_argument('--identity', type=Path)
    parser.add_argument('--known-hosts', type=Path)
    parser.add_argument('--sudo', action='store_true', help='Use existing passwordless sudo for diagnostic reads')
    args = parser.parse_args()
    if args.host and (args.host.startswith('-') or any(c.isspace() for c in args.host)):
        raise SystemExit('Invalid SSH destination')
    serial = SerialShell(args.serial_port) if args.serial_port else None

    def run(command):
        options = []
        if args.identity:
            options += ['-i', str(args.identity), '-o', 'IdentitiesOnly=yes']
        if args.known_hosts:
            options += ['-o', 'UserKnownHostsFile=' + str(args.known_hosts), '-o', 'StrictHostKeyChecking=yes']
        if args.sudo:
            command = 'sudo -n -- sh -c ' + shlex.quote(command)
        if serial:
            return serial.run(command)
        try:
            p = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                                *options, args.host, command], capture_output=True, text=True, timeout=40)
            return dict(exit_code=p.returncode, stdout=p.stdout, stderr=p.stderr)
        except subprocess.TimeoutExpired:
            return dict(exit_code=124, stdout='', stderr='Capture timed out')

    identity = run('uname -r; cat /proc/device-tree/model')
    if identity['exit_code'] or 'g955n-ubuntu' not in identity['stdout'] or 'SM-G955N' not in identity['stdout']:
        raise SystemExit('Refusing capture: not the expected SM-G955N Ubuntu kernel/DT')
    os.umask(0o077)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory = ROOT / 'inventory' / stamp
    directory.mkdir(parents=True, mode=0o700)
    checks = {name: run(command) for name, command in CHECKS.items()}
    kernel = checks['dmesg']
    report = dict(timestamp_utc=stamp, identity=identity, checks=checks,
                  kernel_audit=audit(kernel['stdout']) if kernel['exit_code'] == 0 else
                  dict(status='unavailable', reason='Kernel log capture failed'),
                  hardware_validation='Not qualified by service/node enumeration')
    (directory / 'linux.json').write_text(json.dumps(report, indent=2))
    (directory / 'dmesg.raw').write_text(kernel['stdout'])
    if serial:
        serial.close()
    print(directory)


if __name__ == '__main__':
    main()
