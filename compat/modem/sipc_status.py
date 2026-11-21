#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Bounded SIPC status queries. No RF enable, SIM PIN, NV write or payload log.

Wire-format/command reference (not a supported G955N backend): LineageOS
libsamsung-ipc6d244414f7c66b0d0f93ef4b34f5276023408016 include/protocol.h,
pwr.h and sec.h. That reference's device list does not support this handset.
This implementation is independent; it reads fragmented kernel IPC streams,
validates lengths and correlates replies before exposing a known status.
"""
import os
import select
import struct
import time

FMT = struct.Struct('<HBBBBB')
RFS = struct.Struct('<IBB')
MAX_FRAME = 1024 * 1024 + 16


class Frames:
    def __init__(self, header):
        self.header = header
        self.pending = bytearray()

    def feed(self, data):
        self.pending.extend(data)
        frames = []
        while len(self.pending) >= self.header.size:
            fields = self.header.unpack_from(self.pending)
            length = fields[0]
            if length < self.header.size or length > MAX_FRAME:
                raise ValueError('Invalid SIPC frame length')
            if len(self.pending) < length:
                break
            frames.append((fields, bytes(self.pending[self.header.size:length])))
            del self.pending[:length]
        if len(self.pending) > MAX_FRAME:
            raise ValueError('Unbounded SIPC receive stream')
        return frames


def request(command, sequence):
    if command not in (0x0107, 0x0501) or not 1 <= sequence <= 254:
        raise ValueError('Only read-only power/SIM status queries are implemented')
    return FMT.pack(FMT.size, sequence, 0xff, command >> 8, command & 255, 2)


def reply_status(fields, payload, pending):
    _, mseq, aseq, group, index, kind = fields
    command = group << 8 | index
    # A notification is not an answer to a submitted query.
    if kind != 2 or pending.get(aseq) != command:
        return None
    if command == 0x0107 and len(payload) == 1:
        return {'power': {1: 'low-power', 2: 'normal'}.get(payload[0], 'unknown')}
    if command == 0x0501 and len(payload) == 2:
        return {'sim': {0: 'ready', 0x80: 'not-present', 0x81: 'card-error',
                        0x82: 'initialization-complete', 1: 'locked'}.get(payload[0], 'unknown')}
    return None


def observe(fmt_fd, rfs_fd, seconds=5, query=False, progress=lambda step: None):
    readers = {fmt_fd: Frames(FMT), rfs_fd: Frames(RFS)}
    poll = select.poll()
    for fd in readers:
        poll.register(fd, select.POLLIN | select.POLLHUP | select.POLLERR)
    result = {'fmt_frames': 0, 'rfs_frames': 0, 'power_up_notification': False,
              'queries_sent': False, 'replies': {}, 'commands': {},
              'rfs_requests_answered': False}
    pending = {}
    progress('status-receiver-ready')
    deadline = time.monotonic() + seconds
    query_at = time.monotonic() + min(1, seconds / 2)
    while time.monotonic() < deadline:
        # Validate a real FMT packet before sending even read-only GETs.
        if query and not result['queries_sent'] and result['fmt_frames'] and time.monotonic() >= query_at:
            for seq, command in enumerate((0x0107, 0x0501), 1):
                packet = request(command, seq)
                step = 'power-get' if command == 0x0107 else 'sim-get'
                progress('status-send-' + step)
                if os.write(fmt_fd, packet) != len(packet):
                    raise OSError('Incomplete SIPC status request')
                pending[seq] = command
                progress('status-sent-' + step)
            result['queries_sent'] = True
        for fd, events in poll.poll(100):
            if events & (select.POLLHUP | select.POLLERR | select.POLLNVAL):
                raise OSError('CP status endpoint disconnected')
            data = os.read(fd, 65536)
            if not data:
                continue
            for fields, payload in readers[fd].feed(data):
                if fd == fmt_fd:
                    if fields[-1] not in (1, 2, 3):
                        raise ValueError('Unknown SIPC message type')
                    result['fmt_frames'] += 1
                    if result['fmt_frames'] == 1:
                        progress('status-first-fmt-frame')
                    command = fields[3] << 8 | fields[4]
                    name = f'{command:04x}'
                    result['commands'][name] = result['commands'].get(name, 0) + 1
                    result['power_up_notification'] |= command == 0x0101 and fields[-1] == 3
                    status = reply_status(fields, payload, pending)
                    if status:
                        result['replies'].update(status)
                        del pending[fields[2]]
                else:
                    result['rfs_frames'] += 1
    result['incomplete_bytes'] = sum(len(r.pending) for r in readers.values())
    progress('status-observation-completed')
    return result
