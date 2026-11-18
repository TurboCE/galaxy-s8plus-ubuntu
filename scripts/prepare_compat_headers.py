#!/usr/bin/env python3
"""Build-only: export pinned Android 9 headers/libhybris in Linux storage.

No handset access, upstream firmware redistribution, flashing or installation.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    sources = json.loads((ROOT / 'sources.json').read_text())['sources']
    volume = 'g955n-hybris-build'
    builder = os.environ.get('G955N_BUILDER', 'g955n-ubuntu-builder:24.04')
    if subprocess.check_output(['docker', 'ps', '--filter', 'volume=' + volume,
                                '--format', '{{.ID}}'], text=True).strip():
        raise SystemExit('Compatibility build volume is already active')
    output = ROOT / 'artifacts/compat'
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run(['docker', 'volume', 'create', volume], check=True, stdout=subprocess.DEVNULL)
    selected = {k: v for k, v in sources.items() if k == 'libhybris' or k.startswith('aosp-')}
    for name, source in selected.items():
        repo = ROOT / 'upstream' / (name + '.git')
        actual = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != source['commit']:
            raise SystemExit('Unpinned compatibility source: ' + name)
        path = 'libhybris' if name == 'libhybris' else 'aosp/' + source['export_path']
        if PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts:
            raise SystemExit('Invalid export path')
        archive = subprocess.Popen(['git', '-C', str(repo), 'archive', actual], stdout=subprocess.PIPE)
        try:
            subprocess.run(['docker', 'run', '--rm', '-i', '--network', 'none',
                            '-v', volume + ':/work', builder, 'sh', '-ec',
                            'mkdir -p /work/' + path + '; tar -x -C /work/' + path],
                           stdin=archive.stdout, check=True)
        finally:
            archive.stdout.close()
        if archive.wait() != 0:
            raise SystemExit('Source archive export failed: ' + name)
    patch_dir = ROOT / 'compat/patches'
    patch_files = sorted(patch_dir.glob('*.patch'))
    selected['libhybris']['local_patches'] = [
        dict(file=str(path.relative_to(ROOT)), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in patch_files]
    subprocess.run(['docker', 'run', '--rm', '--network', 'none', '-v', volume + ':/work',
                    '-v', str(output) + ':/outputs',
                    '-v', str(patch_dir) + ':/compat-patches:ro', builder, 'sh', '-ec',
                    'sh /work/libhybris/utils/extract-headers.sh -v 9.0.0 /work/aosp /work/android9-headers; '
                    'test -f /work/android9-headers/android-version.h; '
                    'tar -C /work -czf /outputs/android9-headers.tar.gz android9-headers; '
                    'cd /work/libhybris; '
                    'for p in /compat-patches/*.patch; do git apply --check "$p"; git apply "$p"; done; '
                    'tar -C /work -czf /outputs/libhybris-source.tar.gz libhybris'], check=True)
    (output / 'sources.json').write_text(json.dumps(selected, indent=2))
    print(output)


if __name__ == '__main__':
    main()
