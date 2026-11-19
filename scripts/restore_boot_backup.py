#!/usr/bin/env python3
"""Explicit full-BOOT rollback from a verified live backup; no reboot/USERDATA write."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
from install_ubuntu import BASE, PROTECTED, ROOT, digest, verify_backup, verify_boot, expected_boot_hash


def verify_working_boot(raw, manifest, known_image):
    record = json.loads(manifest.read_text())
    if (record.get('target') != 'SM-G955N' or record.get('verified') is not True
            or record.get('bytes') != 41943040
            or not re.fullmatch(r'[0-9a-f]{64}', record.get('working_boot_sha256', ''))):
        raise ValueError('Requires a verified complete SM-G955N working BOOT backup')
    verify_backup(raw, record['bytes'], record['working_boot_sha256'])
    verify_boot(known_image)
    meta = json.loads(known_image.with_suffix('.json').read_text())
    if meta.get('target') != 'SM-G955N' or meta.get('kernel_trial') is not False:
        raise ValueError('Rollback must restore a normal native Ubuntu boot image')
    if meta.get('image_sha256') != digest(known_image):
        raise ValueError('Reference image metadata hash mismatch')
    if not 0 < known_image.stat().st_size <= record['bytes']:
        raise ValueError('Reference image exceeds BOOT capacity')
    with raw.open('rb') as file:
        if file.read(known_image.stat().st_size) != known_image.read_bytes():
            raise ValueError('Working partition does not contain the reviewed reference image')
    return record, meta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', required=True)
    parser.add_argument('--working-boot', type=Path, required=True)
    parser.add_argument('--working-manifest', type=Path, required=True)
    parser.add_argument('--known-boot-image', type=Path, required=True)
    parser.add_argument('--protected-baseline', type=Path, required=True)
    parser.add_argument('--prior-boot-record', type=Path, required=True)
    args = parser.parse_args()
    working, meta = verify_working_boot(args.working_boot, args.working_manifest, args.known_boot_image)
    directory = args.protected_baseline
    backup = json.loads((directory / 'manifest.json').read_text())
    if backup.get('verified') is not True or backup.get('model') != 'SM-G955N' or not backup['bootloader'].startswith('G955N'):
        raise SystemExit('Reviewed protected baseline required')
    expected = expected_boot_hash(backup, args.prior_boot_record)
    adb = [args.adb, '-s', args.serial]

    def shell(command):
        return subprocess.check_output(adb + ['shell', command], text=True, timeout=180).strip()

    if (shell('id -u') != '0' or not shell('getprop ro.twrp.version')
            or shell('getprop ro.bootloader') != backup['bootloader']):
        raise SystemExit('Requires the exact root G955N recovery identity')
    if shell('sha256sum ' + BASE + 'BOOT').split()[0] != expected:
        raise SystemExit('Current BOOT differs from predecessor receipt')
    if int(shell('blockdev --getsize64 ' + BASE + 'BOOT')) != working['bytes']:
        raise SystemExit('Unexpected BOOT capacity')
    protected = (*PROTECTED, 'MISC')
    for name in protected:
        entry = backup['partitions'][name]
        verify_backup(directory / (name + '.img'), entry['bytes'], entry['sha256'])
        if shell('sha256sum ' + BASE + name).split()[0] != entry['sha256']:
            raise SystemExit('Protected partition mismatch: ' + name)
    os.umask(0o077)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    receipt = ROOT / 'artifacts' / ('boot-restore-' + stamp + '.json')
    state = dict(target='SM-G955N', bootloader=backup['bootloader'], userdata_written=False,
                 kernel_trial=False, restore=True, state='preflight_passed',
                 image_sha256=meta['image_sha256'], previous_boot_partition_sha256=expected,
                 working_backup_sha256=working['working_boot_sha256'])
    receipt.write_text(json.dumps(state, indent=2))
    remote = '/tmp/g955n-known-working-full-boot.img'
    subprocess.run(adb + ['push', str(args.working_boot), remote], check=True, timeout=180,
                   stdout=subprocess.DEVNULL)
    if shell('sha256sum ' + remote).split()[0] != working['working_boot_sha256']:
        raise SystemExit('RAM transfer mismatch; BOOT not written')
    shell('dd if=' + remote + ' of=' + BASE + 'BOOT bs=1048576 conv=fsync,notrunc 2>/dev/null')
    actual = shell('sha256sum ' + BASE + 'BOOT').split()[0]
    if actual != working['working_boot_sha256']:
        raise SystemExit('Full BOOT readback failed; retained recovery and raw backup required')
    for name in protected:
        if shell('sha256sum ' + BASE + name).split()[0] != backup['partitions'][name]['sha256']:
            raise SystemExit('Protected partition changed: ' + name)
    state.update(boot_partition_sha256=actual, state='boot_only_readback_verified_not_booted',
                 protected_partitions_unchanged=list(protected))
    receipt.write_text(json.dumps(state, indent=2))
    shell('rm -f ' + remote + '; sync')
    print(receipt)


if __name__ == '__main__':
    main()
