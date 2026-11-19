#!/usr/bin/python3
"""Observe active G955N X11 damage without pixels/input or framebuffer ownership.

Presenter API: m = DamageMonitor(); dirty = m.poll(); m.ready; m.close().
reconnect() asynchronously rechecks the active GNOME process display/auth.
Advanced observer API: XDamageMonitor.poll(timeout) returns event dictionaries.
Xlib runs in a disposable worker: a server I/O error cannot exit the presenter.
"""
import argparse
import ctypes as C
import ctypes.util
from dataclasses import dataclass
import json
import os
from pathlib import Path
import platform
import pwd
import select
import signal
import subprocess
import sys
import time


@dataclass(frozen=True)
class Session:
    pid: int
    uid: int
    display: str
    authority: str
    start_time: str
    authority_inode: int
    authority_mtime: int


def _native():
    if ('SM-G955N' not in Path('/proc/device-tree/model').read_text()
            or 'g955n-ubuntu' not in platform.release()):
        raise RuntimeError('Requires the native SM-G955N Ubuntu image')


def find_session():
    """Read only GNOME-shell's selected environment keys, never cookie contents."""
    candidates = []
    allowed = {pwd.getpwnam(name).pw_uid for name in ('ubuntu', 'gdm')}
    for directory in Path('/proc').glob('[0-9]*'):
        try:
            if (directory / 'comm').read_text().strip() != 'gnome-shell':
                continue
            uid = int((directory / 'status').read_text().split('Uid:')[1].split()[0])
            if uid not in allowed or (os.geteuid() != 0 and uid != os.geteuid()):
                continue
            env = {}
            for entry in (directory / 'environ').read_bytes().split(b'\0'):
                key, sep, value = entry.partition(b'=')
                if sep and key in (b'DISPLAY', b'XAUTHORITY', b'XDG_SESSION_ID'):
                    env[key.decode()] = value.decode()
            display = env.get('DISPLAY', '')
            if not display.startswith(':') or not display[1:].replace('.', '').isdigit():
                continue
            authority = Path(env.get('XAUTHORITY', ''))
            if not authority.is_absolute() or authority.parent != Path(f'/run/user/{uid}/gdm'):
                continue
            metadata = authority.stat()
            if not authority.is_file() or metadata.st_uid not in (0, uid):
                continue
            stat = (directory / 'stat').read_text()
            fields = stat[stat.rindex(')') + 2:].split()
            if fields[0] == 'Z':
                continue
            active = None
            sid = env.get('XDG_SESSION_ID')
            if sid and all(c.isalnum() or c in '_-' for c in sid):
                query = subprocess.run(['loginctl', 'show-session', sid, '-p', 'Active', '--value'],
                                       capture_output=True, text=True, timeout=2)
                if query.returncode == 0:
                    active = query.stdout.strip() == 'yes'
            if active is False:
                continue
            session = Session(int(directory.name), uid, display, str(authority), fields[19],
                              metadata.st_ino, metadata.st_mtime_ns)
            candidates.append(((active is True, uid == pwd.getpwnam('ubuntu').pw_uid), session))
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            continue
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


class XDamageMonitor:
    """Nonblocking supervisor. Owns only its observer worker and X connection."""
    def __init__(self, refresh_seconds=1.0):
        _native()
        self.refresh_seconds = max(0.5, refresh_seconds)
        self.session = None
        self.process = None
        self._buffer = bytearray()
        self._stderr = bytearray()
        self._events = []
        self._refresh_at = 0.0
        self._missing = False
        self._closed = False

    def _stop(self):
        process, self.process = self.process, None
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        for stream in (process.stdout, process.stderr):
            stream.close()
        self._buffer.clear()
        self._stderr.clear()

    def reconnect(self, force=False):
        """Re-discover DISPLAY/auth from the active process, not guessed :0/:1."""
        if self._closed:
            return
        self._refresh_at = time.monotonic() + self.refresh_seconds
        session = find_session()
        alive = self.process is not None and self.process.poll() is None
        if not force and session == self.session and alive:
            return
        if self.session is not None and session != self.session:
            self._events.append({'event': 'failed', 'reason': 'Active X11 session changed'})
        self._stop()
        self.session = session
        if session is None:
            if not self._missing:
                self._events.append({'event': 'failed', 'reason': 'No active GNOME X11 session'})
            self._missing = True
            return
        self._missing = False
        command = [sys.executable, str(Path(__file__).resolve()), '--worker',
                   '--display', session.display, '--authority', session.authority,
                   '--uid', str(session.uid)]
        self.process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for stream in (self.process.stdout, self.process.stderr):
            os.set_blocking(stream.fileno(), False)

    def poll(self, timeout=0.0):
        """Return queued ready/damaged/failed events; timeout zero never waits."""
        if self._closed:
            return []
        if time.monotonic() >= self._refresh_at:
            self.reconnect()
        process = self.process
        if process is not None:
            readable, _, _ = select.select([process.stdout, process.stderr], [], [], max(0, timeout))
            for stream in readable:
                try:
                    data = os.read(stream.fileno(), 65536)
                except BlockingIOError:
                    continue
                if stream is process.stderr:
                    self._stderr.extend(data)
                    del self._stderr[:-4096]
                else:
                    self._buffer.extend(data)
                    while b'\n' in self._buffer:
                        line, _, rest = self._buffer.partition(b'\n')
                        self._buffer[:] = rest
                        try:
                            self._events.append(json.loads(line))
                        except (ValueError, UnicodeError):
                            self._events.append({'event': 'failed', 'reason': 'Invalid worker message'})
            status = process.poll()
            if status is not None:
                self._events.append({'event': 'failed', 'reason': 'X worker exited',
                                     'exit': status, 'stderr': self._stderr.decode(errors='replace')})
                self._stop()
                self._refresh_at = time.monotonic() + self.refresh_seconds
        elif timeout > 0:
            # Retry/session lookup lives in this supervisor, never spin while
            # waiting for an X server. The presenter uses a separate pipe.
            time.sleep(min(timeout, max(0.0, self._refresh_at - time.monotonic())))
        result, self._events = self._events, []
        return result

    def close(self):
        self._closed = True
        self._stop()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class DamageMonitor:
    """Presenter API: poll() is nonblocking and returns only newly dirty state.

    Session lookup/loginctl/Xlib live outside the presentation process. ready,
    last_events and counts expose status; failures return False and clear ready.
    """
    def __init__(self):
        _native()
        self.ready = False
        self.last_events = []
        self.counts = {'ready': 0, 'damaged': 0, 'subsequent': 0, 'failed': 0}
        self._process = None
        self._buffer = bytearray()
        self._stderr = bytearray()
        self._retry_at = 0.0
        self._closed = False

    def _start(self):
        self._process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), '--supervise'],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True)
        for stream in (self._process.stdout, self._process.stderr):
            os.set_blocking(stream.fileno(), False)

    def poll(self):
        self.last_events = []
        if self._closed:
            return False
        if self._process is None and time.monotonic() >= self._retry_at:
            try:
                self._start()
            except OSError as error:
                self._retry_at = time.monotonic() + 1
                self.last_events.append({'event': 'failed', 'reason': str(error)})
        process = self._process
        if process is not None:
            readable, _, _ = select.select([process.stdout, process.stderr], [], [], 0)
            for stream in readable:
                try:
                    data = os.read(stream.fileno(), 65536)
                except BlockingIOError:
                    continue
                if stream is process.stderr:
                    self._stderr.extend(data)
                    del self._stderr[:-4096]
                else:
                    self._buffer.extend(data)
                    while b'\n' in self._buffer:
                        line, _, rest = self._buffer.partition(b'\n')
                        self._buffer[:] = rest
                        try:
                            self.last_events.append(json.loads(line))
                        except (ValueError, UnicodeError):
                            self.last_events.append({'event': 'failed', 'reason': 'Invalid supervisor message'})
            status = process.poll()
            if status is not None:
                self.last_events.append({'event': 'failed', 'reason': 'Supervisor exited',
                                         'exit': status, 'stderr': self._stderr.decode(errors='replace')})
                # Its worker shares this separate process group. Never signal
                # the presenter's own group, framebuffer owner or X server.
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                for stream in (process.stdout, process.stderr):
                    stream.close()
                self._process = None
                self._buffer.clear()
                self._stderr.clear()
                self._retry_at = time.monotonic() + 1
        dirty = False
        for event in self.last_events:
            kind = event.get('event')
            if kind in self.counts:
                self.counts[kind] += 1
            if kind == 'ready':
                self.ready = True
            elif kind == 'failed':
                self.ready = False
            elif kind == 'damaged':
                dirty = True
                if not event.get('initial'):
                    self.counts['subsequent'] += 1
        return dirty and self.ready

    def reconnect(self):
        """Request asynchronous actual-session rediscovery; never guess display."""
        self.ready = False
        if self._process is not None and self._process.poll() is None:
            self._process.send_signal(signal.SIGHUP)
        else:
            self._retry_at = 0.0

    def close(self):
        self._closed = True
        self.ready = False
        process, self._process = self._process, None
        if process is None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=1)
        except ProcessLookupError:
            process.wait(timeout=1)
        finally:
            for stream in (process.stdout, process.stderr):
                stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class Rectangle(C.Structure):
    _fields_ = [('x', C.c_short), ('y', C.c_short), ('width', C.c_ushort), ('height', C.c_ushort)]


class DamageEvent(C.Structure):
    _fields_ = [('type', C.c_int), ('serial', C.c_ulong), ('send_event', C.c_int),
                ('display', C.c_void_p), ('drawable', C.c_ulong), ('damage', C.c_ulong),
                ('level', C.c_int), ('more', C.c_int), ('timestamp', C.c_ulong),
                ('area', Rectangle), ('geometry', Rectangle)]


class XEvent(C.Union):
    _fields_ = [('type', C.c_int), ('damage', DamageEvent), ('pad', C.c_long * 24)]


def _emit(event):
    print(json.dumps(event), flush=True)


def _worker(display, authority, uid):
    _native()
    if os.geteuid() == 0 and uid != 0:
        account = pwd.getpwuid(uid)
        os.setgroups([])
        os.setgid(account.pw_gid)
        os.setuid(uid)
    elif uid != os.geteuid():
        raise RuntimeError('Cannot change observer identity')
    os.environ['DISPLAY'], os.environ['XAUTHORITY'] = display, authority
    x = C.CDLL(ctypes.util.find_library('X11'))
    damage = C.CDLL(ctypes.util.find_library('Xdamage'))
    declarations = [
        (x, 'XOpenDisplay', [C.c_char_p], C.c_void_p),
        (x, 'XDefaultRootWindow', [C.c_void_p], C.c_ulong),
        (x, 'XConnectionNumber', [C.c_void_p], C.c_int),
        (x, 'XPending', [C.c_void_p], C.c_int),
        (x, 'XNextEvent', [C.c_void_p, C.POINTER(XEvent)], C.c_int),
        (x, 'XSync', [C.c_void_p, C.c_int], C.c_int),
        (x, 'XFlush', [C.c_void_p], C.c_int),
        (x, 'XCloseDisplay', [C.c_void_p], C.c_int),
        (damage, 'XDamageQueryExtension', [C.c_void_p, C.POINTER(C.c_int), C.POINTER(C.c_int)], C.c_int),
        (damage, 'XDamageCreate', [C.c_void_p, C.c_ulong, C.c_int], C.c_ulong),
        (damage, 'XDamageSubtract', [C.c_void_p, C.c_ulong, C.c_ulong, C.c_ulong], None),
        (damage, 'XDamageDestroy', [C.c_void_p, C.c_ulong], None),
    ]
    for lib, name, arguments, result in declarations:
        function = getattr(lib, name)
        function.argtypes, function.restype = arguments, result
    handle = x.XOpenDisplay(display.encode())
    if not handle:
        raise RuntimeError('XOpenDisplay failed')
    observer = 0
    running = True
    def stop(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        event_base, error_base = C.c_int(), C.c_int()
        if not damage.XDamageQueryExtension(handle, C.byref(event_base), C.byref(error_base)):
            raise RuntimeError('DAMAGE extension unavailable')
        root = x.XDefaultRootWindow(handle)
        observer = damage.XDamageCreate(handle, root, 3)  # XDamageReportNonEmpty
        if not observer:
            raise RuntimeError('XDamageCreate failed')
        x.XSync(handle, 0)
        _emit({'event': 'ready', 'display': display, 'uid': uid, 'worker_pid': os.getpid(),
               'drawable': root, 'damage': observer})
        event, count = XEvent(), 0
        while running:
            if not x.XPending(handle):
                select.select([x.XConnectionNumber(handle)], [], [], 0.2)
            while running and x.XPending(handle):
                x.XNextEvent(handle, C.byref(event))
                if event.type != event_base.value or event.damage.damage != observer:
                    continue
                count += 1
                e = event.damage
                _emit({'event': 'damaged', 'sequence': count, 'initial': count == 1,
                       'monotonic': time.monotonic(), 'server_ms': int(e.timestamp),
                       'area': [e.area.x, e.area.y, e.area.width, e.area.height],
                       'more': bool(e.more)})
                damage.XDamageSubtract(handle, observer, 0, 0)
                x.XFlush(handle)
    finally:
        if observer:
            damage.XDamageDestroy(handle, observer)
        x.XCloseDisplay(handle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=float, default=15)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--supervise', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--display', help=argparse.SUPPRESS)
    parser.add_argument('--authority', help=argparse.SUPPRESS)
    parser.add_argument('--uid', type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        try:
            _worker(args.display, args.authority, args.uid)
            return 0
        except Exception as error:
            _emit({'event': 'failed', 'reason': str(error)})
            return 1
    if args.supervise:
        running, reconnect = True, False
        def stop(*_):
            nonlocal running
            running = False
        def reload_session(*_):
            nonlocal reconnect
            reconnect = True
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGHUP, reload_session)
        with XDamageMonitor() as monitor:
            while running:
                if reconnect:
                    monitor.reconnect(force=True)
                    reconnect = False
                for event in monitor.poll(0.1):
                    _emit(event)
        return 0
    if not 0 < args.duration <= 300:
        parser.error('duration must be 0..300 seconds')
    counts = {'ready': 0, 'damaged': 0, 'subsequent': 0, 'failed': 0}
    start = time.monotonic()
    with XDamageMonitor() as monitor:
        while time.monotonic() - start < args.duration:
            for event in monitor.poll(0.1):
                counts[event['event']] += 1
                if event['event'] == 'damaged' and not event['initial']:
                    counts['subsequent'] += 1
                _emit(event)
    _emit({'event': 'summary', 'seconds': time.monotonic() - start, **counts})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
