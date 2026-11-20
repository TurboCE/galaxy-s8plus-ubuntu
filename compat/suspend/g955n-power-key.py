#!/usr/bin/env python3
"""Toggle the active GNOME display with the handset power key."""

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
GPIO_KEYS = '/dev/input/by-path/platform-gpio_keys-event'
PANEL_RUNTIME = Path('/sys/class/graphics/fb0/device/power/runtime_status')
SLEEP_MARKER = Path('/run/g955n-display-suspend')
MUTTER = 'org.gnome.Mutter.DisplayConfig'
MUTTER_PATH = '/org/gnome/Mutter/DisplayConfig'


def read_command(*args):
    return subprocess.check_output(args, text=True, timeout=3).strip()


def set_display(on):
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
    # Use the session's normal privileges and preserve its lock state.
    run = ['/usr/sbin/runuser', '-u', user.pw_name, '--', '/usr/bin/env',
           'DBUS_SESSION_BUS_ADDRESS=unix:path=' + str(bus)]
    if details['Type'] == 'x11':
        # Mutter's property does not drive DPMS on the native X11 server.
        env = [line for line in read_command(*run, '/usr/bin/systemctl', '--user',
                   'show-environment').splitlines()
               if line.startswith(('DISPLAY=', 'XAUTHORITY='))]
        if not any(value.startswith('DISPLAY=') for value in env):
            return
        read_command(*run, *env, '/usr/bin/xset', 'dpms', 'force', 'on' if on else 'off')
    else:
        read_command(*run, '/usr/bin/busctl', '--user', 'set-property',
                     MUTTER, MUTTER_PATH, MUTTER, 'PowerSaveMode', 'i', '0' if on else '3')
    print('Power key requested display ' + ('wake' if on else 'blank'), flush=True)
    return True


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
        set_display(True)
        return
    # A normal read shares the device with the compositor and logind.
    with open(GPIO_KEYS, 'rb', buffering=0) as key:
        fcntl.ioctl(key, EVIOCSCLOCKID, struct.pack('@i', time.CLOCK_BOOTTIME))
        watch_keys(key)


def watch_keys(key):
    was_on = panel_is_on()
    press = None
    while True:
        if not select.select([key], [], [], 0.2)[0]:
            # X can wake DPMS as soon as it receives a key. Save the earlier
            # hardware state before waiting for the physical key event.
            was_on = panel_is_on()
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
                on = not before or is_resume_press(pressed_at)
                if not on:
                    # Let X process the release before blanking, so it cannot
                    # immediately turn the screen on again on that release.
                    time.sleep(0.15)
                if set_display(on):
                    was_on = on
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
                print(f'Display power change unavailable ({type(error).__name__})', flush=True)


if __name__ == '__main__':
    main()
