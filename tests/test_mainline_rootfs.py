"""Check that the offline 6.18 profile stages the native Ubuntu services."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


source = Path(__file__).resolve().parents[1] / 'image/stage-ubuntu-hardware.py'
spec = importlib.util.spec_from_file_location('stage_ubuntu_hardware', source)
hardware = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hardware)


class MainlineRootfsTests(unittest.TestCase):
    def test_native_services_and_manual_suspend_are_staged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            wifi = root / 'system/etc/wifi'
            bluetooth = root / 'usr/lib/firmware/samsung/g955n/bcm4361B0_semco.hcd'
            for file in (
                root / 'usr/bin/wpctl', root / 'usr/bin/zenity', bluetooth,
                wifi / 'bcmdhd_sta.bin_b0', wifi / 'nvram.txt_r02j_b0', wifi / 'bcmdhd_clm.blob',
            ):
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(file.name.encode())
            units = root / 'etc/systemd/system'
            units.mkdir(parents=True)
            for unit in ('sleep.target', 'suspend.target', 'hibernate.target', 'hybrid-sleep.target'):
                (units / unit).symlink_to('/dev/null')

            with patch.object(hardware, 'digest', side_effect=[
                '56c7c64290132add7720ce98a0e0ee55a73452c6f41fba5c23d3eea3b2cc5a49',
                '343fb252959cf643dde61e16967aaeea82012301b5033262cb3547a8736d5a92',
            ] * 2):
                hardware.install_mainline618(root)
                hardware.install_mainline618(root)

            self.assertFalse((root / hardware.WIREPLUMBER).is_symlink())
            self.assertFalse((units / 'sleep.target').is_symlink())
            self.assertFalse((units / 'suspend.target').is_symlink())
            self.assertTrue((units / 'hibernate.target').is_symlink())
            self.assertTrue((units / 'hybrid-sleep.target').is_symlink())
            self.assertTrue((units / 'graphical.target.wants/g955n-power-key.service').exists())
            self.assertTrue((units / 'multi-user.target.wants/g955n-mainline-speaker.service').exists())
            self.assertFalse((units / 'sockets.target.wants/g955n-gnss.socket').exists())
            for unit in ('g955n-power-key.service', 'systemd-suspend.service'):
                config = units / (unit + '.d') / '50-g955n-mainline-suspend.conf'
                self.assertIn('ConditionKernelCommandLine=g955n.desktop_suspend=1', config.read_text())
                self.assertIn('12860000.decon-handoff/drm', config.read_text())
            self.assertIn('[wifi]', (root / 'etc/geoclue/conf.d/70-g955n-network-location.conf').read_text())

    def test_legacy_wireplumber_mask_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            mask = root / hardware.WIREPLUMBER
            mask.parent.mkdir(parents=True)
            mask.symlink_to('/dev/null')
            with self.assertRaisesRegex(ValueError, 'requires stock PipeWire'):
                hardware.install_mainline618(root)
            self.assertEqual(mask.readlink(), Path('/dev/null'))

    def test_module_release_is_verified_before_installing(self):
        release = '6.18.0-g955n-usb-r98'
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / 'rootfs'
            modules = base / release
            for name in (
                'kernel/drivers/gpu/drm/tiny/g955n-decon-handoff.ko',
                'kernel/sound/soc/samsung/g955n-abox-speaker.ko',
                'modules.order',
            ):
                file = modules / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(name)
            (modules / 'build').symlink_to('/work/source')
            destination = root / 'usr/lib/modules' / release

            with patch.object(hardware.subprocess, 'check_output', return_value='wrong-release SMP\n'):
                with self.assertRaisesRegex(ValueError, 'Kernel module release mismatch'):
                    hardware.install_mainline_modules(root, modules)
            self.assertFalse(destination.exists())

            with patch.object(hardware.subprocess, 'check_output', return_value=f'{release} SMP\n'), \
                 patch.object(hardware.subprocess, 'run') as depmod:
                hardware.install_mainline_modules(root, modules)
                hardware.install_mainline_modules(root, modules)
            self.assertTrue((destination / 'modules.order').is_file())
            self.assertFalse((destination / 'build').is_symlink())
            depmod.assert_called_with(['chroot', str(root), '/usr/sbin/depmod', release], check=True)


if __name__ == '__main__':
    unittest.main()
