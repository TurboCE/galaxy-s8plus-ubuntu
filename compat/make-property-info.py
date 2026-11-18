#!/usr/bin/env python3
"""Build a minimal Android 9 serialized property-info file in staging only.

Format: pinned AOSP system/core property_service/libpropertyinfoparser and
libpropertyinfoserializer. One default context/type, with an empty root trie.
This contains metadata, no property values or invented service readiness.
"""
import argparse
from pathlib import Path
import struct


def property_info():
    data = bytearray(24)

    def append(raw):
        offset = len(data)
        data.extend(raw)
        data.extend(b'\0' * (-len(data) % 4))
        return offset

    def strings(value):
        table = append(struct.pack('<2I', 1, 0))
        string = append(value.encode('ascii') + b'\0')
        struct.pack_into('<I', data, table + 4, string)
        return table

    contexts = strings('u:object_r:default_prop:s0')
    types = strings('string')
    root = append(bytes(28))
    entry = append(bytes(16))
    name = append(b'root\0')
    struct.pack_into('<7I', data, root, entry, 0, 0, 0, 0, 0, 0)
    struct.pack_into('<4I', data, entry, name, 4, 0, 0)
    struct.pack_into('<6I', data, 0, 1, 1, len(data), contexts, types, root)
    return bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    path = args.output.resolve()
    if str(path).startswith(('/dev/', '/proc/', '/sys/', '/efs/')):
        raise SystemExit('Write a staging file, never a live device property area')
    with path.open('xb') as file:
        file.write(property_info())
    print('Created serialized property metadata:', path, path.stat().st_size, 'bytes')


if __name__ == '__main__':
    main()
