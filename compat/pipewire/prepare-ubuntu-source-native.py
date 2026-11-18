#!/usr/bin/env python3
"""Download/authenticate/extract exact Ubuntu PipeWire source under HOME only.

Uses a private APT lists/cache and signed Sources metadata. Does not install
packages, modify system APT settings, open ALSA or start any services.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import pwd
import re
import runpy
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path,
                        default=Path.home() / 'g955n-pipewire-build')
    parser.add_argument('--patch', type=Path,
                        default=Path(__file__).parent / 'patches/0001-disable-pro-audio-backport.patch')
    args = parser.parse_args()
    if (os.geteuid() == 0 or platform.machine() != 'aarch64'
            or 'g955n-ubuntu' not in platform.release()
            or 'SM-G955N' not in Path('/proc/device-tree/model').read_text()):
        raise SystemExit('Run unprivileged on the native SM-G955N Ubuntu handset')
    pins = runpy.run_path(str(Path(__file__).with_name('build-alsa-plugin-native.py')),
                         run_name='g955n_pipewire_source_pins')
    version = pins['VERSION']
    expected = pins['SOURCE_HASHES']
    work = args.workspace.resolve()
    if not work.is_relative_to(Path.home().resolve()):
        raise SystemExit('Keep source preparation under HOME')
    os.umask(0o077)
    work.mkdir(mode=0o700, parents=True, exist_ok=True)
    for relative in ('apt-lists/partial', 'apt-cache/archives/partial'):
        (work / relative).mkdir(mode=0o700, parents=True, exist_ok=True)
    source_list = work / 'sources.list'
    source_list.write_text(''.join(
        'deb-src [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] '
        'https://ports.ubuntu.com/ubuntu-ports ' + suite + ' main\n'
        for suite in ('noble', 'noble-updates', 'noble-security')))
    options = [
        '-o', 'Dir::Etc::sourcelist=' + str(source_list),
        '-o', 'Dir::Etc::sourceparts=-',
        '-o', 'Dir::State::lists=' + str(work / 'apt-lists'),
        '-o', 'Dir::Cache=' + str(work / 'apt-cache'),
        '-o', 'APT::Sandbox::User=' + pwd.getpwuid(os.getuid()).pw_name,
        '-o', 'APT::Get::AllowUnauthenticated=false',
        '-o', 'Acquire::AllowInsecureRepositories=false',
    ]

    def run(command, name):
        with (work / name).open('w') as log:
            result = subprocess.run(command, cwd=work, stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT, timeout=180)
        if result.returncode:
            raise SystemExit(name + ' failed; inspect ' + str(work / name))
        print(name + ' completed', flush=True)

    run(['apt-get', *options, 'update'], 'apt-update.log')
    metadata = subprocess.check_output(['apt-cache', *options, 'showsrc', 'pipewire'],
                                       text=True, timeout=30)
    (work / 'source-metadata.txt').write_text(metadata)
    paragraphs = [part for part in metadata.split('\n\n')
                  if re.search(r'^Version: ' + re.escape(version) + r'$', part, re.M)]
    if not paragraphs:
        raise SystemExit('Exact version absent from authenticated Sources; do not substitute')
    block = re.search(r'^Checksums-Sha256:\n((?: [^\n]+\n?)+)', paragraphs[0], re.M)
    if block is None:
        raise SystemExit('Authenticated source SHA-256 block missing')
    listed = {name: (digest, int(size))
              for digest, size, name in (line.split() for line in block.group(1).splitlines())}
    if {name: value[0] for name, value in listed.items()} != expected:
        raise SystemExit('Authenticated source files differ from reviewed source pins')
    run(['apt-get', *options, 'source', '--download-only', '--only-source',
         'pipewire=' + version], 'apt-source-download.log')
    verified = {}
    for name, (digest, size) in listed.items():
        path = work / name
        if path.stat().st_size != size or pins['digest'](path) != digest:
            raise SystemExit('Downloaded source failed SHA-256/size check: ' + name)
        verified[name] = dict(sha256=digest, bytes=size)
    receipt = dict(package='pipewire', version=version, files=verified,
                   authentication='APT InRelease with ubuntu-archive-keyring; signed Sources SHA256 independently checked')
    (work / 'source-authentication.json').write_text(json.dumps(receipt, indent=2))
    source = work / 'pipewire-1.0.5'
    if source.exists():
        if all(pins['digest'](source / name) == value
               for name, value in pins['PATCHED_HASHES'].items()):
            print('Existing reviewed patched tree retained; build runner checks Ubuntu patch series')
            return
        raise SystemExit('Existing source tree differs; retain it for review rather than overwrite')
    dsc = next(name for name in listed if name.endswith('.dsc'))
    run(['dpkg-source', '-x', dsc], 'dpkg-source-extract.log')
    patch = args.patch.resolve(strict=True)
    copied_patch = work / patch.name
    if patch != copied_patch.resolve():
        shutil.copyfile(patch, copied_patch)
    with copied_patch.open('r') as data:
        subprocess.run(['patch', '--dry-run', '-p1'], cwd=source, stdin=data, check=True)
    with copied_patch.open('r') as data:
        subprocess.run(['patch', '-p1'], cwd=source, stdin=data, check=True)
    for name, digest in pins['PATCHED_HASHES'].items():
        if pins['digest'](source / name) != digest:
            raise SystemExit('Applied backport differs from reviewed source: ' + name)
    (work / 'local-backport.json').write_text(json.dumps(dict(
        upstream_commit='a8b9ce2050dfb3f91c19061562d0a161117c3ab8',
        patch_sha256=pins['digest'](copied_patch), patched_files=pins['PATCHED_HASHES']), indent=2))
    print('Authenticated Ubuntu sources and local backport prepared:', source)


if __name__ == '__main__':
    main()
