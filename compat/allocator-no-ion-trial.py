#!/usr/bin/env python3
"""Explicit ten-second allocator lifecycle inside an existing private runtime.

Does not construct a runtime, mount a filesystem, expose a device or allocate a
buffer. No operation occurs without --run-no-ion. Coordinate with the port owner.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import tempfile
import time

SERVICE = '/vendor/bin/hw/android.hardware.graphics.allocator@2.0-service'
FORBIDDEN = ('/efs', '/proc/1/root/efs', '/dev/block', '/dev/snd', '/dev/ion',
             '/dev/mali0', '/dev/fb0', '/dev/graphics/fb0', '/dev/sw_sync')
DANGEROUS = sum(1 << n for n in (16, 17, 21, 22, 27))


def registration_matches(code, text, expected):
    match = re.fullmatch(r'allocator_registration=present namespace_pid=([0-9]+) expected_pid=([0-9]+) transport=hwbinder debug_pid=(-?[0-9]+) pid_source=manager_registration\n?', text)
    return code == 0 and bool(match) and int(match[1]) == int(match[2]) == expected and int(match[3]) in (-1, expected)


def nnp_verified(actual_prctl, status):
    return actual_prctl == 1 and ('NoNewPrivs' not in status or int(status['NoNewPrivs']) == 1)


def guard():
    if os.geteuid() != 0 or os.getpid() == 1:
        raise RuntimeError('Requires a separate root controller in an existing private runtime')
    if (os.environ.get('G955N_ANDROID_PRIVATE_RUNTIME') != '1' or
            any(os.readlink('/proc/self/ns/' + name) == os.environ.get(key, '')
                for name, key in [('pid', 'G955N_PARENT_PID_NS'), ('mnt', 'G955N_PARENT_MOUNT_NS')]) or
            not all(os.environ.get(k) for k in ('G955N_PARENT_PID_NS', 'G955N_PARENT_MOUNT_NS'))):
        raise RuntimeError('Private PID/mount identities not verified')
    if ('SM-G955N' not in Path('/sys/firmware/devicetree/base/model').read_text() or
            'g955n-ubuntu' not in Path('/proc/sys/kernel/osrelease').read_text()):
        raise RuntimeError('Wrong device/kernel')
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    actual_nnp = ctypes.CDLL(None, use_errno=True).prctl(39, 0, 0, 0, 0)
    if (not nnp_verified(actual_nnp, status) or
            any(int(status.get(k, 'ffffffff'), 16) & DANGEROUS for k in ('CapEff', 'CapPrm', 'CapBnd'))):
        raise RuntimeError('Dangerous capabilities or new privileges remain')
    allowed = {'null', 'zero', 'random', 'urandom', 'binder', 'hwbinder', 'vndbinder', 'ashmem', '__properties__', 'socket'}
    if set(p.name for p in Path('/dev').iterdir()) - allowed:
        raise RuntimeError('Unexpected device-directory entry')
    for path in FORBIDDEN:
        try:
            Path(path).lstat()
        except FileNotFoundError:
            continue
        raise RuntimeError('Forbidden path present: ' + path)
    if not all(os.statvfs(p).f_flag & os.ST_RDONLY for p in ('/proc', '/sys', '/system', '/vendor')):
        raise RuntimeError('Required read-only filesystem missing')
    if not any(' /dev ' in line and ' - tmpfs ' in line for line in Path('/proc/self/mountinfo').read_text().splitlines()):
        raise RuntimeError('Private tmpfs /dev missing')
    existing = []
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            if path.read_bytes().split(b'\0', 1)[0] == SERVICE.encode():
                existing.append(int(path.parent.name))
        except FileNotFoundError:
            pass
    if existing:
        raise RuntimeError('Existing allocator detected; refusing interference')


def query(binary, arguments, seconds=5):
    result = subprocess.run([str(binary), *arguments], capture_output=True, text=True,
                            timeout=max(.1, min(5, seconds)), close_fds=True,
                            env={**os.environ, 'LD_LIBRARY_PATH': '/system/lib64:/vendor/lib64'})
    return dict(exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr)


def service_setup(parent_pid):
    os.setgroups([1026])
    os.setgid(1003)
    os.setuid(1000)
    # Credential changes reset PDEATHSIG: install only after dropping privileges.
    if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL, 0, 0, 0) != 0 or os.getppid() != parent_pid:
        os._exit(125)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (262144, 262144))


def trial(binary):
    guard()
    if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise RuntimeError('Cannot bind controller lifetime to outer supervisor')
    def terminate(signum, frame):
        raise InterruptedError('Controller termination requested')
    signal.signal(signal.SIGTERM, terminate)
    report = dict(no_hardware_nodes=True, rendering_qualified=False, allocation_tested=False,
                  uid=1000, gid=1003, supplementary_gids=[1026], sys_nice_granted=False,
                  controller_nnp_prctl=ctypes.CDLL(None, use_errno=True).prctl(39, 0, 0, 0, 0),
                  child_nnp_inherited_from_verified_controller=True)
    before = query(binary, ['--expect-allocator-absent'])
    report['registration_before'] = before
    if before['exit_code'] != 0 or before['stdout'].strip() != 'allocator_registration=absent':
        raise RuntimeError('Actual registration absence not verified; no service started')
    service = None
    started = time.monotonic()
    with tempfile.TemporaryFile(dir='/run') as log:
        try:
            parent_pid = os.getpid()
            # Never interpret init RC/onrestart or acknowledge ctl autostart.
            service = subprocess.Popen([SERVICE], stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       close_fds=True, start_new_session=True,
                                       preexec_fn=lambda: service_setup(parent_pid),
                                       env={k: v for k, v in os.environ.items()
                                            if k not in ('LD_PRELOAD', 'LD_LIBRARY_PATH') and not k.startswith('HYBRIS_')})
            report['allocator_namespace_pid'] = service.pid
            print('allocator_namespace_pid=' + str(service.pid), flush=True)
            report['service_status'] = Path('/proc', str(service.pid), 'status').read_text()
            fields = dict(line.split(':', 1) for line in report['service_status'].splitlines() if ':' in line)
            if (set(fields.get('Uid', '').split()) != {'1000'} or
                    set(fields.get('Gid', '').split()) != {'1003'} or
                    fields.get('Groups', '').split() != ['1026'] or
                    ('NoNewPrivs' in fields and int(fields['NoNewPrivs']) != 1) or
                    any(int(fields.get(k, 'ffffffff'), 16) & DANGEROUS for k in ('CapEff', 'CapPrm', 'CapBnd'))):
                raise RuntimeError('Actual allocator credentials/capability guard failed')
            report['child_nnp_proc_field_available'] = 'NoNewPrivs' in fields
            deadline = started + 10
            observations = []
            while service.poll() is None and time.monotonic() < deadline:
                try:
                    observation = query(binary, ['--query-allocator', str(service.pid)], deadline - time.monotonic())
                    observations.append(observation)
                    if registration_matches(observation['exit_code'], observation['stdout'], service.pid):
                        report['registration_verified'] = True
                        # Keep observation inside the same ten-second lifetime.
                        break
                    if observation['exit_code'] not in (3,):
                        break
                except subprocess.TimeoutExpired:
                    observations.append(dict(timeout=True))
                    break
                time.sleep(min(.2, max(0, deadline - time.monotonic())))
            report['registration_observations'] = observations
        except Exception as error:
            report['exception'] = repr(error)
        finally:
            if service is not None:
                # Signal the whole group even if the original leader exited.
                try:
                    os.killpg(service.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    service.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
                try:
                    os.killpg(service.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                service.wait(timeout=1)
                remaining = []
                for proc in Path('/proc').glob('[0-9]*'):
                    try:
                        if os.getpgid(int(proc.name)) == service.pid:
                            remaining.append(int(proc.name))
                    except ProcessLookupError:
                        pass
                report['remaining_service_group_pids'] = remaining
                # Reap does not prove no forked descendants. Check the private
                # process tree by exact service cmdline as well as original PID.
                report['service_exit_code'] = service.returncode
                report['allocator_pid_gone'] = not Path('/proc', str(service.pid)).exists()
            report['service_elapsed_seconds'] = round(time.monotonic() - started, 3)
            log.seek(0)
            report['stdout'] = log.read(262144).decode(errors='replace')
            try:
                report['registration_after'] = query(binary, ['--expect-allocator-absent'])
                guard()  # also detects any remaining allocator process
                report['post_service_guard_passed'] = True
            except Exception as error:
                report['cleanup_error'] = repr(error)
    after = report.get('registration_after', {})
    report['cleanup_passed'] = (not report.get('remaining_service_group_pids') and
                                report.get('allocator_pid_gone', service is None) and
                                report.get('post_service_guard_passed', False) and
                                after.get('exit_code') == 0 and after.get('stdout', '').strip() == 'allocator_registration=absent')
    report['allocator_registration_passed'] = bool(report.get('registration_verified')) and report['cleanup_passed']
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--run-no-ion', action='store_true')
    mode.add_argument('--selftest', action='store_true')
    parser.add_argument('--query', type=Path)
    parser.add_argument('--query-sha256')
    args = parser.parse_args()
    if args.selftest:
        assert nnp_verified(1, {})
        assert nnp_verified(1, {'NoNewPrivs': '1'})
        assert not nnp_verified(0, {})
        assert not nnp_verified(-1, {'NoNewPrivs': '1'})
        assert not nnp_verified(1, {'NoNewPrivs': '0'})
        good = 'allocator_registration=present namespace_pid=45 expected_pid=45 transport=hwbinder debug_pid=45 pid_source=manager_registration\n'
        assert registration_matches(0, good, 45)
        assert registration_matches(0, good.replace('debug_pid=45', 'debug_pid=-1'), 45)
        assert not registration_matches(0, good.replace('debug_pid=45', 'debug_pid=46'), 45)
        assert not registration_matches(0, good, 46)
        assert not registration_matches(4, good, 45)
        assert not registration_matches(0, good.replace('expected_pid=45', 'expected_pid=46'), 45)
        assert not registration_matches(0, 'allocator_registration=absent\n', 45)
        assert not registration_matches(0, good + 'unexpected extra row\n', 45)
        print('Exact registration/PID evidence selftest passed; no service/device access')
        return 0
    if not args.run_no_ion:
        parser.print_help()
        return 0
    if not args.query or not args.query_sha256 or not re.fullmatch(r'[0-9a-f]{64}', args.query_sha256):
        parser.error('Supply the reviewed query executable and exact SHA256')
    binary = args.query.resolve(strict=True)
    if (not binary.is_relative_to('/home') or not binary.is_file() or
            hashlib.sha256(binary.read_bytes()).hexdigest() != args.query_sha256):
        raise SystemExit('Reviewed private query binary does not match')
    try:
        report = trial(binary)
    except Exception as error:
        report = dict(refused=True, exception=repr(error), allocation_tested=False, rendering_qualified=False)
    print(json.dumps(report, indent=2), flush=True)
    return 0 if report.get('cleanup_passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
