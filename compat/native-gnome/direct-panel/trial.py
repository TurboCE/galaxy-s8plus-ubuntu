#!/usr/bin/env python3
"""Install, trial or restore direct output for the SM-G955N GNOME session."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

PREFIX = Path('/opt/g955n-native-gpu')
KEY = 'lib/libhybris/eglplatform_x11.so'
LIBRARY = PREFIX / KEY
MANIFEST = PREFIX / 'manifest.json'
LAUNCHER = PREFIX / 'session.py'
FILES = (LIBRARY, MANIFEST, LAUNCHER)
BACKUP = Path('/var/lib/g955n/direct-panel-trial')
LEASE = Path('/run/lock/g955n-direct-panel-trial')
TIMER = 'g955n-direct-panel-rollback'
CONTROLLER = Path('/usr/local/sbin/g955n-direct-panel-trial')
RECOVERY = 'g955n-direct-panel-recover.service'
CONTROL_LOCK = Path('/run/lock/g955n-direct-panel-control')
DEFAULT = BACKUP / 'enabled-default.json'
SHELL_DATA = PREFIX / 'direct-shell'
STOCK_MODE = Path('/usr/share/gnome-shell/modes/ubuntu.json')
PRIVATE_MODE = SHELL_DATA / 'gnome-shell/modes/ubuntu.json'
EXTENSION_ID = 'g955n-direct-panel@local'
EXTENSION = SHELL_DATA / 'gnome-shell/extensions' / EXTENSION_ID
POLICY_FILES = (EXTENSION / 'extension.js', EXTENSION / 'metadata.json', PRIVATE_MODE)
KERNEL_NOTES = Path('/sys/kernel/notes')
KERNEL36_NOTES_SHA256 = '1bc70f6013b1af4529cef38d8ce0d9529103cd1f9e4b03bdbe0842b11716d01b'


def sync_directory(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def replace(path, data, mode=None):
    if mode is None:
        mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    fd, name = tempfile.mkstemp(prefix='.direct-output-', dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            os.fchmod(stream.fileno(), mode)
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(path)
        sync_directory(path.parent)
    finally:
        temp.unlink(missing_ok=True)


def ctl(*args):
    subprocess.run(['systemctl', *args], check=True, timeout=45)


def remove_backup():
    # Retire all snapshots together after the original files are durable.
    with tempfile.TemporaryDirectory(prefix='.direct-panel-cleanup-', dir=BACKUP.parent) as stage:
        BACKUP.rename(Path(stage) / BACKUP.name)
        sync_directory(BACKUP.parent)


def restore_files():
    LEASE.unlink(missing_ok=True)
    for path in FILES:
        snapshot = BACKUP / path.name
        mode = stat.S_IMODE(snapshot.stat().st_mode)
        replace(path, snapshot.read_bytes(), mode)


def restore():
    subprocess.run(['systemctl', 'stop', TIMER + '.timer'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   timeout=15)
    if not BACKUP.exists():
        return
    ctl('stop', 'gdm.service')
    restore_files()
    ctl('restart', 'g955n-fb-display.service')
    ctl('start', 'gdm.service')
    remove_backup()


def create_lease():
    fd = os.open(LEASE, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o644)
    os.close(fd)


def qualified_kernel():
    version = subprocess.check_output(['uname', '-v'], text=True)
    if version.startswith('#32 '):
        return True
    if not version.startswith('#36 '):
        return False
    try:
        return digest(KERNEL_NOTES.read_bytes()) == KERNEL36_NOTES_SHA256
    except OSError:
        return False


def default_hashes():
    return {str(path.relative_to(PREFIX)): digest(path.read_bytes())
            for path in (*FILES, *POLICY_FILES)}


def prepare_shell_policy():
    for path in (*POLICY_FILES[:2], EXTENSION, EXTENSION.parent, SHELL_DATA):
        info = path.stat()
        if info.st_uid or info.st_mode & 0o022:
            raise RuntimeError(f'Untrusted GNOME shell policy: {path}')
    mode = json.loads(STOCK_MODE.read_text())
    extensions = mode.get('enabledExtensions')
    if not isinstance(extensions, list) or EXTENSION_ID in extensions:
        raise RuntimeError('Unexpected stock Ubuntu GNOME shell mode')
    extensions.append(EXTENSION_ID)
    PRIVATE_MODE.parent.mkdir(parents=True, exist_ok=True)
    replace(PRIVATE_MODE, json.dumps(mode, indent=2).encode())


def prepare_boot():
    if LEASE.exists() or not BACKUP.exists():
        return
    if DEFAULT.is_file() and qualified_kernel():
        try:
            hashes = json.loads(DEFAULT.read_text())
            if hashes == default_hashes():
                create_lease()
                return
        except (OSError, ValueError) as error:
            print(f'Direct output boot verification: {error}', file=sys.stderr)
    restore_files()
    remove_backup()


def run(candidate, expected, default):
    if LEASE.exists() or BACKUP.exists():
        raise RuntimeError('A previous trial still has state; restore it before staging another')
    if b'pan_with_trial_lease' not in Path('/usr/local/sbin/g955n-fb-display').read_bytes():
        raise RuntimeError('The installed framebuffer service does not honor the trial lease')
    ctl('is-active', 'g955n-fb-display.service', 'gdm.service')
    prepare_shell_policy()
    data = candidate.read_bytes()
    if digest(data) != expected:
        raise RuntimeError('Candidate checksum mismatch')
    original = {path: path.read_bytes() for path in FILES}
    manifest = json.loads(original[MANIFEST])
    if manifest['target'] != 'SM-G955N' or digest(original[LIBRARY]) != manifest['files'][KEY]['sha256']:
        raise RuntimeError('The installed GPU prefix does not match its manifest')
    marker = b' original=dict(os.environ);env=environment(original)'
    cleanup = b"keys=sorted(set(ENV)|set(REMOVE))"
    if (original[LAUNCHER].count(marker) != 1 or original[LAUNCHER].count(cleanup) != 1
            or b'G955N_DIRECT_PANEL_TRIAL' in original[LAUNCHER]):
        raise RuntimeError('Unexpected GNOME launcher')
    with tempfile.TemporaryDirectory(prefix='.direct-panel-backup-', dir=BACKUP.parent) as stage:
        snapshot = Path(stage) / BACKUP.name
        snapshot.mkdir(mode=0o700)
        for path, content in original.items():
            with (snapshot / path.name).open('wb') as stream:
                os.fchmod(stream.fileno(), stat.S_IMODE(path.stat().st_mode))
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        sync_directory(snapshot)
        snapshot.rename(BACKUP)
        sync_directory(BACKUP.parent)

    # Schedule recovery on the phone before interrupting its desktop.
    try:
        subprocess.run(['systemd-run', '--collect', f'--unit={TIMER}', '--on-active=150s',
                        sys.executable, str(Path(__file__).resolve()), '--restore-trial'],
                       check=True, timeout=15)
    except (subprocess.SubprocessError, OSError):
        remove_backup()
        raise
    try:
        ctl('stop', 'gdm.service')
        create_lease()
        # Reopen the legacy presenter while GDM is stopped. All future pans
        # will go through the lease, including the next greeter.
        ctl('restart', 'g955n-fb-display.service')
        manifest['files'][KEY]['sha256'] = expected
        replace(LIBRARY, data)
        replace(MANIFEST, json.dumps(manifest, indent=2).encode())
        settings = b"\n env.pop('G955N_DIRECT_PANEL_TRIAL',None)\n"
        settings += b" if Path('/run/lock/g955n-direct-panel-trial').is_file():\n"
        settings += b"  env['G955N_DIRECT_PANEL_TRIAL']='1'\n"
        settings += (b"  env['XDG_DATA_DIRS']="
                     + repr(str(SHELL_DATA) + ':').encode()
                     + b"+(original.get('XDG_DATA_DIRS') or '/usr/local/share:/usr/share')\n")
        # Include the two dynamic keys in logout cleanup.
        launcher = original[LAUNCHER].replace(marker, marker + settings.rstrip(b"\n"))
        launcher = launcher.replace(cleanup,
            b"keys=sorted(set(ENV)|set(REMOVE)|{'XDG_DATA_DIRS','G955N_DIRECT_PANEL_TRIAL'})")
        replace(LAUNCHER, launcher)
        ctl('start', 'gdm.service')
        if default:
            hashes = default_hashes()
            with DEFAULT.open('x') as marker:
                json.dump(hashes, marker)
                marker.flush()
                os.fsync(marker.fileno())
            sync_directory(BACKUP)
    except (subprocess.SubprocessError, OSError):
        restore()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--candidate', type=Path)
    mode.add_argument('--restore', action='store_true')
    mode.add_argument('--restore-trial', action='store_true')
    mode.add_argument('--boot-recover', action='store_true')
    parser.add_argument('--sha256')
    parser.add_argument('--enable-default', action='store_true')
    args = parser.parse_args()
    if os.getuid() or b'SM-G955N' not in Path('/proc/device-tree/model').read_bytes():
        raise RuntimeError('Requires root on the SM-G955N')
    with CONTROL_LOCK.open('a') as control:
        if args.boot_recover:
            # GDM can be starting while a trial controller holds the lock.
            # A live lease means the snapshots belong to the current boot.
            if LEASE.exists() or not BACKUP.exists():
                return
            fcntl.flock(control, fcntl.LOCK_EX | fcntl.LOCK_NB)
            prepare_boot()
            return
        fcntl.flock(control, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.restore or args.restore_trial:
            if args.restore or not DEFAULT.exists():
                restore()
            return
        if not args.sha256:
            parser.error('--candidate requires --sha256')
        if not qualified_kernel():
            raise RuntimeError('Direct output requires a reviewed display kernel build')
        if Path('/proc/sys/kernel/tainted').read_text().strip() != '0':
            raise RuntimeError('Expected an untainted kernel before the trial')
        # The delayed root recovery must invoke a trusted copy of this file.
        own_file = Path(__file__).resolve()
        if own_file != CONTROLLER:
            raise RuntimeError(f'Install the trial controller at {CONTROLLER}')
        for path in (own_file, *own_file.parents):
            info = path.stat()
            if info.st_uid or info.st_mode & 0o022:
                raise RuntimeError('Install the trial controller under a root-owned prefix')
        ctl('is-enabled', RECOVERY)
        run(args.candidate, args.sha256, args.enable_default)


if __name__ == '__main__':
    main()
