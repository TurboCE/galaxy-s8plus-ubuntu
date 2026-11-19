"""Isolated root-owned journal recovery; never opens real sensor sysfs."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('ssp_recovery', Path(__file__).resolve().parents[1] / 'compat/sensors/recover-ssp-lease.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


@unittest.skipUnless(os.geteuid() == 0, 'Root-owned isolated fixtures: run in the sensor builder container')
class SSPLeaseRecovery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.node = self.root / 'sensor'
        self.node.mkdir()
        self.saved = ['0', '64', '0', '200000000']
        for name, value in zip(recovery.ATTRIBUTES, ['1', '128', '1', '100000000']):
            p = self.node / name
            p.parent.mkdir(exist_ok=True)
            p.write_text(value)
        self.enable = self.root / 'enable'
        self.enable.write_text(str((1 << 42) | 1))
        self.journal = self.root / '0.ini'
        self.journal.write_text('[sensor]\nboot=fixture-boot\npath=' + str(self.node) + '\nbit=0\n' + ''.join(f'saved{i}={value}\n' for i, value in enumerate(self.saved)))
        self.journal.chmod(0o600)
        self.devices = {'accelerometer_sensor': self.node.resolve()}

    def run_recovery(self):
        recovery.restore_record(self.journal, 'fixture-boot', self.devices, self.enable)

    def test_restores_attributes_and_only_own_bit(self):
        self.run_recovery()
        self.assertFalse(self.journal.exists())
        self.assertEqual(int(self.enable.read_text()), 1 << 42)
        self.assertEqual([(self.node / x).read_text() for x in recovery.ATTRIBUTES], self.saved)

    def test_old_boot_refuses_before_mutation(self):
        with self.assertRaises(RuntimeError):
            recovery.restore_record(self.journal, 'other-boot', self.devices, self.enable)
        self.assertEqual(int(self.enable.read_text()), (1 << 42) | 1)
        self.assertTrue(self.journal.exists())

    def test_symlink_journal_refuses(self):
        actual = self.root / 'actual'
        self.journal.rename(actual)
        self.journal.symlink_to(actual)
        with self.assertRaises(RuntimeError):
            self.run_recovery()
        self.assertTrue(actual.exists())

    def test_shared_inode_refuses(self):
        os.link(self.journal, self.root / 'other')
        with self.assertRaises(RuntimeError):
            self.run_recovery()

    def test_wrong_device_refuses(self):
        self.devices['accelerometer_sensor'] = self.root
        with self.assertRaises(RuntimeError):
            self.run_recovery()
        self.assertEqual(int(self.enable.read_text()), (1 << 42) | 1)

    def test_active_original_buffer_refuses(self):
        self.journal.write_text(self.journal.read_text().replace('saved2=0', 'saved2=1'))
        with self.assertRaises(RuntimeError):
            self.run_recovery()
        self.assertTrue(self.journal.exists())

    def test_partial_write_failure_keeps_journal_for_retry(self):
        poll = self.node / 'poll_delay'
        poll.unlink()
        poll.mkdir()
        with self.assertRaises(IsADirectoryError):
            self.run_recovery()
        self.assertTrue(self.journal.exists())
        self.assertEqual(int(self.enable.read_text()), 1 << 42)
        poll.rmdir()
        poll.write_text('100000000')
        self.run_recovery()
        self.assertFalse(self.journal.exists())

    def test_untrusted_permissions_refuse(self):
        self.journal.chmod(0o644)
        with self.assertRaises(RuntimeError):
            self.run_recovery()

    def test_light_recovery_preserves_accel_claim(self):
        self.journal.rename(self.root / '9.ini')
        self.journal = self.root / '9.ini'
        self.journal.write_text(self.journal.read_text().replace('bit=0', 'bit=9'))
        self.devices = {'light_sensor': self.node.resolve()}
        self.enable.write_text(str((1 << 9) | 1))
        self.run_recovery()
        self.assertEqual(int(self.enable.read_text()), 1)


if __name__ == '__main__':
    unittest.main()
