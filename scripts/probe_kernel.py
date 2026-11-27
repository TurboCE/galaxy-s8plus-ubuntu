#!/usr/bin/env python3
"""Explicit BOOT-only trial/update. Never mounts or writes USERDATA; no reboot."""
import argparse
import datetime
import json
import os
from pathlib import Path
import struct
import subprocess
from boot.verify_cam0 import verify_cam0_ownership
from install_ubuntu import (BASE, PROTECTED, ROOT, digest, verify_backup, verify_boot,
                            expected_boot_hash, expected_installed_boot_hash,
                            verify_rootfs_superblock)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', required=True)
    parser.add_argument('--boot', type=Path, required=True)
    parser.add_argument('--backup-dir', type=Path, required=True)
    predecessor = parser.add_mutually_exclusive_group()
    predecessor.add_argument('--prior-trial', '--prior-boot-record', type=Path,
                             help='Require exact full-partition hash from a prior BOOT-only receipt')
    predecessor.add_argument('--prior-install', type=Path,
                             help='Bridge a verified first-install receipt using its original BOOT image')
    parser.add_argument('--installed-boot', type=Path)
    parser.add_argument('--normal-boot', action='store_true',
                        help='Explicitly update normal Ubuntu BOOT on an already labeled Ubuntu USERDATA')
    args = parser.parse_args()
    verify_boot(args.boot)
    with args.boot.open('rb') as image:
        header = image.read(2048)
        size = struct.unpack_from('<I', header, 8)[0]
        try:
            verify_cam0_ownership(image.read(size))
        except ValueError as error:
            parser.error(str(error))
    meta = json.loads(args.boot.with_suffix('.json').read_text())
    if (meta.get('target') != 'SM-G955N' or meta.get('kernel_trial') is not (not args.normal_boot)
            or meta.get('image_sha256') != digest(args.boot)):
        raise SystemExit('Boot image model/hash or explicit trial/normal mode mismatch')
    if bool(args.prior_install) != bool(args.installed_boot):
        raise SystemExit('--prior-install and --installed-boot must be supplied together')
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
    if args.prior_install:
        verify_boot(args.installed_boot)
        expected_boot = expected_installed_boot_hash(args.backup_dir, args.prior_install, args.installed_boot)
    for name in ('BOOT', *PROTECTED):
        info = backup['partitions'][name]
        verify_backup(args.backup_dir / (name + '.img'), info['bytes'], info['sha256'])
        expected_current = expected_boot if name == 'BOOT' else info['sha256']
        if shell('sha256sum ' + BASE + name).split()[0] != expected_current:
            raise SystemExit('Unexpected current partition contents: ' + name)
    if args.normal_boot:
        superblock = subprocess.check_output(adb + ['exec-out',
            'dd if=' + BASE + 'USERDATA bs=1024 skip=1 count=1 2>/dev/null'], timeout=20)
        verify_rootfs_superblock(superblock)
    if args.boot.stat().st_size > int(shell('blockdev --getsize64 ' + BASE + 'BOOT')):
        raise SystemExit('BOOT capacity exceeded')
    os.umask(0o077)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    record = ROOT / 'artifacts' / ('kernel-trial-' + stamp + '.json')
    state = dict(target='SM-G955N', bootloader=backup['bootloader'],
                 image_sha256=meta['image_sha256'], state='preflight_passed', userdata_written=False,
                 kernel_trial=meta['kernel_trial'])
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
