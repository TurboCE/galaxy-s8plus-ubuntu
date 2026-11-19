#!/usr/bin/env python3
"""Measure normal GNOME/X11 window motion and device CPU on the SM-G955N."""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import time


def cpu():
    fields = Path('/proc/stat').read_text().splitlines()[0].split()[1:9]
    return list(map(int, fields))


def measure(fixture, env, runner):
    before = cpu()
    start = time.monotonic()
    output = subprocess.check_output([*runner, fixture, '--run'], env=env, text=True, timeout=15)
    duration = time.monotonic() - start
    after = cpu()
    ticks = [b - a for a, b in zip(before, after)]
    rows = [tuple(map(int, line.split(','))) for line in output.splitlines()]
    if len(rows) != 180:
        raise RuntimeError('Incomplete motion fixture output')
    changes = [row[0] for prev, row in zip(rows, rows[1:]) if row[2:] != prev[2:]]
    gaps = [b - a for a, b in zip(changes, changes[1:])]
    return {
        'whole_cpu_busy_percent': round(100 * (1 - (ticks[3] + ticks[4]) / sum(ticks)), 2),
        'seconds_including_setup': round(duration, 3),
        'requested_positions': len(rows),
        'observed_window_position_changes': len(changes),
        'median_window_update_gap_ms': statistics.median(gaps) if gaps else None,
        'p95_window_update_gap_ms': statistics.quantiles(gaps, n=20, method='inclusive')[18] if len(gaps) > 1 else None,
        'longest_window_update_gap_ms': max(gaps, default=None),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() or b'SM-G955N' not in Path('/proc/device-tree/model').read_bytes():
        raise RuntimeError('Run as root on the selected SM-G955N')
    shells = []
    for entry in Path('/proc').glob('[0-9]*'):
        try:
            if entry.stat().st_uid == 1000 and (entry / 'comm').read_text().strip() == 'gnome-shell':
                shells.append(entry)
        except (FileNotFoundError, ProcessLookupError):
            continue
    if len(shells) != 1:
        raise RuntimeError('Expected a single logged-in GNOME desktop')
    env = dict(item.split('=', 1) for item in (shells[0] / 'environ').read_bytes().decode().split('\0') if '=' in item)
    if env.get('XDG_SESSION_DESKTOP') != 'ubuntu-g955n' or env.get('XDG_SESSION_TYPE') != 'x11':
        raise RuntimeError('Expected the normal GNOME X11 session')
    runner = ['setpriv', '--reuid=1000', '--regid=1000', '--init-groups', '--no-new-privs']
    def require_visible():
        state = subprocess.check_output([*runner, 'gdbus', 'call', '--session',
            '--dest', 'org.gnome.ScreenSaver', '--object-path', '/org/gnome/ScreenSaver',
            '--method', 'org.gnome.ScreenSaver.GetActive'], env=env, text=True, timeout=5)
        panel = Path('/sys/class/graphics/fb0/device/power/runtime_status').read_text().strip()
        if state.strip() != '(false,)' or panel != 'active':
            raise RuntimeError('Unlock the GNOME desktop and keep the panel on')
    def status():
        return [Path(name).read_text().strip() for name in
                ('/proc/sys/kernel/random/boot_id', '/proc/sys/kernel/tainted')]
    modifier = subprocess.check_output([*runner, 'gsettings', 'get',
        'org.gnome.desktop.wm.preferences', 'mouse-button-modifier'],
        env=env, text=True, timeout=5).strip()
    if modifier != "'<Super>'":
        raise RuntimeError('Fixture requires the GNOME Super mouse modifier')
    before = status()
    require_visible()
    trials = [measure(str(args.fixture.resolve(strict=True)), env, runner) for _ in range(3)]
    require_visible()
    if before != status() or before[1] != '0':
        raise RuntimeError('Kernel health or boot identity changed during measurement')
    print(json.dumps({'scope': 'synthetic X11 drag, window geometry only; no panel FPS',
                      'trials': trials}, indent=2))


if __name__ == '__main__':
    main()
