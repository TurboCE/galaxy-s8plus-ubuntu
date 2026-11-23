#!/usr/bin/env python3
"""Read-only SSH capture after G955N Ubuntu boot. Not an automated feature pass."""
import argparse
import datetime
import json
import os
import re
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

IDENTIFY = ("uname -r; tr -d '\\000' < /proc/device-tree/model; printf '\\n'; "
            "cat /proc/sys/kernel/random/boot_id")


def capture_identity(result):
    lines = result['stdout'].splitlines()
    if result['exit_code'] or len(lines) != 3:
        return None
    release, model, boot_id = lines
    accepted = 'g955n-ubuntu' in release or re.fullmatch(
        r'6\.18\.\d+(-g955n-usb-r\d+){1,2}', release)
    if accepted and 'SM-G955N' in model and boot_id:
        return release, model, boot_id
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    transport = parser.add_mutually_exclusive_group(required=True)
    transport.add_argument('--host', help='SSH host or user@host; configure host key and authentication first')
    transport.add_argument('--serial-port', help='Explicit G955N USB console port for bring-up without host networking')
    parser.add_argument('--wifi-host', help='Fallback SSH destination on the same handset if the primary SSH probe cannot connect')
    parser.add_argument('--identity', type=Path)
    parser.add_argument('--known-hosts', type=Path)
    parser.add_argument('--host-key-alias', help='Use the pinned handset key for a different verified address')
    parser.add_argument('--console-password-file', type=Path,
                        help='Private local credential file for manual USB console login')
    parser.add_argument('--sudo', action='store_true', help='Use existing passwordless sudo for diagnostic reads')
    args = parser.parse_args()
    if any(host and (host.startswith('-') or any(c.isspace() for c in host))
           for host in (args.host, args.wifi_host)):
        raise SystemExit('Invalid SSH destination')
    if args.wifi_host and not (args.host and args.known_hosts and args.host_key_alias):
        parser.error('--wifi-host requires --host, --known-hosts and --host-key-alias for the same handset')
    host = args.host
    serial = SerialShell(args.serial_port) if args.serial_port else None
    if args.console_password_file:
        if not serial:
            raise SystemExit('Console password input requires --serial-port')
        serial.login(args.console_password_file.read_text().removesuffix('\n'))

    def run(command):
        options = []
        if args.identity:
            options += ['-i', str(args.identity), '-o', 'IdentitiesOnly=yes']
        if args.known_hosts:
            options += ['-o', 'UserKnownHostsFile=' + str(args.known_hosts), '-o', 'StrictHostKeyChecking=yes']
        if args.host_key_alias:
            options += ['-o', 'HostKeyAlias=' + args.host_key_alias]
        if args.wifi_host:
            options += ['-o', 'GlobalKnownHostsFile=/dev/null']
        if args.sudo:
            command = 'sudo -n -- sh -c ' + shlex.quote(command)
        if serial:
            return serial.run(command)
        try:
            p = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                                *options, host, command], capture_output=True, text=True, timeout=40)
            return dict(exit_code=p.returncode, stdout=p.stdout, stderr=p.stderr)
        except subprocess.TimeoutExpired:
            return dict(exit_code=124, stdout='', stderr='Capture timed out')

    def switch_to_wifi():
        nonlocal host, transport_used
        host = args.wifi_host
        transport_used = 'wifi_fallback'
        return run(IDENTIFY)

    transport_used = 'serial' if serial else 'ssh'
    identity = run(IDENTIFY)
    if args.wifi_host and identity['exit_code'] in (124, 255):
        identity = switch_to_wifi()
    device = capture_identity(identity)
    if device is None:
        raise SystemExit('Refusing capture: not the expected SM-G955N Ubuntu kernel/DT')
    identity['stdout'] = '\n'.join(device[:2]) + '\n'
    os.umask(0o077)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory = ROOT / 'inventory' / stamp
    directory.mkdir(parents=True, mode=0o700)
    checks = {}
    for name, command in CHECKS.items():
        result = run(command)
        if args.wifi_host and transport_used == 'ssh' and result['exit_code'] in (124, 255):
            if capture_identity(switch_to_wifi()) != device:
                transport_used = 'ssh'
                checks[name] = result
                break
            result = run(command)
        checks[name] = result
    kernel = checks['dmesg']
    report = dict(timestamp_utc=stamp, transport=transport_used, identity=identity, checks=checks,
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
