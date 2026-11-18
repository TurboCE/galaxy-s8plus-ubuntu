#!/usr/bin/env python3
"""Explicit, bounded native G955N speaker-route diagnostic.

Temporarily routes one RDMA frontend to the existing UAIF4/MAX98506 backend.
Captures PCM progress and IRQ snapshots, then restores every touched control.
No microphone capture, firmware writes or calibration changes are performed.
PCM completion alone does not establish that sound was physically audible.
"""
import argparse
import array
import json
import math
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import time
import wave


def read_text(path):
    try:
        return Path(path).read_text(errors='replace')
    except OSError as error:
        return f'unavailable: {error}'


def mixer(name, value=None):
    command = ['amixer', '-c', '0', 'cget' if value is None else 'cset',
               'name=' + name]
    if value is not None:
        command.append(value)
    return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT,
                                   timeout=8)


def interrupt(_signal, _frame):
    raise KeyboardInterrupt('Speaker diagnostic interrupted; restoring controls')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--initialize-speaker', action='store_true',
                        help='Explicitly permit temporary mixer/PCM changes')
    parser.add_argument('--rdma', type=int, choices=(0, 1, 2, 3, 6, 7), default=0)
    parser.add_argument('--mmap', action='store_true', help='Use aplay --mmap')
    parser.add_argument('--seconds', type=float, default=2)
    parser.add_argument('--output-dir', type=Path, required=True,
                        help='New private /var/tmp/g955n-audio-* directory')
    args = parser.parse_args()
    if not args.initialize_speaker or not 0.25 <= args.seconds <= 3:
        parser.error('Explicit --initialize-speaker and 0.25..3 seconds required')
    if (os.geteuid() != 0 or 'g955n-ubuntu' not in platform.release()
            or 'SM-G955N' not in Path('/proc/device-tree/model').read_text()):
        raise SystemExit('Requires root on the native SM-G955N Ubuntu kernel')
    if 'Exynos8895-Madera' not in read_text('/proc/asound/cards'):
        raise SystemExit('Unexpected ALSA card; no controls changed')
    destination = args.output_dir.absolute()
    if (destination.parent != Path('/var/tmp')
            or not destination.name.startswith('g955n-audio-')
            or destination.exists() or destination.is_symlink()):
        raise SystemExit('Use a new /var/tmp/g955n-audio-* evidence directory')
    status_dir = Path(f'/proc/asound/card0/pcm{args.rdma}p/sub0')
    pcm_list = read_text('/proc/asound/pcm')
    if not re.search(rf'^00-{args.rdma:02d}:.*playback', pcm_list, re.M):
        raise SystemExit('Selected playback PCM is not registered; no controls changed')
    try:
        initial_status = (status_dir / 'status').read_text().strip()
    except FileNotFoundError:
        raise SystemExit(
            'Unsupported diagnostic: selected PCM is registered but its ALSA '
            'status node is absent. Enable CONFIG_SND_VERBOSE_PROCFS; '
            'no device opened or controls changed')
    except OSError as error:
        raise SystemExit(
            f'Cannot read ALSA PCM status: {error}; no controls changed')
    if initial_status != 'closed':
        state = re.search(r'^state:\s*(\S+)', initial_status, re.M)
        if state:
            raise SystemExit(
                f'Selected PCM is busy (state={state.group(1)}); no controls changed')
        raise SystemExit(
            'Unsupported diagnostic: unrecognized ALSA PCM status; '
            'no device opened or controls changed')
    os.umask(0o077)
    destination.mkdir(mode=0o700)
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    routes = [
        ('Speaker Gain', '1'),  # -6 dB; never use the stock high gain for a probe.
        ('ABOX Sampling Rate Out1', '48000'),
        (f'ABOX SPUS ASRC{args.rdma}', 'On'),
        ('ABOX ERAP info DSM On', '1'),
        ('ABOX NSRC3', 'UAIF4'),
        (f'ABOX SPUS OUT{args.rdma}', 'SIFS1'),
        ('ABOX SIFS1', f'SPUS OUT{args.rdma}'),
        ('ABOX UAIF SPK4', 'SIFS1'),
    ]
    report = dict(kernel=platform.release(), rdma=args.rdma,
                  access='mmap' if args.mmap else 'rw', seconds=args.seconds,
                  tone_hz=440, tone_peak_dbfs=-25, speaker_gain=-6,
                  physical_audio_verified=False, controls_restored=False)
    saved, observations = [], []
    child = None
    tone = destination / 'synthetic-tone.wav'
    started = time.monotonic()
    try:
        # Snapshot all controls before the first write so partial setup failures
        # can still be unwound with the original numeric enum values.
        original = {}
        for name, _ in routes:
            text = mixer(name)
            values = re.search(r'^\s*: values=([^\n]+)', text, re.M)
            if not values:
                raise RuntimeError('Cannot snapshot control: ' + name)
            original[name] = dict(value=values.group(1).strip(), description=text)
        (destination / 'controls-before.json').write_text(json.dumps(original, indent=2))
        (destination / 'interrupts-before.txt').write_text(read_text('/proc/interrupts'))
        for name, value in routes:
            saved.append((name, original[name]['value']))
            mixer(name, value)
        # Exactly -25 dBFS peak, stereo 48 kHz, with 50 ms fade in/out.
        frame_count = round(48000 * args.seconds)
        amplitude = 32767 * 10 ** (-25 / 20)
        samples = array.array('h')
        for index in range(frame_count):
            ramp = min(1, index / 2400, (frame_count - 1 - index) / 2400)
            sample = round(amplitude * ramp * math.sin(2 * math.pi * 440 * index / 48000))
            samples.extend((sample, sample))
        if samples.itemsize != 2:
            raise RuntimeError('Unexpected sample integer size')
        if os.sys.byteorder != 'little':
            samples.byteswap()
        with wave.open(str(tone), 'wb') as output:
            output.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
            output.writeframes(samples.tobytes())
        command = ['aplay', '--verbose', '--dump-hw-params', '-D',
                   f'hw:0,{args.rdma}']
        if args.mmap:
            command.append('--mmap')
        command.append(str(tone))
        report['command'] = command
        started = time.monotonic()
        with (destination / 'aplay.log').open('w') as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            with (destination / 'pcm-observations.jsonl').open('w') as evidence:
                while child.poll() is None:
                    snapshot = dict(seconds=round(time.monotonic() - started, 6),
                                    status=read_text(status_dir / 'status'),
                                    hw_params=read_text(status_dir / 'hw_params'),
                                    sw_params=read_text(status_dir / 'sw_params'))
                    observations.append(snapshot)
                    evidence.write(json.dumps(snapshot) + '\n')
                    evidence.flush()
                    if time.monotonic() - started > args.seconds + 4:
                        report['timed_out'] = True
                        break
                    time.sleep(0.02)
                if child.poll() is not None:
                    report['aplay_exit'] = child.returncode
    except (Exception, KeyboardInterrupt) as error:
        report['error'] = str(error)
    finally:
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=1)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=1)
            report['aplay_exit'] = child.returncode
        report['elapsed_seconds'] = round(time.monotonic() - started, 6)
        (destination / 'interrupts-after.txt').write_text(read_text('/proc/interrupts'))
        failures = []
        for name, value in reversed(saved):
            try:
                mixer(name, value)
                actual = re.search(r'^\s*: values=([^\n]+)', mixer(name), re.M)
                if actual is None or actual.group(1).strip() != value:
                    raise RuntimeError('Control readback differs from original value')
            except Exception as error:
                failures.append(dict(control=name, error=str(error)))
        report['restore_failures'] = failures
        report['controls_restored'] = not failures
        tone.unlink(missing_ok=True)
        pointer_values = []
        for observation in observations:
            match = re.search(r'^hw_ptr\s*:\s*(\d+)', observation['status'], re.M)
            if match:
                pointer_values.append(int(match.group(1)))
        report['status_observations'] = len(observations)
        report['distinct_hw_ptr_values'] = sorted(set(pointer_values))
        report['pcm_progress_observed'] = len(set(pointer_values)) > 1
        playback_log = read_text(destination / 'aplay.log')
        report['xrun_reported'] = bool(re.search('underrun|overrun', playback_log, re.I))
        report['pcm_completed'] = (report.get('aplay_exit') == 0
                                   and report['pcm_progress_observed']
                                   and not report['xrun_reported']
                                   and report['controls_restored'])
        (destination / 'result.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
    return 0 if report.get('pcm_completed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
