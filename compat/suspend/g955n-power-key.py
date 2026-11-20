#!/usr/bin/env python3
"""Wake the active GNOME display when the handset power key is pressed."""

from pathlib import Path
import pwd
import struct
import subprocess
import sys


INPUT_EVENT = struct.Struct('@llHHi')
POWER_PRESS = (1, 116, 1)  # EV_KEY, KEY_POWER, press (no release or autorepeat)
GPIO_KEYS = '/dev/input/by-path/platform-gpio_keys-event'
MUTTER = 'org.gnome.Mutter.DisplayConfig'
MUTTER_PATH = '/org/gnome/Mutter/DisplayConfig'


def read_command(*args):
    return subprocess.check_output(args, text=True, timeout=3).strip()


def wake_display():
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
    # Use the session's normal privileges. Waking the display leaves its lock in effect.
    run = ['/usr/sbin/runuser', '-u', user.pw_name, '--', '/usr/bin/env',
           'DBUS_SESSION_BUS_ADDRESS=unix:path=' + str(bus)]
    if details['Type'] == 'x11':
        # Mutter's property does not drive DPMS on the native X11 server.
        env = [line for line in read_command(*run, '/usr/bin/systemctl', '--user',
                   'show-environment').splitlines()
               if line.startswith(('DISPLAY=', 'XAUTHORITY='))]
        if not any(value.startswith('DISPLAY=') for value in env):
            return
        read_command(*run, *env, '/usr/bin/xset', 'dpms', 'force', 'on')
    else:
        read_command(*run, '/usr/bin/busctl', '--user', 'set-property',
                     MUTTER, MUTTER_PATH, MUTTER, 'PowerSaveMode', 'i', '0')
    print('Power key requested display wake', flush=True)


def main():
    if b'SM-G955N' not in Path('/proc/device-tree/model').read_bytes():
        raise SystemExit('Unexpected device model')
    if sys.argv[1:] == ['--wake']:
        wake_display()
        return
    # A normal read shares the device with the compositor and logind.
    with open(GPIO_KEYS, 'rb', buffering=0) as key:
        watch_keys(key)


def watch_keys(key):
    while event := key.read(INPUT_EVENT.size):
        if INPUT_EVENT.unpack(event)[2:] == POWER_PRESS:
            try:
                wake_display()
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
                print(f'Display wake unavailable ({type(error).__name__})', flush=True)


if __name__ == '__main__':
    main()
