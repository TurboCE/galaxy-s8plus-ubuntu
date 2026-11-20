#!/usr/bin/env python3
"""Offline, matching-image/KASLR-aware retained panic decoding. Reports stay private."""
import argparse
from bisect import bisect_right
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

BANNER = re.compile(rb'Linux version [^\r\n\0]{1,700}')
BOOT_BANNER = re.compile(rb'^(?:<\d+>)?(?:\[[^\r\n]{1,40}\][ \t]*)?(' + BANNER.pattern + rb')', re.M)
FAULT = re.compile(r'Unable to handle kernel|Internal error:|Kernel panic|\bBUG:|\bWARNING:|hard LOCKUP|soft lockup', re.I)
LOADER = re.compile(rb'(?:^|\n)(?:\[[^\r\n]{1,40}\]\s*)?Samsung S-Boot')
PAIR = re.compile(r'PC is at ([\w.]+)\+0x([\da-f]+)/0x[\da-f]+[^\n]*\n'
                  r'[^\n]*LR is at ([\w.]+)\+0x([\da-f]+)/0x[\da-f]+[^\n]*\n'
                  r'[^\n]*pc\s*:\s*\[<([\da-f]{16})>\]\s+lr\s*:\s*\[<([\da-f]{16})>\]', re.I)


def map_symbols(text):
    names, code = {}, []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[1] in ('t', 'T') and re.fullmatch('[0-9a-fA-F]{16}', fields[0]):
            address = int(fields[0], 16)
            names[fields[2]] = address
            code.append((address, fields[2]))
    if not code:
        raise ValueError('No ARM64 code symbols')
    return names, sorted(code)


def resolve(address, code):
    offsets = [item[0] for item in code]
    index = bisect_right(offsets, address) - 1
    if index < 0 or index == len(code)-1:
        return None
    base, name = code[index]
    return {'symbol': name, 'offset': hex(address-base), 'link_address': hex(address)}


def analyze(raw, expected_banner, symbols):
    names, code = symbols
    report = {'scope': 'Matching retained boot segment only; not hardware acceptance or root-cause proof',
              'hardware_qualified': False, 'status': 'unmatched', 'faults': [], 'panic_callers': []}
    banners = list(BOOT_BANNER.finditer(raw))
    if not banners:
        report['reason'] = 'No intact Linux banner; manual examination required'
        return report
    latest = banners[-1]
    # Never search backward for an older matching image when the latest boot differs.
    if latest.group(1) != expected_banner:
        report['reason'] = 'Latest retained banner differs from image, or is damaged'
        return report
    loaders = list(LOADER.finditer(raw, latest.end()))
    if len(loaders) > 1:
        report['reason'] = 'Multiple later bootloader sections; a newer Linux banner may be damaged'
        return report
    end = loaders[0] if loaders else None
    segment = raw[latest.start():end.start() if end else len(raw)].decode('utf-8', errors='replace')
    report.update(status='segment-matched', segment_start=latest.start(),
                  segment_end=end.start() if end else len(raw), older_banners_excluded=len(banners)-1)
    report['faults'] = [{'segment_line': n, 'message': line[:320]}
                        for n, line in enumerate(segment.splitlines(), 1) if FAULT.search(line)]
    evidence = []
    for match in re.finditer(r'Kernel loaded at:\s*0x[\da-f]+,\s*offset from compile-time address\s+(?:0x)?([\da-f]+)', segment, re.I):
        evidence.append(('explicit-boot-offset', int(match[1], 16)))
    for pair in PAIR.finditer(segment):
        pc_name, pc_delta, lr_name, lr_delta, pc, lr = pair.groups()
        if pc_name not in names or lr_name not in names:
            continue
        candidates = [int(pc, 16)-names[pc_name]-int(pc_delta, 16),
                      int(lr, 16)-names[lr_name]-int(lr_delta, 16)]
        if candidates[0] != candidates[1]:
            report['relocation_status'] = 'conflicting-pc-lr-evidence'
            return report
        evidence.append(('agreeing-pc-lr', candidates[0]))
    values = {value for _, value in evidence}
    if not evidence:
        report['relocation_status'] = 'unavailable'
        return report
    if len(values) != 1 or any(value < 0 or value > 0x40000000 or value % 4096 for value in values):
        report['relocation_status'] = 'conflicting-or-invalid-evidence'
        return report
    relocation = values.pop()
    report.update(relocation_status='verified', relocation=hex(relocation),
                  relocation_evidence=[kind for kind, _ in evidence])
    for match in re.finditer(r'stack-protector: Kernel stack is corrupted in:\s*(?:0x)?([\da-f]{16})', segment, re.I):
        runtime_return = int(match[1], 16)
        # __stack_chk_fail prints its return address. AArch64 BL's instruction
        # is four bytes earlier, possibly in the preceding function at a boundary.
        callsite = runtime_return-relocation-4
        report['panic_callers'].append({'runtime_return_address': hex(runtime_return),
                                        'callsite': resolve(callsite, code),
                                        'interpretation': 'Stack-check failure caller, not proof of the first corrupting writer'})
    return report


def validate_output(log, kernel_dir, output):
    destination = output.resolve()
    if destination == log.resolve() or destination.is_relative_to(kernel_dir.resolve()):
        raise ValueError('Report cannot overwrite the captured log or matching build')
    if not output.parent.is_dir():
        raise ValueError('Create the private report directory explicitly')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--log', type=Path, required=True)
    p.add_argument('--kernel-dir', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True, help='Private JSON output; never commit device addresses')
    a = p.parse_args()
    validate_output(a.log, a.kernel_dir, a.output)
    plan = json.loads((a.kernel_dir/'plan.json').read_text())
    if plan.get('target') != 'SM-G955N' or plan.get('build_exit') != 0:
        raise SystemExit('Expected completed own-device build plan')
    for name in ('vmlinux', 'System.map'):
        with (a.kernel_dir/name).open('rb') as f:
            actual = hashlib.file_digest(f, 'sha256').hexdigest()
        if actual != plan['artifacts'].get(name):
            raise SystemExit('Changed matching-image artifact: '+name)
    elf = (a.kernel_dir/'vmlinux').read_bytes()
    if not elf.startswith(b'\x7fELF\x02\x01') or int.from_bytes(elf[18:20], 'little') != 183:
        raise SystemExit('Expected AArch64 little-endian ELF64')
    banners = {m.group() for m in BANNER.finditer(elf) if m.group().startswith(b'Linux version 4.4.111-g955n-ubuntu')}
    if len(banners) != 1:
        raise SystemExit('Ambiguous compiled Linux banner')
    report = analyze(a.log.read_bytes(), banners.pop(), map_symbols((a.kernel_dir/'System.map').read_text()))
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', dir=a.output.parent, prefix='.panic-', delete=False) as f:
            temporary = Path(f.name)
            json.dump(report, f, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(temporary, a.output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print('Private decoder report:', report['status'], report.get('relocation_status', 'not-attempted'))
    return 0 if report.get('relocation_status') == 'verified' else 2


if __name__ == '__main__':
    raise SystemExit(main())
