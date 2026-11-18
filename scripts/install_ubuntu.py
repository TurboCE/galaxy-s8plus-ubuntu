#!/usr/bin/env python3
"""Explicit experimental installer: verified USERDATA first, then BOOT. No reboot."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = '/dev/block/platform/11120000.ufs/by-name/'
MIB = 1024 * 1024
CHUNK = 64 * MIB
PROTECTED = ('RECOVERY', 'EFS', 'CPEFS', 'RADIO', 'PARAM')


def digest(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def verify_backup(path, size, expected):
    if path.suffix != '.img' or path.stat().st_size != size:
        raise ValueError('Backup is incomplete or contains appended diagnostics: ' + path.name)
    if digest(path) != expected:
        raise ValueError('Backup checksum mismatch: ' + path.name)


def expected_boot_hash(backup, prior_trial=None):
    if prior_trial is None:
        return backup['partitions']['BOOT']['sha256']
    previous = json.loads(prior_trial.read_text())
    expected = previous.get('boot_partition_sha256', '')
    if (previous.get('target') != 'SM-G955N'
            or previous.get('bootloader') != backup['bootloader']
            or previous.get('state') != 'boot_only_readback_verified_not_booted'
            or previous.get('userdata_written') is not False
            or not re.fullmatch(r'[0-9a-f]{64}', expected)):
        raise ValueError('Invalid prior BOOT trial record')
    return expected


def verify_rootfs_header(path):
    with path.open('rb') as file:
        file.seek(1024)
        sb = file.read(1024)
    if len(sb) != 1024 or sb[56:58] != b'\x53\xef' or sb[120:136].split(b'\0')[0] != b'g955n-root':
        raise ValueError('Not the G955N ext4 root filesystem')
    if path.stat().st_size % MIB:
        raise ValueError('Rootfs length must be a whole MiB')


def verify_boot(path):
    blob = path.read_bytes()
    if blob[:8] != b'ANDROID!' or not blob.endswith(b'SEANDROIDENFORCE'):
        raise ValueError('Invalid Samsung boot image')
    ks, _, rs, _, second, _, _, page, ds, _ = struct.unpack_from('<10I', blob, 8)
    if page != 2048 or second != 0 or len(blob) > 40 * MIB:
        raise ValueError('Unexpected boot geometry')
    align = lambda n: (n + page - 1) // page * page
    k = blob[page:page + ks]
    ro = page + align(ks)
    r = blob[ro:ro + rs]
    do = ro + align(rs)
    dt = blob[do:do + ds]
    if b'SM-G955N' not in dt or len(k) != ks or len(r) != rs or len(dt) != ds:
        raise ValueError('Boot model/payload mismatch')
    check = hashlib.sha1()
    for part in (k, r, b'', dt):
        check.update(part)
        check.update(struct.pack('<I', len(part)))
    if blob[576:596] != check.digest():
        raise ValueError('Android boot image ID mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', required=True)
    parser.add_argument('--boot', type=Path, required=True)
    parser.add_argument('--rootfs', type=Path, required=True)
    parser.add_argument('--backup-dir', type=Path, required=True)
    parser.add_argument('--prior-trial', type=Path,
                        help='Require exact readback hash of a previously installed BOOT-only trial')
    parser.add_argument('--initialize-userdata', action='store_true', required=True,
                        help='Explicitly permit destruction of Android app data on USERDATA')
    args = parser.parse_args()
    verify_boot(args.boot)
    verify_rootfs_header(args.rootfs)
    boot_meta = json.loads(args.boot.with_suffix('.json').read_text())
    root_meta = json.loads(args.rootfs.with_suffix('.validation.json').read_text())
    for meta in (boot_meta, root_meta):
        if meta.get('target') != 'SM-G955N':
            raise SystemExit('Image validation belongs to another model')
    if boot_meta.get('kernel_trial') is not False:
        raise SystemExit('Installation requires a normal Ubuntu boot image, not a rescue trial')
    boot_hash, root_hash = digest(args.boot), digest(args.rootfs)
    if boot_meta['image_sha256'] != boot_hash or root_meta['image_sha256'] != root_hash or not root_meta.get('fsck_clean'):
        raise SystemExit('Image validation/hash mismatch')
    backup = json.loads((args.backup_dir / 'manifest.json').read_text())
    if not backup.get('verified') or backup.get('model') != 'SM-G955N':
        raise SystemExit('Requires a verified G955N raw backup manifest')
    expected_boot = expected_boot_hash(backup, args.prior_trial)
    for name in ('BOOT', *PROTECTED):
        item = backup['partitions'][name]
        verify_backup(args.backup_dir / (name + '.img'), item['bytes'], item['sha256'])
    adb = [args.adb, '-s', args.serial]

    def shell(command, timeout=180):
        return subprocess.check_output(adb + ['shell', command], text=True, timeout=timeout).strip()

    if shell('id -u') != '0' or not shell('getprop ro.twrp.version'):
        raise SystemExit('Requires root TWRP')
    if shell('getprop ro.bootloader') != backup['bootloader'] or not backup['bootloader'].startswith('G955N'):
        raise SystemExit('Recovery bootloader identity mismatch')
    capacities = {name: int(shell('blockdev --getsize64 ' + BASE + name)) for name in ('USERDATA', 'BOOT')}
    if args.rootfs.stat().st_size >= capacities['USERDATA'] or args.boot.stat().st_size > capacities['BOOT']:
        raise SystemExit('Image exceeds actual partition capacity')
    for name in PROTECTED:
        if shell('sha256sum ' + BASE + name).split()[0] != backup['partitions'][name]['sha256']:
            raise SystemExit('Protected partition changed since backup: ' + name)
    if shell('sha256sum ' + BASE + 'BOOT').split()[0] != expected_boot:
        raise SystemExit('Unexpected BOOT contents; USERDATA has not been written')
    mounts = shell('cat /proc/mounts')
    if any('/dev/block/dm-' in line or ' /data ' in line or '/dev/block/sda24 ' in line for line in mounts.splitlines()):
        raise SystemExit('USERDATA or decrypted Android data is mounted; no write permitted')
    os.umask(0o077)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory = ROOT / 'artifacts' / ('install-' + stamp)
    directory.mkdir(mode=0o700)
    state = dict(target='SM-G955N', rootfs_sha256=root_hash, boot_sha256=boot_hash,
                 userdata_bytes=args.rootfs.stat().st_size, state='preflight_passed', verified_chunks=[])
    manifest = directory / 'install.json'

    def save():
        temporary = manifest.with_suffix('.tmp')
        temporary.write_text(json.dumps(state, indent=2))
        temporary.replace(manifest)

    save()
    remote = '/tmp/g955n-install-chunk'
    chunk_file = directory / 'chunk.bin'
    with args.rootfs.open('rb') as image:
        offset = 0
        while data := image.read(CHUNK):
            chunk_file.write_bytes(data)
            expected = hashlib.sha256(data).hexdigest()
            subprocess.run(adb + ['push', str(chunk_file), remote], check=True, timeout=180, stdout=subprocess.DEVNULL)
            if shell('sha256sum ' + remote).split()[0] != expected:
                raise SystemExit('RAM transfer checksum mismatch')
            state['state'] = 'writing_userdata'
            save()
            shell(f'dd if={remote} of={BASE}USERDATA bs={MIB} seek={offset // MIB} conv=fsync,notrunc 2>/dev/null')
            actual = shell(f'dd if={BASE}USERDATA bs={MIB} skip={offset // MIB} count={len(data) // MIB} 2>/dev/null | sha256sum').split()[0]
            if actual != expected:
                raise SystemExit('USERDATA chunk readback mismatch; working RECOVERY is preserved')
            state['verified_chunks'].append(dict(offset=offset, bytes=len(data), sha256=expected))
            offset += len(data)
            save()
            print('USERDATA verified', offset, '/', args.rootfs.stat().st_size, flush=True)
    if shell(f'dd if={BASE}USERDATA bs={MIB} count={args.rootfs.stat().st_size // MIB} 2>/dev/null | sha256sum', timeout=900).split()[0] != root_hash:
        raise SystemExit('Full USERDATA image hash mismatch; BOOT not written')
    state['state'] = 'userdata_fully_verified'
    save()
    if shell('sha256sum ' + BASE + 'BOOT').split()[0] != expected_boot:
        raise SystemExit('BOOT changed unexpectedly; refusing overwrite')
    subprocess.run(adb + ['push', str(args.boot), remote], check=True, timeout=180, stdout=subprocess.DEVNULL)
    if shell('sha256sum ' + remote).split()[0] != boot_hash:
        raise SystemExit('BOOT RAM hash mismatch')
    shell(f'dd if={remote} of={BASE}BOOT bs={MIB} conv=fsync,notrunc 2>/dev/null')
    if shell(f'head -c {args.boot.stat().st_size} {BASE}BOOT | sha256sum').split()[0] != boot_hash:
        raise SystemExit('BOOT readback mismatch; enter the preserved TWRP RECOVERY')
    for name in PROTECTED:
        if shell('sha256sum ' + BASE + name).split()[0] != backup['partitions'][name]['sha256']:
            raise SystemExit('Protected partition verification failed: ' + name)
    shell('rm -f ' + remote + '; sync')
    chunk_file.unlink()
    state['state'] = 'installed_readback_verified_not_booted'
    state['protected_partitions_unchanged'] = list(PROTECTED)
    save()
    print('Verified installation; no reboot performed:', manifest)


if __name__ == '__main__':
    main()
