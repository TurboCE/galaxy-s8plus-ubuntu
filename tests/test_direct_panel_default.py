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
                      DRM_PROBE=root / 'drm-kms-probe')
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
