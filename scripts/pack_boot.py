#!/usr/bin/env python3
"""Build-only G955N Android boot image from pinned kernel, own stock and firmware."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import stat
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ('calliope_sram.bin', 'calliope_dram.bin', 'calliope_iva.bin', 'dsm.bin',
         'AP_AUDIO_SLSI.bin', 'APBargeIn_AUDIO_SLSI.bin', 'SoundBoosterParam.bin',
         'APBiBF_AUDIO_SLSI.bin', 'dsm_tune.bin')


def verify_embedded_config(kernel, config):
    start = kernel.index(b'IKCFG_ST') + 8
    end = kernel.index(b'IKCFG_ED', start)
    if gzip.decompress(kernel[start:end]) != config:
        raise ValueError('Embedded kernel configuration differs from supplied config')


def compress_initramfs(data, config):
    settings = config.splitlines()
    if 'CONFIG_RD_LZ4=y' in settings:
        blob = subprocess.run(['lz4', '-l', '-9', '-c'], input=data,
                              capture_output=True, check=True).stdout
        if blob[:4] != b'\x02\x21\x4c\x18':
            raise ValueError('Expected Linux 4.4-compatible legacy LZ4 frame')
        return 'lz4-legacy', blob
    if 'CONFIG_RD_GZIP=y' in settings:
        return 'gzip', gzip.compress(data, compresslevel=9, mtime=0)
    raise ValueError('No supported initramfs decompressor in this kernel configuration')


def newc(entries):
    output = bytearray()
    for index, (name, mode, data) in enumerate(entries + [('TRAILER!!!', 0, b'')], 1):
        encoded = name.encode() + b'\0'
        device_numbers = {'dev/console': (5, 1), 'dev/null': (1, 3), 'dev/kmsg': (1, 11)}
        major, minor = device_numbers.get(name, (0, 0))
        values = (index, mode, 0, 0, 1, 0, len(data), 0, 0, major, minor, len(encoded), 0)
        output += b'070701' + ''.join(f'{value:08x}' for value in values).encode()
        output += encoded
        output += bytes((-len(output)) % 4)
        output += data
        output += bytes((-len(output)) % 4)
    return bytes(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel-dir', required=True, type=Path)
    parser.add_argument('--busybox', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--kernel-trial', action='store_true', help='Stop in initramfs without mounting USERDATA')
    args = parser.parse_args()
    stock = ROOT / 'backups/stock/boot.img'
    if hashlib.file_digest(stock.open('rb'), 'sha256').hexdigest() != '6de0f78b0f5f6476cf1ad91bc4871c32160769735847596c530401630e027862':
        raise SystemExit('Stock G955N reference checksum mismatch')
    config = (args.kernel_dir / 'kernel.config').read_bytes()
    verify_embedded_config((args.kernel_dir / 'Image.unqualified').read_bytes(), config)
    elf = args.busybox.read_bytes()
    if elf[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', elf, 18)[0] != 183:
        raise SystemExit('Busybox is not AArch64 ELF')
    phoff = struct.unpack_from('<Q', elf, 32)[0]
    entsize, count = struct.unpack_from('<HH', elf, 54)
    if any(struct.unpack_from('<I', elf, phoff + i * entsize)[0] == 3 for i in range(count)):
        raise SystemExit('Busybox must be static')
    entries = [(name, stat.S_IFDIR | 0o755, b'') for name in
               ('bin', 'sbin', 'dev', 'proc', 'sys', 'run', 'tmp', 'newroot', 'efs', 'vendor', 'vendor/firmware', 'etc', 'etc/firmware')]
    entries += [('bin/busybox', stat.S_IFREG | 0o755, elf),
                ('bin/sh', stat.S_IFLNK | 0o777, b'busybox'),
                ('init', stat.S_IFREG | 0o755, (ROOT / 'image/initramfs/init').read_bytes())]
    entries += [(name, stat.S_IFCHR | 0o600, b'') for name in ('dev/console', 'dev/null', 'dev/kmsg')]
    if args.kernel_trial:
        entries.append(('etc/g955n-kernel-trial', stat.S_IFREG | 0o644, b'USERDATA must not be mounted\n'))
    for name in AUDIO:
        data = (ROOT / 'inventory/vendor/firmware' / name).read_bytes()
        for folder in ('vendor/firmware/', 'etc/firmware/'):
            entries.append((folder + name, stat.S_IFREG | 0o644, data))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    compression, compressed = compress_initramfs(newc(entries), config.decode())
    ramdisk = args.output.with_suffix('.ramdisk')
    ramdisk.write_bytes(compressed)
    dtb = args.kernel_dir / 'exynos8895-dream2lte_kor_10.dtb'
    if b'SM-G955N' not in dtb.read_bytes():
        raise SystemExit('Wrong model DTB')
    dtimg = args.output.with_suffix('.dt.img')
    subprocess.run(['python3', str(ROOT / 'scripts/boot/mkdtbh.py'), str(dtb), '-o', str(dtimg)], check=True)
    console = 'tty0' if 'CONFIG_VT_CONSOLE=y' in config.decode().splitlines() else 'ram'
    commandline = (f'console={console} log_buf_len=4M loglevel=7 androidboot.hardware=samsungexynos8895 '
                   'androidboot.selinux=permissive enforcing=0 loop.max_part=7 '
                   'firmware_class.path=/vendor/firmware systemd.unified_cgroup_hierarchy=0')
    subprocess.run(['python3', str(ROOT / 'scripts/boot/mkboot.py'), '--ref', str(stock),
                    '--kernel', str(args.kernel_dir / 'Image.unqualified'), '--dt', str(dtimg),
                    '--ramdisk', str(ramdisk), '--cmdline', commandline, '-o', str(args.output)], check=True)
    if args.output.stat().st_size > 41943040:
        raise SystemExit('BOOT image exceeds verified 40 MiB capacity')
    manifest = dict(target='SM-G955N', qualified=False, kernel_trial=args.kernel_trial,
                    initramfs_compression=compression,
                    image_sha256=hashlib.file_digest(args.output.open('rb'), 'sha256').hexdigest(),
                    kernel_sha256=hashlib.file_digest((args.kernel_dir / 'Image.unqualified').open('rb'), 'sha256').hexdigest(),
                    config_sha256=hashlib.file_digest((args.kernel_dir / 'kernel.config').open('rb'), 'sha256').hexdigest(),
                    dtb_sha256=hashlib.file_digest(dtb.open('rb'), 'sha256').hexdigest())
    args.output.with_suffix('.json').write_text(json.dumps(manifest, indent=2))
    print('Built unqualified image:', args.output, args.output.stat().st_size)


if __name__ == '__main__':
    main()
