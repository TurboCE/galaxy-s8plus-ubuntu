#!/usr/bin/env python3
"""Container-only real mount/permission rollback tests with synthetic null nodes.

Never a handset/GPU qualification. Requires a fresh disposable Linux container
with SYS_ADMIN, no device/host mounts and no network. Default prints help.
"""
import argparse
import ctypes
import grp
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import pwd
import signal
import stat
import subprocess
import sys
import time
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-in-isolated-container',action='store_true');a=p.parse_args()
if not a.run_in_isolated_container:p.print_help();raise SystemExit(0)
if sys.platform!='linux' or os.getpid()!=1 or os.environ.get('G955N_NATIVE_LEASE_TEST_CONTAINER')!='1' or not Path('/.dockerenv').exists():raise SystemExit('Disposable container PID1 only')
if Path('/proc/device-tree/model').exists() and b'SM-G955N' in Path('/proc/device-tree/model').read_bytes():raise SystemExit('Never run on handset')
m=SourceFileLoader('lease_under_test','/compat/host-pid-gui.py').load_module();m.UNIT='/';m.LEASE_UNITS=('/',*m.LEASE_UNITS)
assert not m.LEASE.exists() and not Path('/dev/__properties__').exists()
assert all(not Path('/dev',name).exists() for name in m.NODES)
try:grp.getgrnam('video')
except KeyError:subprocess.run(['groupadd','-g','44','video'],check=True)
try:pwd.getpwnam('ubuntu')
except KeyError:subprocess.run(['useradd','-u','1000','-m','ubuntu'],check=True)
subprocess.run(['usermod','-aG','video','ubuntu'],check=True)
for name in m.NODES:os.mknod('/dev/'+name,stat.S_IFCHR|0o600,os.makedev(1,3))
original={name:m.node_state(Path('/dev',name)) for name in m.NODES}
root=Path('/run/g955n-native-property-source');root.mkdir(mode=0o700);area=root/'properties';area.mkdir(mode=0o711);area.chmod(0o711);(area/'property_info').write_bytes(b'synthetic lifecycle-only metadata')
r,w=os.pipe();child=os.fork()
if not child:
 os.close(r)
 if ctypes.CDLL(None).unshare(0x20000):os._exit(20)
 subprocess.run(['mount','--make-rprivate','/'],check=True)
 subprocess.run(['mount','-t','tmpfs','-o','mode=755,size=1m','lease-test-dev','/dev'],check=True)
 Path('/dev/__properties__').mkdir(mode=0o711)
 subprocess.run(['mount','--bind',str(area),'/dev/__properties__'],check=True)
 os.write(w,b'1');os.close(w)
 while True:signal.pause()
os.close(w)
assert os.read(r,1)==b'1';os.close(r)
def restored():
 assert not m.LEASE.exists() and not Path('/dev/__properties__').exists()
 assert {name:m.node_state(Path('/dev',name)) for name in m.NODES}==original
try:
 lease=m.NativeLease(child,owner_unit='/');lease.acquire()
 assert os.statvfs('/dev/__properties__').f_flag&os.ST_RDONLY
 assert Path('/dev/__properties__/property_info').read_bytes()==b'synthetic lifecycle-only metadata'
 assert all(m.node_state(Path('/dev',n))['gid']==grp.getgrnam('video').gr_gid for n in m.NODES)
 lease.release();restored()
 lease=m.NativeLease(child,owner_unit='/');lease.acquire();del lease
 assert m.restore_native_lease('/');restored()
 real_run=m.subprocess.run;fired=[False]
 def fail_remount(command,*args,**kwargs):
  if not fired[0] and 'remount,bind,ro' in command:fired[0]=True;raise OSError('injected remount failure')
  return real_run(command,*args,**kwargs)
 m.subprocess.run=fail_remount
 try:
  try:m.NativeLease(child,owner_unit='/').acquire()
  except OSError:pass
  else:raise AssertionError('Expected remount failure')
 finally:m.subprocess.run=real_run
 restored()
 real_chmod=m.os.chmod;fired=[False]
 def fail_policy(path,mode,*args,**kwargs):
  if str(path)=='/dev/hwbinder' and mode==0o660 and not fired[0]:fired[0]=True;raise OSError('injected policy failure')
  return real_chmod(path,mode,*args,**kwargs)
 m.os.chmod=fail_policy
 try:
  try:m.NativeLease(child,owner_unit='/').acquire()
  except OSError:pass
  else:raise AssertionError('Expected policy failure')
 finally:m.os.chmod=real_chmod
 restored()
 lease=m.NativeLease(child,owner_unit='/');lease.acquire();record=json.loads(m.LEASE.read_text());changed={**record,'boot_id':'wrong-boot'};m.save_lease(changed)
 try:m.restore_native_lease('/')
 except RuntimeError:pass
 else:raise AssertionError('Wrong boot restored')
 m.save_lease(record);m.LEASE.chmod(0o644)
 try:m.restore_native_lease('/')
 except RuntimeError:pass
 else:raise AssertionError('Unsafe record mode restored')
 m.LEASE.chmod(0o600);lease.release();restored()
 lease=m.NativeLease(child,owner_unit='/');lease.acquire()
 assert m.restore_native_lease('g955n-native-gpu.service',skip_other_owner=True) is False
 assert m.LEASE.exists();lease.release();restored()
 print('Native lease passed real RO bind, normal/independent restore, remount/policy interruption rollback, wrong boot/mode and owner separation; synthetic container devices only')
finally:
 if m.LEASE.exists():m.restore_native_lease('/')
 os.kill(child,signal.SIGKILL);os.waitpid(child,0)
