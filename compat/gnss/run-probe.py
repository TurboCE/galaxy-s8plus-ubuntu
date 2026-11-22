#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Run a bounded vendor GNSS test without changing Ubuntu location settings."""
import argparse
import hashlib
from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile
import time
from xml.etree import ElementTree

MODEL = Path('/proc/device-tree/model')
STOCK_CONFIG = Path('/android/system/vendor/etc/gnss/gps.xml')
ENGINE = Path('/vendor/bin/hw/gpsd')
GPS_HAL = Path('/vendor/lib64/hw/gps.default.so')
GPS_HAL_SHA256 = '26dd3097af5a3a57cb9371f8213a0bba38c68ff68a0e897ced597b9b25fc24aa'


def make_config(source, scratch):
    # The vendor parser expects the original XML names, including its unprefixed
    # namespace. ElementTree reserialization replaces these with ns0 prefixes.
    element, = (node for node in ElementTree.fromstring(source).iter()
                if node.tag.rsplit('}', 1)[-1] == 'hal')
    if element.get('PortName') != 'lhd':
        raise ValueError('Expected the board GNSS engine to use the shared location hub')
    attributes = {
        'CtrlPipe': str(scratch / 'ctrl'),
        'NmeaOutName': str(scratch / 'nmea'),
        'NvStorageDir': '/data/vendor/gps/',
        'LtoDir': str(scratch / 'lto') + '/',
        'LogDirectory': str(scratch) + '/',
        'LogEnabled': 'false',
        'SuplEnable': 'false',
        'LbsEnable': 'false',
        'LbsCellEnable': 'false',
        'HttpSyncLto': 'false',
    }
    tag, = re.finditer(r'<hal\b[^>]*>', source)
    text = tag.group(0)[:-1].rstrip()
    suffix = ' />' if text.endswith('/') else '>'
    text = text.removesuffix('/').rstrip()
    for key, value in attributes.items():
        attribute = r'\b' + key + r'\s*=\s*"[^"]*"'
        assignment = f'{key}="{value}"'
        if re.search(attribute, text):
            text = re.sub(attribute, lambda _: assignment, text)
        else:
            text += ' ' + assignment
    result = source[:tag.start()] + text + suffix + source[tag.end():]
    candidate, = (node for node in ElementTree.fromstring(result).iter()
                  if node.tag.rsplit('}', 1)[-1] == 'hal')
    if candidate.attrib != {**element.attrib, **attributes}:
        raise ValueError('GNSS configuration changed outside the intended attributes')
    return result


def supervise(directory, seconds):
    # Called inside the systemd scope with a shared, private vendor GPS directory.
    with subprocess.Popen([str(ENGINE), '-c', str(directory / 'gps.xml')],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as engine:
        try:
            time.sleep(2)
            if engine.poll() is not None:
                raise RuntimeError('The vendor GNSS engine exited before its client started')
            return subprocess.run([str(directory / 'hal-probe'), '--test-standalone', str(seconds)],
                                  timeout=seconds + 7).returncode
        finally:
            if engine.poll() is None:
                engine.terminate()
                try:
                    engine.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    engine.kill()


def main():
    if os.geteuid() != 0 or b'SM-G955N' not in MODEL.read_bytes():
        raise SystemExit('Requires root on the SM-G955N')
    if len(sys.argv) == 4 and sys.argv[1] == '_supervise' and os.environ.get('INVOCATION_ID'):
        return supervise(Path(sys.argv[2]), int(sys.argv[3]))

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', required=True, type=Path)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--seconds', type=int, default=18)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 90:
        parser.error('--seconds must be between 1 and 90')
    binary = args.client.read_bytes()
    if (hashlib.sha256(binary).hexdigest() != args.sha256
            or binary[:6] != b'\x7fELF\x02\x01' or binary[18:20] != b'\xb7\x00'):
        parser.error('expected the reviewed AArch64 GNSS client')
    if ENGINE.resolve(strict=True) != Path('/android/system/vendor/bin/hw/gpsd') or STOCK_CONFIG.is_symlink():
        raise SystemExit('The own-device GNSS engine or its configuration changed')
    if (GPS_HAL.resolve(strict=True) != Path('/android/system/vendor/lib64/hw/gps.default.so')
            or hashlib.sha256(GPS_HAL.read_bytes()).hexdigest() != GPS_HAL_SHA256):
        raise SystemExit('The GNSS HAL does not match the reviewed callback layout')
    subprocess.run(['systemctl', 'is-active', '--quiet', 'g955n-location-hub.service'],
                   check=True, timeout=5)
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix='g955n-gnss-probe-', dir='/run') as temporary:
        scratch = Path(temporary)
        for name in ('lto', 'sockets', 'cache'):
            (scratch / name).mkdir()
        (scratch / 'gps.xml').write_text(make_config(STOCK_CONFIG.read_text(), scratch))
        client = scratch / 'hal-probe'
        client.write_bytes(binary)
        client.chmod(0o700)
        supervisor = scratch / 'supervise.py'
        supervisor.write_bytes(Path(__file__).read_bytes())
        options = [
            'ProtectSystem=strict', 'ProtectHome=yes', 'PrivateTmp=yes', 'NoNewPrivileges=yes',
            'ProtectKernelTunables=yes', 'DevicePolicy=closed', 'RestrictAddressFamilies=AF_UNIX AF_NETLINK',
            'IPAddressDeny=any', 'KillMode=control-group', 'LimitCORE=0', 'TimeoutStopSec=3s',
            f'RuntimeMaxSec={args.seconds + 15}s', 'UMask=0077',
            'InaccessiblePaths=-/efs -/dev/ttyBCM -/dev/bbd_control -/dev/bbd_sensor',
            f'ReadWritePaths={scratch}',
            f'BindPaths={scratch}/sockets:/dev/socket {scratch}/cache:/data/vendor/gps',
        ]
        unit = 'g955n-gnss-probe-' + scratch.name.rsplit('-', 1)[-1]
        command = ['systemd-run', '--wait', '--pipe', '--quiet', '--collect', '--unit', unit]
        command += [arg for value in options for arg in ('-p', value)]
        command += ['systemd-inhibit', '--what=sleep', '--who=G955N GNSS test',
                    '--why=Bounded satellite acquisition', '--mode=block', sys.executable,
                    str(supervisor), '_supervise', str(scratch), str(args.seconds)]
        try:
            return subprocess.run(command, timeout=args.seconds + 23).returncode
        finally:
            subprocess.run(['systemctl', 'stop', unit], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=5)


if __name__ == '__main__':
    raise SystemExit(main())
