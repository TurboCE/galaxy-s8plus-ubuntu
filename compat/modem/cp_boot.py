#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Bounded SM-G955N CP RAM boot trial; no firmware/NV storage writes.

Protocol references: Samsung/LineageOS cpboot_v3 (Apache-2.0), commit
e9816cf6ed8123a2f20ea334641794a0e64b1e7f, BootDumpModap.cpp and Protocol*.cpp.
ABI reference: the pinned G955N kernel's modem_v1/modem_prj.h and
link_device_shmem.c. This older ABI does NOT support full TOC/VSS security
modes 7/12. It uses normal signed BOOT/MAIN verification, not a bypass.

Default invocation only validates private inputs. --boot-trial additionally
boots the CP once, observes its read-only state, then powers it off. This is
not a persistent RIL/RFS backend or evidence of LTE service.
"""
import argparse
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import select
import signal
import stat
import struct
import subprocess
import time
import zlib

TOC = struct.Struct('<12sIIIII')
FIRMWARE = struct.Struct('<QIIIII')  # packed u64 pointer, five u32 fields
SECURITY = struct.Struct('<IIII')
CHUNK = 62 * 1024
BOOT_LIMIT = 0x08000000  # DT shmem,ipc_offset; not the AP address space
CP_BASE = 0x40000000
LABELS = Path('/dev/disk/by-partlabel')


@dataclass(frozen=True)
class Stage:
    name: str
    offset: int
    payload: bytes


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def validate_nv(nv, expected_sha, companion):
    if len(nv) != 1024 * 1024 or sha256(nv) != expected_sha:
        raise RuntimeError('Existing NV differs from private inventory')
    # The companion covers NV plus this public format suffix, not plain MD5.
    # SHA256 still pins the separately verified private backup.
    if hashlib.md5(nv + b'Samsung_Android_RIL').hexdigest() != companion.strip().lower():
        raise RuntimeError('Existing Samsung NV companion checksum mismatch')


def plan(radio, nv):
    """Validate every section before opening a modem node or issuing IOCTLs."""
    if len(radio) < 512 or len(nv) != 1024 * 1024:
        raise ValueError('Missing complete firmware or existing 1 MiB NV')
    entries = [TOC.unpack_from(radio, n * TOC.size) for n in range(16)]
    names = [e[0].split(b'\0', 1)[0] for e in entries]
    if names[:6] != [b'TOC', b'BOOT', b'MAIN', b'VSS', b'NV', b'OFFSET']:
        raise ValueError('Unsupported G955N TOC layout')
    if any(names[6:]) or entries[0][1:] != (0, 0, 512, 0, 5):
        raise ValueError('Unsupported extended TOC/security layout')
    result = []
    memory_ranges, file_ranges = [], []
    for index, entry in enumerate(entries[1:5], 1):
        raw_name, file_offset, address, size, crc, section = entry
        name = raw_name.split(b'\0', 1)[0].decode('ascii')
        if section != index or not size or address < CP_BASE:
            raise ValueError('Invalid section identity/address/size')
        offset = address - CP_BASE
        if offset >= BOOT_LIMIT or size > BOOT_LIMIT - offset:
            raise ValueError('Section exceeds CP boot RAM')
        if name == 'NV':
            if file_offset != 0 or size != len(nv) or crc != 0:
                raise ValueError('NV must use the existing separate read-only file')
            data = nv
        else:
            if file_offset < 512 or file_offset > len(radio) - size:
                raise ValueError('Firmware section exceeds RADIO')
            data = radio[file_offset:file_offset + size]
            if zlib.crc32(data) != crc:
                raise ValueError('Firmware CRC mismatch: ' + name)
            file_ranges.append((file_offset, file_offset + size))
        memory_ranges.append((offset, offset + size))
        result.append(Stage(name, offset, data))
    for ranges in (memory_ranges, file_ranges):
        ranges.sort()
        if any(a[1] > b[0] for a, b in zip(ranges, ranges[1:])):
            raise ValueError('Overlapping firmware sections')
    return result


def load_and_handshake(transport, stages, progress=lambda step: None):
    """Old SIPC SHMEM ABI only. Every unsuccessful transfer stops the sequence."""
    # The reference treats return11 as CP-not-working only for RE_INIT.
    progress('security-reinit')
    transport.security(2, 0, 0)
    for stage in stages:
        progress('load-' + stage.name)
        for done in range(0, len(stage.payload), CHUNK):
            transport.load(stage, done, stage.payload[done:done + CHUNK])
    by_name = {stage.name: stage for stage in stages}
    progress('verify-signed-boot-main')
    transport.security(0, len(by_name['BOOT'].payload), len(by_name['MAIN'].payload))
    progress('power-on')
    transport.command(0x19)  # CP power on after signed image verification
    progress('bootloader-ready')
    transport.command(0x22)  # wait for CP bootloader mailbox
    transport.command(0x28)  # download map + AP ready
    progress('boot-done-handshake')
    transport.exchange(0x900d, 0xa00d)  # BOOT_DONE
    transport.exchange(0x9f00, 0xaf00)  # final stage
    progress('normal-init-completion')
    transport.command(0x23)  # real init completion; may block up to kernel15s
    transport.command(0x24)


class NativeTransport:
    def __init__(self, fd):
        self.fd = fd
        self.powered = False

    def command(self, number, argument=0):
        if number not in (0x19, 0x20, 0x21, 0x22, 0x23, 0x24, 0x28, 0x40, 0x53):
            raise ValueError('Command outside normal RAM boot protocol')
        if number == 0x19:
            self.powered = True  # also attempt shutdown if power-on fails halfway
        result = fcntl.ioctl(self.fd, (ord('o') << 8) | number, argument)
        if isinstance(result, int) and result:
            raise OSError('Nonzero modem command result: ' + str(result))

    def security(self, mode, boot, main):
        if mode not in (0, 2):
            raise ValueError('Security mode not supported by this kernel')
        data = bytearray(SECURITY.pack(mode, boot, main, 0))
        result = fcntl.ioctl(self.fd, (ord('o') << 8) | 0x53, data)
        if result != 0 and not (mode == 2 and result == 11):
            raise OSError('CP signed-image verification failed: ' + str(result))

    def load(self, stage, done, data):
        if not data or done + len(data) > len(stage.payload):
            raise ValueError('Invalid CP transfer bounds')
        payload = ctypes.create_string_buffer(data, len(data))
        args = FIRMWARE.pack(ctypes.addressof(payload), len(stage.payload),
                             stage.offset + done, 0, 0, len(data))
        # payload stays alive until the kernel's synchronous copy_from_user ends.
        self.command(0x40, bytearray(args))

    def exchange(self, request, expected):
        if os.write(self.fd, struct.pack('<I', request)) != 4:
            raise OSError('Incomplete SIPC command')
        poll = select.poll()
        poll.register(self.fd, select.POLLIN | select.POLLERR | select.POLLHUP)
        deadline = time.monotonic() + 5
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('SIPC handshake timeout')
            ready = poll.poll(max(1, int(remaining * 1000)))
            if not ready:
                continue
            if ready[0][1] & (select.POLLERR | select.POLLHUP | select.POLLNVAL):
                raise OSError('CP disconnected during SIPC handshake')
            data = os.read(self.fd, 4)
            if data != struct.pack('<I', expected):
                raise OSError('Unexpected or incomplete SIPC response')
            return


def modem_state():
    nodes = list(Path('/sys/devices/platform').glob('**/modem_state'))
    if len(nodes) != 1:
        raise RuntimeError('Ambiguous modem state interface')
    return nodes[0].read_text().strip()


@contextmanager
def sleep_inhibitor():
    """Hold a real logind inhibitor and confirm readiness before touching CP.

    The pipe's EOF also releases the inhibitor if this parent disappears.
    Android wake_lock alone is not a substitute for desktop sleep policy.
    """
    child = subprocess.Popen(['/usr/bin/systemd-inhibit', '--what=sleep:idle',
                              '--mode=block', '--who=G955N CP RAM trial',
                              '--why=Bounded modem initialization', '/bin/cat'],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        child.stdin.write(b'ready\n')
        child.stdin.flush()
        if not select.select([child.stdout], [], [], 5)[0] or child.stdout.readline() != b'ready\n':
            raise RuntimeError('Desktop sleep inhibitor did not become ready')
        yield
    finally:
        try:
            child.stdin.close()
        except BrokenPipeError:
            pass
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=3)
        child.stdout.close()


def preflight(record):
    if os.geteuid() or platform.machine() != 'aarch64':
        raise RuntimeError('Requires native G955N root')
    tree = Path('/proc/device-tree')
    if b'SM-G955N' not in (tree / 'model').read_bytes() or record['model'] != 'SM-G955N':
        raise RuntimeError('Wrong handset')
    mif = list(tree.glob('**/mif,name'))
    limits = list(tree.glob('**/shmem,ipc_offset'))
    if (len(mif) != 1 or mif[0].read_bytes() != b'ss355ap\0' or
            len(limits) != 1 or limits[0].read_bytes() != struct.pack('>I', BOOT_LIMIT)):
        raise RuntimeError('Unsupported CP/SHMEM device tree')
    options = subprocess.check_output(['findmnt', '-rn', '-o', 'OPTIONS', '/efs'], text=True)
    if 'ro' not in options.strip().split(','):
        raise RuntimeError('Requires existing EFS mounted read-only')
    # Inventory includes verified private raw-backup hashes, never identifiers.
    radio = None
    for name in ('RADIO', 'EFS', 'CPEFS', 'RECOVERY', 'PARAM'):
        path = LABELS / name
        if not stat.S_ISBLK(path.stat().st_mode):
            raise RuntimeError('Protected partition missing: ' + name)
        with path.open('rb') as stream:
            digest = hashlib.sha256()
            size = 0
            chunks = [] if name == 'RADIO' else None
            while data := stream.read(1024 * 1024):
                digest.update(data)
                size += len(data)
                if chunks is not None:
                    chunks.append(data)
        expected = record['partitions'][name]
        if size != expected['bytes'] or digest.hexdigest() != expected['sha256']:
            raise RuntimeError('Protected backup/current mismatch: ' + name)
        if chunks is not None:
            radio = b''.join(chunks)
    nv = Path('/efs/nv_data.bin').read_bytes()
    validate_nv(nv, record['nv_sha256'], Path('/efs/nv_data.bin.md5').read_text())
    stages = plan(radio, nv)
    if modem_state() != 'OFFLINE':
        raise RuntimeError('CP must be offline before this single trial')
    paths = {'/dev/umts_boot0', '/dev/umts_ipc0', '/dev/umts_rfs0'}
    for fd in Path('/proc').glob('[0-9]*/fd/*'):
        try:
            target = os.readlink(fd)
        except OSError:
            continue
        if target in paths:
            raise RuntimeError('A modem client is already active')
    return stages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-inventory', type=Path, required=True)
    parser.add_argument('--boot-trial', action='store_true')
    parser.add_argument('--query-status', action='store_true',
                        help='Read-only SIPC power/SIM GETs during the bounded trial')
    args = parser.parse_args()
    if args.query_status and not args.boot_trial:
        parser.error('--query-status requires --boot-trial')
    stages = preflight(json.loads(args.private_inventory.read_text()))
    print(json.dumps({'validated': True, 'sections': [s.name for s in stages],
                      'storage_write': False, 'boot_requested': args.boot_trial}), flush=True)
    if not args.boot_trial:
        return
    def interrupted(signum, frame):
        raise InterruptedError('CP trial interrupted; shutting down')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    fds = []
    transport = None
    os.umask(0o077)
    with Path('/run/g955n-cp-boot.lock').open('a') as lock, sleep_inhibitor():
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            Path('/sys/power/wake_lock').write_text('g955n-cp-boot-trial')
            for name in ('umts_boot0', 'umts_ipc0', 'umts_rfs0'):
                fd = os.open('/dev/' + name, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC | os.O_NOFOLLOW)
                fds.append(fd)
            transport = NativeTransport(fds[0])
            load_and_handshake(transport, stages,
                               lambda step: print(json.dumps({'step': step}), flush=True))
            print(json.dumps({'cp_after_handshake': modem_state(), 'LTE_qualified': False}), flush=True)
            if args.query_status:
                from sipc_status import observe
                print(json.dumps({'sipc_status': observe(fds[1], fds[2], query=True)}), flush=True)
            else:
                time.sleep(5)
            print(json.dumps({'cp_after_observation': modem_state()}), flush=True)
        finally:
            try:
                if transport and transport.powered:
                    try:
                        transport.command(0x21)  # restore OFFLINE, no storage IO
                    finally:
                        transport.command(0x20)  # no persistent modem service yet
            finally:
                for fd in reversed(fds):
                    os.close(fd)
                Path('/sys/power/wake_unlock').write_text('g955n-cp-boot-trial')


if __name__ == '__main__':
    main()
