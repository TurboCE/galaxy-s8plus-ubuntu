#!/usr/bin/env python3
"""Fetch exact source commits without executing upstream scripts."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    for name, source in json.loads((ROOT / 'sources.json').read_text())['sources'].items():
        # Bare repositories preserve case-sensitive Linux paths on macOS.
        # Existing working checkouts are deliberately left untouched.
        path = ROOT / 'upstream' / (name + '.git')
        if not path.exists():
            path.mkdir(parents=True)
            subprocess.run(['git', 'init', '--bare', str(path)], check=True, capture_output=True)
            subprocess.run(['git', '-C', str(path), 'remote', 'add', 'origin', source['url']], check=True)
        remote = subprocess.check_output(['git', '-C', str(path), 'remote', 'get-url', 'origin'], text=True).strip()
        if remote != source['url']:
            raise SystemExit(f'Remote mismatch: {name}')
        bare = subprocess.check_output(['git', '-C', str(path), 'rev-parse', '--is-bare-repository'], text=True).strip()
        if bare != 'true':
            raise SystemExit(f'Refusing non-bare source destination: {name}')
        subprocess.run(['git', '-C', str(path), 'fetch', '--depth', '1', 'origin', source['commit']], check=True)
        subprocess.run(['git', '-C', str(path), 'update-ref', 'refs/heads/pinned', source['commit']], check=True)
        subprocess.run(['git', '-C', str(path), 'symbolic-ref', 'HEAD', 'refs/heads/pinned'], check=True)


if __name__ == '__main__':
    main()
