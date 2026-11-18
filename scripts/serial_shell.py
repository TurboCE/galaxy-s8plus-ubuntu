"""Framed shell transport for the explicitly selected G955N USB console.

No commands run on import. Callers must verify live kernel/DT identity before
device changes. This transport does not qualify hardware or image safety.
"""
import os
from pathlib import Path
import re
import select
import termios
import time
import tty
import uuid


class SerialShell:
    def __init__(self, port):
        if not Path(port).name.startswith('cu.usbmodemG955N_UBUNTU'):
            raise ValueError('Select the dedicated G955N USB serial port explicitly')
        self.fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        self.original = termios.tcgetattr(self.fd)
        tty.setraw(self.fd)

    def close(self):
        try:
            termios.tcsetattr(self.fd, termios.TCSANOW, self.original)
        finally:
            os.close(self.fd)

    def run(self, command, timeout=40):
        marker = 'G955N_' + uuid.uuid4().hex
        begin, end = marker + '_BEGIN', marker + '_END'
        wire = (f"\nprintf '\\n{begin}\\n'; ( {command} ) 2>&1; "
                f"g955n_rc=$?; printf '\\n{end}:%s\\n' \"$g955n_rc\"\n").encode()
        deadline = time.monotonic() + timeout
        offset, received = 0, bytearray()
        while time.monotonic() < deadline:
            readers, writers, _ = select.select([self.fd], [self.fd] if offset < len(wire) else [], [], 1)
            if writers:
                offset += os.write(self.fd, wire[offset:offset + 1024])
            if readers:
                chunk = os.read(self.fd, 65536)
                if not chunk:
                    break
                received.extend(chunk)
                text = received.decode(errors='replace').replace('\r', '')
                start = text.find('\n' + begin + '\n')
                match = re.search(r'\n' + end + r':(\d+)\n', text)
                if start >= 0 and match:
                    return dict(exit_code=int(match[1]),
                                stdout=text[start + len(begin) + 2:match.start()], stderr='')
        return dict(exit_code=124, stdout=received.decode(errors='replace'),
                    stderr='USB serial response did not complete; not a successful check')
