#!/usr/bin/env python3
"""Explicit BOOT-only kernel trial. Never mounts or writes USERDATA; no reboot."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
from install_ubuntu import BASE, PROTECTED, ROOT, digest, verify_backup, verify_boot, expected_boot_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', required=True)
    parser.add_argument('--boot', type=Path, required=True)
    parser.add_argument('--backup-dir', type=Path, required=True)
    parser.add_argument('--prior-trial', type=Path, help='Allow replacement of an exactly verified prior BOOT trial')
    args = parser.parse_args()
    verify_boot(args.boot)
    meta = json.loads(args.boot.with_suffix('.json').read_text())
    if meta.get('target') != 'SM-G955N' or not meta.get('kernel_trial') or meta.get('image_sha256') != digest(args.boot):
        raise SystemExit('Requires the exact model-validated, USERDATA-free kernel trial image')
    backup = json.loads((args.backup_dir / 'manifest.json').read_text())
    if not backup.get('verified') or backup.get('model') != 'SM-G955N':
        raise SystemExit('Requires verified private raw backups')
    adb = [args.adb, '-s', args.serial]

    def shell(command):
        return subprocess.check_output(adb + ['shell', command], text=True, timeout=180).strip()

    if shell('id -u') != '0' or not shell('getprop ro.twrp.version') or shell('getprop ro.bootloader') != backup['bootloader']:
        raise SystemExit('Recovery root/model identity mismatch')
    if not backup['bootloader'].startswith('G955N'):
        raise SystemExit('Not G955N')
    expected_boot = expected_boot_hash(backup, args.prior_trial)
    for name in ('BOOT', *PROTECTED):
        info = backup['partitions'][name]
        verify_backup(args.backup_dir / (name + '.img'), info['bytes'], info['sha256'])
        expected_current = expected_boot if name == 'BOOT' else info['sha256']
        if shell('sha256sum ' + BASE + name).split()[0] != expected_current:
            raise SystemExit('Unexpected current partition contents: ' + name)
    if args.boot.stat().st_size > int(shell('blockdev --getsize64 ' + BASE + 'BOOT')):
        raise SystemExit('BOOT capacity exceeded')
    os.umask(0o077)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    record = ROOT / 'artifacts' / ('kernel-trial-' + stamp + '.json')
    state = dict(target='SM-G955N', bootloader=backup['bootloader'],
                 image_sha256=meta['image_sha256'], state='preflight_passed', userdata_written=False)
    record.write_text(json.dumps(state, indent=2))
    remote = '/tmp/g955n-kernel-trial.img'
    subprocess.run(adb + ['push', str(args.boot), remote], check=True, timeout=180, stdout=subprocess.DEVNULL)
    if shell('sha256sum ' + remote).split()[0] != meta['image_sha256']:
        raise SystemExit('RAM transfer hash mismatch')
    shell('dd if=' + remote + ' of=' + BASE + 'BOOT bs=1048576 conv=fsync,notrunc 2>/dev/null')
    if shell(f'head -c {args.boot.stat().st_size} {BASE}BOOT | sha256sum').split()[0] != meta['image_sha256']:
        raise SystemExit('BOOT readback mismatch; preserved TWRP can restore original BOOT')
    for name in PROTECTED:
        if shell('sha256sum ' + BASE + name).split()[0] != backup['partitions'][name]['sha256']:
            raise SystemExit('Protected partition changed: ' + name)
    state['boot_partition_sha256'] = shell('sha256sum ' + BASE + 'BOOT').split()[0]
    state['state'] = 'boot_only_readback_verified_not_booted'
    record.write_text(json.dumps(state, indent=2))
    shell('rm -f ' + remote + '; sync')
    print(record)


if __name__ == '__main__':
    main()
