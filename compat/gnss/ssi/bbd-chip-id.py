#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read the Samsung SSP chip ID through the SM-G955N BCM4773 transport."""

import argparse
import errno
import json
import os
import select
import struct
import time

ESC = 0xB0
START = 0
END = 1
ESCAPED = {3: ESC, 4: 0x11, 5: 0x13}
ESCAPE_CODES = {value: key for key, value in ESCAPED.items()}
SENSOR_REQUEST = 32
SENSOR_RESPONSE = 33
WHOAMI = 0x0F
EXPECTED_ID = 0x55
MAX_FRAME = 2048 + 14
DEVICE = "/dev/g955n-bcm4773-ssi"


def checksum(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ (0x4D if crc & 0x80 else 0)) & 0xFF
    return ((crc << 4) | (crc >> 4)) & 0xFF


def frame(sequence, payload):
    header = bytes((len(payload), 0))
    body = bytes((sequence,)) + header + payload + bytes((checksum(header + payload),))
    wire = bytearray((ESC, START))
    for byte in body:
        if byte in ESCAPE_CODES:
            wire.extend((ESC, ESCAPE_CODES[byte]))
        else:
            wire.append(byte)
    wire.extend((ESC, END))
    return bytes(wire)


def chip_id_request():
    request = struct.pack("<BHHI", WHOAMI, 1, 0, 0)
    rpc = bytes((SENSOR_REQUEST, len(request) + 2)) + struct.pack("<H", len(request)) + request
    return frame(1, rpc)


class Frames:
    def __init__(self):
        self.body = None
        self.escaped = False
        self.invalid = 0

    def feed(self, data):
        for byte in data:
            if byte in (0x11, 0x13):
                continue
            if self.escaped:
                self.escaped = False
                if byte == START:
                    self.body = bytearray()
                elif byte == END and self.body is not None:
                    body = self.body
                    self.body = None
                    if len(body) >= 4 and checksum(body[1:-1]) == body[-1]:
                        yield body[:-1]
                    else:
                        self.invalid += 1
                elif byte in ESCAPED and self.body is not None:
                    self.body.append(ESCAPED[byte])
                else:
                    self.body = None
                    self.escaped = byte == ESC
            elif byte == ESC:
                self.escaped = True
            elif self.body is not None:
                self.body.append(byte)
            if self.body is not None and len(self.body) > MAX_FRAME:
                self.body = None
                self.invalid += 1


def payload(body):
    size = body[1]
    flags = body[2]
    pos = 3
    for bit in range(16):
        if not flags & (1 << bit):
            continue
        if pos >= len(body) or bit > 9:
            return None
        detail = body[pos]
        pos += 1
        if bit == 6:
            size |= detail << 8
        elif bit == 7:
            flags |= detail << 8
    if flags & (1 << 8) or size != len(body) - pos:
        return None
    return body[pos:]


def rpc_number(data, pos):
    value = data[pos]
    pos += 1
    if value & 0x80:
        value = ((value & 0x7F) << 8) | data[pos]
        pos += 1
    return value, pos


def chip_id_reply(body):
    data = payload(body)
    if data is None:
        return None
    pos = 0
    match = None
    while pos < len(data):
        try:
            kind, start = rpc_number(data, pos)
            size, start = rpc_number(data, start)
        except IndexError:
            return None
        pos = start + size
        if pos > len(data):
            return None
        if kind != SENSOR_RESPONSE or size != 7:
            continue
        inner_size, options, count, reply = struct.unpack_from("<HHHB", data, start)
        if (inner_size, options, count) == (5, 0, 1):
            if match is not None:
                return None
            match = reply
    return match


def probe(seconds):
    parser = Frames()
    request = chip_id_request()
    sent = received = frames = 0
    deadline = time.monotonic() + seconds
    fd = os.open(DEVICE, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        watcher = select.poll()
        while time.monotonic() < deadline:
            events = select.POLLIN | (select.POLLOUT if sent < len(request) else 0)
            watcher.register(fd, events)
            timeout = max(0, round((deadline - time.monotonic()) * 1000))
            for _, ready in watcher.poll(timeout):
                if ready & (select.POLLERR | select.POLLHUP | select.POLLNVAL):
                    raise OSError(errno.EIO, "SSI endpoint stopped")
                if ready & select.POLLIN:
                    try:
                        data = os.read(fd, 254)
                    except OSError as error:
                        if error.errno not in (errno.EAGAIN, errno.ENODATA):
                            raise
                        time.sleep(0.01)
                        continue
                    received += len(data)
                    for body in parser.feed(data):
                        frames += 1
                        reply = chip_id_reply(body)
                        if reply is not None and sent == len(request):
                            return result(sent, received, frames, parser, reply)
                if ready & select.POLLOUT and sent < len(request):
                    try:
                        sent += os.write(fd, request[sent:])
                    except BlockingIOError:
                        continue
    finally:
        os.close(fd)
    return result(sent, received, frames, parser, None)


def result(sent, received, frames, parser, reply):
    return dict(bytes_sent=sent, bytes_received=received, valid_frames=frames,
                invalid_frames=parser.invalid, ssp_chip_id=reply)


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--seconds", type=int, choices=range(1, 16), default=3)
    outcome = probe(args.parse_args().seconds)
    print(json.dumps(outcome))
    return 0 if outcome["ssp_chip_id"] == EXPECTED_ID else 1


if __name__ == "__main__":
    raise SystemExit(main())
