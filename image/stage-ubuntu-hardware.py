#!/usr/bin/env python3
"""Stage opt-in G955N hardware adapters in an offline Ubuntu root filesystem."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

SOURCE = Path(__file__).resolve().parents[1]
AUDIO = SOURCE / 'compat/pipewire'
SENSORS = SOURCE / 'compat/sensors'
STOCK_SPA = Path('usr/lib/aarch64-linux-gnu/spa-0.2')
PRIVATE_SPA = Path('usr/local/lib/g955n/spa-0.2')
WIREPLUMBER = Path('etc/systemd/user/wireplumber.service')


def digest(file):
    with file.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def arm64_elf(file):
    with file.open('rb') as stream:
        header = stream.read(20)
    return header[:6] == b'\x7fELF\x02\x01' and header[18:20] == b'\xb7\x00'


def stage(root, target, contents, mode=0o644):
    dest = root / target
    parent = dest.parent
    if not parent.resolve().is_relative_to(root):
        raise ValueError(f'Unsafe target parent: {parent}')
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=parent, delete=False) as output:
        name = Path(output.name)
        try:
            output.write(contents)
            os.fchmod(output.fileno(), mode)
            output.close()
            name.replace(dest)
        finally:
            name.unlink(missing_ok=True)


def install_sensors(root, daemon):
    binary = daemon.read_bytes()
    if not arm64_elf(daemon) or any(tag not in binary for tag in (b'samsung-ssp-accel', b'samsung-ssp-als')):
        raise ValueError('Expected the AArch64 Samsung SSP SensorProxy build')
    for input_file, target, mode in (
        (daemon, 'opt/g955n-sensors/libexec/iio-sensor-proxy', 0o755),
        (SENSORS / 'prepare-ssp.py', 'opt/g955n-sensors/prepare-ssp.py', 0o755),
        (SENSORS / 'recover-ssp-lease.py', 'opt/g955n-sensors/recover-ssp-lease.py', 0o755),
        (SOURCE / 'compat/light-calibration-probe.py', 'opt/g955n-sensors/light-calibration-probe.py', 0o755),
        (SENSORS / 'g955n-ssp.tmpfiles', 'etc/tmpfiles.d/g955n-ssp.conf', 0o644),
        (SENSORS / '99-g955n-sensors.rules', 'etc/udev/rules.d/99-g955n-sensors.rules', 0o644),
        (SENSORS / '90-g955n-ssp.conf', 'etc/systemd/system/iio-sensor-proxy.service.d/90-g955n-ssp.conf', 0o644),
    ):
        stage(root, target, input_file.read_bytes(), mode)


def link(root, name, target):
    file = root / name
    if not file.parent.resolve().is_relative_to(root):
        raise ValueError(f'Unsafe link parent: {file.parent}')
    file.parent.mkdir(parents=True, exist_ok=True)
    if file.is_symlink() and file.readlink() == target:
        return
    file.symlink_to(target)


def install_audio(root, build):
    guards = {
        'usr/local/libexec/g955n-wireplumber': 'g955n-wireplumber',
        'etc/systemd/user/wireplumber.service.d/10-g955n-validated-plugin.conf': '10-g955n-validated-plugin.conf',
        'etc/systemd/user/pipewire.service.d/10-g955n-validated-plugin.conf': '10-g955n-validated-core.conf',
    }
    if any((root / dest).read_bytes() != (AUDIO / name).read_bytes()
           for dest, name in guards.items()):
        raise ValueError('Both audio services require the reviewed startup guard')
    mask = root / WIREPLUMBER
    if not mask.is_symlink() or mask.readlink() != Path('/dev/null'):
        raise ValueError('Expected the existing WirePlumber mask')
    record_file = build / 'build.json'
    record = json.loads(record_file.read_text())
    binary = build / 'libspa-alsa.so'
    stock_plugin = root / STOCK_SPA / 'alsa/libspa-alsa.so'
    scope = AUDIO / 'patches/0002-g955n-pcm-open-scope.patch'
    package = subprocess.check_output(
        ['dpkg-query', '--admindir=' + str(root / 'var/lib/dpkg'), '-W',
         '-f=${Version}', 'libspa-0.2-modules'], text=True)
    if (record.get('ubuntu_source_version') != package
            or record.get('hardware_open_scope') != 'g955n-rdma0-wdma1-ucm-v3'
            or record.get('feature') != 'api.acp.disable-pro-audio'
            or record.get('exported_symbol_abi_matches') is not True
            or record.get('scope_patch_sha256') != digest(scope)
            or record.get('original_plugin_sha256') != digest(stock_plugin)
            or record.get('candidate_sha256') != digest(binary)
            or not arm64_elf(binary)):
        raise ValueError('Scoped ALSA adapter does not match the reviewed Ubuntu image')
    stage(root, PRIVATE_SPA / 'alsa/libspa-alsa.so', binary.read_bytes())
    for family in (root / STOCK_SPA).iterdir():
        if family.name != 'alsa' and family.is_dir():
            link(root, PRIVATE_SPA / family.name, Path('/') / STOCK_SPA / family.name)
    stage(root, 'etc/wireplumber/main.lua.d/52-g955n-ucm-only.lua',
          (AUDIO / '52-g955n-ucm-only.lua').read_bytes())
    stage(root, 'usr/share/alsa-card-profile/mixer/profile-sets/g955n-ucm-only.conf',
          (AUDIO / 'g955n-ucm-only.conf').read_bytes())
    link(root, 'usr/share/alsa/ucm2/conf.d/Exynos8895-Made/Exynos8895-Madera.conf',
         Path('../../Samsung/SM-G955N/SM-G955N.conf'))
    manifest = subprocess.check_output(
        ['python3', str(AUDIO / 'create-install-manifest.py'), '--stage-root', str(root),
         '--build-record', str(record_file)])
    stage(root, 'usr/local/share/g955n/pipewire-plugin.json', manifest)
    stage(root, 'etc/systemd/user/wireplumber.service.d/20-g955n-desktop-user.conf',
          b'[Unit]\nConditionUser=ubuntu\n')
    mask.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rootfs', required=True, type=Path)
    parser.add_argument('--sensor-daemon', type=Path)
    parser.add_argument('--audio-build', type=Path)
    args = parser.parse_args()
    root = args.rootfs.resolve(strict=True)
    if root == Path('/') or (root / 'etc/hostname').read_text().strip() != 'g955n-ubuntu':
        parser.error('requires the offline SM-G955N Ubuntu rootfs')
    if args.sensor_daemon:
        install_sensors(root, args.sensor_daemon)
    if args.audio_build:
        install_audio(root, args.audio_build)


if __name__ == '__main__':
    main()
