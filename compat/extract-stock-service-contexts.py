#!/usr/bin/env python3
"""Offline extraction of selected own-device policy files into private artifacts.

Checks the exact verified SM-G955N stock BOOT hash. Never publishes the files,
accesses a handset, flashes partitions or runs Android init.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
STOCK_BOOT_SHA256 = '6de0f78b0f5f6476cf1ad91bc4871c32160769735847596c530401630e027862'
ALLOWED = {'plat_hwservice_contexts', 'vendor_hwservice_contexts',
           'plat_service_contexts', 'vendor_service_contexts', 'vndservice_contexts'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-boot', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    boot = args.stock_boot.read_bytes()
    if hashlib.sha256(boot).hexdigest() != STOCK_BOOT_SHA256:
        raise SystemExit('Not the verified G955N stock BOOT image')
    output = args.output_dir.resolve()
    if not output.is_relative_to(ROOT / 'artifacts'):
        raise SystemExit('Keep original policy files in ignored private artifacts')
    fields = struct.unpack_from('<10I', boot, 8)
    kernel_size, ramdisk_size, page_size = fields[0], fields[2], fields[7]
    start = page_size + ((kernel_size + page_size - 1) // page_size) * page_size
    cpio = gzip.decompress(boot[start:start + ramdisk_size])
    os.umask(0o077)
    output.mkdir(mode=0o700)
    manifest = dict(target='SM-G955N', stock_boot_sha256=STOCK_BOOT_SHA256, verified=True, files={})
    cursor = 0
    while cursor < len(cpio):
        if cpio[cursor:cursor + 6] not in (b'070701', b'070702'):
            raise SystemExit('Invalid verified-stock CPIO header')
        header = [int(cpio[cursor + 6 + i * 8:cursor + 14 + i * 8], 16) for i in range(13)]
        name = cpio[cursor + 110:cursor + 110 + header[11] - 1].decode()
        data_start = (cursor + 110 + header[11] + 3) & ~3
        payload = cpio[data_start:data_start + header[6]]
        cursor = (data_start + header[6] + 3) & ~3
        if name == 'TRAILER!!!':
            break
        basename = Path(name).name
        if basename in ALLOWED:
            if name != basename or header[1] & 0o170000 != 0o100000 or basename in manifest['files']:
                raise SystemExit('Unexpected stock service-context entry')
            with (output / basename).open('xb') as file:
                file.write(payload)
            manifest['files'][basename] = dict(archive_path=name, bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    if not {'plat_hwservice_contexts', 'vendor_hwservice_contexts'} <= manifest['files'].keys():
        raise SystemExit('Required original hardware service contexts unavailable')
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print('Verified selected stock context files retained privately:', output)


if __name__ == '__main__':
    main()
