#!/usr/bin/env python3
"""Native G955N VIDIOC_QUERYCAP regression probe; does not start streaming."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import platform
import struct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('devices', nargs='+', help='Explicit /dev/videoN nodes to query')
    args = parser.parse_args()
    if ('SM-G955N' not in Path('/proc/device-tree/model').read_text()
            or 'g955n-ubuntu' not in platform.release()):
        raise SystemExit('Requires the native G955N Ubuntu kernel')
    for device in args.devices:
        path = Path(device)
        if path.parent != Path('/dev') or not path.name.startswith('video') or not path.name[5:].isdigit():
            raise SystemExit('Expected explicit /dev/videoN nodes')
    for device in args.devices:
        result = dict(device=device)
        try:
            fd = os.open(device, os.O_RDWR | os.O_NONBLOCK)
            try:
                cap = bytearray(104)
                fcntl.ioctl(fd, 0x80685600, cap, True)
                result.update(driver=cap[:16].split(b'\0')[0].decode(errors='replace'),
                              card=cap[16:48].split(b'\0')[0].decode(errors='replace'),
                              capabilities=hex(struct.unpack_from('I', cap, 84)[0]),
                              querycap='returned')
            finally:
                os.close(fd)
        except OSError as error:
            result.update(errno=error.errno, error=error.strerror)
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
