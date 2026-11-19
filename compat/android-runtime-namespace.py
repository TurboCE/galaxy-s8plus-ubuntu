#!/usr/bin/env python3
"""Explicit, bounded private PID/mount namespace for a real Android HAL trial.

Without an explicit mode this only prints help. The outer supervisor keeps the
host child PID and handles timeout/cleanup; the child becomes namespace PID 1,
uses a fresh read-only procfs and never runs Android init. Coordinate any real
namespace/property-service trial with the port owner before invocation.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import time


EXPECTED_INFO = 'da0513e6390829ebeb5dd2508ceaeb24e42460550b423fd37b0fdec2e16358cc'

EXPECTED_BOOT = '6de0f78b0f5f6476cf1ad91bc4871c32160769735847596c530401630e027862'
EXPECTED_CONTEXTS = {
    'plat_hwservice_contexts': '852ec77ce415d58b891876eb65cfdcfb2eaedc56302a55630670437282a3fbe7',
    'vendor_hwservice_contexts': '0c1471d080d64fd83875db80b8e99b0f73f76071cd6a12a1293f17e2e00abe04',
    'plat_service_contexts': 'c675be2152d01917dea926c7d81dbd6eec90e0dac386d16302e6c31dc185ef33',
    'vendor_service_contexts': '75e32f537e4d8064bbaa18b5b5f18b1ea4ffaa884b92546c3f1d0191a0a1f577',
    'vndservice_contexts': '8af15238f049b12f98625504d850b33d02a6ea3f7c96c30dadce51c1c874747c',
}


def run(*args):
    subprocess.run(args, check=True)


def bind_readonly(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    run('mount', '--bind', str(source), str(destination))
    run('mount', '-o', 'remount,bind,ro', str(destination))


def prepare_child(runtime, info_bytes, system, devices, library_dirs, seconds,
                  namespace_selftest, permissions_selftest, parent_pid, parent_pid_ns, parent_mount_ns, contexts):
    libc = ctypes.CDLL(None, use_errno=True)
    # If the outer supervisor disappears, killing namespace PID 1 also kills
    # all of its descendants and releases their private mounts.
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0):  # PR_SET_PDEATHSIG
        raise OSError(ctypes.get_errno(), 'Unable to set parent-death cleanup')
    if not Path(f'/proc/{parent_pid}').exists():
        raise SystemExit('Outer supervisor exited before isolation setup')
    if os.getpid() != 1:
        raise SystemExit('Child did not enter a fresh PID namespace')
    if libc.unshare(0x00020000):  # CLONE_NEWNS, only this child changes mounts.
        raise OSError(ctypes.get_errno(), 'Unable to create private mount namespace')
    run('mount', '--make-rprivate', '/')
    run('mount', '-t', 'tmpfs', '-o', 'mode=0700,size=64m', 'g955n-private-run', '/run')
    root = Path('/run/g955n-android-root')
    root.mkdir(mode=0o755)
    root.chmod(0o755)  # Outer host staging keeps umask077; chroot / must be traversable.
    (root / 'android').mkdir(mode=0o755)
    (root / 'android').chmod(0o755)
    context_stage = Path('/run/g955n-stock-service-contexts')
    context_stage.mkdir(mode=0o700)
    for name, payload in contexts.items():
        source = context_stage / name
        source.write_bytes(payload)
        source.chmod(0o444)
        target = root / name
        target.touch(mode=0o444)
        run('mount', '--bind', str(source), str(target))
        run('mount', '-o', 'remount,bind,ro', str(target))
    for name, source, link in library_dirs:
        target = root / name
        if link is not None:
            target.symlink_to(link)
        else:
            bind_readonly(source, target)
    (root / 'proc').mkdir(mode=0o755)
    # Do not bind host procfs: /proc/1/root and /proc/*/fd must not expose the
    # original filesystem/processes to the Android runtime.
    run('mount', '-t', 'proc', '-o', 'ro,nosuid,nodev,noexec', 'proc', str(root / 'proc'))
    bind_readonly('/sys', root / 'sys')
    bind_readonly(system, root / 'system')
    bind_readonly(system / 'vendor', root / 'vendor')
    bind_readonly(system, root / 'android/system')
    for name in ('data', 'tmp', 'run', 'dev'):
        (root / name).mkdir(mode=0o755)
        (root / name).chmod(0o755)
    (root / 'tmp').chmod(0o1777)
    run('mount', '-t', 'tmpfs', '-o', 'mode=0755,size=16m', 'g955n-private-dev', str(root / 'dev'))
    for name, mode, number in devices:
        target = root / 'dev' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        os.mknod(target, stat.S_IFCHR | stat.S_IMODE(mode), number)
        target.chmod(stat.S_IMODE(mode))  # Preserve only this new private node's original access mode.
        if name == 'hwbinder':
            # Private RPC only: root manager/query plus the assessed graphics
            # GID1003 service. Do not chmod/chown the original native node.
            os.chown(target, 0, 1003)
            target.chmod(0o660)
    properties = root / 'dev/__properties__'
    properties.mkdir(mode=0o711)
    properties.chmod(0o711)
    (root / 'dev/socket').mkdir(mode=0o755)
    (root / 'dev/socket').chmod(0o755)
    path = properties / 'property_info'
    path.write_bytes(info_bytes)
    path.chmod(0o644)
    env = {key: value for key, value in os.environ.items()
           if key not in ('LD_LIBRARY_PATH', 'LD_PRELOAD') and not key.startswith('HYBRIS_')}
    env.update(G955N_ANDROID_PRIVATE_RUNTIME='1',
               G955N_PARENT_PID_NS=parent_pid_ns,
               G955N_PARENT_MOUNT_NS=parent_mount_ns,
               ANDROID_ROOT='/system', ANDROID_DATA='/data')
    os.chroot(root)
    os.chdir('/')
    child_pid_ns = os.readlink('/proc/self/ns/pid')
    child_mount_ns = os.readlink('/proc/self/ns/mnt')
    if (child_pid_ns == parent_pid_ns or child_mount_ns == parent_mount_ns or
            os.getpid() != 1 or Path('/proc/1/root/efs').exists()):
        raise SystemExit('Private PID/mount/proc isolation check failed')
    mounts = Path('/proc/self/mountinfo').read_text()
    if not any(' /proc ro' in line and ' - proc ' in line for line in mounts.splitlines()):
        raise SystemExit('Fresh read-only procfs missing')
    print('namespace_pid=1 fresh_proc_readonly=yes host_proc_hidden=yes', flush=True)
    if permissions_selftest:
        arguments = [str(runtime), '--permissions-selftest']
    elif namespace_selftest:
        arguments = [str(runtime), '--namespace-selftest']
    else:
        arguments = [str(runtime), '--serve', '/system/bin/hwservicemanager', str(seconds)]
    os.execve(runtime, arguments, env)


def supervise(pid, seconds):
    stopping = False
    reaped = False

    def request_stop(_signal, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    deadline = time.monotonic() + seconds + 20
    try:
        while not stopping and time.monotonic() < deadline:
            found, status = os.waitpid(pid, os.WNOHANG)
            if found == pid:
                reaped = True
                return os.waitstatus_to_exitcode(status)
            time.sleep(0.1)
        return 124
    finally:
        if not reaped:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            limit = time.monotonic() + 3
            while time.monotonic() < limit:
                found, _status = os.waitpid(pid, os.WNOHANG)
                if found == pid:
                    reaped = True
                    break
                time.sleep(0.1)
            if not reaped:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                os.waitpid(pid, 0)
        print('Private namespace child reaped; no host mount changes made', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--run-trial', action='store_true')
    mode.add_argument('--namespace-selftest', action='store_true')
    mode.add_argument('--permissions-selftest', action='store_true',
                      help='Only private property-area initialization plus unprivileged file/exec-access checks; no manager/HAL')
    parser.add_argument('--runtime', type=Path)
    parser.add_argument('--property-info', type=Path)
    parser.add_argument('--stock-contexts', type=Path, help='Private selected context files/manifest from verified stock BOOT')
    parser.add_argument('--seconds', type=int, default=45)
    parser.add_argument('--include-display-devices', action='store_true',
                        help='Expose display nodes only for a separately coordinated HWC trial; no open here')
    args = parser.parse_args()
    if not (args.run_trial or args.namespace_selftest or args.permissions_selftest):
        parser.print_help()
        return 0
    if not args.runtime or not args.property_info or not 1 <= args.seconds <= 300:
        raise SystemExit('Supply a built runtime, staged metadata and a bounded duration')
    if (os.geteuid() or 'SM-G955N' not in Path('/proc/device-tree/model').read_text() or
            'g955n-ubuntu' not in Path('/proc/sys/kernel/osrelease').read_text()):
        raise SystemExit('Requires root on verified native G955N')
    runtime = args.runtime.resolve(strict=True)
    metadata = args.property_info.resolve(strict=True)
    if not runtime.is_relative_to('/home') or not runtime.is_file():
        raise SystemExit('Stage the executable in the handset private /home build directory')
    info_bytes = metadata.read_bytes()
    if len(info_bytes) != 128 or hashlib.sha256(info_bytes).hexdigest() != EXPECTED_INFO:
        raise SystemExit('Metadata differs from the AOSP-parser-verified 128-byte layout')
    system = Path('/android/system')
    filesystem = json.loads(subprocess.check_output(
        ['findmnt', '-J', '-T', str(system), '-o', 'TARGET,SOURCE,FSTYPE,OPTIONS'], text=True))['filesystems'][0]
    if (filesystem['target'] != str(system) or 'ro' not in filesystem['options'].split(',') or
            filesystem['fstype'] != 'ext4'):
        raise SystemExit('Requires the already verified read-only own-device SYSTEM mount')
    if not (system / 'bin/hwservicemanager').is_file() or not (system / 'bin/linker64').is_file():
        raise SystemExit('Stock Android runtime files unavailable')
    contexts = {}
    if args.stock_contexts:
        directory = args.stock_contexts.resolve(strict=True)
        manifest = json.loads((directory / 'manifest.json').read_text())
        if (manifest.get('target') != 'SM-G955N' or not manifest.get('verified') or
                manifest.get('stock_boot_sha256') != EXPECTED_BOOT):
            raise SystemExit('Unverified original service-context provenance')
        for name, entry in manifest['files'].items():
            if name not in EXPECTED_CONTEXTS:
                raise SystemExit('Unexpected service-context file')
            payload = (directory / name).read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            if (digest != EXPECTED_CONTEXTS[name] or digest != entry.get('sha256') or
                    len(payload) != entry.get('bytes') or entry.get('archive_path') != name):
                raise SystemExit('Original service-context checksum mismatch')
            contexts[name] = payload
    if args.run_trial and not {'plat_hwservice_contexts', 'vendor_hwservice_contexts'} <= contexts.keys():
        raise SystemExit('Supply verified original hardware-service contexts before another real trial')
    names = ['null', 'zero', 'random', 'urandom', 'binder', 'hwbinder', 'vndbinder', 'ashmem']
    if args.include_display_devices:
        names += ['mali0', 'ion', 'fb0', 'graphics/fb0', 'sw_sync']
    devices = []
    for name in names:
        try:
            info = (Path('/dev') / name).stat()
        except FileNotFoundError:
            continue
        if not stat.S_ISCHR(info.st_mode):
            raise SystemExit('Expected a character device: ' + name)
        devices.append((name, info.st_mode, info.st_rdev))
    if not any(name == 'hwbinder' for name, *_ in devices):
        raise SystemExit('HWBinder character device unavailable')
    for cmdline in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            process = cmdline.read_bytes().split(b'\0', 1)[0]
        except (OSError, PermissionError):
            continue
        if process.endswith(b'/hwservicemanager'):
            raise SystemExit('An existing hwservicemanager is running')
    library_dirs = []
    for name in ('usr', 'bin', 'sbin', 'lib', 'lib64', 'etc', 'home'):
        source = Path('/') / name
        if source.is_symlink():
            library_dirs.append((name, None, os.readlink(source)))
        elif source.is_dir():
            library_dirs.append((name, source, None))
    parent_pid = os.getpid()
    parent_pid_ns = os.readlink('/proc/self/ns/pid')
    parent_mount_ns = os.readlink('/proc/self/ns/mnt')
    os.umask(0o077)
    libc = ctypes.CDLL(None, use_errno=True)
    # Only future children enter the new PID namespace; the supervisor retains
    # its host PID and original mount namespace throughout the trial.
    if libc.unshare(0x20000000):  # CLONE_NEWPID
        raise OSError(ctypes.get_errno(), 'Unable to prepare private PID namespace')
    pid = os.fork()
    if not pid:
        try:
            prepare_child(runtime, info_bytes, system, devices, library_dirs, args.seconds,
                          args.namespace_selftest, args.permissions_selftest, parent_pid, parent_pid_ns, parent_mount_ns, contexts)
        except BaseException as error:
            print('Private namespace setup failed: ' + str(error), flush=True)
            os._exit(1)
    print('namespace_host_pid=' + str(pid), flush=True)
    return supervise(pid, args.seconds)


if __name__ == '__main__':
    raise SystemExit(main())
