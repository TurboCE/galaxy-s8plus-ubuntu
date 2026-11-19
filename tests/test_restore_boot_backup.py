import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from restore_boot_backup import verify_working_boot


class RestoreBootGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.raw = cls.root / 'BOOT-working.img'
        cls.prefix = b'known-reviewed-normal-boot'
        with cls.raw.open('wb') as file:
            file.write(cls.prefix)
            file.truncate(41943040)
        with cls.raw.open('rb') as file:
            cls.raw_hash = hashlib.file_digest(file, 'sha256').hexdigest()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.image = self.root / 'normal.img'
        self.image.write_bytes(self.prefix)
        self.meta = self.image.with_suffix('.json')
        self.meta.write_text(json.dumps(dict(target='SM-G955N', kernel_trial=False, image_sha256=hashlib.sha256(self.prefix).hexdigest())))
        self.manifest = self.root / 'working.json'
        self.record = dict(target='SM-G955N', verified=True, bytes=41943040, working_boot_sha256=self.raw_hash)
        self.manifest.write_text(json.dumps(self.record))
        # Android image parsing/hash/footer already has separate tests. Isolate
        # these rollback-specific raw-partition/provenance guards here.
        self.check = patch('restore_boot_backup.verify_boot')
        self.check.start()
        self.addCleanup(self.check.stop)

    def validate(self, raw=None):
        return verify_working_boot(raw or self.raw, self.manifest, self.image)

    def test_exact_full_backup_matches_normal_reference(self):
        record, meta = self.validate()
        self.assertEqual(record['working_boot_sha256'], self.raw_hash)
        self.assertFalse(meta['kernel_trial'])

    def test_wrong_target_rejected(self):
        self.record['target'] = 'SM-G965N'
        self.manifest.write_text(json.dumps(self.record))
        with self.assertRaises(ValueError): self.validate()

    def test_truncated_partition_rejected(self):
        truncated = self.root / 'truncated.img'
        with truncated.open('wb') as file: file.truncate(41943039)
        with self.assertRaises(ValueError): self.validate(truncated)

    def test_wrong_full_hash_rejected(self):
        self.record['working_boot_sha256'] = '0' * 64
        self.manifest.write_text(json.dumps(self.record))
        with self.assertRaises(ValueError): self.validate()

    def test_different_reference_prefix_rejected(self):
        self.image.write_bytes(b'a-different-reference')
        self.meta.write_text(json.dumps(dict(target='SM-G955N', kernel_trial=False,
            image_sha256=hashlib.sha256(self.image.read_bytes()).hexdigest())))
        with self.assertRaises(ValueError): self.validate()

    def test_wrong_reference_metadata_hash_rejected(self):
        self.meta.write_text(json.dumps(dict(target='SM-G955N', kernel_trial=False, image_sha256='0'*64)))
        with self.assertRaises(ValueError): self.validate()

    def test_initramfs_only_reference_rejected(self):
        self.meta.write_text(json.dumps(dict(target='SM-G955N', kernel_trial=True)))
        with self.assertRaises(ValueError): self.validate()


if __name__ == '__main__': unittest.main()
