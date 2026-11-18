#!/usr/bin/env python3
"""Read-only verified G955N partition backups from privileged TWRP ADB."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = '/dev/block/platform/11120000.ufs/by-name/'
PARTITIONS = ('BOOT', 'RECOVERY', 'EFS', 'CPEFS', 'RADIO', 'MISC', 'PARAM')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', required=True)
    args = parser.parse_args()
    adb = [args.adb, '-s', args.serial]

    def shell(command):
        return subprocess.check_output(adb + ['shell', command], text=True, timeout=90).strip()

    if shell('id -u') != '0' or not shell('getprop ro.twrp.version'):
        raise SystemExit('Requires verified root TWRP; no root escalation attempted')
    bootloader = shell('getprop ro.bootloader')
    if not bootloader.startswith('G955N'):
        raise SystemExit('Refusing non-G955N bootloader identity')
    # Unified TWRP may expose overseas product properties/DT. Bootloader identity
    # and verified initial recovery image are required instead of those props.
    expected = ROOT / 'artifacts/recovery/twrp-3.7.0_9-0-dream2lte.verified.img'
    expected_hash = 'e21a11df7c33b9897d1eb7371906650c53595e50ea24f1138ba96bdfe81321db'
    with expected.open('rb') as file:
        if hashlib.file_digest(file, 'sha256').hexdigest() != expected_hash:
            raise SystemExit('Initial recovery reference checksum mismatch')
    os.umask(0o077)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory = ROOT / 'backups' / ('recovery-' + stamp)
    directory.mkdir(parents=True, mode=0o700)
    report = dict(timestamp_utc=stamp, model='SM-G955N', bootloader=bootloader,
                  recovery=shell('getprop ro.twrp.version'), partitions={}, verified=False)
    manifest = directory / 'manifest.json'
    manifest.write_text(json.dumps(report, indent=2))
    for name in PARTITIONS:
        device = BASE + name
        size = int(shell('blockdev --getsize64 ' + device))
        if not 0 < size <= 256 * 1024 * 1024:
            raise SystemExit(f'Unexpected partition size: {name} {size}')
        partial = directory / (name + '.img.part')
        with partial.open('wb') as file:
            # Raw exec transport can merge *remote* stderr into stdout even
            # when host stderr is separate. Suppress dd statistics remotely;
            # byte count and the independent device hash remain mandatory.
            process = subprocess.run(adb + ['exec-out', 'dd if=' + device + ' bs=1048576 2>/dev/null'],
                                     stdout=file, stderr=subprocess.PIPE, timeout=180)
            file.flush()
            os.fsync(file.fileno())
        if process.returncode or partial.stat().st_size != size:
            raise SystemExit(f'Unverified backup: {name}; retained .part file, do not restore it')
        with partial.open('rb') as file:
            local_hash = hashlib.file_digest(file, 'sha256').hexdigest()
        device_hash = shell('sha256sum ' + device).split()[0]
        if local_hash != device_hash:
            raise SystemExit(f'Backup hash mismatch: {name}')
        if name == 'RECOVERY':
            with partial.open('rb') as file:
                actual_prefix = hashlib.sha256(file.read(expected.stat().st_size)).hexdigest()
            if actual_prefix != expected_hash:
                raise SystemExit('RECOVERY prefix does not match the approved TWRP image')
        target = partial.with_suffix('')
        partial.rename(target)
        report['partitions'][name] = dict(bytes=size, sha256=local_hash, file=target.name)
        manifest.write_text(json.dumps(report, indent=2))
        print(name, size, 'bytes verified', flush=True)
    report['verified'] = True
    report['scope'] = 'Raw listed partitions only; no app-private or encrypted USERDATA backup'
    manifest.write_text(json.dumps(report, indent=2))
    print('Verified private backups:', directory)


if __name__ == '__main__':
    main()
