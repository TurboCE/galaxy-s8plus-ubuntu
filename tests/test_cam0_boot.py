"""Exercise the BOOT preflight for the SM-G955N CAM0 ownership conflict."""

from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from boot.mkdtbh import FDT_BEGIN_NODE, FDT_END_NODE, FDT_PROP, FDT_END, FDT_MAGIC
from boot.verify_cam0 import verify_cam0_ownership


def cells(*values):
    return struct.pack('>' + 'I' * len(values), *values)


def tree(video_status=None, *, parent_status=None):
    strings = bytearray()

    def prop(name, value):
        offset = len(strings)
        strings.extend(name.encode() + b'\0')
        return cells(FDT_PROP, len(value), offset) + value + bytes(-len(value) % 4)

    def node(name, *entries):
        raw = name.encode() + b'\0'
        return cells(FDT_BEGIN_NODE) + raw + bytes(-len(raw) % 4) + b''.join(entries) + cells(FDT_END_NODE)

    parent = [] if parent_status is None else [prop('status', parent_status)]
    video = [] if video_status is None else [prop('status', video_status)]
    nodes = node('', prop('compatible', b'samsung,dream2lteks\0'),
                 node('soc@0',
                      node('iommu@12d10000', prop('phandle', cells(4)), prop('#iommu-cells', cells(0))),
                      node('other-iommu', prop('phandle', cells(5)), prop('#iommu-cells', cells(1))),
                      node('csis1-buffer-test', prop('iommus', cells(4))),
                      node('camera', *parent,
                           node('csis@12cb0000', *video, prop('iommus', cells(5, 4, 4)))))) + cells(FDT_END)
    offset = 40 + 16  # header plus the empty reservation table
    return (cells(FDT_MAGIC, offset + len(nodes) + len(strings), offset, offset + len(nodes),
                  40, 17, 16, 0, len(strings), len(nodes)) + bytes(16) + nodes + strings)


class Cam0BootTests(unittest.TestCase):
    def test_rejects_two_enabled_consumers_in_embedded_tree(self):
        payload = b'code' + cells(FDT_MAGIC, 20) + b'\0' * 48 + tree() + b'ramdisk'
        with self.assertRaisesRegex(ValueError, 'CAM0 has multiple enabled consumers'):
            verify_cam0_ownership(payload)

    def test_allows_disabled_consumer_or_ancestor(self):
        verify_cam0_ownership(tree(video_status=b'disabled\0'))
        verify_cam0_ownership(tree(parent_status=b'disabled\0'))
