#!/usr/bin/env python3
"""Bounded G955N CPU scaling/idle observation without changing power policy.

Two low-priority workers exercise one LITTLE and one big core for six seconds.
Thermal observation stops load at 65 C. No governor, clock, affinity of another
process, idle policy or suspend setting is written. CPU-idle residency is not
whole-phone suspend, battery-life or thermal-limit qualification.
"""
import argparse
import json
import multiprocessing
import os
from pathlib import Path
import platform
import time

CPUS = (0, 4)


def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def thermal():
    values = []
    for zone in Path('/sys/class/thermal').glob('thermal_zone*'):
        raw = read(zone / 'temp')
        if raw is not None:
            try:
                value = int(raw)
            except ValueError:
                continue
            if -10000 <= value <= 150000:
                values.append(value)
    return max(values) if values else None


def snapshot():
    result = {}
    for cpu in CPUS:
        base = Path('/sys/devices/system/cpu') / ('cpu' + str(cpu))
        scaling = base / 'cpufreq'
        idle = {}
        for state in (base / 'cpuidle').glob('state*'):
            name, duration, usage = read(state / 'name'), read(state / 'time'), read(state / 'usage')
            if duration is not None and usage is not None:
                idle[state.name] = dict(name=name, time_us=int(duration), usage=int(usage))
        result[str(cpu)] = dict(frequency_khz=read(scaling / 'scaling_cur_freq'),
                                governor=read(scaling / 'scaling_governor'),
                                min_khz=read(scaling / 'scaling_min_freq'),
                                max_khz=read(scaling / 'scaling_max_freq'), idle=idle)
    return result


def worker(cpu):
    os.nice(10)
    os.sched_setaffinity(0, {cpu})
    deadline = time.monotonic() + 6
    value = 1
    while time.monotonic() < deadline:
        for _ in range(10000):
            value = (value * 1664525 + 1013904223) & 0xffffffff


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exercise-cpu', action='store_true')
    args = parser.parse_args()
    if not args.exercise_cpu:
        parser.error('Explicit --exercise-cpu required')
    if ('g955n-ubuntu' not in platform.release()
            or 'SM-G955N' not in Path('/proc/device-tree/model').read_text()
            or not set(CPUS) <= os.sched_getaffinity(0)):
        raise SystemExit('Requires native SM-G955N with both CPU clusters available')
    boot = read('/proc/sys/kernel/random/boot_id')
    before = snapshot()
    if any(before[str(cpu)]['frequency_khz'] is None for cpu in CPUS):
        raise SystemExit('CPU frequency diagnostics unavailable; no load started')
    baseline_temp = thermal()
    if baseline_temp is None or baseline_temp >= 65000:
        raise SystemExit('Thermal diagnostics unavailable or too warm; no load started')
    workers, samples = [], []
    result = dict(before=before, full_suspend_tested=False, passed=False,
                  baseline_max_temperature_millic=baseline_temp)
    try:
        for cpu in CPUS:
            process = multiprocessing.Process(target=worker, args=(cpu,))
            workers.append(process)
            process.start()
        started = time.monotonic()
        while time.monotonic() - started < 7 and any(p.is_alive() for p in workers):
            temperature = thermal()
            samples.append(dict(seconds=round(time.monotonic() - started, 3),
                                temperature_millic=temperature,
                                frequency_khz={str(cpu):read('/sys/devices/system/cpu/cpu%d/cpufreq/scaling_cur_freq' % cpu) for cpu in CPUS}))
            if temperature is None or temperature >= 65000:
                result['thermal_stop'] = True
                break
            time.sleep(0.1)
    finally:
        for process in workers:
            if process.pid is not None:
                process.join(timeout=0.5)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=1)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=1)
        result['worker_exits'] = [p.exitcode for p in workers]
    time.sleep(3)
    after = snapshot()
    policy_fields = ('governor', 'min_khz', 'max_khz')
    result.update(after=after, samples=samples,
                  policy_unchanged=all(before[str(cpu)][key] == after[str(cpu)][key] for cpu in CPUS for key in policy_fields),
                  same_boot=read('/proc/sys/kernel/random/boot_id') == boot)
    result['frequencies_observed_khz'] = {str(cpu):sorted({int(s['frequency_khz'][str(cpu)]) for s in samples if s['frequency_khz'][str(cpu)] is not None}) for cpu in CPUS}
    result['frequency_changes_observed'] = {
        str(cpu):len(set(result['frequencies_observed_khz'][str(cpu)]) |
                     {int(value) for value in (before[str(cpu)]['frequency_khz'], after[str(cpu)]['frequency_khz']) if value is not None}) > 1
        for cpu in CPUS}
    result['idle_residency_increased'] = {
        str(cpu):{state:values['time_us'] > before[str(cpu)]['idle'][state]['time_us']
                  for state, values in after[str(cpu)]['idle'].items() if state in before[str(cpu)]['idle']}
        for cpu in CPUS}
    result['passed'] = (len(workers) == 2 and all(p.exitcode == 0 for p in workers)
                        and not result.get('thermal_stop') and result['policy_unchanged']
                        and result['same_boot'] and bool(samples))
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
