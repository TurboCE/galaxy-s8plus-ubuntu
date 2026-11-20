#!/usr/bin/env python3
"""Bounded native G955N WDMA1/main-microphone diagnostic.

Requires explicit initialization. Records at most three seconds into RAM only,
retains numeric signal/PCM diagnostics, and restores every touched mixer value.
The main microphone is duplicated into both ALSA channels; this is not proof of
stereo capture, acoustic response, intelligibility, or complete microphone HALs.
"""
import argparse
import array
import json
import math
import os
from pathlib import Path
import platform
import re
import select
import signal
import subprocess
import time


CAPTURE_DAPM = Path('/sys/kernel/debug/asoc/Exynos8895-Madera')
CAPTURE_WIDGETS = {
    'dapm': ('DMIC1',),
    'codec:cs47l92-codec/dapm': ('MICBIAS1A', 'IN3L PGA', 'LHPF1', 'ASRC1IN1L',
                                'AIF1TX1', 'AIF1TX2', 'AIF1 Capture'),
    'codec:13e50000.abox/dapm': ('ABOX UAIF0 Capture', 'ABOX NSRC0', 'ABOX SPUM ASRC1',
                               'ABOX SIFM0', 'ABOX WDMA1 Capture'),
}


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
    raise KeyboardInterrupt('Microphone diagnostic interrupted; restoring controls')


def signal_statistics(raw, channels):
    samples = array.array('h')
    channel = array.array('h')
    try:
        samples.frombytes(raw)
        if os.sys.byteorder != 'little':
            samples.byteswap()
        result = []
        for index in range(channels):
            channel = samples[index::channels]
            count = len(channel)
            if not count:
                result.append(dict(channel=index, samples=0, signal_detected=False))
                continue
            mean = sum(channel) / count
            mean_square = sum(value * value for value in channel) / count
            ac_rms = math.sqrt(max(0, mean_square - mean * mean))
            minimum, maximum = min(channel), max(channel)
            peak = max(abs(minimum), abs(maximum))
            distinct = len(set(channel))
            clipped = sum(abs(value) >= 32767 for value in channel)
            # Repeated short fixed patterns can be stale/uninitialized DMA, not
            # a live ADC. Do not accept those as a working microphone either.
            periodic = any(
                count > period * 4 and all(
                    channel[pos] == channel[pos % period]
                    for pos in range(period, count))
                for period in range(1, 17))
            result.append(dict(
                channel=index, samples=count, minimum=minimum, maximum=maximum,
                dc_mean=round(mean, 6), rms=round(math.sqrt(mean_square), 6),
                ac_rms=round(ac_rms, 6), peak=peak, distinct_values=distinct,
                clipped_samples=clipped, fixed_pattern=periodic,
                signal_detected=(peak > 0 and distinct > 1 and ac_rms >= 1
                                 and not periodic)))
            del channel[:]
        return dict(
            channels=result,
            channels_identical=(channels == 2 and len(samples) >= 2
                                and all(samples[pos] == samples[pos + 1]
                                        for pos in range(0, len(samples) - 1, 2))),
            nonconstant_signal_detected=any(item['signal_detected'] for item in result))
    finally:
        del channel[:]
        del samples[:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--initialize-microphone', action='store_true',
                        help='Explicitly permit temporary mixer/PCM changes')
    parser.add_argument('--seconds', type=int, choices=(1, 2, 3), default=3)
    parser.add_argument('--mmap', action='store_true')
    parser.add_argument('--output-dir', type=Path, required=True,
                        help='New private /var/tmp/g955n-mic-* directory')
    args = parser.parse_args()
    if not args.initialize_microphone:
        parser.error('Explicit --initialize-microphone required')
    if (os.geteuid() != 0 or 'g955n-ubuntu' not in platform.release()
            or 'SM-G955N' not in Path('/proc/device-tree/model').read_text()):
        raise SystemExit('Requires root on the native SM-G955N Ubuntu kernel')
    if 'Exynos8895-Madera' not in read_text('/proc/asound/cards'):
        raise SystemExit('Unexpected ALSA card; no controls changed')
    if not re.search(r'^00-09:.*capture', read_text('/proc/asound/pcm'), re.M):
        raise SystemExit('WDMA1 capture PCM is not registered; no controls changed')
    playback_status = Path('/proc/asound/card0/pcm0p/sub0/status')
    if read_text(playback_status).strip() != 'closed':
        raise SystemExit('RDMA0 playback is not idle; no controls changed')
    status_dir = Path('/proc/asound/card0/pcm9c/sub0')
    try:
        initial_status = (status_dir / 'status').read_text().strip()
    except FileNotFoundError:
        raise SystemExit('Unsupported diagnostic: ALSA status absent; enable '
                         'CONFIG_SND_VERBOSE_PROCFS. No controls changed')
    except OSError as error:
        raise SystemExit(f'Cannot read WDMA1 status: {error}; no controls changed')
    if initial_status != 'closed':
        state = re.search(r'^state:\s*(\S+)', initial_status, re.M)
        if state:
            raise SystemExit(f'WDMA1 is busy (state={state.group(1)}); no controls changed')
        raise SystemExit('Unsupported WDMA1 status; no controls changed')
    destination = args.output_dir.absolute()
    if (destination.parent != Path('/var/tmp')
            or not destination.name.startswith('g955n-mic-')
            or destination.exists() or destination.is_symlink()):
        raise SystemExit('Use a new /var/tmp/g955n-mic-* evidence directory')
    os.umask(0o077)
    destination.mkdir(mode=0o700)
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    routes = [
        ('ABOX Sampling Rate Inmux0', '48000'),
        ('ABOX NSRC0', 'UAIF0'),
        ('ABOX SPUM ASRC1', 'On'),
        ('ABOX SIFM0', 'WDMA'),
        ('IN3L HPF Switch', '1'),
        ('LHPF1 Input 1', 'IN3L'),
        ('ASRC1IN1L Input 1', 'LHPF1'),
        ('AIF1TX1 Input 1', 'ASRC1IN1L'),
        ('AIF1TX2 Input 1', 'ASRC1IN1L'),
        ('DMIC1 Switch', '1'),
    ]
    report = dict(kernel=platform.release(), pcm='hw:0,9', seconds=args.seconds,
                  access='mmap' if args.mmap else 'rw', rate=48000, channels=2,
                  expected_frames=48000 * args.seconds,
                  physical_signal_verified=False, controls_restored=False,
                  audio_storage='RAM only; discarded after numeric analysis')
    saved, observations = [], []
    raw = bytearray()
    child = None
    started = time.monotonic()
    try:
        original = {}
        for name, _ in routes:
            description = mixer(name)
            values = re.search(r'^\s*: values=([^\n]+)', description, re.M)
            if not values:
                raise RuntimeError('Cannot snapshot control: ' + name)
            original[name] = dict(value=values.group(1).strip(), description=description)
        (destination / 'controls-before.json').write_text(json.dumps(original, indent=2))
        (destination / 'interrupts-before.txt').write_text(read_text('/proc/interrupts'))
        for name, value in routes:
            saved.append((name, original[name]['value']))
            mixer(name, value)
        command = ['arecord', '-D', 'hw:0,9', '-f', 'S16_LE', '-r', '48000',
                   '-c', '2', '-t', 'raw', '-d', str(args.seconds)]
        if args.mmap:
            command.append('--mmap')
        report['command'] = command
        started = time.monotonic()
        with (destination / 'arecord.log').open('w') as log:
            child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=log,
                                     start_new_session=True)
            fd = child.stdout.fileno()
            os.set_blocking(fd, False)
            eof = False
            next_status = started
            with (destination / 'pcm-observations.jsonl').open('w') as evidence:
                while child.poll() is None or not eof:
                    if not eof and select.select([fd], [], [], 0.02)[0]:
                        chunk = os.read(fd, 65536)
                        if chunk:
                            raw.extend(chunk)
                            if len(raw) > report['expected_frames'] * 4 + 65536:
                                raise RuntimeError('Capture exceeded bounded byte limit')
                        else:
                            eof = True
                    elif eof:
                        time.sleep(0.02)
                    now = time.monotonic()
                    if now >= next_status:
                        snapshot = dict(seconds=round(now - started, 6),
                                        status=read_text(status_dir / 'status'),
                                        hw_params=read_text(status_dir / 'hw_params'),
                                        sw_params=read_text(status_dir / 'sw_params'))
                        if ('RUNNING' in snapshot['status']
                                and 'running_dapm_widgets' not in report):
                            report['running_dapm_widgets'] = {
                                name: read_text(CAPTURE_DAPM / directory / name)
                                .partition('\n')[0]
                                for directory, names in CAPTURE_WIDGETS.items()
                                for name in names
                            }
                        observations.append(snapshot)
                        evidence.write(json.dumps(snapshot) + '\n')
                        evidence.flush()
                        next_status = now + 0.02
                    if now - started > args.seconds + 4:
                        report['timed_out'] = True
                        break
                if child.poll() is not None:
                    report['arecord_exit'] = child.returncode
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
            report['arecord_exit'] = child.returncode
        if child is not None and child.stdout is not None:
            child.stdout.close()
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
        report['captured_bytes'] = len(raw)
        report['captured_frames'] = len(raw) // 4
        try:
            if len(raw) % 4:
                report['signal_error'] = 'Capture byte count is not frame-aligned'
            else:
                report.update(signal_statistics(raw, 2))
        finally:
            # Raw samples never enter files, logs or the JSON evidence.
            raw[:] = bytes(len(raw))
            raw.clear()
        pointers = []
        for observation in observations:
            match = re.search(r'^hw_ptr\s*:\s*(\d+)', observation['status'], re.M)
            if match:
                pointers.append(int(match.group(1)))
        report['status_observations'] = len(observations)
        report['distinct_hw_ptr_values'] = sorted(set(pointers))
        report['pcm_progress_observed'] = len(set(pointers)) > 1
        report['xrun_reported'] = bool(re.search(
            'underrun|overrun', read_text(destination / 'arecord.log'), re.I))
        report['capture_completed'] = (
            report.get('arecord_exit') == 0 and not report.get('timed_out')
            and report['captured_frames'] == report['expected_frames']
            and not report.get('signal_error') and report['pcm_progress_observed']
            and not report['xrun_reported'] and report['controls_restored'])
        report['signal_probe_passed'] = (
            report['capture_completed'] and report.get('nonconstant_signal_detected', False))
        (destination / 'result.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
    return 0 if report.get('signal_probe_passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
