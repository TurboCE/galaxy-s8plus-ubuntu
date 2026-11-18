import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('install', Path(__file__).resolve().parents[1] / 'scripts/install_ubuntu.py')
install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install)


class InstallGuards(unittest.TestCase):
    def test_initial_install_bridge_rejects_unverified_or_wrong_image(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original, image = b'original partition bytes', b'new boot'
            (root / 'BOOT.img').write_bytes(original)
            boot = root / 'normal.img'
            boot.write_bytes(image)
            record = root / 'install.json'
            valid = dict(target='SM-G955N', state='installed_readback_verified_not_booted',
                         boot_sha256=hashlib.sha256(image).hexdigest(),
                         protected_partitions_unchanged=list(install.PROTECTED))
            record.write_text(json.dumps(valid))
            expected = hashlib.sha256(image + original[len(image):]).hexdigest()
            self.assertEqual(install.expected_installed_boot_hash(root, record, boot), expected)
            for field, value in [('target', 'SM-G965N'), ('state', 'writing_userdata'),
                                 ('boot_sha256', 'bad'), ('protected_partitions_unchanged', [])]:
                record.write_text(json.dumps(dict(valid, **{field: value})))
                with self.assertRaises(ValueError):
                    install.expected_installed_boot_hash(root, record, boot)
            record.write_text(json.dumps(dict(valid, boot_partition_sha256='c' * 64)))
            self.assertEqual(install.expected_installed_boot_hash(root, record, boot), 'c' * 64)

    def test_prior_boot_trial_requires_matching_identity_and_complete_readback(self):
        backup = dict(bootloader='G955NKSU5DZE1', partitions={'BOOT': {'sha256': 'a' * 64}})
        self.assertEqual(install.expected_boot_hash(backup), 'a' * 64)
        valid = dict(target='SM-G955N', bootloader=backup['bootloader'],
                     state='boot_only_readback_verified_not_booted',
                     userdata_written=False, boot_partition_sha256='b' * 64)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trial.json'
            path.write_text(json.dumps(valid))
            self.assertEqual(install.expected_boot_hash(backup, path), 'b' * 64)
            for field, value in [('target', 'SM-G965N'), ('bootloader', 'G955F'),
                                 ('state', 'preflight_passed'), ('userdata_written', True),
                                 ('boot_partition_sha256', 'truncated')]:
                path.write_text(json.dumps(dict(valid, **{field: value})))
                with self.assertRaises(ValueError):
                    install.expected_boot_hash(backup, path)

    def test_dd_stderr_and_interrupted_backups_rejected(self):
        good = bytes(4096)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'BOOT.img'
            expected = hashlib.sha256(good).hexdigest()
            for data in (good + b'1+0 records in\n', good[:-1], b'x' + good[1:]):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    install.verify_backup(path, len(good), expected)
            path.write_bytes(good)
            install.verify_backup(path, len(good), expected)

    def test_wrong_model_rootfs_rejected_before_any_device_access(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'wrong.img'
            data = bytearray(1024 * 1024)
            data[1080:1082] = b'\x53\xef'
            data[1144:1155] = b's9plus-root'
            path.write_bytes(data)
            with self.assertRaises(ValueError):
                install.verify_rootfs_header(path)

    def test_non_boot_payload_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'wrong.img'
            path.write_bytes(b'not a boot image')
            with self.assertRaises(ValueError):
                install.verify_boot(path)
