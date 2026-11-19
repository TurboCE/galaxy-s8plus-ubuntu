#!/usr/bin/env python3
"""Explicit CPU-only single-buffer lifecycle in an existing private runtime.

Default/help and --selftest do not access a device. No GLES/HWC/display mode.
The caller must supply the reviewed probe SHA and exact boot identity.
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
import stat
import subprocess
import tempfile
import time
from importlib.machinery import SourceFileLoader

BASE = Path(__file__).resolve().parent
legacy = SourceFileLoader('no_ion_evidence', str(BASE / 'allocator-no-ion-trial.py')).load_module()
SERVICE = legacy.SERVICE
DANGEROUS = legacy.DANGEROUS
TRACE_CALLS = 'process,open,openat,close,dup,dup2,dup3,fcntl,mmap,munmap,ioctl'
MAX_TRACE = 4 * 1024 * 1024


def processes(command):
    result = []
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            if path.read_bytes().split(b'\0', 1)[0] == command.encode():
                result.append(int(path.parent.name))
        except FileNotFoundError:
            pass
    return result


def guard(boot, allow_service=False):
    if os.geteuid() != 0 or os.getpid() == 1:
        raise RuntimeError('Requires a separate root controller')
    if (os.environ.get('G955N_ANDROID_PRIVATE_RUNTIME') != '1' or
            any(not os.environ.get(key) or os.readlink('/proc/self/ns/' + name) == os.environ[key]
                for name, key in [('pid', 'G955N_PARENT_PID_NS'), ('mnt', 'G955N_PARENT_MOUNT_NS')])):
        raise RuntimeError('Private namespace provenance failed')
    if ('SM-G955N' not in Path('/sys/firmware/devicetree/base/model').read_text() or
            'g955n-ubuntu' not in Path('/proc/sys/kernel/osrelease').read_text() or
            Path('/proc/sys/kernel/random/boot_id').read_text().strip() != boot):
        raise RuntimeError('Device/kernel/exact boot mismatch')
    fields = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    nnp = ctypes.CDLL(None, use_errno=True).prctl(39, 0, 0, 0, 0)
    if not legacy.nnp_verified(nnp, fields) or any(int(fields.get(k, 'ffffffff'), 16) & DANGEROUS for k in ('CapEff', 'CapPrm', 'CapBnd')):
        raise RuntimeError('Capability/NNP guard failed')
    allowed = {'null', 'zero', 'random', 'urandom', 'binder', 'hwbinder', 'vndbinder', 'ashmem', '__properties__', 'socket', 'ion'}
    if set(p.name for p in Path('/dev').iterdir()) - allowed:
        raise RuntimeError('Unexpected device directory entry')
    for name in ('/efs', '/proc/1/root/efs', '/dev/block', '/dev/snd', '/dev/mali0', '/dev/graphics', '/dev/fb0', '/dev/dri', '/dev/sw_sync'):
        try:
            Path(name).lstat()
        except FileNotFoundError:
            continue
        raise RuntimeError('Forbidden path: ' + name)
    inode_proof = {}
    for name, uid, gid, mode in [('/dev/ion', 1000, 1000, 0o600), ('/dev/hwbinder', 0, 1003, 0o660)]:
        st = Path(name).lstat()
        if not stat.S_ISCHR(st.st_mode) or (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) != (uid, gid, mode):
            raise RuntimeError('Private inode policy differs: ' + name)
        inode_proof[name] = dict(uid=uid, gid=gid, mode=oct(mode), major=os.major(st.st_rdev), minor=os.minor(st.st_rdev))
    if not all(os.statvfs(p).f_flag & os.ST_RDONLY for p in ('/proc', '/sys', '/system', '/vendor')):
        raise RuntimeError('Required read-only filesystem missing')
    if not any(' /dev ' in line and ' - tmpfs ' in line for line in Path('/proc/self/mountinfo').read_text().splitlines()):
        raise RuntimeError('Private tmpfs dev missing')
    if not allow_service and processes(SERVICE):
        raise RuntimeError('Existing allocator detected')
    return dict(nnp_prctl=nnp, inodes=inode_proof)


def inspect(pid):
    root = Path('/proc', str(pid))
    result = {}
    for name in ('status', 'maps'):
        try:
            result[name] = (root / name).read_text()
        except OSError as error:
            result[name + '_error'] = repr(error)
    result['fds'] = {}
    for path in (root / 'fd').glob('*'):
        try:
            result['fds'][path.name] = os.readlink(path)
        except FileNotFoundError:
            pass
    return result


def query(binary, arguments, boot, seconds=5):
    result = subprocess.run([str(binary), *arguments, boot], capture_output=True, text=True,
                            timeout=max(.1, min(5, seconds)), close_fds=True,
                            env={**os.environ, 'LD_LIBRARY_PATH': '/system/lib64:/vendor/lib64'})
    return dict(exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr)


def setup_child(parent, service=False):
    if service:
        os.setgroups([1026]); os.setgid(1003); os.setuid(1000)
    if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL, 0, 0, 0) or os.getppid() != parent:
        os._exit(125)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_TRACE, MAX_TRACE))


def stop_group(process):
    if process is None:
        return dict(reaped=True, remaining=[])
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            continue
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        pass
    remaining = []
    for path in Path('/proc').glob('[0-9]*'):
        try:
            if os.getpgid(int(path.name)) == process.pid:
                remaining.append(int(path.name))
        except ProcessLookupError:
            pass
    return dict(wrapper_exit=process.returncode, reaped=process.poll() is not None, remaining=remaining)


def read_log(file):
    file.flush(); file.seek(0)
    return file.read(MAX_TRACE).decode(errors='replace')


def trace_evidence(path):
    text = path.read_text(errors='replace') if path.exists() else ''
    forbidden_open = [line for line in text.splitlines()
                      if re.search(r'open(?:at)?\(.*"/dev/(?:mali|fb|graphics|snd|dri|block|video)', line)
                      and re.search(r'= [0-9]+(?:\s|$)', line)]
    return dict(bytes=path.stat().st_size if path.exists() else 0,
                complete=path.exists() and 0 < path.stat().st_size < MAX_TRACE,
                mali_library_seen='libGLES_mali' in text,
                mali_library_attempts=[line for line in text.splitlines() if 'libGLES_mali' in line],
                forbidden_open_attempts=[line for line in text.splitlines() if re.search(r'open(?:at)?\(.*"/dev/(?:mali|fb|graphics|snd|dri|block|video)', line)],
                forbidden_successful_opens=forbidden_open, raw=text[:MAX_TRACE])


def trial(binary, boot):
    proof = guard(boot)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) or libc.prctl(36, 1, 0, 0, 0):
        raise RuntimeError('Parent-death/subreaper setup failed')
    def terminate(signum, frame):
        raise InterruptedError('Controller termination requested')
    signal.signal(signal.SIGTERM, terminate)
    report = dict(cpu_only=True, gpu_tested=False, rendering_qualified=False, initial_guard=proof)
    before = query(binary, ['--expect-allocator-absent'], boot)
    report['registration_before'] = before
    if before['exit_code'] != 0 or before['stdout'].strip() != 'allocator_registration=absent':
        raise RuntimeError('Actual initial registration absence not verified')
    service = probe = None
    service_pid = probe_pid = None
    parent = os.getpid()
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='g955n-cpu-buffer-', dir='/run') as temp:
        directory = Path(temp)
        # Only this private scratch directory is traversable by the traced UID.
        directory.chmod(0o711)
        service_trace = directory / 'allocator.strace'
        service_trace.touch(mode=0o600); os.chown(service_trace, 1000, 1003)
        probe_trace = directory / 'probe.strace'
        with tempfile.TemporaryFile(dir='/run') as service_log, tempfile.TemporaryFile(dir='/run') as probe_log:
            try:
                service = subprocess.Popen(['/usr/bin/strace', '-f', '-tt', '-s', '80', '-e', 'trace=' + TRACE_CALLS,
                                            '-o', str(service_trace), SERVICE], stdin=subprocess.DEVNULL,
                                           stdout=service_log, stderr=service_log, close_fds=True, start_new_session=True,
                                           preexec_fn=lambda: setup_child(parent, True),
                                           env={k: v for k, v in os.environ.items() if k not in ('LD_PRELOAD', 'LD_LIBRARY_PATH') and not k.startswith('HYBRIS_')})
                deadline = started + 15
                discovery = min(deadline, time.monotonic() + 3)
                while time.monotonic() < discovery:
                    candidates = processes(SERVICE)
                    if len(candidates) == 1:
                        service_pid = candidates[0]; break
                    if service.poll() is not None:
                        break
                    time.sleep(.01)
                if not service_pid:
                    raise RuntimeError('Original traced allocator process did not become observable')
                report['allocator_namespace_pid'] = service_pid
                print('allocator_namespace_pid=' + str(service_pid), flush=True)
                report['allocator_before_probe'] = inspect(service_pid)
                fields = dict(line.split(':', 1) for line in report['allocator_before_probe'].get('status', '').splitlines() if ':' in line)
                if (set(fields.get('Uid', '').split()) != {'1000'} or set(fields.get('Gid', '').split()) != {'1003'} or
                        fields.get('Groups', '').split() != ['1026'] or
                        ('NoNewPrivs' in fields and int(fields['NoNewPrivs']) != 1) or
                        any(int(fields.get(k, 'ffffffff'), 16) & DANGEROUS for k in ('CapEff', 'CapPrm', 'CapBnd'))):
                    raise RuntimeError('Actual service UID/GID/capability proof failed')
                observations = []
                registration_deadline = min(deadline, time.monotonic() + 4)
                while time.monotonic() < registration_deadline:
                    q = query(binary, ['--registration-only', str(service_pid)], boot, registration_deadline-time.monotonic())
                    observations.append(q)
                    if legacy.registration_matches(q['exit_code'], q['stdout'], service_pid):
                        report['registration_verified'] = True; break
                    if q['exit_code'] != 3:
                        break
                    time.sleep(.1)
                report['registration_observations'] = observations
                if not report.get('registration_verified'):
                    raise RuntimeError('Actual registered allocator PID not verified')
                report['pre_probe_guard'] = guard(boot, True)
                probe = subprocess.Popen(['/usr/bin/strace', '-f', '-tt', '-s', '80', '-e', 'trace=' + TRACE_CALLS,
                                          '-o', str(probe_trace), '/usr/bin/env', 'LD_LIBRARY_PATH=/system/lib64:/vendor/lib64', str(binary), '--allocate-only', str(service_pid), boot],
                                         stdin=subprocess.DEVNULL, stdout=probe_log, stderr=probe_log,
                                         close_fds=True, start_new_session=True, preexec_fn=lambda: setup_child(parent),
                                         env={k: v for k, v in os.environ.items() if k not in ('LD_LIBRARY_PATH', 'LD_PRELOAD')})
                probe_deadline = min(deadline, time.monotonic() + 10)
                while probe.poll() is None and time.monotonic() < probe_deadline:
                    text = read_log(probe_log)
                    match = re.search(r'headless_probe_pid=(\d+)', text)
                    if match and not probe_pid:
                        probe_pid = int(match[1]); report['probe_namespace_pid'] = probe_pid
                        report['probe_live'] = inspect(probe_pid)
                    imported = re.search(r'headless_buffer_imported_pid=(\d+)', text)
                    if imported and not report.get('probe_after_import'):
                        report['probe_after_import'] = inspect(int(imported[1]))
                    time.sleep(.005)
                report['probe_exit_code'] = probe.poll()
                if probe.poll() is None:
                    report['probe_timeout'] = True
                report['allocator_after_probe'] = inspect(service_pid)
            except Exception as error:
                report['exception'] = repr(error)
            finally:
                report['probe_cleanup'] = stop_group(probe)
                report['probe_stdout'] = read_log(probe_log)
                report['service_cleanup'] = stop_group(service)
                # Reap traced orphans only after both direct Popen children have
                # been waited; never steal the other wrapper's real exit status.
                reap_deadline = time.monotonic() + .5
                while time.monotonic() < reap_deadline:
                    try:
                        pid, _ = os.waitpid(-1, os.WNOHANG)
                        if not pid:
                            time.sleep(.02)
                    except ChildProcessError:
                        break
                for process, key in [(probe, 'probe_cleanup'), (service, 'service_cleanup')]:
                    if process is not None:
                        remaining = []
                        for path in Path('/proc').glob('[0-9]*'):
                            try:
                                if os.getpgid(int(path.name)) == process.pid:
                                    remaining.append(int(path.name))
                            except ProcessLookupError:
                                pass
                        report[key]['remaining'] = remaining
                report['service_stdout'] = read_log(service_log)
                report['service_elapsed_seconds'] = round(time.monotonic()-started, 3)
                report['allocator_pid_gone'] = service_pid is None or not Path('/proc', str(service_pid)).exists()
                report['probe_pid_gone'] = probe_pid is None or not Path('/proc', str(probe_pid)).exists()
                report['probe_trace'] = trace_evidence(probe_trace)
                report['allocator_trace'] = trace_evidence(service_trace)
                try:
                    report['registration_after'] = query(binary, ['--expect-allocator-absent'], boot)
                    report['post_guard'] = guard(boot)
                except Exception as error:
                    report['cleanup_error'] = repr(error)
    after = report.get('registration_after', {})
    report['cleanup_passed'] = (report['allocator_pid_gone'] and report['probe_pid_gone'] and
                                not report['probe_cleanup']['remaining'] and not report['service_cleanup']['remaining'] and
                                report['probe_cleanup']['reaped'] and report['service_cleanup']['reaped'] and
                                after.get('exit_code') == 0 and after.get('stdout', '').strip() == 'allocator_registration=absent' and bool(report.get('post_guard')))
    traces = [report['probe_trace'], report['allocator_trace']]
    report['maps_evidence_complete'] = bool(
        report.get('allocator_before_probe', {}).get('maps') and report.get('allocator_after_probe', {}).get('maps') and
        report.get('probe_live', {}).get('maps') and report.get('probe_after_import', {}).get('maps'))
    report['cpu_buffer_operation_passed'] = (report['cleanup_passed'] and report.get('registration_verified', False) and
                                   report.get('probe_exit_code') == 0 and
                                   'buffer_roundtrip_passed=yes gpu_native_buffer=not_tested' in report['probe_stdout'] and
                                   'probe_exit=0 buffers_cleanup=yes allocation_only=yes' in report['probe_stdout'] and
                                   all(t['complete'] and not t['mali_library_seen'] and not t['forbidden_successful_opens'] for t in traces))
    report['cpu_buffer_passed'] = report['cpu_buffer_operation_passed'] and report['maps_evidence_complete']
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--cpu-buffer', action='store_true')
    mode.add_argument('--selftest', action='store_true')
    parser.add_argument('--probe', type=Path)
    parser.add_argument('--probe-sha256')
    parser.add_argument('--expected-boot-id')
    args = parser.parse_args()
    if args.selftest:
        good = 'allocator_registration=present namespace_pid=7 expected_pid=7 transport=hwbinder debug_pid=-1 pid_source=manager_registration\n'
        assert legacy.registration_matches(0, good, 7)
        assert not legacy.registration_matches(0, good, 8)
        assert legacy.nnp_verified(1, {}) and not legacy.nnp_verified(0, {})
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / 'trace'
            trace.touch()
            assert not trace_evidence(trace)['complete']
            trace.write_text('7 openat(AT_FDCWD, "/dev/ion", O_RDWR) = 3\n')
            assert trace_evidence(trace)['complete']
            trace.write_text('7 openat(AT_FDCWD, "/vendor/lib64/egl/libGLES_mali.so", O_RDONLY) = -1 ENOENT\n')
            assert trace_evidence(trace)['mali_library_seen'] and trace_evidence(trace)['mali_library_attempts']
        print('CPU evidence parser/trace completeness selftest passed; no service/device access'); return 0
    if not args.cpu_buffer:
        parser.print_help(); return 0
    if not args.probe or not re.fullmatch(r'[0-9a-f]{64}', args.probe_sha256 or '') or not re.fullmatch(r'[0-9a-f-]{36}', args.expected_boot_id or ''):
        parser.error('Supply reviewed probe hash and exact boot ID')
    binary = args.probe.resolve(strict=True)
    if not binary.is_relative_to('/home') or hashlib.sha256(binary.read_bytes()).hexdigest() != args.probe_sha256:
        raise SystemExit('Reviewed probe mismatch')
    try:
        report = trial(binary, args.expected_boot_id)
    except Exception as error:
        report = dict(refused=True, exception=repr(error), cpu_buffer_passed=False, rendering_qualified=False)
    print(json.dumps(report, indent=2), flush=True)
    return 0 if report.get('cleanup_passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
