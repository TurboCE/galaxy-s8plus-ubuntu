import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('install', Path(__file__).resolve().parents[1] / 'scripts/install_ubuntu.py')
install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install)


class InstallGuards(unittest.TestCase):
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
