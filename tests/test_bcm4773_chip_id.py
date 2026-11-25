import importlib.util
import struct
import unittest
from pathlib import Path

source = Path(__file__).resolve().parents[1] / "compat/gnss/ssi/bbd-chip-id.py"
spec = importlib.util.spec_from_file_location("bbd_chip_id", source)
bbd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bbd)


class BbdChipIdTests(unittest.TestCase):
    def test_request_header(self):
        body, = bbd.Frames().feed(bbd.chip_id_request())
        self.assertEqual(bbd.payload(body), bytes.fromhex("20 0b 09 00 0f 01 00 00 00 00 00 00 00"))

    def test_sensor_reply_across_split_escaped_frames(self):
        reply = bytes((33, 7)) + struct.pack("<HHHB", 5, 0, 1, 0x55)
        wire = bbd.frame(0xB0, reply)
        parser = bbd.Frames()
        self.assertEqual(list(parser.feed(wire[:3])), [])
        body, = parser.feed(wire[3:])
        self.assertEqual(bbd.chip_id_reply(body), 0x55)

    def test_rejects_truncation_and_wrong_response_size(self):
        for payload in (b"\xa1", b"\x21\x07\x05\x00", b"\x21\x07\x04\x00\x00\x00\x01\x00\x55"):
            with self.subTest(payload=payload):
                body, = bbd.Frames().feed(bbd.frame(4, payload))
                self.assertIsNone(bbd.chip_id_reply(body))

    def test_matches_only_a_single_well_formed_reply(self):
        reply = bytes((33, 7)) + struct.pack("<HHHB", 5, 0, 1, 0x55)
        for payload in (reply + reply, reply + b"\xa1"):
            with self.subTest(payload=payload):
                body, = bbd.Frames().feed(bbd.frame(4, payload))
                self.assertIsNone(bbd.chip_id_reply(body))

    def test_rejects_invalid_crc(self):
        wire = bytearray(bbd.chip_id_request())
        wire[6] ^= 1
        parser = bbd.Frames()
        self.assertEqual(list(parser.feed(wire)), [])
        self.assertEqual(parser.invalid, 1)


if __name__ == "__main__":
    unittest.main()
