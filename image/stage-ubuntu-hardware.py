#!/usr/bin/env python3
"""Stage opt-in G955N hardware adapters in an offline Ubuntu root filesystem."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

SOURCE = Path(__file__).resolve().parents[1]
AMBIENT = SOURCE / 'compat/ambient-brightness'
AUDIO = SOURCE / 'compat/pipewire'
GNSS = SOURCE / 'compat/gnss'
SENSORS = SOURCE / 'compat/sensors'
SUSPEND = SOURCE / 'compat/suspend'
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


def install_ambient_power(root, daemon):
    binary = daemon.read_bytes()
    if not arm64_elf(daemon) or b'[gsd-power] ambient ramp' not in binary:
        raise ValueError('Expected the AArch64 ambient brightness power daemon')
    package = subprocess.check_output(
        ['dpkg-query', '--admindir=' + str(root / 'var/lib/dpkg'), '-W',
         '-f=${Version}', 'gnome-settings-daemon'], text=True)
    launcher = (AMBIENT / 'run-power.sh').read_bytes()
    if b'built_for=' + package.encode() + b'\n' not in launcher:
        raise ValueError('Ambient brightness daemon does not match the Ubuntu package')
    stage(root, 'opt/g955n-ambient-brightness/gsd-power', binary, 0o755)
    stage(root, 'opt/g955n-ambient-brightness/run-power.sh', launcher, 0o755)
    name = '60-g955n-ambient-brightness.conf'
    stage(root, 'etc/systemd/user/org.gnome.SettingsDaemon.Power.service.d/' + name,
          (AMBIENT / name).read_bytes())


def link(root, name, target):
    file = root / name
    if not file.parent.resolve().is_relative_to(root):
        raise ValueError(f'Unsafe link parent: {file.parent}')
    file.parent.mkdir(parents=True, exist_ok=True)
    if file.is_symlink() and file.readlink() == target:
        return
    file.symlink_to(target)


def install_gnss(root, client, *, mainline=False):
    binary = client.read_bytes()
    if not arm64_elf(client) or any(tag not in binary for tag in (
            b'/vendor/lib64/hw/gps.default.so', b'GPS XTRA injection result', b'--serve')):
        raise ValueError('Expected the reviewed AArch64 SM-G955N GNSS client')
    if not any(line.startswith('geoclue:') for line in (root / 'etc/group').read_text().splitlines()):
        raise ValueError('Install geoclue-2.0 in the Ubuntu rootfs before staging GNSS')
    socket = 'g955n-gnss-mainline' if mainline else 'g955n-gnss'
    units = [socket + '.socket', socket + '@.service', 'g955n-gnss-assist.service']
    helpers = ['serve.py', 'assistance.py', 'lto.py', 'run-probe.py']
    if mainline:
        helpers.append('serve-mainline.py')
    else:
        units.extend(('g955n-gnss-bsp.service', 'g955n-gnss-lto.service'))
    library = Path('usr/local/lib/g955n-gnss')
    stage(root, library / 'hal-probe', binary, 0o755)
    for name in helpers:
        target = 'run_probe.py' if name == 'run-probe.py' else name
        stage(root, library / target, (GNSS / name).read_bytes())
    for name in units:
        stage(root, Path('etc/systemd/system') / name, (GNSS / name).read_bytes())
    name = '80-g955n-location.conf'
    stage(root, Path('etc/geoclue/conf.d') / name, (GNSS / name).read_bytes())
    link(root, f'etc/systemd/system/sockets.target.wants/{socket}.socket',
         Path(f'../{socket}.socket'))


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


def install_mainline618(root):
    for path in (
        root / WIREPLUMBER,
        root / 'etc/systemd/user/wireplumber.service.d/10-g955n-validated-plugin.conf',
        root / 'etc/systemd/user/pipewire.service.d/10-g955n-validated-plugin.conf',
    ):
        if path.exists() or path.is_symlink():
            raise ValueError('The mainline profile requires stock PipeWire and WirePlumber')
    for package_file in ('usr/bin/wpctl', 'usr/bin/zenity'):
        if not (root / package_file).is_file():
            raise ValueError(f'Missing mainline package file: {package_file}')

    firmware_dir = Path('usr/lib/firmware/brcm')
    wifi_source = root / 'system/etc/wifi'
    nvram = wifi_source / 'nvram.txt_r02j_b0'
    bluetooth = root / 'usr/lib/firmware/samsung/g955n/bcm4361B0_semco.hcd'
    # The r02j NVRAM and Semco E32 patch are the pair verified on R97.
    if (digest(nvram) != '56c7c64290132add7720ce98a0e0ee55a73452c6f41fba5c23d3eea3b2cc5a49'
            or digest(bluetooth) != '343fb252959cf643dde61e16967aaeea82012301b5033262cb3547a8736d5a92'):
        raise ValueError('The mainline profile requires the verified r02j firmware pair')
    for source_file, name in (
        (wifi_source / 'bcmdhd_sta.bin_b0', 'brcmfmac4361b0-pcie.bin'),
        (nvram, 'brcmfmac4361b0-pcie.txt'),
        (wifi_source / 'bcmdhd_clm.blob', 'brcmfmac4361b0-pcie.clm_blob'),
        (bluetooth, 'BCM.samsung,dream2lteks.hcd'),
    ):
        stage(root, firmware_dir / name, source_file.read_bytes())

    unit_dir = Path('etc/systemd/system')
    for source_file, target, mode in (
        (SOURCE / 'compat/g955n-mainline-speaker.service', unit_dir / 'g955n-mainline-speaker.service', 0o644),
        (SUSPEND / 'g955n-power-key.service', unit_dir / 'g955n-power-key.service', 0o644),
        (SUSPEND / 'g955n-power-key.py', 'usr/local/lib/g955n/g955n-power-key.py', 0o755),
        (SUSPEND / '60-g955n-wake-report', 'usr/lib/systemd/system-sleep/60-g955n-wake-report', 0o755),
        (SUSPEND / '60-g955n-suspend-to-idle.conf', 'etc/systemd/sleep.conf.d/60-g955n-suspend-to-idle.conf', 0o644),
        (GNSS / '70-g955n-network-location.conf', 'etc/geoclue/conf.d/70-g955n-network-location.conf', 0o644),
    ):
        stage(root, target, source_file.read_bytes(), mode)

    suspend_conditions = (
        b'[Unit]\nConditionKernelCommandLine=g955n.desktop_suspend=1\n'
        b'ConditionPathExists=/sys/bus/platform/devices/12860000.decon-handoff/drm\n'
    )
    for unit in ('g955n-power-key.service', 'systemd-suspend.service'):
        stage(root, unit_dir / (unit + '.d') / '50-g955n-mainline-suspend.conf',
              suspend_conditions)
    for db in ('local.d', 'gdm.d'):
        stage(root, Path('etc/dconf/db') / db / '60-g955n-manual-suspend',
              (SUSPEND / '60-g955n-manual-suspend').read_bytes())
    for unit in ('sleep.target', 'suspend.target'):
        mask = root / unit_dir / unit
        if mask.is_symlink() and mask.readlink() == Path('/dev/null'):
            mask.unlink()
    link(root, unit_dir / 'graphical.target.wants/g955n-power-key.service',
         Path('../g955n-power-key.service'))
    link(root, unit_dir / 'multi-user.target.wants/g955n-mainline-speaker.service',
         Path('../g955n-mainline-speaker.service'))


def install_mainline_modules(root, source):
    release = source.name
    if not re.fullmatch(r'6\.18\.\d+-g955n-[a-z0-9.-]+', release):
        raise ValueError('Expected a SM-G955N 6.18 kernel release directory')
    if not (source / 'modules.order').is_file():
        raise ValueError('Kernel release directory is missing modules.order')
    if (any(path.is_symlink() for path in source.iterdir() if path.name not in ('build', 'source'))
            or any(path.is_symlink() for path in (source / 'kernel').rglob('*'))):
        raise ValueError('Kernel module files must be local to the release directory')
    modules = Path('usr/lib/modules')
    destination = root / modules / release
    if destination.is_symlink() or not destination.parent.resolve().is_relative_to(root):
        raise ValueError('Unsafe target kernel module directory')
    destination.parent.mkdir(parents=True, exist_ok=True)
    required = (
        'kernel/drivers/gpu/drm/tiny/g955n-decon-handoff.ko',
        'kernel/sound/soc/samsung/g955n-abox-speaker.ko',
    )
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        candidate = Path(temporary) / release
        shutil.copytree(source, candidate, ignore=shutil.ignore_patterns('build', 'source'))
        for name in required:
            result = subprocess.check_output(
                ['chroot', str(root), '/usr/sbin/modinfo', '-F', 'vermagic',
                 '/' + str((candidate / name).relative_to(root))], text=True)
            if result.split(maxsplit=1)[:1] != [release]:
                raise ValueError(f'Kernel module release mismatch: {name}')
        if destination.exists():
            if not (destination / 'modules.order').is_file():
                raise ValueError(f'Existing module tree is incomplete: {release}')
            files = set(path.relative_to(candidate) for path in candidate.rglob('*.ko'))
            installed = set(path.relative_to(destination) for path in destination.rglob('*.ko'))
            if files != installed or any(digest(candidate / name) != digest(destination / name)
                                         for name in files):
                raise ValueError(f'Existing modules differ for kernel release {release}')
        else:
            candidate.rename(destination)
    subprocess.run(['chroot', str(root), '/usr/sbin/depmod', release], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rootfs', required=True, type=Path)
    parser.add_argument('--sensor-daemon', type=Path)
    parser.add_argument('--audio-build', type=Path)
    parser.add_argument('--ambient-power-daemon', type=Path)
    parser.add_argument('--gnss-client', type=Path)
    parser.add_argument('--mainline618', action='store_true')
    parser.add_argument('--mainline-modules', type=Path)
    args = parser.parse_args()
    root = args.rootfs.resolve(strict=True)
    if root == Path('/') or (root / 'etc/hostname').read_text().strip() != 'g955n-ubuntu':
        parser.error('requires the offline SM-G955N Ubuntu rootfs')
    if args.mainline618:
        if any((args.sensor_daemon, args.ambient_power_daemon, args.audio_build)):
            parser.error('--mainline618 cannot be combined with downstream adapters')
        install_mainline618(root)
        if args.gnss_client:
            install_gnss(root, args.gnss_client, mainline=True)
        if args.mainline_modules:
            install_mainline_modules(root, args.mainline_modules)
        return
    if args.mainline_modules:
        parser.error('--mainline-modules requires --mainline618')
    if args.sensor_daemon:
        install_sensors(root, args.sensor_daemon)
    if args.ambient_power_daemon:
        install_ambient_power(root, args.ambient_power_daemon)
    if args.audio_build:
        install_audio(root, args.audio_build)
    if args.gnss_client:
        install_gnss(root, args.gnss_client)


if __name__ == '__main__':
    main()
