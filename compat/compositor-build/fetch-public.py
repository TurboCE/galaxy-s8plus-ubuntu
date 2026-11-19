#!/usr/bin/env python3
"""Fetch only pinned public compositor tarballs; never connect to a handset.

Existing AOSP inputs use their separately pinned Git commits in sources.json.
Private own-device link libraries are deliberately outside this fetcher.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    sources = json.loads(Path(__file__).with_name('sources.json').read_text())
    for name, source in sources.items():
        if not isinstance(source, dict) or 'archive_sha256' not in source:
            continue
        archive = output / (name + '.tar.gz')
        if not archive.exists():
            repository = source['url'].removeprefix('https://github.com/')
            request = urllib.request.Request(
                f"https://api.github.com/repos/{repository}/tarball/{source['commit']}",
                headers={'User-Agent': 'g955n-compositor-source-build'})
            with urllib.request.urlopen(request, timeout=60) as response:
                archive.write_bytes(response.read(64 * 1024 * 1024))
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest != source['archive_sha256']:
            raise SystemExit('Pinned archive checksum mismatch: ' + name)
        with tarfile.open(archive, 'r:gz') as package:
            package.extractall(output, filter='data')
        print(name, source['commit'], digest)


if __name__ == '__main__':
    main()
