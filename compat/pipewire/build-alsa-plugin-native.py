#!/usr/bin/env python3
"""Build-only G955N SPA ALSA plugin from authenticated exact Ubuntu sources.

Never installs a library, opens an ALSA device, starts a service or installs
dependencies. Configure resource paths match Ubuntu; build output stays in HOME.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

VERSION = '1.0.5-1ubuntu3.3'
SOURCE_HASHES = {
    'pipewire_1.0.5.orig.tar.bz2': 'd5e5f3d0b8460e5711c1571c500156fd61768ba55a062eaeb94356abdb955a56',
    'pipewire_1.0.5-1ubuntu3.3.debian.tar.xz': 'a1650f8e95859b3a8057ea95dad7e0509bfed9896db5b0d17c70910c4e9a3ff0',
    'pipewire_1.0.5-1ubuntu3.3.dsc': '8c9f84687253a01bd787431bf8ef04f4c9306db1a7c0dda6c9564f17da6a7c02',
}
PATCHED_HASHES = {
    'spa/plugins/alsa/acp/acp.c': 'b3428f8789094d0d3298ddbfa556a4659b56dbe3ee7badd34be14ad57607d4b1',
    'spa/plugins/alsa/acp/card.h': '5c45c2eab81a24c88551ad1f0c79465ee66907adceee93127d28a8dc23872f41',
}


def digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def output(command, **kwargs):
    return subprocess.check_output(command, text=True, **kwargs).strip()


def exported_symbols(path):
    lines = output(['nm', '-D', '--defined-only', str(path)]).splitlines()
    return sorted(line.split()[-1] for line in lines if line.split())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path,
                        default=Path.home() / 'g955n-pipewire-build')
    args = parser.parse_args()
    if (os.geteuid() == 0 or platform.machine() != 'aarch64'
            or 'g955n-ubuntu' not in platform.release()
            or 'SM-G955N' not in Path('/proc/device-tree/model').read_text()):
        raise SystemExit('Build unprivileged on the native G955N Ubuntu handset')
    work = args.workspace.resolve()
    if not work.is_relative_to(Path.home().resolve()):
        raise SystemExit('Keep all build output under the user HOME directory')
    installed = output(['dpkg-query', '-W', '-f=${Version}', 'libspa-0.2-modules'])
    if installed != VERSION:
        raise SystemExit('Exact installed Ubuntu plugin version changed; review source pins')
    for name, expected in SOURCE_HASHES.items():
        if digest(work / name) != expected:
            raise SystemExit('Authenticated source archive checksum mismatch: ' + name)
    source = work / 'pipewire-1.0.5'
    for name, expected in PATCHED_HASHES.items():
        if digest(source / name) != expected:
            raise SystemExit('Reviewed backport source checksum mismatch: ' + name)
    if not (source / 'debian/changelog').read_text().startswith('pipewire (' + VERSION + ')'):
        raise SystemExit('Unexpected Ubuntu changelog/version')
    series = [line.split()[0] for line in (source / 'debian/patches/series').read_text().splitlines()
              if line.strip() and not line.lstrip().startswith('#')]
    applied = (source / '.pc/applied-patches').read_text().splitlines()
    if series != applied:
        raise SystemExit('The original Ubuntu patch series is not fully applied')
    for command in ('meson', 'ninja', 'gcc', 'pkg-config', 'nm', 'readelf', 'dpkg-buildflags'):
        if shutil.which(command) is None:
            raise SystemExit('Missing build dependency: ' + command)
    subprocess.run(['pkg-config', '--exists', 'alsa', 'libudev'], check=True)
    build = work / 'build-alsa'
    candidate = work / 'candidate'
    candidate.mkdir(mode=0o700, exist_ok=True)
    environment = dict(os.environ, DEB_BUILD_MAINT_OPTIONS='hardening=+all',
                       DEB_LDFLAGS_MAINT_APPEND='-Wl,-z,defs')
    for flag in ('CPPFLAGS', 'CFLAGS', 'CXXFLAGS', 'LDFLAGS'):
        environment[flag] = output(['dpkg-buildflags', '--get', flag], env=environment)
    configure = [
        'meson', 'setup', str(build), str(source), '--prefix=/usr',
        '--libdir=lib/aarch64-linux-gnu', '--buildtype=plain', '--wrap-mode=nodownload',
        '-Dauto_features=disabled', '-Dspa-plugins=enabled', '-Dalsa=enabled',
        '-Dudev=enabled', '-Ddbus=disabled', '-Dsession-managers=[]',
        '-Dtests=disabled', '-Dexamples=disabled', '-Ddocs=disabled', '-Dman=disabled',
        '-Dflatpak=disabled', '-Dgsettings=disabled', '-Dpipewire-jack=disabled',
        '-Dpipewire-v4l2=disabled', '-Dsystemd-user-service=disabled',
    ]
    if (build / 'meson-private/coredata.dat').exists():
        configure.append('--reconfigure')
    with (work / 'meson-alsa.log').open('w') as log:
        subprocess.run(configure, env=environment, stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    with (work / 'ninja-alsa.log').open('w') as log:
        subprocess.run(['ninja', '-C', str(build), '-j2', 'spa/plugins/alsa/libspa-alsa.so'],
                       env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
    built = build / 'spa/plugins/alsa/libspa-alsa.so'
    original = Path('/usr/lib/aarch64-linux-gnu/spa-0.2/alsa/libspa-alsa.so')
    elf = output(['readelf', '-h', str(built)])
    dynamic = output(['readelf', '-d', str(built)])
    symbols = exported_symbols(built)
    if 'AArch64' not in elf or 'DYN (Shared object file)' not in elf:
        raise SystemExit('Unexpected candidate ELF architecture/type')
    if '(RPATH)' in dynamic or '(RUNPATH)' in dynamic:
        raise SystemExit('Unexpected runtime path in candidate plugin')
    if symbols != exported_symbols(original):
        raise SystemExit('Candidate exported symbol ABI differs from installed plugin')
    plugin = candidate / 'libspa-alsa.so'
    shutil.copyfile(built, plugin)
    plugin.chmod(0o644)
    metadata = dict(
        package='libspa-0.2-modules', ubuntu_source_version=VERSION,
        upstream_backport='a8b9ce2050dfb3f91c19061562d0a161117c3ab8',
        feature='api.acp.disable-pro-audio', source_archives=SOURCE_HASHES,
        patched_source_files=PATCHED_HASHES, ubuntu_patch_series=applied,
        compiler_flags={key: environment[key] for key in ('CPPFLAGS', 'CFLAGS', 'CXXFLAGS', 'LDFLAGS')},
        candidate_sha256=digest(plugin), original_plugin_sha256=digest(original),
        candidate_bytes=plugin.stat().st_size, exported_symbols=symbols,
        exported_symbol_abi_matches=True, installed=False, hardware_tested=False,
    )
    (candidate / 'elf-header.txt').write_text(elf + '\n')
    (candidate / 'elf-dynamic.txt').write_text(dynamic + '\n')
    (candidate / 'elf-versions.txt').write_text(output(['readelf', '--version-info', str(plugin)]) + '\n')
    (candidate / 'build.json').write_text(json.dumps(metadata, indent=2))
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main()
