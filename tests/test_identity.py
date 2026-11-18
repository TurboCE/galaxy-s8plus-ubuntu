import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('collector', Path(__file__).resolve().parents[1] / 'scripts/collect_device.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class IdentityGuard(unittest.TestCase):
    def test_target(self):
        self.assertTrue(collector.validate_identity({'ro.product.model': 'SM-G955N', 'ro.product.device': 'dream2lteks', 'ro.bootloader': 'G955NKSU5DZE1'}))

    def test_spoofed_model_or_other_phone(self):
        for device, bootloader in [('star2lteks', 'G965NKSU5FVA2'), ('dream2lteks', 'G955FXXU1'), ('dreamlteks', 'G950NKSU5')]:
            self.assertFalse(collector.validate_identity({'ro.product.model': 'SM-G955N', 'ro.product.device': device, 'ro.bootloader': bootloader}))

    def test_missing_identity(self):
        self.assertFalse(collector.validate_identity({}))
