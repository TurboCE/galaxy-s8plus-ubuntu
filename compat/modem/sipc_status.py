#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Bounded SIPC status queries. No RF enable, SIM PIN, NV write or payload log.

Wire-format/command reference (not a supported G955N backend): LineageOS
libsamsung-ipc6d244414f7c66b0d0f93ef4b34f5276023408016 include/protocol.h,
gen.h, pwr.h and sec.h. That reference's device list does not support this handset.
This implementation is independent; it reads fragmented kernel IPC streams,
validates lengths and correlates replies before exposing a known status.
"""
import os
import select
import struct
import time

FMT = struct.Struct('<HBBBBB')
RFS = struct.Struct('<IBB')
RFS_OPEN = struct.Struct('<II')
RFS_PATH_LIMIT = 1024
# Linux/Bionic open flags in the stock ARM64 vendor protocol.
RFS_WRITE_OPEN_FLAGS = 0x40 | 0x200 | 0x400 | 0x400000
GEN_RESULT = struct.Struct('<BBBH')
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


def status_payload(command, payload):
    if command == 0x0107 and len(payload) == 1:
        return {'power': {1: 'low-power', 2: 'normal'}.get(payload[0], 'unknown')}
    if command == 0x0501 and len(payload) == 2:
        return {'sim': {0: 'ready', 0x80: 'not-present', 0x81: 'card-error',
                        0x82: 'initialization-complete', 1: 'locked'}.get(payload[0], 'unknown')}
    return None


def reply_status(fields, payload, pending):
    _, _, sequence, group, index, kind = fields
    command = group << 8 | index
    if kind == 2 and pending.get(sequence) == command:
        return status_payload(command, payload)
    return None


def query_acknowledgement(fields, payload, pending):
    _, _, sequence, group, index, kind = fields
    if (group, index, kind) != (0x80, 0x01, 2) or len(payload) != GEN_RESULT.size:
        return None
    request_group, request_index, request_kind, code = GEN_RESULT.unpack(payload)
    command = request_group << 8 | request_index
    name = {0x0107: 'power', 0x0501: 'sim'}.get(command)
    if not name or request_kind != 2 or pending.get(sequence) != command:
        return None
    return name, code


def rfs_open_access(payload):
    """Classify stock G955N opcode 0x11 without opening or disclosing the path."""
    if len(payload) < RFS_OPEN.size:
        return 'invalid'
    flags, path_size = RFS_OPEN.unpack_from(payload)
    access = flags & 3
    if access == 3 or not 0 < path_size <= RFS_PATH_LIMIT or path_size != len(payload) - RFS_OPEN.size:
        return 'invalid'
    if access or flags & RFS_WRITE_OPEN_FLAGS:
        return 'may-write'
    return 'read-only'


def observe(fmt_fd, rfs_fd, seconds=5, query=False, progress=lambda step: None):
    readers = {fmt_fd: Frames(FMT), rfs_fd: Frames(RFS)}
    poll = select.poll()
    for fd in readers:
        poll.register(fd, select.POLLIN | select.POLLHUP | select.POLLERR)
    result = {'fmt_frames': 0, 'rfs_frames': 0, 'power_up_notification': False,
              'queries_sent': False, 'replies': {}, 'commands': {},
              'query_acknowledgements': {}, 'status_notifications': {}, 'rfs_commands': {},
              'rfs_open_access': {}, 'rfs_requests_answered': False}
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
                    ack = query_acknowledgement(fields, payload, pending)
                    if ack:
                        name, code = ack
                        result['query_acknowledgements'][name] = code
                    if fields[-1] == 3:
                        notification = status_payload(command, payload)
                        if notification:
                            for key, value in notification.items():
                                counts = result['status_notifications'].setdefault(key, {})
                                counts[value] = counts.get(value, 0) + 1
                else:
                    result['rfs_frames'] += 1
                    command = f'{fields[1]:02x}'
                    counts = result['rfs_commands']
                    counts[command] = counts.get(command, 0) + 1
                    if fields[1] == 0x11:
                        access = rfs_open_access(payload)
                        counts = result['rfs_open_access']
                        counts[access] = counts.get(access, 0) + 1
    result['incomplete_bytes'] = sum(len(r.pending) for r in readers.values())
    progress('status-observation-completed')
    return result
