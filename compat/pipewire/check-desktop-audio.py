#!/usr/bin/env python3
"""Explicit five-second desktop speaker/mic test; microphone bytes stay in RAM."""
import argparse
import array
from collections import Counter
import io
import json
import math
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import tempfile
import time
import wave

RATE = 48000
USER = ['runuser', '-u', 'ubuntu', '--', 'env', 'XDG_RUNTIME_DIR=/run/user/1000',
        'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']


def command(*args):
    return subprocess.check_output([*USER, *args], text=True, timeout=8).strip()


def volume(selector):
    text = command('wpctl', 'get-volume', selector)
    return float(re.search(r'Volume: ([\d.]+)', text)[1]), '[MUTED]' in text


def stop(child):
    if child is not None and child.poll() is None:
        os.killpg(child.pid, signal.SIGINT)
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=2)


def statistics(raw):
    if raw.startswith(b'RIFF'):
        with wave.open(io.BytesIO(raw)) as stream:
            if stream.getsampwidth() != 2 or stream.getnchannels() != 2:
                raise RuntimeError('Unexpected recording format')
            raw = stream.readframes(RATE * 6)
    if len(raw) % 4:
        raise RuntimeError('Incomplete stereo frame')
    samples = array.array('h')
    samples.frombytes(raw)
    if os.sys.byteorder != 'little':
        samples.byteswap()
    # Keep startup transients separate from the steady ADC signal.
    startup = samples[:RATE//2:2]
    mono = samples[RATE//2::2]
    if len(mono) < RATE:
        raise RuntimeError('Less than one second of captured PCM')
    rms = math.sqrt(sum(x*x for x in mono) / len(mono))
    windows = []
    for first in range(0, len(mono) - RATE//4 + 1, RATE//4):
        window = mono[first:first+RATE//4]
        energies = []
        for frequency in (523.25, 697.0):
            omega = 2 * math.pi * frequency / RATE
            real = sum(x * math.cos(omega*i) for i, x in enumerate(window))
            imag = sum(x * math.sin(omega*i) for i, x in enumerate(window))
            energies.append(round(2 * math.hypot(real, imag) / len(window), 3))
        windows.append(energies)
    startup_clips = [index for index, value in enumerate(startup) if abs(value) >= 32767]
    result = dict(startup_ignored_seconds=0.25,
                  startup_clipped_samples=len(startup_clips),
                  startup_first_clip_ms=round(startup_clips[0] * 1000 / RATE, 2) if startup_clips else None,
                  startup_last_clip_ms=round(startup_clips[-1] * 1000 / RATE, 2) if startup_clips else None,
                  frames=len(mono), seconds=round(len(mono)/RATE, 3),
                  rms=round(rms, 3), peak=max(abs(x) for x in mono),
                  distinct_values=len(set(mono)),
                  clipped_samples=sum(abs(x) >= 32767 for x in mono),
                  channels_identical=samples[::2] == samples[1::2],
                  quarter_second_tone_amplitudes=windows)
    result['nonconstant_signal'] = result['distinct_values'] > 16 and rms >= 1
    result['synthetic_tone_response_detected'] = all(
        any(pair[index] > 5 and pair[index] > 5 * max(pair[1-index], .01)
            for pair in windows) for index in (0, 1))
    del mono[:]
    del samples[:]
    return result


def hardware_error_samples(text):
    """Read only active hardware counters, excluding client startup errors."""
    result = {'sink': [], 'source': []}
    for line in text.splitlines():
        columns = line.split()
        if len(columns) < 11 or columns[0] != 'R' or not columns[8].isdigit():
            continue
        for name, prefix in [('sink', 'alsa_output.'), ('source', 'alsa_input.')]:
            if prefix in line:
                result[name].append(int(columns[8]))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test-speaker-microphone', action='store_true')
    args = parser.parse_args()
    if not args.test_speaker_microphone:
        parser.error('Requires explicit --test-speaker-microphone')
    if os.geteuid() or b'SM-G955N' not in Path('/proc/device-tree/model').read_bytes():
        raise RuntimeError('Run as root only on SM-G955N')
    subprocess.run(['/usr/local/libexec/g955n-wireplumber', '--check'], check=True,
                   stdout=subprocess.DEVNULL, timeout=10)
    for selector, device, media in [('@DEFAULT_AUDIO_SINK@', '0', 'Audio/Sink'),
                                    ('@DEFAULT_AUDIO_SOURCE@', '9', 'Audio/Source')]:
        info = command('wpctl', 'inspect', selector)
        if ('Exynos8895-Madera' not in info or f'alsa.device = "{device}"' not in info
                or f'media.class = "{media}"' not in info):
            raise RuntimeError('Default device does not match the built-in hardware')
    kernel_before = Counter(subprocess.check_output(['dmesg'], text=True).splitlines())
    boot = Path('/proc/sys/kernel/random/boot_id').read_text()
    taint = Path('/proc/sys/kernel/tainted').read_text()
    saved = {s: volume(s) for s in ('@DEFAULT_AUDIO_SINK@', '@DEFAULT_AUDIO_SOURCE@')}
    pointers = {'playback': set(), 'capture': set()}
    statuses = {'playback': Path('/proc/asound/card0/pcm0p/sub0/status'),
                'capture': Path('/proc/asound/card0/pcm9c/sub0/status')}
    raw = bytearray()
    record = play = monitor = None
    report = {}
    try:
        command('wpctl', 'set-volume', '@DEFAULT_AUDIO_SINK@', '0.8')
        for selector in saved:
            command('wpctl', 'set-mute', selector, '0')
        with tempfile.TemporaryDirectory(prefix='g955n-tone-', dir='/run/user/1000') as folder:
            os.chown(folder, 1000, 1000)
            tone = Path(folder) / 'synthetic.wav'
            pcm = array.array('h')
            for index in range(int(RATE * 1.6)):
                t = index / RATE
                value = 0
                for begin, frequency in ((0, 523.25), (0.9, 697.0)):
                    phase = t - begin
                    if 0 <= phase < 0.7:
                        fade = min(1, phase/.04, (.7-phase)/.04)
                        value = round(32767 * .18 * fade * math.sin(2*math.pi*frequency*phase))
                pcm.extend((value, value))
            if os.sys.byteorder != 'little':
                pcm.byteswap()
            with wave.open(str(tone), 'wb') as output:
                output.setparams((2, 2, RATE, 0, 'NONE', 'not compressed'))
                output.writeframes(pcm.tobytes())
            tone.chmod(0o644)
            record = subprocess.Popen([*USER, 'pw-record', '--rate', str(RATE),
                '--channels', '2', '--format', 's16', '-'], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, start_new_session=True)
            monitor = subprocess.Popen([*USER, 'pw-top', '-b', '-n', '6'],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       start_new_session=True)
            started = time.monotonic()
            while time.monotonic() - started < 5:
                elapsed = time.monotonic() - started
                if elapsed >= .8 and play is None:
                    play = subprocess.Popen([*USER, 'pw-play', str(tone)],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
                if select.select([record.stdout], [], [], .03)[0]:
                    block = os.read(record.stdout.fileno(), 65536)
                    if not block:
                        raise RuntimeError('Recorder ended before the bounded test')
                    raw.extend(block)
                    if len(raw) > RATE * 4 * 6:
                        raise RuntimeError('Recording byte bound exceeded')
                for name, status in statuses.items():
                    match = re.search(r'^hw_ptr\s*:\s*(\d+)', status.read_text(), re.M)
                    if match:
                        pointers[name].add(int(match[1]))
            stop(record)
            drain_until = time.monotonic() + .3
            while time.monotonic() < drain_until and select.select([record.stdout], [], [], 0)[0]:
                block = os.read(record.stdout.fileno(), 65536)
                if not block:
                    break
                raw.extend(block)
            play.wait(timeout=5)
            top = monitor.communicate(timeout=5)[0].decode(errors='replace')
            hardware_errors = hardware_error_samples(top)
            report = statistics(raw)
            report['hardware_error_samples'] = hardware_errors
            report['hardware_error_growth'] = {
                name: max(values) - min(values) if len(values) >= 2 else None
                for name, values in hardware_errors.items()}

            report.update(playback_exit=play.returncode,
                          playback_pointer_positions=len(pointers['playback']),
                          capture_pointer_positions=len(pointers['capture']),
                          microphone_audio_saved=False,
                          physical_audibility_confirmed=False)
            for stream in (record.stderr, play.stderr):
                os.set_blocking(stream.fileno(), False)
            errors = ((record.stderr.read() or b'') + (play.stderr.read() or b'')).decode(errors='replace')
            report['xrun_reported'] = bool(re.search(r'underrun|overrun|xrun', errors, re.I))
    finally:
        stop(record)
        stop(play)
        stop(monitor)
        raw[:] = b''
        for selector, (level, muted) in saved.items():
            command('wpctl', 'set-volume', selector, str(level))
            command('wpctl', 'set-mute', selector, '1' if muted else '0')
    report['volume_and_mute_restored'] = all(volume(s) == value for s, value in saved.items())
    report['same_boot_and_taint'] = (Path('/proc/sys/kernel/random/boot_id').read_text() == boot
                                    and Path('/proc/sys/kernel/tainted').read_text() == taint)
    added = Counter(subprocess.check_output(['dmesg'], text=True).splitlines()) - kernel_before
    report['new_kernel_fault_count'] = sum(count for line, count in added.items()
        if re.search(r'WARNING:|BUG:|Call trace:|Kernel panic|Unable to handle|'
                     r'(?:SysMMU|sysmmu).*(?:fault|FAULT)', line))
    report['pcm_transport_checks_passed'] = (report['playback_exit'] == 0
        and report['nonconstant_signal'] and report['clipped_samples'] == 0
        and report['playback_pointer_positions'] > 1
        and report['capture_pointer_positions'] > 1 and not report['xrun_reported']
        and all(value == 0 for value in report['hardware_error_growth'].values())
        and report['volume_and_mute_restored'] and report['same_boot_and_taint']
        and report['new_kernel_fault_count'] == 0)
    report['acoustic_quality_requires_confirmation'] = True
    print(json.dumps(report, indent=2))
    return 0 if report['pcm_transport_checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
