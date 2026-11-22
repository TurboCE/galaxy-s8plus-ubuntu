#!/usr/bin/env python3
"""Container-only Ubuntu builder. No phone access; private firmware stays local."""
import argparse
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--volume', default='g955n-ubuntu-rootfs-build')
    parser.add_argument('--finalize-only', action='store_true')
    parser.add_argument('--sensor-daemon', type=Path,
                        help='Stage the reviewed AArch64 Samsung SSP SensorProxy executable')
    parser.add_argument('--ambient-power-daemon', type=Path,
                        help='Stage the reviewed AArch64 GNOME power daemon with ambient brightness ramping')
    parser.add_argument('--audio-build', type=Path,
                        help='Stage the reviewed scoped ALSA build directory for desktop speaker output')
    parser.add_argument('--gnss-client', type=Path,
                        help='Stage the reviewed AArch64 SM-G955N GNSS client and GeoClue configuration')
    args = parser.parse_args()
    if not re.fullmatch(r'g955n-[a-z0-9-]+', args.volume):
        raise SystemExit('Requires a dedicated g955n-* build volume')
    if subprocess.check_output(['docker', 'ps', '--filter', 'volume=' + args.volume, '--format', '{{.ID}}'], text=True).strip():
        raise SystemExit('Build volume is already in use; refusing concurrent mutation')
    builder = os.environ.get('G955N_BUILDER', 'g955n-ubuntu-builder:24.04')
    os.umask(0o077)
    output = ROOT / 'artifacts/rootfs'
    inputs = ROOT / 'artifacts/inputs'
    output.mkdir(parents=True, exist_ok=True)
    inputs.mkdir(parents=True, exist_ok=True)
    identity = ROOT / 'artifacts/g955n-local-ssh'
    if not identity.exists():
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(identity), '-C', 'g955n-ubuntu-local'], check=True)
    (inputs / 'ssh.pub').write_bytes(identity.with_suffix('.pub').read_bytes())
    common = ['docker', 'run', '--rm', '--cpus', '3', '--memory', '4g',
              '-v', args.volume + ':/work', '-v', str(output) + ':/outputs']
    subprocess.run(['docker', 'volume', 'create', args.volume], check=True, stdout=subprocess.DEVNULL)
    if not args.finalize_only:
        for name in ('firmware', 'wifi'):
            if not (ROOT / 'inventory/vendor' / name).is_dir():
                raise SystemExit('Extract own-device firmware before building')
        subprocess.run([*common, '--cap-add', 'SYS_ADMIN', '--security-opt', 'apparmor=unconfined',
                        '-v', str(inputs) + ':/inputs:ro',
                        '-v', str(ROOT / 'inventory/vendor') + ':/firmware:ro', builder,
                        'bash', '-c', (ROOT / 'image/build-rootfs.sh').read_text()], check=True)
    hardware_mounts = []
    if args.sensor_daemon:
        hardware_mounts += ['-v', str(args.sensor_daemon.resolve(strict=True)) + ':/adapters/sensor-proxy:ro']
    if args.ambient_power_daemon:
        hardware_mounts += ['-v', str(args.ambient_power_daemon.resolve(strict=True)) + ':/adapters/gsd-power:ro']
    if args.audio_build:
        hardware_mounts += ['-v', str(args.audio_build.resolve(strict=True)) + ':/adapters/audio:ro']
    if args.gnss_client:
        hardware_mounts += ['-v', str(args.gnss_client.resolve(strict=True)) + ':/adapters/gnss-client:ro']
    subprocess.run([*common, '--network', 'none',
                    '-v', str(inputs) + ':/inputs:ro',
                    '-v', str(ROOT / 'image') + ':/source/image:ro',
                    '-v', str(ROOT / 'compat') + ':/source/compat:ro', *hardware_mounts, builder,
                    'bash', '-c', (ROOT / 'image/finalize-rootfs.sh').read_text()], check=True)


if __name__ == '__main__':
    main()
