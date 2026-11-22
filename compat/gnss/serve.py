#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Relay receiver NMEA to the connected GeoClue client."""
import os
from pathlib import Path
import select
import signal
import socket
import stat
import subprocess

from lto import read_cache
from run_probe import ENGINE, MODEL, STOCK_CONFIG, check_vendor, make_config


def stop(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=4)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def relay(peer, stream, engine, client):
    pending = bytearray()
    while engine.poll() is None and client.poll() is None:
        readable, writable, _ = select.select([peer, stream], [peer] if pending else [], [], 1)
        if peer in readable:
            # The GeoClue NMEA Unix stream is receive-only.
            return
        if stream in readable:
            data = os.read(stream.fileno(), 8192)
            if not data or len(pending) + len(data) > 65536:
                return
            pending.extend(data)
        if peer in writable:
            try:
                del pending[:peer.send(pending)]
            except BlockingIOError:
                continue


def main():
    if os.geteuid() or b'SM-G955N' not in MODEL.read_bytes():
        raise SystemExit('Requires root on the SM-G955N')
    check_vendor()

    def stopped(*_):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stopped)
    signal.signal(signal.SIGINT, stopped)
    # gpsd and the already-running Broadcom hub must open the same IPC inode.
    # A separate bind-mounted cache creates a second FIFO with the same name.
    state = Path('/data/vendor/gps')
    fifo = state / '.pipe.gpsd_to_lhd.to_server'
    if state.is_symlink() or state.stat().st_uid != 0 or not stat.S_ISFIFO(fifo.lstat().st_mode):
        raise SystemExit('The verified location hub does not own its GNSS FIFO')
    scratch = Path(os.environ['RUNTIME_DIRECTORY'])
    (scratch / 'lto').mkdir(exist_ok=True)
    config = scratch / 'gps.xml'
    config.write_text(make_config(STOCK_CONFIG.read_text(), scratch,
                                  lto_directory=Path('/data/vendor/gps/lto')))
    Path('/data/vendor/gps/lto').mkdir(mode=0o700, exist_ok=True)
    env = os.environ.copy()
    seed = Path('/var/lib/g955n-gnss-assist/seed')
    if seed.is_file():
        env['G955N_GNSS_SEED'] = str(seed)
    lto = read_cache()
    if lto:
        path = scratch / 'lto.dat'
        path.write_bytes(lto)
        env['G955N_GNSS_LTO'] = str(path)
    try:
        sync = subprocess.check_output(['timedatectl', 'show', '-p', 'NTPSynchronized', '--value'],
                                       text=True, timeout=3)
        if sync.strip() == 'yes':
            env['G955N_GNSS_SYNCED_CLOCK'] = '1'
    except (OSError, subprocess.SubprocessError):
        pass

    with socket.socket(fileno=0) as peer:
        peer.setblocking(False)
        engine = subprocess.Popen([str(ENGINE), '-c', str(config)], stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            # Give the vendor process its usual time to create the shared FIFOs.
            if select.select([peer], [], [], 2)[0] or engine.poll() is not None:
                return
            read_fd, write_fd = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
            with os.fdopen(read_fd, 'rb', buffering=0) as stream:
                try:
                    client = subprocess.Popen(['/usr/local/lib/g955n-gnss/hal-probe', '--serve'],
                                              env=env, stdin=subprocess.DEVNULL, stdout=write_fd)
                finally:
                    os.close(write_fd)
                try:
                    relay(peer, stream, engine, client)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    stop(client)
        finally:
            stop(engine)


if __name__ == '__main__':
    main()
