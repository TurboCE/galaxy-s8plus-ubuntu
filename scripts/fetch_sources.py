#!/usr/bin/env python3
"""Fetch exact source commits without executing upstream scripts."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    for name, source in json.loads((ROOT / 'sources.json').read_text())['sources'].items():
        path = ROOT / 'upstream' / name
        if not path.exists():
            path.mkdir(parents=True)
            subprocess.run(['git', 'init', str(path)], check=True, capture_output=True)
            subprocess.run(['git', '-C', str(path), 'remote', 'add', 'origin', source['url']], check=True)
        remote = subprocess.check_output(['git', '-C', str(path), 'remote', 'get-url', 'origin'], text=True).strip()
        if remote != source['url']:
            raise SystemExit(f'Remote mismatch: {name}')
        if subprocess.check_output(['git', '-C', str(path), 'status', '--porcelain'], text=True).strip():
            raise SystemExit(f'Refusing to overwrite modified source: {name}')
        subprocess.run(['git', '-C', str(path), 'fetch', '--depth', '1', 'origin', source['commit']], check=True)
        subprocess.run(['git', '-C', str(path), 'checkout', '--detach', source['commit']], check=True)


if __name__ == '__main__':
    main()
