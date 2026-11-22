#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Cache a recent coarse network estimate for the GNSS receiver."""
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib import error, request

from gi.repository import Gio, GLib

NM = 'org.freedesktop.NetworkManager'
MM = 'org.freedesktop.ModemManager1'
ENDPOINT = 'https://api.beacondb.net/v1/geolocate'


def location_enabled():
    # This port's desktop account owns the GNOME location preference.
    env = ['XDG_RUNTIME_DIR=/run/user/1000', 'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
    try:
        result = subprocess.run(['runuser', '-u', 'ubuntu', '--', 'env', *env,
                                 'gsettings', 'get', 'org.gnome.system.location', 'enabled'],
                                capture_output=True, text=True, timeout=3)
        return result.returncode == 0 and result.stdout.strip() == 'true'
    except (OSError, subprocess.SubprocessError):
        return False


def call(bus, dest, path, interface, method, parameters=None):
    return bus.call_sync(dest, path, interface, method, parameters, None,
                         Gio.DBusCallFlags.NONE, 2200, None).unpack()[0]


def wifi_points(bus):
    devices = call(bus, NM, '/org/freedesktop/NetworkManager', NM, 'GetDevices')
    candidates = {}
    for device in devices:
        try:
            paths = call(bus, NM, device, NM + '.Device.Wireless', 'GetAccessPoints')
        except GLib.Error:
            continue
        for path in paths[:48]:
            try:
                props = call(bus, NM, path, 'org.freedesktop.DBus.Properties', 'GetAll',
                             GLib.Variant('(s)', (NM + '.AccessPoint',)))
            except GLib.Error:
                continue
            address = props.get('HwAddress', '')
            ssid = bytes(props.get('Ssid', []))
            if (not ssid or ssid.endswith(b'_nomap') or not re.fullmatch(r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', address)
                    or int(address[:2], 16) & 3 or address == '00:00:00:00:00:00'):
                continue
            candidates[address.upper()] = props.get('Strength', 0)
    return [{'macAddress': address} for address in sorted(candidates, key=candidates.get, reverse=True)[:12]]


def cell_towers(bus):
    try:
        objects = call(bus, MM, '/org/freedesktop/ModemManager1',
                       'org.freedesktop.DBus.ObjectManager', 'GetManagedObjects')
        path = next(path for path, interfaces in objects.items() if MM + '.Modem' in interfaces)
        rows = call(bus, MM, path, MM + '.Modem', 'GetCellInfo')
    except (GLib.Error, StopIteration):
        return []
    cells = []
    for row in rows[:16]:
        operator = row.get('operator-id', '')
        if not re.fullmatch(r'[0-9]{5,6}', operator) or not all(key in row for key in ('tac', 'ci')):
            continue
        try:
            tac = int(str(row['tac']), 16)
            cell = int(str(row['ci']), 16)
        except ValueError:
            continue
        if 0 <= tac <= 65535 and 0 <= cell <= 0xFFFFFFF:
            cells.append({'radioType': 'lte', 'mobileCountryCode': int(operator[:3]),
                          'mobileNetworkCode': int(operator[3:]), 'locationAreaCode': tac, 'cellId': cell})
    return cells


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise error.URLError('unexpected location service redirect')


def lookup(payload):
    query = request.Request(ENDPOINT, data=json.dumps(payload).encode(),
                            headers={'Content-Type': 'application/json',
                                     'User-Agent': 'SM-G955N Ubuntu GNSS assistance/1.0'})
    with request.build_opener(NoRedirect).open(query, timeout=4) as response:
        body = response.read(8193)
    if len(body) > 8192:
        return
    value = json.loads(body)
    lat, lon, accuracy = value['location']['lat'], value['location']['lng'], value['accuracy']
    if all(type(v) in (float, int) and math.isfinite(v) for v in (lat, lon, accuracy)):
        if -90 <= lat <= 90 and -180 <= lon <= 180 and 1 <= accuracy <= 100000:
            return lat, lon, accuracy


def main():
    target = Path(os.environ['STATE_DIRECTORY']) / 'seed'
    if not location_enabled():
        target.unlink(missing_ok=True)
        return
    if target.is_file() and 0 <= time.time() - target.stat().st_mtime < 120:
        return
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM)
    try:
        wifi = wifi_points(bus)
    except GLib.Error:
        wifi = []
    cells = cell_towers(bus)
    payload = {'considerIp': True}
    if len(wifi) >= 2:
        payload['wifiAccessPoints'] = wifi
    if cells:
        payload['cellTowers'] = cells
    try:
        seed = lookup(payload)
    except (OSError, KeyError, TypeError, ValueError):
        seed = None
    if not seed or not location_enabled():
        print('GNSS coarse network seed unavailable')
        return
    with tempfile.NamedTemporaryFile(mode='w', dir=target.parent, delete=False) as output:
        temp = Path(output.name)
        try:
            line = ' '.join(str(value) for value in (*seed, time.time()))
            output.write(line + '\n')
            output.flush()
            os.fsync(output.fileno())
            temp.replace(target)
        finally:
            temp.unlink(missing_ok=True)
    print('GNSS coarse network seed cached')


if __name__ == '__main__':
    main()
