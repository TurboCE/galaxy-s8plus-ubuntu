#!/usr/bin/env python3
"""Suspend, wake, or ask to power off from the handset power key."""

import fcntl
from pathlib import Path
import pwd
import select
import struct
import subprocess
import sys
import time


INPUT_EVENT = struct.Struct('@llHHi')
EVIOCSCLOCKID = 0x400445A0
POWER_KEY = (1, 116)  # EV_KEY, KEY_POWER
LONG_PRESS = 1.4
GPIO_KEYS = '/dev/input/by-path/platform-gpio_keys-event'
PANEL_RUNTIME = Path('/sys/class/graphics/fb0/device/power/runtime_status')
SLEEP_MARKER = Path('/run/g955n-display-suspend')
MUTTER = 'org.gnome.Mutter.DisplayConfig'
MUTTER_PATH = '/org/gnome/Mutter/DisplayConfig'
LOGIND_SUSPEND = ('/usr/bin/busctl', '--system', 'call',
                  'org.freedesktop.login1', '/org/freedesktop/login1',
                  'org.freedesktop.login1.Manager', 'Suspend', 'b', 'false')


def read_command(*args, timeout=3):
    return subprocess.check_output(args, text=True, timeout=timeout).strip()


def active_session():
    session = read_command('/usr/bin/loginctl', 'show-seat', 'seat0',
                           '-p', 'ActiveSession', '--value')
    if not session:
        return
    details = dict(line.split('=', 1) for line in read_command(
        '/usr/bin/loginctl', 'show-session', session, '-p', 'Active',
        '-p', 'Remote', '-p', 'Type', '-p', 'User').splitlines())
    if (details.get('Active') != 'yes' or details.get('Remote') != 'no'
            or details.get('Type') not in ('x11', 'wayland')):
        return
    user = pwd.getpwuid(int(details['User']))
    if user.pw_uid == 0:
        return
    bus = Path(f'/run/user/{user.pw_uid}/bus')
    if not bus.is_socket():
        return
    run = ['/usr/sbin/runuser', '-u', user.pw_name, '--', '/usr/bin/env',
           'XDG_RUNTIME_DIR=' + str(bus.parent),
           'DBUS_SESSION_BUS_ADDRESS=unix:path=' + str(bus)]
    return session, details['Type'], run


def display_environment(run, keys):
    return [line for line in read_command(*run, '/usr/bin/systemctl', '--user',
                'show-environment').splitlines()
            if line.partition('=')[0] in keys]


def wake_display(session):
    _, session_type, run = session
    if session_type == 'x11':
        # Mutter's property does not drive DPMS on the native X11 server.
        env = display_environment(run, ('DISPLAY', 'XAUTHORITY'))
        if not any(value.startswith('DISPLAY=') for value in env):
            return
        # A brief resume press can be lost before X sees it. Reset idle time
        # without changing the screen lock, then turn the panel on.
        read_command(*run, *env, '/usr/bin/xset', 's', 'reset')
        read_command(*run, *env, '/usr/bin/xset', 'dpms', 'force', 'on')
    else:
        read_command(*run, '/usr/bin/busctl', '--user', 'set-property',
                     MUTTER, MUTTER_PATH, MUTTER, 'PowerSaveMode', 'i', '0')
    print('Power key requested display wake', flush=True)


def session_locked(session):
    return read_command('/usr/bin/loginctl', 'show-session', session[0],
                        '-p', 'LockedHint', '--value') == 'yes'


def lock_before_sleep(session):
    run = session[2]
    if (read_command(*run, '/usr/bin/gsettings', 'get',
                     'org.gnome.desktop.screensaver', 'ubuntu-lock-on-suspend') != 'true'
            or read_command(*run, '/usr/bin/gsettings', 'get',
                            'org.gnome.desktop.lockdown', 'disable-lock-screen') == 'true'):
        return
    # ScreenSaver.GetActive describes the shield/blanking state, not whether
    # credentials are required. In particular it may be false while locked.
    if session_locked(session):
        return
    read_command('/usr/bin/loginctl', 'lock-session', session[0])
    deadline = time.monotonic() + 3
    while not session_locked(session):
        if time.monotonic() >= deadline:
            raise RuntimeError('Screen lock did not complete; suspend was not requested')
        time.sleep(.05)


def suspend_session(session):
    _, session_type, run = session
    # Root's direct systemctl path can bypass logind's PrepareForSleep and its
    # desktop delay inhibitors. Finish the configured lock while rendering is
    # available, before our explicit blanking barrier.
    try:
        lock_before_sleep(session)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        wake_display(session)
        raise
    if session_type == 'x11':
        # Blank while the graphical session can still process X requests.
        # systemd's later sleep hooks run with user sessions frozen.
        env = display_environment(run, ('DISPLAY', 'XAUTHORITY'))
        if not any(value.startswith('DISPLAY=') for value in env):
            raise RuntimeError('No active display to blank before suspend')
        read_command(*run, *env, '/usr/bin/xset', 'dpms', 'force', 'off')
    else:
        read_command(*run, '/usr/bin/busctl', '--user', 'set-property',
                     MUTTER, MUTTER_PATH, MUTTER, 'PowerSaveMode', 'i', '3')
    deadline = time.monotonic() + 2
    while panel_is_on():
        if time.monotonic() >= deadline:
            wake_display(session)
            raise RuntimeError('Panel did not blank; suspend was not requested')
        time.sleep(.05)
    try:
        read_command(*LOGIND_SUSPEND, timeout=10)
    except (OSError, subprocess.SubprocessError):
        wake_display(session)
        raise


def open_power_dialog(session):
    _, _, run = session
    wake_display(session)
    env = display_environment(run, ('DISPLAY', 'XAUTHORITY', 'WAYLAND_DISPLAY'))
    dialog = subprocess.Popen([
        *run, *env, '/usr/bin/zenity', '--question', '--modal', '--default-cancel',
        '--title=Power Off', '--text=Turn off this phone?',
        '--ok-label=Power Off', '--cancel-label=Cancel',
    ])
    print('Power key opened shutdown confirmation', flush=True)
    return dialog


def panel_is_on():
    return PANEL_RUNTIME.read_text().strip() == 'active'


def is_resume_press(pressed_at):
    try:
        marker = SLEEP_MARKER.read_text().strip()
    except FileNotFoundError:
        return False
    if marker == 'sleeping':
        state = read_command('/usr/bin/systemctl', 'show', 'systemd-suspend.service',
                             '-p', 'ActiveState', '--value')
        return state not in ('inactive', 'failed')
    # A key can have been queued during resume and delivered later.
    return pressed_at <= float(marker) + 1.5


def main():
    if b'SM-G955N' not in Path('/proc/device-tree/model').read_bytes():
        raise SystemExit('Unexpected device model')
    if sys.argv[1:] == ['--wake']:
        if session := active_session():
            wake_display(session)
        return
    # A normal read shares the device with the compositor and logind.
    with open(GPIO_KEYS, 'rb', buffering=0) as key:
        fcntl.ioctl(key, EVIOCSCLOCKID, struct.pack('@i', time.CLOCK_BOOTTIME))
        watch_keys(key)


def watch_keys(key):
    was_on = panel_is_on()
    press = None
    pending_dialog = None
    dialog_seat = None
    while True:
        if pending_dialog is not None and pending_dialog.poll() is not None:
            result = pending_dialog.returncode
            pending_dialog = None
            try:
                if result == 0 and (session := active_session()) and session[0] == dialog_seat:
                    read_command('/usr/bin/systemctl', 'poweroff')
            except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
                print(f'Confirmed shutdown unavailable ({type(error).__name__})', flush=True)
        if not select.select([key], [], [], 0.2)[0]:
            # X can wake DPMS as soon as it receives a key. Save the earlier
            # hardware state before waiting for the physical key event.
            was_on = panel_is_on()
            if press is not None:
                _, pressed_at = press
                if time.clock_gettime(time.CLOCK_BOOTTIME) - pressed_at >= LONG_PRESS:
                    press = None
                    try:
                        if pending_dialog is None and (session := active_session()):
                            if not is_resume_press(pressed_at):
                                pending_dialog = open_power_dialog(session)
                                dialog_seat = session[0]
                            else:
                                wake_display(session)
                    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
                        print(f'Power dialog unavailable ({type(error).__name__})', flush=True)
            continue
        event = key.read(INPUT_EVENT.size)
        if not event:
            return
        sec, usec, kind, code, value = INPUT_EVENT.unpack(event)
        if (kind, code) != POWER_KEY:
            continue
        if value == 1:
            press = (was_on, sec + usec / 1_000_000)
        elif value == 0 and press is not None:
            before, pressed_at = press
            press = None
            try:
                if pending_dialog is not None or not (session := active_session()):
                    continue
                if is_resume_press(pressed_at):
                    wake_display(session)
                elif sec + usec / 1_000_000 - pressed_at >= LONG_PRESS:
                    pending_dialog = open_power_dialog(session)
                    dialog_seat = session[0]
                elif before:
                    print('Power key requested system suspend', flush=True)
                    suspend_session(session)
                else:
                    wake_display(session)
            except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
                print(f'Power key action unavailable ({type(error).__name__})', flush=True)


if __name__ == '__main__':
    main()
