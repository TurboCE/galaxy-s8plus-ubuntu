import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SOURCE = (Path(__file__).resolve().parents[1] /
          'compat/native-gnome/direct-panel/trial.py')
SPEC = importlib.util.spec_from_file_location('direct_panel_controller', SOURCE)
controller = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(controller)


class DirectPanelBootTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        backup = root / 'backup'
        backup.mkdir()
        self.files = tuple(root / name for name in ('module.so', 'manifest.json', 'session.py'))
        self.policy = backup / 'enabled-default.json'
        self.lease = root / 'lease'
        for path in self.files:
            path.write_bytes(b'direct ' + path.name.encode())
            (backup / path.name).write_bytes(b'original ' + path.name.encode())
        (backup / 'session.py').chmod(0o755)
        values = dict(PREFIX=root, FILES=self.files, POLICY_FILES=(), BACKUP=backup,
                      DEFAULT=self.policy, LEASE=self.lease, LAUNCHER=self.files[2],
                      DRM_PROBE=root / 'drm-kms-probe', PRIVATE_FBDEV=root / 'private-fbdev.so')
        options = patch.multiple(controller, **values)
        options.start()
        self.addCleanup(options.stop)

    def enable_default(self):
        self.policy.write_text(json.dumps(controller.default_hashes()))

    def prepare(self, qualified=True):
        with patch.object(controller, 'qualified_kernel', return_value=qualified):
            controller.prepare_boot()

    def assert_recovered(self):
        self.assertFalse(self.lease.exists())
        self.assertFalse(self.policy.parent.exists())
        for path in self.files:
            self.assertEqual(path.read_bytes(), b'original ' + path.name.encode())

    def test_trial_rolls_back_after_reboot(self):
        self.prepare()
        self.assert_recovered()

    def test_rotation_trial_restores_driver_and_xorg_config_after_reboot(self):
        rotation = tuple(self.files[0].parent / name for name in
                         ('fbdev_drv.so', '10-g955n-fbdev.conf'))
        for path in rotation:
            path.write_bytes(b'candidate')
            snapshot = self.policy.parent / path.name
            snapshot.write_bytes(path.name.encode())
            snapshot.chmod(0o644)
        with patch.multiple(controller, FBDEV=rotation[0], XORG_CONFIG=rotation[1], ROTATION_FILES=rotation):
            self.prepare()
        self.assert_recovered()
        for path in rotation:
            self.assertEqual(path.read_bytes(), path.name.encode())
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)

    def test_verified_default_recreates_runtime_lease(self):
        self.enable_default()
        self.prepare()
        self.assertTrue(self.lease.is_file())
        self.assertTrue(self.policy.is_file())
        self.assertEqual(self.files[0].read_bytes(), b'direct module.so')

    def test_incompatible_kernel_recovers_original_files(self):
        self.enable_default()
        self.prepare(qualified=False)
        self.assert_recovered()

    def test_changed_default_files_recover_original_files(self):
        self.enable_default()
        self.files[0].write_bytes(b'changed')
        self.prepare()
        self.assert_recovered()

    def test_missing_launcher_is_restored_with_executable_mode(self):
        self.enable_default()
        self.files[2].unlink()
        self.prepare()
        self.assert_recovered()
        self.assertEqual(self.files[2].stat().st_mode & 0o777, 0o755)

    def test_kernel36_requires_reviewed_linked_notes(self):
        notes = self.policy.parent / 'notes'
        notes.write_bytes(b'reviewed kernel build')
        with patch.object(controller, 'KERNEL_NOTES', notes), \
             patch.object(controller, 'KERNEL36_NOTES_SHA256',
                          hashlib.sha256(notes.read_bytes()).hexdigest()), \
             patch.object(controller.subprocess, 'check_output', return_value='#36 SMP\n'):
            self.assertTrue(controller.qualified_kernel())
            notes.write_bytes(b'other kernel build')
            self.assertFalse(controller.qualified_kernel())
            notes.unlink()
            self.assertFalse(controller.qualified_kernel())

    def test_kernel50_requires_its_linked_notes(self):
        notes = self.policy.parent / 'notes50'
        notes.write_bytes(b'reviewed kernel50')
        with patch.object(controller, 'KERNEL_NOTES', notes), \
             patch.object(controller, 'KERNEL50_NOTES_SHA256',
                          hashlib.sha256(notes.read_bytes()).hexdigest()), \
             patch.object(controller.subprocess, 'check_output', return_value='#50 SMP\n'):
            self.assertTrue(controller.qualified_kernel())
            notes.write_bytes(b'different kernel50')
            self.assertFalse(controller.qualified_kernel())
            notes.unlink()
            self.assertFalse(controller.qualified_kernel())

    def select_kms(self):
        self.files[2].write_bytes(b" env['G955N_DRM_KMS']='1'")
        controller.DRM_PROBE.write_bytes(b'reviewed capability probe')
        self.enable_default()

    def test_kms_boot_uses_capabilities_without_kernel_number_allowlist(self):
        self.select_kms()
        with patch.object(controller, 'qualified_kms', return_value=True), \
             patch.object(controller, 'qualified_kernel', side_effect=AssertionError):
            controller.prepare_boot()
        self.assertTrue(self.lease.exists())
        self.assertTrue(self.policy.exists())

    def test_kms_interface_loss_restores_original_files(self):
        self.select_kms()
        with patch.object(controller, 'qualified_kms', return_value=False):
            controller.prepare_boot()
        self.assert_recovered()

    def test_persistent_rotation_verifies_xorg_driver_and_config(self):
        xorg_dir = tempfile.TemporaryDirectory()
        self.addCleanup(xorg_dir.cleanup)
        rotation = tuple(Path(xorg_dir.name) / name for name in
                         ('fbdev_drv.so', '10-g955n-fbdev.conf'))
        for path in rotation:
            path.write_bytes(b'candidate')
            (self.policy.parent / path.name).write_bytes(b'prior')
        self.files[2].write_bytes(
            b"env['G955N_DRM_KMS']='1'\nenv['G955N_DIRECT_PANEL_ROTATION']='1'")
        controller.DRM_PROBE.write_bytes(b'reviewed probe')
        with patch.multiple(controller, FBDEV=rotation[0], XORG_CONFIG=rotation[1], ROTATION_FILES=rotation):
            self.enable_default()
            self.assertTrue(all(str(path) in json.loads(self.policy.read_text())
                                for path in rotation))
            with patch.object(controller, 'qualified_kms', return_value=True):
                controller.prepare_boot()
                self.assertTrue(self.lease.exists())
                self.lease.unlink()
                rotation[1].write_bytes(b'changed')
                controller.prepare_boot()
            self.assert_recovered()
        self.assertEqual([path.read_bytes() for path in rotation], [b'prior', b'prior'])

    def test_legacy_recovery_preserves_a_replaced_package_module(self):
        xorg_dir = tempfile.TemporaryDirectory()
        self.addCleanup(xorg_dir.cleanup)
        config = Path(xorg_dir.name) / 'xorg.conf'
        fbdev = Path(xorg_dir.name) / 'fbdev_drv.so'
        for path in (config, fbdev):
            path.write_bytes(b'candidate')
            (self.policy.parent / path.name).write_bytes(b'original')
        self.select_kms()
        self.files[2].write_bytes(self.files[2].read_bytes() +
                                  b"\nenv['G955N_DIRECT_PANEL_ROTATION']='1'")
        with patch.multiple(controller, FBDEV=fbdev, XORG_CONFIG=config,
                            ROTATION_FILES=(fbdev, config)):
            self.enable_default()
            fbdev.write_bytes(b'new package version')
            controller.prepare_boot()
            self.assert_recovered()
        self.assertEqual(config.read_bytes(), b'original')
        self.assertEqual(fbdev.read_bytes(), b'new package version')

    def test_private_rotation_preserves_package_module_and_checks_server(self):
        root = self.files[0].parent
        config = root / 'xorg.conf'
        fbdev = root / 'package-fbdev.so'
        server = root / 'Xorg'
        files = (config, fbdev, server, controller.PRIVATE_FBDEV)
        for path in files:
            path.write_bytes(b'validated')
        (self.policy.parent / config.name).write_bytes(b'original config')
        (self.policy.parent / 'xorg-server.sha256').touch()
        self.select_kms()
        self.files[2].write_bytes(self.files[2].read_bytes() +
                                  b"\nenv['G955N_DIRECT_PANEL_ROTATION']='1'")
        with patch.multiple(controller, FBDEV=fbdev, XORG_CONFIG=config, XORG_SERVER=server), \
             patch.object(controller, 'qualified_kms', return_value=True):
            self.enable_default()
            fbdev.write_bytes(b'upgraded package module')
            controller.prepare_boot()
            self.assertTrue(self.lease.exists())
            self.lease.unlink()
            server.write_bytes(b'changed Xorg')
            controller.prepare_boot()
            self.assert_recovered()
        self.assertFalse(controller.PRIVATE_FBDEV.exists())
        self.assertEqual(config.read_bytes(), b'original config')
        self.assertEqual(fbdev.read_bytes(), b'upgraded package module')

    def test_kms_probe_binary_is_part_of_persistent_hashes(self):
        self.select_kms()
        controller.DRM_PROBE.write_bytes(b'changed probe')
        with patch.object(controller, 'qualified_kms', side_effect=AssertionError('Changed probe must not execute')):
            controller.prepare_boot()
        self.assert_recovered()

    def test_manual_restore_cancels_transient_timer_before_restarting_gdm(self):
        self.lease.touch()
        calls = []

        def run(command, **kwargs):
            calls.append(tuple(command))

        with patch.object(controller.subprocess, 'run', side_effect=run):
            controller.restore()

        self.assertEqual(calls[0], ('systemctl', 'stop', controller.TIMER + '.timer'))
        self.assertIn(('systemctl', 'start', 'gdm.service'), calls)
        self.assert_recovered()
