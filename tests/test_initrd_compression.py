import importlib.util
from pathlib import Path
import shutil
import subprocess
import unittest

spec = importlib.util.spec_from_file_location('pack', Path(__file__).resolve().parents[1] / 'scripts/pack_boot.py')
pack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pack)


class InitrdCompatibility(unittest.TestCase):
    @unittest.skipUnless(shutil.which('lz4'), 'lz4 command required')
    def test_lz4_only_kernel_gets_legacy_lz4_not_gzip(self):
        data = b'070701' + b'x' * 10000
        name, compressed = pack.compress_initramfs(data, 'CONFIG_RD_LZ4=y\n# CONFIG_RD_GZIP is not set\n')
        self.assertEqual(name, 'lz4-legacy')
        self.assertEqual(compressed[:4], b'\x02\x21\x4c\x18')
        result = subprocess.run(['lz4', '-d', '-c'], input=compressed, capture_output=True, check=True)
        self.assertEqual(result.stdout, data)

    def test_no_compatible_decoder_is_rejected(self):
        with self.assertRaises(ValueError):
            pack.compress_initramfs(b'payload', '# CONFIG_RD_GZIP is not set\n')
