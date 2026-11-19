#!/usr/bin/env python3
"""Explicit bounded G955N Wi-Fi reconnect and real HTTPS diagnostic.

Uses the active or explicitly selected stored NetworkManager Wi-Fi profile
without reading credentials; restores the original active profile afterward.
Never changes profile, MAC, power-saving policy, radio firmware or partitions.
It disconnects only wlan0, so launch from an independent bounded local service,
not an SSH session tied to that interface. Evidence excludes SSID/IP/UUID.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import time

URL = 'https://ports.ubuntu.com/ubuntu-ports/dists/noble/Release'


def command(*args, timeout=40):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        # NetworkManager errors may contain the private profile identifier.
        raise RuntimeError('Diagnostic command failed: ' + args[0])
    return result.stdout.strip()


def interrupt(_signal, _frame):
    raise InterruptedError('Reconnect diagnostic interrupted')


def traffic():
    link = command('iw', 'dev', 'wlan0', 'link', timeout=5)
    frequency = re.search(r'^\s*freq:\s*(\d+)', link, re.M)
    if frequency is None:
        raise RuntimeError('Wi-Fi is not associated')
    raw = command('curl', '--silent', '--show-error', '--fail', '--location',
                  '--proto', '=https', '--interface', 'wlan0',
                  '--connect-timeout', '10', '--max-time', '25', '--output',
                  '/dev/null', '--write-out', '%{http_code} %{size_download} %{time_total}',
                  URL, timeout=30)
    fields = raw.split()
    if len(fields) != 3 or fields[0] != '200' or float(fields[1]) < 1000:
        raise RuntimeError('Bound Wi-Fi HTTPS did not transfer expected data')
    return dict(http_status=200, bytes=int(float(fields[1])), seconds=float(fields[2]),
                frequency_mhz=int(frequency.group(1)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exercise-reconnect', action='store_true')
    parser.add_argument('--cycles', type=int, choices=(1, 2, 3), default=3)
    parser.add_argument('--profile-uuid', help='Optional existing Wi-Fi profile; original is restored after the trial')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if not args.exercise_reconnect:
        parser.error('Explicit --exercise-reconnect required')
    if (os.geteuid() or 'g955n-ubuntu' not in platform.release()
            or 'SM-G955N' not in Path('/proc/device-tree/model').read_text()):
        raise SystemExit('Requires root on the native SM-G955N Ubuntu kernel')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text()
    if command('nmcli', '-g', 'GENERAL.TYPE', 'device', 'show', 'wlan0') != 'wifi':
        raise SystemExit('Unexpected network interface type')
    original = command('nmcli', '-g', 'GENERAL.CON-UUID', 'device', 'show', 'wlan0')
    profile = args.profile_uuid or original
    if not all(re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', value)
               for value in (original, profile)):
        raise SystemExit('No active Wi-Fi profile; nothing changed')
    if command('nmcli', '-g', 'connection.type', 'connection', 'show', 'uuid', profile) != '802-11-wireless':
        raise SystemExit('Requested stored profile is not Wi-Fi; nothing changed')
    output = args.output_dir.absolute()
    if output.parent != Path('/var/tmp') or not output.name.startswith('g955n-wifi-reconnect-') or output.exists():
        raise SystemExit('Use a new private /var/tmp/g955n-wifi-reconnect-* directory')
    os.umask(0o077)
    output.mkdir(mode=0o700)
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    result = dict(cycles=[], passed=False, physical_suspend_tested=False,
                  original_profile_restored=False)
    disconnected = False
    started = time.monotonic()
    try:
        result['baseline'] = traffic()
        for index in range(args.cycles):
            cycle_start = time.monotonic()
            # Mark first so even an interrupted nmcli call triggers restoration.
            disconnected = True
            command('nmcli', '--wait', '15', 'device', 'disconnect', 'wlan0', timeout=20)
            command('nmcli', '--wait', '30', 'connection', 'up', 'uuid', profile, 'ifname', 'wlan0', timeout=35)
            active = command('nmcli', '-g', 'GENERAL.CON-UUID', 'device', 'show', 'wlan0')
            if active != profile:
                raise RuntimeError('Reconnected profile differs')
            disconnected = False
            sample = traffic()
            sample.update(cycle=index + 1, reconnect_and_traffic_seconds=round(time.monotonic() - cycle_start, 3))
            result['cycles'].append(sample)
        result['passed'] = len(result['cycles']) == args.cycles
    except (Exception, KeyboardInterrupt) as error:
        # Values in our own messages are public; never retain command stderr.
        result['error_type'] = type(error).__name__
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if disconnected or profile != original:
            try:
                command('nmcli', '--wait', '30', 'connection', 'up', 'uuid', original, 'ifname', 'wlan0', timeout=35)
            except Exception:
                result['restoration_error'] = True
        try:
            result['original_profile_restored'] = command('nmcli', '-g', 'GENERAL.CON-UUID', 'device', 'show', 'wlan0') == original
        except Exception:
            result['original_profile_restored'] = False
        result['same_boot'] = Path('/proc/sys/kernel/random/boot_id').read_text() == boot
        result['elapsed_seconds'] = round(time.monotonic() - started, 3)
        result['passed'] = result['passed'] and result['original_profile_restored'] and result['same_boot']
        (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
