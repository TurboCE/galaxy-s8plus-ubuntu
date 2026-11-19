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
                      DEFAULT=self.policy, LEASE=self.lease)
        options = patch.multiple(controller, **values)
        options.start()
        self.addCleanup(options.stop)

    def enable_default(self):
        self.policy.write_text(json.dumps({
            path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in self.files
        }))

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
