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
LOCK_TIMEOUT = 5
LOCK_RETRY_INTERVAL = 1
GPIO_KEYS = (
    Path('/dev/input/by-path/platform-gpio-keys-event'),
    Path('/dev/input/by-path/platform-gpio_keys-event'),
)
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
    SLEEP_MARKER.unlink(missing_ok=True)
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
    started = time.monotonic()
    next_request = started + LOCK_RETRY_INTERVAL
    deadline = started + LOCK_TIMEOUT
    while not session_locked(session):
        now = time.monotonic()
        if now >= deadline:
            raise RuntimeError('Screen lock did not complete; suspend was not requested')
        if now >= next_request:
            # A lock signal can arrive before the new GNOME session listens
            # to logind. Repeat it while waiting for that session to confirm.
            read_command('/usr/bin/loginctl', 'lock-session', session[0])
            next_request = now + LOCK_RETRY_INTERVAL
        time.sleep(.05)


def suspend_session(session):
    _, session_type, run = session
    # Root's direct systemctl path can bypass logind's PrepareForSleep and its
    # desktop delay inhibitors. Finish the configured lock while rendering is
    # available, before our explicit blanking barrier.
    try:
        lock_before_sleep(session)
        if session_type == 'x11':
            # Blank before systemd freezes the graphical session.
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
                raise RuntimeError('Panel did not blank; suspend was not requested')
            time.sleep(.05)
        read_command(*LOGIND_SUSPEND, timeout=10)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        try:
            wake_display(session)
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            print(f'Could not restore the display after failed suspend ({type(error).__name__})',
                  flush=True)
        raise


def open_power_dialog(session):
    _, _, run = session
    wake_display(session)
    env = display_environment(run, (
        'DISPLAY', 'XAUTHORITY', 'WAYLAND_DISPLAY', 'GSK_RENDERER',
    ))
    dialog = subprocess.Popen([
        *run, *env, '/usr/bin/zenity', '--question', '--modal', '--default-cancel',
        '--title=Power Off', '--text=Turn off this phone?',
        '--ok-label=Power Off', '--cancel-label=Cancel',
    ])
    print('Power key opened shutdown confirmation', flush=True)
    return dialog


def panel_state():
    for connector in Path('/sys/class/drm').glob('card*-DSI-1'):
        if (connector / 'device/device/driver').resolve().name == 'g955n-decon-handoff':
            return connector / 'enabled', 'enabled'
    return PANEL_RUNTIME, 'active'


def panel_is_on():
    path, on_value = panel_state()
    return path.read_text().strip() == on_value


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


def should_suspend(session, panel_was_on):
    if not panel_was_on:
        return False
    if session[1] == 'wayland' and SLEEP_MARKER.is_file():
        # The DRM connector may already be enabled after resume while GNOME's
        # lock screen remains blank. The first short press should request wake.
        return not session_locked(session)
    return True


def main():
    if b'SM-G955N' not in Path('/proc/device-tree/model').read_bytes():
        raise SystemExit('Unexpected device model')
    if sys.argv[1:] == ['--wake']:
        if session := active_session():
            wake_display(session)
        return
    # A normal read shares the device with the compositor and logind.
    device = next((path for path in GPIO_KEYS if path.is_char_device()), None)
    if device is None:
        raise SystemExit('Power key input device is unavailable')
    with device.open('rb', buffering=0) as key:
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
                elif should_suspend(session, before):
                    print('Power key requested system suspend', flush=True)
                    suspend_session(session)
                else:
                    wake_display(session)
            except RuntimeError as error:
                print(f'Power key action unavailable: {error}', flush=True)
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
                print(f'Power key action unavailable ({type(error).__name__})', flush=True)


if __name__ == '__main__':
    main()
