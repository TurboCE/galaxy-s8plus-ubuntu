#!/usr/bin/env python3
"""Hold the tested SM-G955N native-desktop MIF floor until process exit.

This is an explicit stability mitigation, not a corruption root-cause fix.
The kernel owns the request by file descriptor, including SIGKILL cleanup.
No frequency table, driver minimum or calibration data is modified.
"""
import argparse
import fcntl
import os
from pathlib import Path
import signal
import socket
import stat
import struct
import time

FREQUENCY_KHZ = 421000
MIF = Path('/sys/class/devfreq/17000010.devfreq_mif')


def notify(message):
    address = os.environ.get('NOTIFY_SOCKET')
    if not address:
        return
    if address.startswith('@'):
        address = '\0' + address[1:]
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as channel:
        channel.connect(address)
        channel.sendall(message.encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hold', action='store_true')
    args = parser.parse_args()
    if not args.hold:
        parser.error('explicit --hold required; merely running this file changes nothing')
    if os.geteuid() != 0:
        raise RuntimeError('Root required for the selected device QoS request')
    model = Path('/proc/device-tree/model').read_bytes().rstrip(b'\0')
    if not model.startswith(b'Samsung SM-G955N '):
        raise RuntimeError('Only the reviewed SM-G955N profile is supported')
    if str(FREQUENCY_KHZ) not in (MIF / 'available_frequencies').read_text().split():
        raise RuntimeError('Tested operating point unavailable')
    node = Path('/dev/bus_throughput')
    info = node.stat()
    if not stat.S_ISCHR(info.st_mode):
        raise RuntimeError('Expected kernel PM QoS character device')
    identity = Path('/sys/dev/char', f'{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}', 'uevent')
    if 'DEVNAME=bus_throughput' not in identity.read_text().splitlines():
        raise RuntimeError('Unexpected QoS device identity')
    # A process-local lease avoids duplicate service/manual owners. SIGKILL
    # closes both the lock and the kernel QoS file automatically.
    with open('/run/g955n-desktop-mif-qos.lock', 'a') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        stopped = False

        def stop(_signum, _frame):
            nonlocal stopped
            stopped = True

        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, stop)
        fd = os.open(node, os.O_RDWR | os.O_CLOEXEC)
        try:
            if os.write(fd, struct.pack('<i', FREQUENCY_KHZ)) != 4:
                raise RuntimeError('Incomplete QoS request')
            aggregate = struct.unpack('<i', os.read(fd, 4))[0]
            if aggregate < FREQUENCY_KHZ:
                raise RuntimeError('Kernel did not accept the requested minimum')
            notify('READY=1\nSTATUS=Holding tested native-desktop MIF stability floor')
            while not stopped:
                # Finite wait avoids a signal arriving between the flag test
                # and pause and leaving systemd waiting for its stop timeout.
                time.sleep(0.25)
        finally:
            os.close(fd)
            notify('STOPPING=1\nSTATUS=Released this process MIF QoS request')


if __name__ == '__main__':
    main()
