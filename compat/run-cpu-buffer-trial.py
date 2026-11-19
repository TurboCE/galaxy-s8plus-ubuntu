#!/usr/bin/env python3
"""Reviewed explicit CPU/GLES ION scope; default/help never activates hardware.

A canonical read-only BSP must already exist. Does not flash/reboot, change GDM,
create a display device. GLES requires a distinct reviewed scope and plugin. All original-service activity is in the
existing bounded private PID/mount runtime with an explicit ION-only device.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import tempfile
import time
from importlib.machinery import SourceFileLoader

REVIEW_FILES = {'run-cpu-buffer-trial.py', 'allocator-cpu-buffer-trial.py',
                'run-property-trial.py', 'allocator-no-ion-trial.py',
                'android-runtime-namespace.py', 'android-property-runtime', 'headless-buffer-probe'}
FAULT = re.compile(r'Kernel panic|Internal error:|Unable to handle kernel|\bBUG:|\bOops:|\bWARNING:|Call trace:|SysMMU.*fault|soft lockup|hard LOCKUP|\brcu\b.*stall', re.I)


def verify_review(build, manifest, expected, boot, gpu=False, composer=False):
    if composer and not gpu:
        raise RuntimeError("Composer scope requires explicit GLES")
    required = REVIEW_FILES | ({"headless-buffer-gles.so"} if gpu else set())
    scope = "gles-composer-no-display" if composer else "gles-buffer-64x64-no-display" if gpu else "cpu-buffer-64x64-no-display"
    payload = manifest.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected:
        raise RuntimeError('Review-manifest hash mismatch')
    data = json.loads(payload)
    if (data.get('target') != 'SM-G955N' or data.get('scope') != scope or
            data.get('expected_boot_id') != boot or type(data.get('expected_taint')) is not int or
            data['expected_taint'] not in (0, 512) or set(data.get('files', {})) != required):
        raise RuntimeError('Wrong or incomplete reviewed scope')
    for name, digest in data['files'].items():
        path = build / name
        if (not re.fullmatch(r'[0-9a-f]{64}', digest) or not path.is_file() or
                path.resolve() != path or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
            raise RuntimeError('Reviewed file missing/changed/symlinked: ' + name)
    return data


def host_allocator_pids():
    result = []
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            if path.read_bytes().split(b'\0', 1)[0] == b'/vendor/bin/hw/android.hardware.graphics.allocator@2.0-service':
                result.append(int(path.parent.name))
        except (FileNotFoundError, PermissionError):
            pass
    return sorted(result)


def boot_state():
    return dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                taint=int(Path('/proc/sys/kernel/tainted').read_text()),
                uptime=Path('/proc/uptime').read_text().split()[0])


def cursor():
    result = subprocess.run(['journalctl', '-k', '-n', '0', '--show-cursor', '--no-pager'],
                            capture_output=True, text=True, timeout=8, check=True)
    match = re.search(r'-- cursor: (\S+)', result.stdout)
    if not match:
        raise RuntimeError('No kernel-journal cursor; refusing an unobserved driver trial')
    return match[1]


def kernel_delta(before):
    result = subprocess.run(['journalctl', '-k', '--after-cursor', before, '-n', '10000',
                             '--no-pager', '-o', 'json'], capture_output=True, text=True, timeout=12, check=True)
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    failures = []
    for row in rows:
        message = row.get('MESSAGE', '')
        if isinstance(message, list):
            message = bytes(message).decode(errors='replace')
        if FAULT.search(str(message)):
            failures.append(message)
    return dict(message_count=len(rows), complete=len(rows) < 10000, fault_signatures=failures, raw_jsonl=result.stdout)


def process_proof(namespace_pid, root_pid, command):
    result = []
    for path in Path('/proc').glob('[0-9]*/status'):
        try:
            fields = dict(line.split(':', 1) for line in path.read_text().splitlines() if ':' in line)
            pids = fields.get('NSpid', '').split()
            if (pids and int(pids[-1]) == namespace_pid and
                    os.readlink(path.parent / 'ns/pid') == os.readlink(Path('/proc', root_pid, 'ns/pid')) and
                    (path.parent / 'cmdline').read_bytes().split(b'\0', 1)[0] == command.encode()):
                result.append(dict(host_pid=int(path.parent.name), namespace_pids=pids,
                                   parent_host_pid=fields.get('PPid', '').strip(), status=path.read_text(),
                                   maps=(path.parent / 'maps').read_text()))
        except (OSError, ValueError):
            pass
    return result


def run_inner(child, build, boot, hashes, runtime, runtime_log, gpu=False, composer=False):
    raw = Path('/proc', child, 'environ').read_bytes().split(b'\0')
    env = dict(item.decode().split('=', 1) for item in raw if item.startswith(b'G955N_') and b'=' in item)
    expected = dict(G955N_ANDROID_PRIVATE_RUNTIME='1', G955N_PARENT_PID_NS=os.readlink('/proc/self/ns/pid'),
                    G955N_PARENT_MOUNT_NS=os.readlink('/proc/self/ns/mnt'))
    if any(env.get(key) != value for key, value in expected.items()):
        raise RuntimeError('Private environment provenance mismatch')
    command = ['nsenter', '--target', child, '--mount', '--pid', '--root', '--wd=/',
               '/usr/bin/setpriv', '--bounding-set=-sys_admin,-mknod,-sys_rawio,-sys_module,-sys_boot',
               '--inh-caps=-all', '--ambient-caps=-all', '--no-new-privs', '/usr/bin/env', '-i',
               'HOME=/home/ubuntu', 'PATH=/usr/sbin:/usr/bin:/sbin:/bin', 'ANDROID_ROOT=/system', 'ANDROID_DATA=/data',
               *[k + '=' + v for k, v in expected.items()], '/usr/bin/python3',
               str(build / 'allocator-cpu-buffer-trial.py'), '--gles-buffer' if gpu else '--cpu-buffer', '--probe', str(build / 'headless-buffer-probe'),
               '--probe-sha256', hashes['headless-buffer-probe'], '--expected-boot-id', boot]
    if gpu:
        command += ['--plugin', str(build/'headless-buffer-gles.so'), '--plugin-sha256', hashes['headless-buffer-gles.so']]
    if composer:
        command.append('--composer-no-display')
    process = None
    output = bytearray()
    report = dict(rendering_qualified=False, gpu_tested=gpu)
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   bufsize=0, start_new_session=True)
        report['launcher_host_pid'] = process.pid
        os.set_blocking(process.stdout.fileno(), False)
        watch = selectors.DefaultSelector()
        watch.register(process.stdout, selectors.EVENT_READ, 'inner')
        watch.register(runtime.stdout, selectors.EVENT_READ, 'runtime')
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            for key, _ in watch.select(.05):
                try:
                    part = os.read(key.fd, 65536)
                except BlockingIOError:
                    continue
                if not part:
                    watch.unregister(key.fileobj)
                elif key.data == 'inner':
                    output.extend(part)
                else:
                    runtime_log.extend(part)
            if len(output) > 16 * 1024 * 1024:
                report['output_limit_exceeded'] = True; break
            match = re.search(rb'allocator_namespace_pid=(\d+)', output)
            if match and not report.get('allocator_host_processes'):
                report['allocator_host_processes'] = process_proof(int(match[1]), child,
                    '/vendor/bin/hw/android.hardware.graphics.allocator@2.0-service')
            if process.poll() is not None and not any(key.data == 'inner' for key in watch.get_map().values()):
                break
            if runtime.poll() is not None:
                report['runtime_ended_early'] = True; break
        report['exit_code'] = process.poll()
        if process.poll() is None:
            report['controller_timeout'] = True
    except Exception as error:
        report['exception'] = repr(error)
    finally:
        if process and process.poll() is None:
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(process.pid, sig)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=2)
                    break
                except subprocess.TimeoutExpired:
                    continue
        report['stdout'] = output.decode(errors='replace')
        start = report['stdout'].find('{')
        if start >= 0:
            try:
                report['lifecycle'] = json.loads(report['stdout'][start:])
            except ValueError as error:
                report['parse_error'] = repr(error)
        report['launcher_reaped'] = process is not None and process.poll() is not None
        report['allocator_host_pids_gone'] = all(not Path('/proc', str(item['host_pid'])).exists()
                                                 for item in report.get('allocator_host_processes', []))
    return report


def run(build, boot, seconds, review):
    gpu = review['scope'] in ('gles-buffer-64x64-no-display','gles-composer-no-display')
    composer = review['scope'] == 'gles-composer-no-display'
    baseline = SourceFileLoader('runtime_evidence', str(build / 'run-property-trial.py')).load_module()
    before = baseline.snapshot()
    before['allocators'] = host_allocator_pids()
    if before['properties_exist'] or before['managers'] or before['allocators']:
        raise RuntimeError('Existing global runtime detected; refusing interference')
    if composer:
        binder=Path('/sys/kernel/debug/binder/state').read_text()
        if binder.strip() != 'binder state:':
            raise RuntimeError('Composer requires an empty host Binder baseline')
        before['host_binder_inode'] = tuple((lambda n:(n.st_uid,n.st_gid,n.st_mode,n.st_rdev,n.st_ino))(Path('/dev/binder').stat()))
    state = boot_state()
    if state['boot_id'] != boot or review.get('expected_boot_id') != boot or state['taint'] != review['expected_taint']:
        raise RuntimeError('Requires the exact reviewed boot and exact explicitly pinned taint baseline')
    journal_cursor = cursor()
    # Recheck the reviewed bytes immediately before launching the namespace.
    for name, digest in review['files'].items():
        if hashlib.sha256((build / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Reviewed source changed before activation')
    result = dict(before=before, kernel_before=state, kernel_cursor_before=journal_cursor,
                  reviewed_files=review['files'], cpu_only=not gpu, gpu_tested=gpu, rendering_qualified=False)
    process = None; child = None
    log = bytearray(); collected = False
    started = time.monotonic()
    try:
        process = subprocess.Popen(['python3', str(build / 'android-runtime-namespace.py'), '--run-trial',
                                    '--runtime', str(build / 'android-property-runtime'), '--property-info', str(build / 'property_info'),
                                    '--stock-contexts', str(build / 'android-stock-service-contexts'), '--seconds', str(seconds),
                                    '--include-ion-device', *(['--include-mali-device'] if gpu else []), *(['--include-composer-ipc'] if composer else [])], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
        os.set_blocking(process.stdout.fileno(), False)
        watch = selectors.DefaultSelector(); watch.register(process.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + seconds + 20
        while time.monotonic() < deadline:
            for key, _ in watch.select(.1):
                try:
                    part = os.read(key.fd, 65536)
                except BlockingIOError:
                    continue
                if part:
                    log.extend(part)
                else:
                    watch.unregister(key.fileobj)
            text = log.decode(errors='replace')
            marker = re.search(r'namespace_host_pid=(\d+)', text)
            if marker:
                child = marker[1]
            ready = re.search(r'Real hwservicemanager readiness request committed: success=yes peer_pid=(\d+) supervised_pid=(\d+) serial=(\d+)', text)
            if ready and child and not collected:
                collected = True
                result['ready_request'] = dict(peer_pid=int(ready[1]), supervised_pid=int(ready[2]), serial=int(ready[3]))
                evidence = baseline.collect_live(child, int(ready[2]), build)
                result.update(evidence)
                client = evidence['independent_property_client']
                if int(ready[1]) != int(ready[2]) or client['exit_code'] or 'value=true ' not in client['stdout']:
                    raise RuntimeError('Actual credential-checked/shared readiness failed')
                result['cpu_buffer_diagnostic'] = run_inner(child, build, boot, review['files'], process, log, gpu=gpu, composer=composer)
            if process.poll() is not None and not watch.get_map():
                break
        result['exit_code'] = process.poll()
        if process.poll() is None:
            result['runtime_timeout'] = True
    except Exception as error:
        result['exception'] = repr(error)
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=3)
        result['runtime_stdout'] = log.decode(errors='replace')
        result['elapsed_seconds'] = round(time.monotonic()-started, 3)
        if child:
            until = time.monotonic()+2
            while Path('/proc', child).exists() and time.monotonic() < until:
                time.sleep(.05)
            result['namespace_child_gone'] = not Path('/proc', child).exists()
        result['after'] = baseline.snapshot()
        result['after']['allocators'] = host_allocator_pids()
        if composer:
            result['after']['host_binder_inode'] = tuple((lambda n:(n.st_uid,n.st_gid,n.st_mode,n.st_rdev,n.st_ino))(Path('/dev/binder').stat()))
            result['standard_binder_empty_after'] = Path('/sys/kernel/debug/binder/state').read_text().strip() == 'binder state:'
        result['parent_state_unchanged'] = before == result['after'] and (not composer or result.get('standard_binder_empty_after'))
        result['kernel_after'] = boot_state()
        try:
            result['kernel_delta'] = kernel_delta(journal_cursor)
        except Exception as error:
            result['kernel_collection_error'] = repr(error)
        contexts = result.get('live_context_hashes_verified', {})
        mounts = result.get('readonly_context_mounts', [])
        request = result.get('ready_request', {})
        result['property_runtime_passed'] = bool(result.get('exit_code') == 0 and result['elapsed_seconds'] >= seconds and
            result.get('namespace_child_gone') and result['parent_state_unchanged'] and result.get('verified_manager_processes') and
            request.get('peer_pid') == request.get('supervised_pid') and request and contexts and all(contexts.values()) and
            len(mounts) == len(contexts) and all(' ro,' in line or ' ro ' in line for line in mounts))
        diagnostic = result.get('cpu_buffer_diagnostic', {})
        delta = result.get('kernel_delta', {})
        result['passed'] = bool(result['property_runtime_passed'] and diagnostic.get('exit_code') == 0 and
            diagnostic.get('lifecycle', {}).get('gpu_buffer_passed' if gpu else 'cpu_buffer_passed') and diagnostic.get('allocator_host_processes') and
            diagnostic.get('allocator_host_pids_gone') and diagnostic.get('launcher_reaped') and
            result['kernel_after']['boot_id'] == boot and result['kernel_after']['taint'] == state['taint'] and
            delta.get('complete') and not delta.get('fault_signatures') and
            (not composer or diagnostic.get('lifecycle', {}).get('composer_no_display', {}).get('cleanup_passed')))
    return result


def selftest():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        for name in REVIEW_FILES:
            (root/name).write_bytes(name.encode())
        boot = '11111111-1111-1111-1111-111111111111'
        data = dict(target='SM-G955N', scope='cpu-buffer-64x64-no-display', expected_boot_id=boot, expected_taint=512,
                    files={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in REVIEW_FILES})
        manifest = root/'review.json'; manifest.write_text(json.dumps(data))
        expected = hashlib.sha256(manifest.read_bytes()).hexdigest()
        verify_review(root, manifest, expected, boot)
        try:
            verify_review(root, manifest, expected, '22222222-2222-2222-2222-222222222222')
        except RuntimeError:
            pass
        else:
            raise AssertionError('Review accepted on a different boot')
        for rejected in (None, 1, 513, True, '512'):
            changed = dict(data, expected_taint=rejected)
            manifest.write_text(json.dumps(changed))
            changed_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
            try:
                verify_review(root, manifest, changed_hash, boot)
            except RuntimeError:
                pass
            else:
                raise AssertionError('Invalid taint baseline accepted')
        manifest.write_text(json.dumps(data))
        expected = hashlib.sha256(manifest.read_bytes()).hexdigest()
        assert FAULT.search('WARNING: a new warning despite unchanged taint')
        assert FAULT.search('Unable to handle kernel NULL pointer dereference')
        try:
            verify_review(root, manifest, expected, boot, gpu=True)
        except RuntimeError:
            pass
        else:
            raise AssertionError('CPU review used for GPU activation')
        (root/'headless-buffer-probe').write_bytes(b'changed')
        try:
            verify_review(root, manifest, expected, boot)
        except RuntimeError:
            pass
        else:
            raise AssertionError('Changed executable accepted')
        try:
            verify_review(root, manifest, '0'*64, boot)
        except RuntimeError:
            pass
        else:
            raise AssertionError('Wrong review hash accepted')
    print('Review hash/source mutation selftests passed; no service/device access')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--cpu-buffer', action='store_true')
    mode.add_argument('--gles-buffer', action='store_true')
    mode.add_argument('--selftest', action='store_true')
    parser.add_argument('--composer-no-display', action='store_true')
    parser.add_argument('--build-dir', type=Path, default=Path('/home/ubuntu/g955n-compat-build'))
    parser.add_argument('--reviewed-manifest', type=Path)
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--expected-boot-id')
    parser.add_argument('--seconds', type=int, default=50)
    args = parser.parse_args()
    if args.selftest:
        selftest(); return 0
    if not args.cpu_buffer and not args.gles_buffer:
        parser.print_help(); return 0
    if (os.geteuid() or not 25 <= args.seconds <= 60 or
            not re.fullmatch(r'[0-9a-f]{64}', args.manifest_sha256 or '') or
            not re.fullmatch(r'[0-9a-f-]{36}', args.expected_boot_id or '') or not args.reviewed_manifest):
        parser.error('Root, reviewed manifest/hash, exact boot and 25..60 second runtime required')
    build = args.build_dir.resolve(strict=True)
    if not build.is_relative_to('/home'):
        parser.error('Use the private handset HOME staging directory')
    review = verify_review(build, args.reviewed_manifest.resolve(strict=True), args.manifest_sha256, args.expected_boot_id, gpu=args.gles_buffer, composer=args.composer_no_display)
    if ('SM-G955N' not in Path('/sys/firmware/devicetree/base/model').read_text() or
            'g955n-ubuntu' not in Path('/proc/sys/kernel/osrelease').read_text()):
        raise SystemExit('Wrong target/kernel')
    for program in ('/usr/bin/strace', '/usr/bin/nsenter', '/usr/bin/setpriv'):
        if not Path(program).is_file():
            raise SystemExit('Existing diagnostic tool unavailable: ' + program)
    result = run(build, args.expected_boot_id, args.seconds, review)
    print(json.dumps(result, indent=2))
    return 0 if result.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
