#!/usr/bin/env python3
"""Build-only review manifest: read staged files and hash them; never activates a device."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from importlib.machinery import SourceFileLoader


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-boot-id', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}', args.expected_boot_id):
        parser.error('An exact reviewed boot UUID is required')
    root = args.build_dir.resolve(strict=True)
    output = args.output.resolve()
    if any(output.is_relative_to(p) for p in ('/dev', '/proc', '/sys', '/efs', '/system', '/vendor', '/boot', '/etc', '/usr')):
        parser.error('Use private staging output')
    module = SourceFileLoader('cpu_review', str(Path(__file__).with_name('run-cpu-buffer-trial.py'))).load_module()
    files = {}
    for name in sorted(module.REVIEW_FILES):
        path = root / name
        if not path.is_file() or path.resolve() != path:
            raise SystemExit('Missing/indirect staged file: ' + name)
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    payload = json.dumps(dict(target='SM-G955N', scope='cpu-buffer-64x64-no-display', expected_boot_id=args.expected_boot_id, files=files), indent=2) + '\n'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload)
    print('Review manifest only:', output)
    print('SHA256:', hashlib.sha256(payload.encode()).hexdigest())


if __name__ == '__main__':
    main()
