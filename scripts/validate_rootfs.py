#!/usr/bin/env python3
"""Offline filesystem/content checks. Does not qualify boot or hardware."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from install_ubuntu import verify_rootfs_header


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    args = parser.parse_args()
    image = args.image.resolve()
    verify_rootfs_header(image)
    builder = os.environ.get('G955N_BUILDER', 'g955n-ubuntu-builder:24.04')
    command = ['docker', 'run', '--rm', '--network', 'none', '-v', str(image.parent) + ':/images:ro', builder]
    target = '/images/' + image.name
    subprocess.run([*command, 'e2fsck', '-fn', target], check=True)

    def read(path):
        return subprocess.check_output([*command, 'debugfs', '-R', 'cat ' + path, target],
                                       text=True, stderr=subprocess.DEVNULL)

    def exists(path):
        result = subprocess.check_output([*command, 'debugfs', '-R', 'stat ' + path, target],
                                         text=True, stderr=subprocess.DEVNULL)
        return result.startswith('Inode:')

    checks = {
        'target_marker': read('/etc/g955n-target').strip() == 'SM-G955N',
        'hostname': read('/etc/hostname').strip() == 'g955n-ubuntu',
        'ubuntu': 'ID=ubuntu' in read('/usr/lib/os-release'),
        'key_only_ssh': 'PasswordAuthentication no' in read('/etc/ssh/sshd_config.d/10-g955n.conf'),
        'authorized_key': read('/home/ubuntu/.ssh/authorized_keys').startswith('ssh-ed25519 '),
        'usb_address': 'Address=192.168.55.2/24' in read('/etc/systemd/network/10-g955n-usb.network'),
        'usb_mac_match': 'MACAddress=02:55:00:00:00:02' in read('/etc/systemd/network/10-g955n-usb.network'),
        'runtime_hardware_service': 'g955n-hardware' in read('/etc/systemd/system/g955n-hardware.service'),
        'physical_usb_console': 'ExecStart=-/sbin/agetty --noclear' in read('/etc/systemd/system/serial-getty@ttyGS0.service.d/10-porting-console.conf'),
        'desktop_session': 'gnome-session' in read('/usr/share/xsessions/ubuntu-xorg.desktop'),
        'manual_desktop_login': 'AutomaticLoginEnable=false' in read('/etc/gdm3/custom.conf'),
        'fbdev_desktop': 'Driver "fbdev"' in read('/etc/X11/xorg.conf.d/10-g955n-fbdev.conf'),
    }
    features = subprocess.check_output([*command, 'dumpe2fs', '-h', target], text=True, stderr=subprocess.DEVNULL)
    feature_line = next(line for line in features.splitlines() if line.startswith('Filesystem features:'))
    checks['legacy_ext4_features'] = not any(name in feature_line.split() for name in ('orphan_file', 'metadata_csum_seed', '64bit'))
    profile = read('/etc/g955n-rootfs-profile').strip() or 'legacy'
    if profile == 'mainline618':
        checks.update({
            'stock_wireplumber': exists('/usr/lib/systemd/user/wireplumber.service')
            and not exists('/etc/systemd/user/wireplumber.service'),
            'native_audio_ucm': exists('/usr/share/alsa/ucm2/conf.d/g955n-audio/g955n-audio.conf')
            and exists('/etc/systemd/system/multi-user.target.wants/g955n-mainline-speaker.service'),
            'network_location': '[wifi]' in read('/etc/geoclue/conf.d/70-g955n-network-location.conf')
            and not exists('/etc/systemd/system/sockets.target.wants/g955n-gnss.socket'),
            'manual_suspend_opt_in': 'ConditionKernelCommandLine=g955n.desktop_suspend=1'
            in read('/etc/systemd/system/systemd-suspend.service.d/50-g955n-mainline-suspend.conf'),
            'power_key_service': exists('/etc/systemd/system/graphical.target.wants/g955n-power-key.service'),
            'board_wireless_firmware': all(exists('/usr/lib/firmware/brcm/' + name) for name in (
                'brcmfmac4361b0-pcie.bin', 'brcmfmac4361b0-pcie.txt',
                'brcmfmac4361b0-pcie.clm_blob', 'BCM.samsung,dream2lteks.hcd')),
        })
    for name, passed in checks.items():
        if not passed:
            raise SystemExit('Filesystem validation failed: ' + name)
    with image.open('rb') as file:
        sha = hashlib.file_digest(file, 'sha256').hexdigest()
    report = dict(target='SM-G955N', profile=profile, fsck_clean=True, image_sha256=sha, bytes=image.stat().st_size,
                  checks=checks, scope='Offline image validation only; not hardware qualification')
    image.with_suffix('.validation.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
