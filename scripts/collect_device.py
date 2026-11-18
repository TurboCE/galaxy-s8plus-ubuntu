#!/usr/bin/env python3
"""Read-only Android baseline. Private output; never a partition backup."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PROPERTIES = ('ro.product.model', 'ro.product.device', 'ro.bootloader',
              'ro.revision', 'ro.build.version.release', 'ro.build.version.security_patch',
              'ro.hardware', 'ro.boot.flash.locked', 'ro.boot.verifiedbootstate',
              'ro.boot.warranty_bit', 'ro.oem_unlock_supported')
CHECKS = {
    'kernel': 'uname -a',
    'identity': 'id; command -v su',
    'partitions': 'cat /proc/partitions; ls -l /dev/block/platform/11120000.ufs/by-name',
    'storage': 'df -k /data',
    'gpu': 'ls -l /dev/mali* /dev/ion /dev/dri; dumpsys SurfaceFlinger',
    'graphics_libraries': 'ls -l /vendor/lib64/egl /vendor/lib/egl /system/lib64/egl /system/vendor/lib64/egl; ls -l /vendor/lib64/hw/*gralloc* /vendor/lib64/hw/*composer*',
    'sensors': 'dumpsys sensorservice',
    'gps': 'dumpsys location',
    'bluetooth': 'dumpsys bluetooth_manager',
    'wifi': 'dumpsys wifi',
    'modem': 'dumpsys telephony.registry',
    'audio': 'cat /proc/asound/cards; dumpsys media.audio_flinger',
    'input': 'cat /proc/bus/input/devices',
    'camera': 'dumpsys media.camera',
    'power': 'dumpsys battery; dumpsys power',
    'services': 'service list',
}


def validate_identity(values):
    return (values.get('ro.product.model') == 'SM-G955N'
            and values.get('ro.product.device') == 'dream2lteks'
            and values.get('ro.bootloader', '').startswith('G955N'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', required=True)
    args = parser.parse_args()

    def shell(command):
        try:
            p = subprocess.run([args.adb, '-s', args.serial, 'shell', command],
                               capture_output=True, text=True, timeout=40)
            return dict(exit_code=p.returncode, stdout=p.stdout, stderr=p.stderr)
        except subprocess.TimeoutExpired:
            return dict(exit_code=124, stdout='', stderr='Timed out after 40 seconds')

    properties = {key: shell('getprop ' + key) for key in PROPERTIES}
    values = {key: value['stdout'].strip() for key, value in properties.items()}
    if not validate_identity(values):
        raise SystemExit('Refusing collection: model/device/bootloader do not match SM-G955N.')
    os.umask(0o077)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target = ROOT / 'inventory' / stamp / 'android-baseline.json'
    target.parent.mkdir(parents=True, mode=0o700)
    report = dict(timestamp_utc=stamp, scope='Read-only Android baseline, not Ubuntu validation or backup',
                  properties=properties, checks={key: shell(cmd) for key, cmd in CHECKS.items()})
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(target)


if __name__ == '__main__':
    main()
