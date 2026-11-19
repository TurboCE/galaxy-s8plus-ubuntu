#!/usr/bin/env python3
"""Record one explicit, bounded, no-display/no-audio property/HWBinder trial."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
import time


def manager_pids():
    result = []
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            if path.read_bytes().split(b'\0', 1)[0].endswith(b'/hwservicemanager'):
                result.append(path.parent.name)
        except OSError:
            pass
    return result


def snapshot():
    return dict(mount_ns=os.readlink('/proc/self/ns/mnt'),
                pid_ns=os.readlink('/proc/self/ns/pid'),
                mountinfo_sha256=hashlib.sha256(Path('/proc/self/mountinfo').read_bytes()).hexdigest(),
                properties_exist=Path('/dev/__properties__').exists(), managers=manager_pids())


def collect_live(child, expected_pid, build):
    proof = subprocess.run(['nsenter', '--target', child, '--mount', '--pid', '--root', '--wd=/',
                            str(build / 'android-property-runtime'), '--read-property', 'hwservicemanager.ready'],
                           capture_output=True, text=True, timeout=6)
    result = dict(independent_property_client=dict(exit_code=proof.returncode, stdout=proof.stdout, stderr=proof.stderr))
    mounts = Path('/proc', child, 'mountinfo').read_text()
    result['readonly_context_mounts'] = [line for line in mounts.splitlines() if 'service_contexts ' in line]
    manifest = json.loads((build / 'android-stock-service-contexts/manifest.json').read_text())
    result['live_context_hashes_verified'] = {
        name: hashlib.sha256(Path('/proc', child, 'root', name).read_bytes()).hexdigest() == entry['sha256']
        for name, entry in manifest['files'].items()}
    children_file = Path('/proc', child, 'task', child, 'children')
    # CONFIG_CHECKPOINT_RESTORE/PROC_CHILDREN is absent on this vendor 4.4 kernel.
    # Always support a PPid scan rather than treating optional procfs as mandatory.
    candidates = children_file.read_text().split() if children_file.exists() else manager_pids()
    result['child_lookup'] = 'proc_children' if children_file.exists() else 'host_PPid_NSpid_scan'
    selected = []
    for pid in candidates:
        try:
            fields = dict(line.split(':', 1) for line in Path('/proc', pid, 'status').read_text().splitlines() if ':' in line)
            ns_pids = fields.get('NSpid', '').split()
            if fields.get('PPid', '').strip() == child and ns_pids and int(ns_pids[-1]) == expected_pid:
                selected.append(dict(host_pid=pid, parent_host_pid=fields['PPid'].strip(), namespace_pids=ns_pids,
                                     name=fields.get('Name', '').strip(), state=fields.get('State', '').strip()))
        except (OSError, ValueError):
            pass
    result['verified_manager_processes'] = selected
    result['binder_debug_evidence'] = {}
    for name in ['/sys/kernel/debug/binder/state', *[f'/sys/kernel/debug/binder/proc/{p["host_pid"]}' for p in selected]]:
        try:
            path = Path(name)
            if path.exists():
                result['binder_debug_evidence'][name] = path.read_text()[:524288]
        except OSError as error:
            result['binder_debug_evidence'][name] = str(error)
    return result


def run_hwc_no_devices(child, build, runtime_process, runtime_log):
    """Dependency diagnostic only; never exposes a display/audio/GPU node."""
    root = Path('/proc', child, 'root')
    forbidden = ['/dev/snd', '/dev/block', '/dev/mali0', '/dev/ion', '/dev/fb0',
                 '/dev/graphics/fb0', '/dev/sw_sync', '/efs']
    present = [name for name in forbidden if (root / name.lstrip('/')).exists()]
    mounts = Path('/proc', child, 'mountinfo').read_text().splitlines()
    sys_ro = any(line.split()[4] == '/sys' and 'ro' in line.split()[5].split(',') for line in mounts)
    if present or not sys_ro:
        return dict(refused=True, unexpected_paths=present, sys_readonly=sys_ro,
                    rendering_qualified=False)
    trace_path = '/run/g955n-hwc-no-device.strace'
    env_args = ['HOME=/home/ubuntu', 'PATH=/usr/sbin:/usr/bin:/sbin:/bin',
                'LD_LIBRARY_PATH=' + str(build.parent / 'g955n-compat-install/lib'),
                'HYBRIS_ANDROID_SDK_VERSION=28', 'HYBRIS_EGLPLATFORM=null',
                'HYBRIS_LD_LIBRARY_PATH=/system/lib64:/vendor/lib64']
    command = ['nsenter', '--target', child, '--mount', '--pid', '--root', '--wd=/',
               '/usr/bin/setpriv', '--bounding-set=-sys_admin,-mknod,-sys_rawio,-sys_module,-sys_boot',
               '--inh-caps=-all', '--ambient-caps=-all', '--no-new-privs',
               '/usr/bin/env', '-i', *env_args, '/usr/bin/strace', '-f', '-tt', '-s', '96',
               '-o', trace_path, '/usr/bin/timeout', '-k', '2s', '15s',
               str(build / 'hwc-module-probe'), '--open-hwc2-no-devices']
    data = dict(no_hardware_nodes=True, sys_readonly=True, rendering_qualified=False,
                capabilities_removed=['sys_admin', 'mknod', 'sys_rawio', 'sys_module', 'sys_boot'])
    probe = None
    output = bytearray()
    try:
        probe = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0,
                                 start_new_session=True)
        data['launcher_host_pid'] = probe.pid
        os.set_blocking(probe.stdout.fileno(), False)
        watch = selectors.DefaultSelector()
        watch.register(probe.stdout, selectors.EVENT_READ, 'probe')
        watch.register(runtime_process.stdout, selectors.EVENT_READ, 'runtime')
        deadline = time.monotonic() + 21
        while time.monotonic() < deadline:
            for key, _ in watch.select(.1):
                try:
                    chunk = os.read(key.fd, 65536)
                except BlockingIOError:
                    continue
                if not chunk:
                    watch.unregister(key.fileobj)
                elif key.data == 'probe':
                    output.extend(chunk)
                else:
                    runtime_log.extend(chunk)
            if probe.poll() is not None:
                # Drain any remaining probe output without stopping the runtime.
                try:
                    output.extend(os.read(probe.stdout.fileno(), 65536))
                except BlockingIOError:
                    pass
                break
            if runtime_process.poll() is not None:
                data['runtime_ended_before_probe'] = True
                break
        data['exit_code'] = probe.poll()
        if data['exit_code'] is None:
            data['coordinator_timeout'] = True
    except Exception as error:
        data['exception'] = repr(error)
    finally:
        if probe and probe.poll() is None:
            try:
                os.killpg(probe.pid, 15)
                probe.wait(timeout=3)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(probe.pid, 9)
                except ProcessLookupError:
                    pass
                probe.wait(timeout=3)
        data['stdout'] = output.decode(errors='replace')
        match = re.search(r'probe_namespace_pid=(\d+)', data['stdout'])
        if match:
            data['probe_namespace_pid'] = int(match[1])
        try:
            trace = root / trace_path.lstrip('/')
            if trace.exists():
                # Raw trace remains in this private diagnostic report only.
                data['strace_bytes'] = trace.stat().st_size
                data['strace_truncated'] = data['strace_bytes'] > 16777216
                data['strace'] = trace.read_text(errors='replace')[:16777216]
        except OSError as error:
            data['trace_error'] = repr(error)
        data['probe_launcher_reaped'] = probe is None or probe.poll() is not None
    return data



def run_allocator_no_ion(child, build, runtime_process, runtime_log):
    """One original allocator lifecycle; private runtime and no hardware nodes."""
    root = Path('/proc', child, 'root')
    for name in ['/efs', '/dev/block', '/dev/snd', '/dev/ion', '/dev/mali0', '/dev/fb0', '/dev/graphics/fb0', '/dev/sw_sync']:
        if (root / name.lstrip('/')).exists():
            return dict(refused=True, reason='Forbidden path: ' + name, rendering_qualified=False)
    raw_env = Path('/proc', child, 'environ').read_bytes().split(b'\0')
    private_env = dict(item.decode().split('=', 1) for item in raw_env if item.startswith(b'G955N_') and b'=' in item)
    expected = dict(G955N_ANDROID_PRIVATE_RUNTIME='1', G955N_PARENT_PID_NS=os.readlink('/proc/self/ns/pid'),
                    G955N_PARENT_MOUNT_NS=os.readlink('/proc/self/ns/mnt'))
    if any(private_env.get(k) != v for k, v in expected.items()):
        return dict(refused=True, reason='Parent namespace provenance mismatch', rendering_qualified=False)
    binary = build / 'allocator-registration-query'
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    command = ['nsenter', '--target', child, '--mount', '--pid', '--root', '--wd=/',
               '/usr/bin/setpriv', '--bounding-set=-sys_admin,-mknod,-sys_rawio,-sys_module,-sys_boot',
               '--inh-caps=-all', '--ambient-caps=-all', '--no-new-privs',
               '/usr/bin/env', '-i', 'HOME=/home/ubuntu', 'PATH=/usr/sbin:/usr/bin:/sbin:/bin',
               'ANDROID_ROOT=/system', 'ANDROID_DATA=/data', *[k + '=' + v for k, v in expected.items()],
               '/usr/bin/python3', str(build / 'allocator-no-ion-trial.py'), '--run-no-ion',
               '--query', str(binary), '--query-sha256', digest]
    data = dict(query_sha256=digest, rendering_qualified=False, allocation_tested=False)
    process = None
    output = bytearray()
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   bufsize=0, start_new_session=True)
        data['launcher_host_pid'] = process.pid
        os.set_blocking(process.stdout.fileno(), False)
        watch = selectors.DefaultSelector()
        watch.register(process.stdout, selectors.EVENT_READ, 'allocator')
        watch.register(runtime_process.stdout, selectors.EVENT_READ, 'runtime')
        deadline = time.monotonic() + 24
        while time.monotonic() < deadline:
            for key, _ in watch.select(.1):
                try:
                    chunk = os.read(key.fd, 65536)
                except BlockingIOError:
                    continue
                if not chunk:
                    watch.unregister(key.fileobj)
                elif key.data == 'allocator':
                    output.extend(chunk)
                else:
                    runtime_log.extend(chunk)
            match = re.search(rb'allocator_namespace_pid=(\d+)', output)
            if match and not data.get('verified_allocator_host_processes'):
                selected = []
                for path in Path('/proc').glob('[0-9]*/status'):
                    try:
                        fields = dict(line.split(':', 1) for line in path.read_text().splitlines() if ':' in line)
                        nspid = fields.get('NSpid', '').split()
                        if (nspid and int(nspid[-1]) == int(match[1]) and
                                os.readlink(path.parent / 'ns/pid') == os.readlink(Path('/proc', child, 'ns/pid')) and
                                (path.parent / 'cmdline').read_bytes().split(b'\0', 1)[0] ==
                                b'/vendor/bin/hw/android.hardware.graphics.allocator@2.0-service'):
                            selected.append(dict(host_pid=int(path.parent.name), namespace_pids=nspid,
                                                 parent_host_pid=fields.get('PPid', '').strip(),
                                                 uid=fields.get('Uid', '').split(), gid=fields.get('Gid', '').split(),
                                                 maps=(path.parent / 'maps').read_text()))
                    except (OSError, ValueError):
                        pass
                data['verified_allocator_host_processes'] = selected
            if process.poll() is not None:
                try:
                    output.extend(os.read(process.stdout.fileno(), 65536))
                except BlockingIOError:
                    pass
                break
            if runtime_process.poll() is not None:
                data['runtime_ended_before_allocator'] = True
                break
        data['exit_code'] = process.poll()
        if process.poll() is None:
            data['coordinator_timeout'] = True
    except Exception as error:
        data['exception'] = repr(error)
    finally:
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, 15)
                process.wait(timeout=2)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(process.pid, 9)
                except ProcessLookupError:
                    pass
                process.wait(timeout=2)
        data['stdout'] = output.decode(errors='replace')
        start = data['stdout'].find('{')
        if start >= 0:
            try:
                data['lifecycle'] = json.loads(data['stdout'][start:])
            except ValueError as error:
                data['report_parse_error'] = repr(error)
        data['launcher_reaped'] = process is None or process.poll() is not None
        data['verified_allocator_host_pids_gone'] = all(not Path('/proc', str(p['host_pid'])).exists()
                                                         for p in data.get('verified_allocator_host_processes', []))
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-trial', action='store_true')
    parser.add_argument('--seconds', type=int, default=30)
    parser.add_argument('--hwc-open-no-devices', action='store_true',
                        help='After verified real readiness, run a bounded dependency-only HWC probe without hardware nodes')
    parser.add_argument('--allocator-no-ion', action='store_true',
                        help='Explicit original allocator ten-second lifecycle without ION/GPU/display/audio nodes')
    parser.add_argument('--build-dir', type=Path, default=Path('/home/ubuntu/g955n-compat-build'))
    args = parser.parse_args()
    if not args.run_trial:
        parser.print_help()
        return 0
    if (os.geteuid() or 'SM-G955N' not in Path('/proc/device-tree/model').read_text() or
            'g955n-ubuntu' not in Path('/proc/sys/kernel/osrelease').read_text() or not 1 <= args.seconds <= 300):
        raise SystemExit('Requires root on native G955N with a bounded duration')
    if args.allocator_no_ion and args.hwc_open_no_devices:
        raise SystemExit('Coordinate one diagnostic at a time')
    if args.allocator_no_ion:
        if args.seconds < 30 or not Path('/usr/bin/setpriv').is_file():
            raise SystemExit('Allocator lifecycle needs at least 30 seconds and capability tools')
    if args.hwc_open_no_devices:
        if args.seconds < 25 or not all(Path(p).is_file() for p in ['/usr/bin/setpriv', '/usr/bin/strace', '/usr/bin/timeout']):
            raise SystemExit('Bounded HWC dependency mode needs at least 25 seconds and existing trace/capability tools')
    before = snapshot()
    if before['properties_exist'] or before['managers']:
        raise SystemExit('Existing host Android runtime detected; refusing interference')
    build = args.build_dir.resolve(strict=True)
    result = dict(before=before)
    process = None
    log = bytearray()
    child = None
    collected = False
    started = time.monotonic()
    try:
        process = subprocess.Popen(['python3', str(build / 'android-runtime-namespace.py'), '--run-trial',
                                    '--runtime', str(build / 'android-property-runtime'),
                                    '--property-info', str(build / 'property_info'),
                                    '--stock-contexts', str(build / 'android-stock-service-contexts'),
                                    '--seconds', str(args.seconds)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
        os.set_blocking(process.stdout.fileno(), False)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + args.seconds + 25
        while time.monotonic() < deadline:
            for key, _ in selector.select(.2):
                try:
                    chunk = os.read(key.fd, 65536)
                except BlockingIOError:
                    continue
                if chunk:
                    log.extend(chunk)
                else:
                    selector.unregister(key.fileobj)
            text = log.decode(errors='replace')
            match = re.search(r'namespace_host_pid=(\d+)', text)
            if match:
                child = match.group(1)
            ready = re.search(r'Real hwservicemanager readiness request committed: success=yes peer_pid=(\d+) supervised_pid=(\d+) serial=(\d+)', text)
            if not collected and child and ready:
                collected = True
                result['ready_request'] = dict(peer_pid=int(ready[1]), supervised_pid=int(ready[2]), serial=int(ready[3]))
                try:
                    result.update(collect_live(child, int(ready[2]), build))
                    if args.hwc_open_no_devices or args.allocator_no_ion:
                        client = result.get('independent_property_client', {})
                        if int(ready[1]) != int(ready[2]) or client.get('exit_code') or 'value=true ' not in client.get('stdout', ''):
                            key = 'allocator_no_ion_diagnostic' if args.allocator_no_ion else 'hwc_no_device_diagnostic'
                            result[key] = dict(refused=True, reason='Real shared readiness not verified', rendering_qualified=False)
                        elif args.allocator_no_ion:
                            result['allocator_no_ion_diagnostic'] = run_allocator_no_ion(child, build, process, log)
                        else:
                            result['hwc_no_device_diagnostic'] = run_hwc_no_devices(child, build, process, log)
                except Exception as error:
                    # Evidence collection must not tear down an otherwise valid trial.
                    result['evidence_collection_error'] = repr(error)
            if process.poll() is not None and not selector.get_map():
                break
        if process.poll() is None:
            result['coordinator_timeout'] = True
        else:
            result['exit_code'] = process.returncode
    except Exception as error:
        result['exception'] = repr(error)
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        result['stdout'] = log.decode(errors='replace')
        result['elapsed_seconds'] = round(time.monotonic() - started, 3)
        if child:
            deadline = time.monotonic() + 2
            while Path('/proc', child).exists() and time.monotonic() < deadline:
                time.sleep(.1)
            result['namespace_child_gone'] = not Path('/proc', child).exists()
        result['after'] = snapshot()
        result['parent_state_unchanged'] = result['before'] == result['after']
        request = result.get('ready_request', {})
        result['passed'] = (result.get('exit_code') == 0 and result['elapsed_seconds'] >= args.seconds and
                            result.get('namespace_child_gone') and result['parent_state_unchanged'] and
                            request.get('peer_pid') == request.get('supervised_pid') and bool(request) and
                            result.get('independent_property_client', {}).get('exit_code') == 0 and
                            'value=true ' in result.get('independent_property_client', {}).get('stdout', '') and
                            bool(result.get('verified_manager_processes')) and
                            bool(result.get('live_context_hashes_verified')) and
                            all(result.get('live_context_hashes_verified', {}).values()) and
                            len(result.get('readonly_context_mounts', [])) == len(result.get('live_context_hashes_verified', {})) and
                            all(' ro,' in line or ' ro ' in line for line in result.get('readonly_context_mounts', [])))
        result['property_runtime_passed'] = result['passed']
        if args.allocator_no_ion:
            diagnostic = result.get('allocator_no_ion_diagnostic', {})
            result['allocator_registration_passed'] = bool(
                result['passed'] and diagnostic.get('exit_code') == 0 and
                diagnostic.get('lifecycle', {}).get('allocator_registration_passed') and
                diagnostic.get('verified_allocator_host_processes') and
                diagnostic.get('verified_allocator_host_pids_gone') and diagnostic.get('launcher_reaped'))
        if args.hwc_open_no_devices or args.allocator_no_ion:
            result['gpu_rendering_qualified_by_this_trial'] = False
        print(json.dumps(result, indent=2))
    return 0 if result.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
