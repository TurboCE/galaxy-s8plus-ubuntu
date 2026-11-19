import importlib.util
from pathlib import Path
import struct
import unittest
spec=importlib.util.spec_from_file_location('pack_builtin',Path(__file__).resolve().parents[1]/'scripts/pack_boot.py')
pack=importlib.util.module_from_spec(spec);spec.loader.exec_module(pack)


def fixture(payload):
    image=bytearray(512);image[56:60]=b'ARMd';image[128:128+len(payload)]=payload
    struct.pack_into('<Q',image,256,len(payload))
    symbols='ffffff8008080000 T _text\nffffff8008080080 T __initramfs_start\nffffff8008080100 T __initramfs_size\n'
    return bytes(image),symbols


class BuiltinInitramfs(unittest.TestCase):
    def test_actual_bytes_override_lz4_filename_assumption(self):
        image,symbols=fixture(b'\x1f\x8b\x08'+bytes(12))
        with self.assertRaisesRegex(ValueError,'gzip'):
            pack.verify_builtin_initramfs(image,'CONFIG_RD_LZ4=y\nCONFIG_DECOMPRESS_LZ4=y\n',symbols)
    def test_legacy_lz4_with_decoder(self):
        image,symbols=fixture(b'\x02\x21\x4c\x18'+bytes(12))
        self.assertEqual(pack.verify_builtin_initramfs(image,'CONFIG_DECOMPRESS_LZ4=y',symbols)['codec'],'lz4-legacy')
    def test_gzip_requires_its_actual_decoder(self):
        image,symbols=fixture(b'\x1f\x8b\x08'+bytes(12))
        self.assertEqual(pack.verify_builtin_initramfs(image,'CONFIG_DECOMPRESS_GZIP=y',symbols)['codec'],'gzip')
    def test_modern_lz4_is_not_legacy(self):
        image,symbols=fixture(b'\x04\x22\x4d\x18'+bytes(12))
        with self.assertRaises(ValueError):pack.verify_builtin_initramfs(image,'CONFIG_DECOMPRESS_LZ4=y',symbols)
    def test_uncompressed_newc_needs_no_decompressor(self):
        image,symbols=fixture(b'070701'+bytes(10))
        self.assertEqual(pack.verify_builtin_initramfs(image,'',symbols)['codec'],'cpio-newc')
    def test_empty_builtin_is_valid(self):
        image,symbols=fixture(b'')
        self.assertEqual(pack.verify_builtin_initramfs(image,'',symbols)['codec'],'empty')
    def test_map_and_payload_bounds(self):
        image,symbols=fixture(b'070701')
        for bad in [symbols.replace('080080','090080'),symbols.replace('080100','080040'),symbols.replace('080080','07ffff')]:
            with self.assertRaises(ValueError):pack.verify_builtin_initramfs(image,'',bad)
        broken=bytearray(image);struct.pack_into('<Q',broken,256,2**63)
        with self.assertRaises(ValueError):pack.verify_builtin_initramfs(broken,'',symbols)
    def test_missing_or_duplicate_symbols_rejected(self):
        image,symbols=fixture(b'070701')
        for bad in ['',symbols+symbols.splitlines()[0]+'\n']:
            with self.assertRaises(ValueError):pack.verify_builtin_initramfs(image,'',bad)
    def test_non_arm64_image_rejected(self):
        image,symbols=fixture(b'070701');bad=bytearray(image);bad[56:60]=b'nope'
        with self.assertRaises(ValueError):pack.verify_builtin_initramfs(bad,'',symbols)


if __name__=='__main__':unittest.main()
