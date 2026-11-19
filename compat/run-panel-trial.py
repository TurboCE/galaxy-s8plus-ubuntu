#!/usr/bin/env python3
"""Explicit bounded HWC panel trial; default/help never changes a service.

Use --launch only from the verified phone, with an exact reviewed manifest.
The systemd unit owns the deadline and an independent ExecStopPost restoration.
No flashing, partition write, global GL replacement or automatic login.
"""
import argparse
import base64
import socket
import shutil
import ctypes
import fcntl
import hashlib
import json
import os
import pwd
from pathlib import Path
import re
import selectors
import signal
import stat
import struct
import subprocess
import tempfile
import time
from importlib.machinery import SourceFileLoader

BASE=Path(__file__).resolve().parent
STATE=Path('/run/g955n-panel-state.json')
PREFIX=Path('/home/ubuntu/g955n-compositor')
UNIT='g955n-panel-trial.service'
FILES={'run-panel-trial.py','run-cpu-buffer-trial.py','allocator-cpu-buffer-trial.py',
       'allocator-no-ion-trial.py','run-property-trial.py','android-runtime-namespace.py',
       'android-property-runtime','headless-buffer-probe','host-pid-gui.py'}
COMMANDS=('/system/bin/servicemanager','/system/bin/hwservicemanager',
 '/vendor/bin/hw/android.hardware.graphics.allocator@2.0-service',
 '/vendor/bin/hw/android.hardware.graphics.composer@2.1-service',str(PREFIX/'bin/tinywl-g955n-candidate'),'/usr/bin/es2gears_wayland',str(BASE/'es2gears-wayland-safe'),str(BASE/'x11-pixel-probe'))


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(*args,**kw):return subprocess.run(args,check=True,**kw)
def active(unit):return subprocess.run(['systemctl','is-active','--quiet',unit]).returncode==0

def identity(boot=None):
 if os.geteuid()!=0 or 'SM-G955N' not in Path('/proc/device-tree/model').read_text() or 'g955n-ubuntu' not in Path('/proc/sys/kernel/osrelease').read_text():
  raise RuntimeError('Requires root on the exact native G955N')
 current=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 if boot and current!=boot:raise RuntimeError('Reviewed boot changed')
 return current

def build_id():
 data=Path('/sys/kernel/notes').read_bytes();offset=0
 while offset+12<=len(data):
  n,d,t=struct.unpack_from('<III',data,offset);offset+=12;name=data[offset:offset+n];offset+=(n+3)&~3;value=data[offset:offset+d];offset+=(d+3)&~3
  if name.rstrip(b'\0')==b'GNU' and t==3:return value.hex()
 raise RuntimeError('No live kernel build identity')

def review(path,sha):
 if digest(path)!=sha:raise RuntimeError('Review digest changed')
 data=json.loads(path.read_text())
 if data.get('target')!='SM-G955N' or data.get('scope') not in ('exclusive-hwc-panel-8s','exclusive-hwc-panel-gtk20s','exclusive-hwc-panel-gnome20s','exclusive-hwc-panel-gnome60s','exclusive-hwc-panel-host-gnome20s','native-x11-pixels-8s','native-host-x11-pixels-8s') or set(data.get('files',{}))!=FILES:
  raise RuntimeError('Wrong/incomplete exclusive panel scope')
 for name,expected in data['files'].items():
  p=BASE/name
  if p.is_symlink() or digest(p)!=expected:raise RuntimeError('Changed reviewed input: '+name)
 manifest=PREFIX/'manifest.json'
 if digest(manifest)!=data.get('compositor_manifest_sha256'):raise RuntimeError('Changed compositor manifest')
 package=json.loads(manifest.read_text())
 if package.get('target')!='SM-G955N' or package.get('destination')!=str(PREFIX):raise RuntimeError('Wrong private compositor prefix')
 for name,entry in package['files'].items():
  p=PREFIX/name
  if not p.resolve().is_relative_to(PREFIX) or p.is_symlink() or digest(p)!=entry['sha256']:raise RuntimeError('Changed compositor ELF')
 for name,target in package['symlinks'].items():
  p=PREFIX/name
  if not p.is_symlink() or str(p.readlink())!=target or not p.resolve().is_relative_to(PREFIX) or not p.exists():raise RuntimeError('Changed/escaping compositor link')
 if data.get('popup_probe') and (not data.get('composite_probe') or data.get('client_probe')!='gnome-x11'):raise RuntimeError('Popup proof requires the fixed GNOME composite fixture')
 if data.get('client_probe'):
  clients={'es2gears-wayland':Path('/usr/bin/es2gears_wayland'),'es2gears-wayland-safe':BASE/'es2gears-wayland-safe','gtk4-zenity':Path('/usr/bin/zenity'),'x11-pixels':BASE/'x11-pixel-probe','gnome-x11':Path('/usr/bin/gnome-shell'),'native-x11-pixels':BASE/'x11-pixel-probe'}
  client_path=clients.get(data['client_probe'])
  if client_path is None or digest(client_path)!=data.get('client_probe_sha256'):raise RuntimeError('Changed client fixture')
  package['client_probe']=True
  package['client_command_path']=str(client_path)
  package['client_kind']=data['client_probe']
  if data['client_probe'] in ('x11-pixels','gnome-x11'):
   if not package.get('features',{}).get('private_x11_candidate') or digest(Path('/usr/bin/Xwayland'))!=data.get('xwayland_sha256'):raise RuntimeError('Changed X11 transport/renderer bundle')
  if data['client_probe']=='gnome-x11' and digest(Path('/usr/bin/dbus-run-session'))!=data.get('dbus_run_session_sha256'):raise RuntimeError('Changed private session launcher')
  if data.get('composite_probe'):
   if data['client_probe']!='gnome-x11' or digest(BASE/'x11-pixel-probe')!=data.get('composite_probe_sha256'):raise RuntimeError('Changed GNOME composite fixture')
   package['composite_probe']=True
   package['popup_probe']=data.get('popup_probe') is True
  package['client_debugger']=data.get('client_debugger') is True
  if data.get('client_preload_sha256'):
   if digest(BASE/'trace-client-gl.so')!=data['client_preload_sha256']:raise RuntimeError('Changed client diagnostic')
   package['client_preload']=True
 if data.get('scope')=='exclusive-hwc-panel-gtk20s' and data.get('client_probe')!='gtk4-zenity':raise RuntimeError('GTK20 scope requires its fixed client')
 if data.get('scope') in ('exclusive-hwc-panel-gnome20s','exclusive-hwc-panel-gnome60s','exclusive-hwc-panel-host-gnome20s') and data.get('client_probe')!='gnome-x11':raise RuntimeError('GNOME20 scope requires its fixed client')
 if bool(data.get('native_system_bus'))!=(data.get('scope') in ('exclusive-hwc-panel-gnome20s','exclusive-hwc-panel-gnome60s','exclusive-hwc-panel-host-gnome20s')):raise RuntimeError('Native system bus is restricted to explicit GNOME20 scope')
 if data.get('touch_input'):
  if data.get('scope') not in ('exclusive-hwc-panel-gnome20s','exclusive-hwc-panel-gnome60s','exclusive-hwc-panel-host-gnome20s') or digest(BASE/'seatd')!=data.get('seatd_sha256'):raise RuntimeError('Touch requires reviewed GNOME scope and seat broker')
  package['touch_input']=True
 if bool(data.get('host_pid_client'))!=(data.get('scope')=='exclusive-hwc-panel-host-gnome20s'):raise RuntimeError('Host PID entry requires its separate reviewed scope')
 if data.get('host_pid_client'):
  if not data.get('touch_input'):raise RuntimeError('Host GUI requires reviewed native input')
  package['host_pid_client']=True
 package['native_system_bus']=data.get('native_system_bus') is True
 if data.get('scope')=='exclusive-hwc-panel-gnome60s' and not data.get('touch_input'):raise RuntimeError('GNOME60 scope requires its reviewed touchscreen')
 if data.get('gnome_geometry'):
  if data.get('client_probe')!='gnome-x11' or data['gnome_geometry']!='720x1480':raise RuntimeError('Unsupported GNOME geometry')
  package['gnome_geometry']=data['gnome_geometry']
 if data.get('scope') in ('native-x11-pixels-8s','native-host-x11-pixels-8s'):
  if data.get('client_probe')!='native-x11-pixels' or not package.get('features',{}).get('private_x11_candidate') or digest(Path('/usr/lib/xorg/Xorg'))!=data.get('native_xorg_sha256'):raise RuntimeError('Native X11 requires its fixed transport/fixture')
  if type(data.get('native_xorg_pid')) is not int or data['native_xorg_pid']<=1 or not re.fullmatch(r'[0-9]+',data.get('native_xorg_starttime','')):raise RuntimeError('Native X server process pin missing')
  if any(data.get(k) for k in ('diagnostic_debugger','diagnostic_trace','client_debugger','client_preload_sha256')):raise RuntimeError('Native X scope excludes diagnostic interposition')
  package['native_x11']=True
  package['native_host_client']=data['scope']=='native-host-x11-pixels-8s'
 package['observation_seconds']=8 if data.get('scope') in ('exclusive-hwc-panel-8s','native-x11-pixels-8s','native-host-x11-pixels-8s') else 60 if data.get('scope')=='exclusive-hwc-panel-gnome60s' else 20
 return data,package

def android_processes():
 found=[]
 for p in Path('/proc').glob('[0-9]*/cmdline'):
  try:
   command=p.read_bytes().split(b'\0',1)[0].decode()
   if command in COMMANDS:found.append(int(p.parent.name))
  except (OSError,UnicodeDecodeError):pass
 return found

def save_state(data):
 temp=STATE.with_suffix('.new');temp.write_text(json.dumps(data));temp.chmod(0o600);temp.replace(STATE)

def cleanup_shared_property_source(saved):
 source=Path('/run/g955n-native-property-source')
 expected=saved.get('shared_property_source')
 if not expected:return True
 if Path('/run/g955n-native-gpu-lease.json').exists():raise RuntimeError('Native property mirror is still leased')
 if saved.get('namespace_pid') and Path('/proc',str(saved['namespace_pid'])).exists():raise RuntimeError('Property writer still alive')
 if source.exists():
  st=source.lstat()
  if not stat.S_ISDIR(st.st_mode) or st.st_uid!=0 or [st.st_dev,st.st_ino]!=expected:raise RuntimeError('Shared property backing identity changed')
  shutil.rmtree(source)
 return not source.exists()

def restore():
 boot=identity()
 lease=Path('/run/g955n-native-gpu-lease.json')
 if lease.exists():SourceFileLoader('native_lease_restore',str(BASE/'host-pid-gui.py')).load_module().restore_native_lease(skip_other_owner=True)
 if not STATE.exists():return
 st=STATE.stat()
 if st.st_uid!=0 or stat.S_IMODE(st.st_mode)!=0o600 or STATE.is_symlink():raise RuntimeError('Untrusted restore record')
 saved=json.loads(STATE.read_text())
 if saved['boot_id']!=boot:raise RuntimeError('Restore belongs to another boot')
 if saved.get('restored'):return
 if saved.get('namespace_pid') and Path('/proc',str(saved['namespace_pid'])).exists():raise RuntimeError('Private display namespace is still alive; refusing parallel owners')
 cleanup_shared_property_source(saved)
 remaining=android_processes()
 if remaining:raise RuntimeError('Refusing parallel display owners; remaining Android/compositor tasks: '+str(remaining))
 if saved.get('tty'):
  if not re.fullmatch(r'/dev/tty[1-9][0-9]*',saved['tty']):raise RuntimeError('Unexpected saved VT')
  fd=os.open(saved['tty'],os.O_RDWR|os.O_NOCTTY)
  try:fcntl.ioctl(fd,0x4b3a,saved['tty_mode'])
  finally:os.close(fd)
 for unit in ('g955n-fb-display.service','gdm.service'):
  if saved['services'][unit]:run('systemctl','start',unit,timeout=20)
 saved['restored']=all(not was or active(unit) for unit,was in saved['services'].items());save_state(saved)
 if not saved['restored']:raise RuntimeError('Display services did not restore')

def panel_guard(boot,touch=False):
 identity(boot)
 if os.getcwd()!='/' or (os.stat('.').st_dev,os.stat('.').st_ino)!=(os.stat('/').st_dev,os.stat('/').st_ino):raise RuntimeError('Working directory must be the private root')
 if os.environ.get('G955N_ANDROID_PRIVATE_RUNTIME')!='1' or os.getpid()==1:raise RuntimeError('Private runtime required')
 for kind,key in [('pid','G955N_PARENT_PID_NS'),('mnt','G955N_PARENT_MOUNT_NS')]:
  if not os.environ.get(key) or os.readlink('/proc/self/ns/'+kind)==os.environ[key]:raise RuntimeError('Namespace provenance failed')
 legacy=SourceFileLoader('panel_legacy',str(BASE/'allocator-cpu-buffer-trial.py')).load_module()
 fields=dict(x.split(':',1) for x in Path('/proc/self/status').read_text().splitlines() if ':' in x)
 nnp=ctypes.CDLL(None).prctl(39,0,0,0,0)
 if not legacy.legacy.nnp_verified(nnp,fields) or any(int(fields.get(k,'ffffffff'),16)&legacy.DANGEROUS for k in ('CapEff','CapPrm','CapBnd')):raise RuntimeError('Capabilities/NNP not removed')
 allowed={'null','zero','random','urandom','binder','hwbinder','vndbinder','ashmem','__properties__','socket','ion','mali0','fb0','graphics','sw_sync','fimg2d','shm'}
 if touch:allowed.add('input')
 if set(p.name for p in Path('/dev').iterdir())-allowed:raise RuntimeError('Unreviewed device entry')
 for p in ('/efs','/proc/1/root/efs','/dev/block','/dev/snd','/dev/dri','/dev/video0',*(() if touch else ('/dev/input',))):
  if Path(p).exists():raise RuntimeError('Forbidden panel device/path')
 for name,uid,gid,mode in [('binder',0,1003,0o660),('ashmem',0,1003,0o660),('hwbinder',0,1003,0o660),('ion',1000,1000,0o600),('mali0',0,1003,0o660),('fb0',0,1003,0o660),('graphics/fb0',0,1003,0o660)]:
  st=Path('/dev',name).lstat()
  if not stat.S_ISCHR(st.st_mode) or (st.st_uid,st.st_gid,stat.S_IMODE(st.st_mode))!=(uid,gid,mode):raise RuntimeError('Private node permissions differ: '+name)
 if not any(' /dev/shm ' in line and ' - tmpfs ' in line for line in Path('/proc/self/mountinfo').read_text().splitlines()):raise RuntimeError('Private compositor SHM mount missing')
 if Path('/dev/fb0').stat().st_rdev!=Path('/dev/graphics/fb0').stat().st_rdev:raise RuntimeError('Framebuffer aliases differ')
 if any(not os.statvfs(p).f_flag&os.ST_RDONLY for p in ('/proc','/sys','/system','/vendor','/home')):raise RuntimeError('Read-only context missing')
 if touch:
  if set(p.name for p in Path('/dev/input').iterdir())!={'event0'} or Path('/sys/class/input/event0/device/name').read_text().strip()!='sec_touchscreen':raise RuntimeError('Unreviewed input device')
  node=Path('/dev/input/event0').stat()
  if not stat.S_ISCHR(node.st_mode) or (node.st_uid,node.st_gid,stat.S_IMODE(node.st_mode))!=(0,0,0o600) or Path('/sys/class/input/event0/dev').read_text().strip()!=f'{os.major(node.st_rdev)}:{os.minor(node.st_rdev)}' or not os.statvfs('/run/udev').f_flag&os.ST_RDONLY:raise RuntimeError('Touchscreen/metadata provenance failed')
 return legacy

def native_xorg_identity(data):
 pid=data.get('native_xorg_pid')
 if type(pid) is not int or pid<=1:raise RuntimeError('Reviewed native X server PID missing')
 root=Path('/proc',str(pid));args=root.joinpath('cmdline').read_bytes().split(b'\0')
 if root.joinpath('comm').read_text().strip()!='Xorg' or root.joinpath('exe').resolve()!=Path('/usr/lib/xorg/Xorg'):raise RuntimeError('Native X server identity differs')
 start=root.joinpath('stat').read_text().rsplit(')',1)[1].split()[19]
 if start!=data.get('native_xorg_starttime'):raise RuntimeError('Native X server restarted')
 if b'-auth' not in args:raise RuntimeError('Native X server authority absent')
 source=Path(args[args.index(b'-auth')+1].decode())
 if str(source) not in ('/run/user/105/gdm/Xauthority','/run/user/1000/gdm/Xauthority'):raise RuntimeError('Unexpected native authority location')
 st=source.lstat()
 if not stat.S_ISREG(st.st_mode) or st.st_uid not in (105,1000) or (stat.S_IMODE(st.st_mode)&0o077) or not (st.st_mode&stat.S_IRUSR) or not 1<=st.st_size<=16384:raise RuntimeError('Untrusted native X authority')
 return {'pid':pid,'starttime':start,'authority_path':str(source),'authority_inode':[st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns]}

def stage_native_authority(data):
 native=native_xorg_identity(data);source=Path(native['authority_path'])
 fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  st=os.fstat(fd)
  if [st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns]!=native['authority_inode']:raise RuntimeError('Native authority changed before staging')
  payload=os.read(fd,16385)
 finally:os.close(fd)
 if len(payload)!=st.st_size:raise RuntimeError('Incomplete native authority')
 target=BASE/'native-Xauthority';fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 try:
  os.fchown(fd,1000,1000);os.fchmod(fd,0o600);os.write(fd,payload);st=os.fstat(fd)
 finally:os.close(fd)
 return native,(st.st_dev,st.st_ino)

def native_x11_inner(boot,package):
 legacy=SourceFileLoader('native_x11_legacy',str(BASE/'allocator-cpu-buffer-trial.py')).load_module()
 proof=legacy.guard(boot,gpu=True)
 if os.getcwd()!='/' or (os.stat('.').st_dev,os.stat('.').st_ino)!=(os.stat('/').st_dev,os.stat('/').st_ino):raise RuntimeError('Headless private CWD missing')
 ctypes.CDLL(None).prctl(36,1,0,0,0)
 inherited={int(p.name) for p in Path('/proc').glob('[0-9]*') if p.is_dir()}
 host_gui=None
 if package.get('native_host_client'):
  if not isinstance(package.get('host_gui_fd'),int):raise RuntimeError('Missing native host channel')
  host_gui=SourceFileLoader('native_x11_host_gui',str(BASE/'host-pid-gui.py')).load_module()
  host_socket=socket.socket(fileno=package['host_gui_fd']);host_socket.settimeout(4)
 parent=os.getpid();processes=[];handles=[];report={'native_x11_passed':False,'panel_presented':False,'native_input_and_display_services_untouched':True,'guard':proof}
 def launch(command,name,service=False,env=None):
  log=tempfile.TemporaryFile(dir='/run');handles.append(log)
  if name=='client' and host_gui:
   try:process=host_gui.RemoteGui(host_socket,env,log)
   except Exception:
    report['host_gui_setup_stdout']=legacy.read_log(log);raise
   report['native_host_process_proof']=process.proof
   processes.append((name,process,log));return process
  process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=log,env=env or {k:v for k,v in os.environ.items() if k not in ('LD_PRELOAD','LD_LIBRARY_PATH') and not k.startswith('HYBRIS_')},
   start_new_session=True,close_fds=True,cwd='/',preexec_fn=lambda:legacy.setup_child(parent,service,128*1024*1024 if name=='client' else legacy.MAX_TRACE))
  processes.append((name,process,log));return process
 try:
  manager=launch(['/system/bin/servicemanager'],'standard_manager');ready=False;until=time.monotonic()+4
  while manager.poll() is None and time.monotonic()<until:
   p=subprocess.run(['/system/bin/service','list'],capture_output=True,text=True,timeout=1)
   if p.returncode==0 and 'Found ' in p.stdout:ready=True;break
   time.sleep(.05)
  if not ready:raise RuntimeError('Real standard manager not ready')
  allocator=launch([COMMANDS[2]],'allocator',True);ready=False;until=time.monotonic()+5
  descriptor='android.hardware.graphics.allocator@2.0::IAllocator/default'
  while allocator.poll() is None and time.monotonic()<until:
   p=subprocess.run([str(BASE/'headless-buffer-probe'),'--list-services-gles',boot],capture_output=True,text=True,timeout=2,env={**os.environ,'LD_LIBRARY_PATH':'/system/lib64:/vendor/lib64'})
   report['allocator_registration']=p.stdout
   if p.returncode==0 and 'live_service='+descriptor+'\n' in p.stdout and 'service_registration='+descriptor+' namespace_pid='+str(allocator.pid)+'\n' in p.stdout:ready=True;break
   time.sleep(.05)
  if not ready:raise RuntimeError('Real allocator registration failed')
  env={'HOME':'/home/ubuntu','USER':'ubuntu','LOGNAME':'ubuntu','LANG':'C.UTF-8','PATH':'/usr/bin:/bin',**package['process_private_environment'],
   'DISPLAY':':0','XAUTHORITY':str(BASE/'native-Xauthority'),'HYBRIS_EGLPLATFORM':'x11','HYBRIS_X11_DISABLE_SHM':'1','HYBRIS_EGL_REPORT_RENDERER':'1','G955N_ANDROID_PRIVATE_RUNTIME':'1'}
  if package.get('native_host_client'):
   env.pop('G955N_ANDROID_PRIVATE_RUNTIME',None);env['G955N_NATIVE_COMPAT_RUNTIME']='1'
  client=launch([str(BASE/'x11-pixel-probe'),'--run-native-x11-pixel-trial',boot],'client',True,env)
  report['client_exit']=client.wait(timeout=12)
 except Exception as error:report['exception']=repr(error)
 finally:
  report['cleanup']={}
  for name,process,log in reversed(processes):
   report['cleanup'][name]=process.stop() if getattr(process,'is_remote',False) else legacy.stop_group(process);report[name+'_stdout']=legacy.read_log(log)
  for sig in (signal.SIGTERM,signal.SIGKILL):
   for p in Path('/proc').glob('[0-9]*'):
    if int(p.name) not in inherited:
     try:os.kill(int(p.name),sig)
     except ProcessLookupError:pass
   time.sleep(.1)
  until=time.monotonic()+1
  while time.monotonic()<until:
   try:
    pid,_=os.waitpid(-1,os.WNOHANG)
    if not pid:time.sleep(.02)
   except ChildProcessError:break
  report['remaining_private_pids']=sorted(int(p.name) for p in Path('/proc').glob('[0-9]*') if int(p.name) not in inherited)
  report['cleanup_passed']=not report['remaining_private_pids'] and all(info.get('native_compat_restored',True) and not info.get('remaining') for info in report['cleanup'].values()) and all(p.poll() is not None for _,p,_ in processes)
  report['logs_complete']=all(os.fstat(log.fileno()).st_size<legacy.MAX_TRACE for log in handles)
  for log in handles:log.close()
 text=report.get('client_stdout','')
 report['native_x11_passed']=bool(report.get('client_exit')==0 and 'Mali-G71' in text and 'G955N_X11_PIXEL_PASS frames=48 resize=passed repeated_egl=passed teardown=passed' in text and report['cleanup_passed'] and report['logs_complete'])
 return report


def inner(boot,package):
 if package.get('native_x11'):return native_x11_inner(boot,package)
 inherited=set(android_processes())
 if len(inherited)!=1:raise RuntimeError('Expected only the supervised hardware manager')
 legacy=panel_guard(boot,package.get('touch_input'));ctypes.CDLL(None).prctl(36,1,0,0,0)
 bus=Path('/run/dbus/system_bus_socket')
 if bus.exists()!=bool(package.get('native_system_bus')) or (bus.exists() and not stat.S_ISSOCK(bus.stat().st_mode)):raise RuntimeError('System bus differs from reviewed scope')
 # Enumerate only after proving private PID/proc provenance.
 def private_pids():return {int(p.name) for p in Path('/proc').glob('[0-9]*') if p.is_dir()}
 inherited_private=private_pids()
 host_gui=None
 if package.get('host_pid_client'):
  if not isinstance(package.get('host_gui_fd'),int):raise RuntimeError('Missing inherited host GUI channel')
  host_gui=SourceFileLoader('panel_host_gui',str(BASE/'host-pid-gui.py')).load_module()
  host_socket=socket.socket(fileno=package['host_gui_fd']);host_socket.settimeout(4)
 parent=os.getpid();processes=[];report={'panel_presented':False,'desktop_qualified':False};handles=[]
 binary=BASE/'headless-buffer-probe'
 def listing():
  p=subprocess.run([str(binary),'--list-services-display',boot],env={**os.environ,'LD_LIBRARY_PATH':'/system/lib64:/vendor/lib64'},capture_output=True,text=True,timeout=3)
  if p.returncode:raise RuntimeError('Actual manager listing failed')
  return p.stdout
 def launch(command,name,system=False,env=None):
  log=tempfile.TemporaryFile(dir='/run');handles.append(log)
  if name=='client' and host_gui:
   try:p=host_gui.RemoteGui(host_socket,env,log)
   except Exception:
    report['host_gui_setup_stdout']=legacy.read_log(log);raise
   processes.append((name,p,log));return p
  p=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,close_fds=True,
   cwd='/',preexec_fn=lambda:legacy.setup_child(parent,system,128*1024*1024 if name in ('compositor','xwayland','client') else legacy.MAX_TRACE),env=env or {k:v for k,v in os.environ.items() if k not in ('LD_PRELOAD','LD_LIBRARY_PATH') and not k.startswith('HYBRIS_')})
  processes.append((name,p,log));return p
 try:
  manager=launch(['/system/bin/servicemanager'],'standard_manager')
  ready=False;until=time.monotonic()+4
  while time.monotonic()<until:
   try:
    p=subprocess.run(['/system/bin/service','list'],capture_output=True,text=True,timeout=1)
    if p.returncode==0 and 'Found ' in p.stdout:report['standard_service_list']=p.stdout;ready=True;break
   except subprocess.TimeoutExpired:pass
   if manager.poll() is not None:break
  if not ready:raise RuntimeError('Real standard manager not ready')
  for name,command,descriptor in [('allocator',COMMANDS[2],'android.hardware.graphics.allocator@2.0::IAllocator/default'),('composer',COMMANDS[3],'android.hardware.graphics.composer@2.1::IComposer/default')]:
   process=launch([command],name,True);until=time.monotonic()+5;registered=False
   while time.monotonic()<until and process.poll() is None:
    text=listing();report[name+'_registration']=text
    if ('live_service='+descriptor+'\n' in text and 'service_registration='+descriptor+' namespace_pid='+str(process.pid)+'\n' in text):registered=True;break
    time.sleep(.05)
   if not registered:raise RuntimeError('Actual '+name+' PID registration failed')
  runtime=Path('/run/g955n-compositor');runtime.mkdir(mode=0o700);os.chown(runtime,1000,1000)
  env={'HOME':'/home/ubuntu','USER':'ubuntu','LOGNAME':'ubuntu','LANG':'C.UTF-8','PATH':'/usr/bin:/bin',
       'XDG_RUNTIME_DIR':str(runtime),'XDG_SESSION_TYPE':'wayland','G955N_PANEL_TEST_PATTERN':'1',**package['process_private_environment']}
  if package.get('touch_input'):
   seatd=launch([str(BASE/'seatd'),'-u','ubuntu','-l','info','-n','1'],'seatd',False,{k:v for k,v in {**os.environ,'SEATD_VTBOUND':'0'}.items() if k not in ('LD_PRELOAD','LD_LIBRARY_PATH') and not k.startswith('HYBRIS_')})
   until=time.monotonic()+3
   while time.monotonic()<until and seatd.poll() is None:
    if Path('/run/seatd.sock').is_socket():break
    time.sleep(.05)
   else:raise RuntimeError('Actual private seat broker not ready')
   env.update(WLR_BACKENDS='hwcomposer,libinput',LIBSEAT_BACKEND='seatd',SEATD_SOCK='/run/seatd.sock')
  if package.get('gnome_geometry'):env['G955N_PANEL_SCALE']='2'
  report['display_irq_before']=display_irqs()
  command=[str(PREFIX/'bin/tinywl-g955n-candidate')]
  if package.get('diagnostic_debugger'):
   command=['/usr/bin/gdb','--batch','--nx','-ex','set auto-load off','-ex','set pagination off',
            '-ex','set startup-with-shell off','-ex','run','-ex','info proc mappings',
            '-ex','thread apply all bt','-ex','thread 1','-ex','info registers',
            '-ex','x/32gx $sp','-ex','frame 3','-ex','x/12i $pc','--args',*command]
  elif package.get('diagnostic_trace'):
   command=['/usr/bin/strace','-f','-s','120','-e','trace=mmap,munmap,ioctl,openat,close',*command]
  android_log=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)
  android_log.bind('/dev/socket/logdw');os.chmod('/dev/socket/logdw',0o666)
  android_log.setblocking(False);captured=[];captured_bytes=0
  compositor=launch(command,'compositor',True,env)
  client=None;composite_probe=None
  start=time.monotonic()
  while time.monotonic()-start<package['observation_seconds'] and compositor.poll() is None:
   if package.get('client_probe') and client is None and (runtime/'wayland-0').exists():
    client_env={**env,'WAYLAND_DISPLAY':'wayland-0','HYBRIS_EGLPLATFORM':'wayland'}
    client_path=package['client_command_path']
    client_args=['-info']
    if package.get('client_kind')=='gtk4-zenity':
     home=runtime/'gtk-home';home.mkdir(mode=0o700);os.chown(home,1000,1000)
     client_env.update(HOME=str(home),XDG_CACHE_HOME=str(home/'cache'),XDG_CONFIG_HOME=str(home/'config'),GSETTINGS_BACKEND='memory',
      GDK_BACKEND='wayland',GDK_GL='gles',G_MESSAGES_DEBUG='all',HYBRIS_EGL_REPORT_RENDERER='1',GSK_RENDERER='gl',GTK_A11Y='none')
     client_args=['--info','--text=Ubuntu display test','--title=Ubuntu']
    if package.get('client_kind') in ('x11-pixels','gnome-x11'):
     authority=runtime/'Xauthority';cookie=os.urandom(16)
     authority.write_bytes(struct.pack('!H',65535)+b''.join(struct.pack('!H',len(v))+v for v in [b'',b'77',b'MIT-MAGIC-COOKIE-1',cookie]));authority.chmod(0o600);os.chown(authority,1000,1000)
     server_env={key:env[key] for key in ('HOME','USER','LOGNAME','LANG','PATH','XDG_RUNTIME_DIR','XDG_SESSION_TYPE')}
     server_env.update(WAYLAND_DISPLAY='wayland-0',XAUTHORITY=str(authority))
     xdir=Path('/tmp/.X11-unix');xdir.mkdir(mode=0o1777,exist_ok=True);xdir.chmod(0o1777)
     server=launch(['/usr/bin/Xwayland',':77','-displayfd','1','-geometry',package.get('gnome_geometry','480x800'),'-shm','-extension','MIT-SHM','-nolisten','tcp','-auth',str(authority),'-noreset'],'xwayland',True,server_env)
     server_log=processes[-1][2];ready_deadline=time.monotonic()+4
     while server.poll() is None and time.monotonic()<ready_deadline:
      if re.search(rb'(?m)^77\r?$',os.pread(server_log.fileno(),legacy.MAX_TRACE,0)):break
      time.sleep(.05)
     else:raise RuntimeError('Xwayland did not report real display readiness')
     report['xwayland_ready']=True
     client_env.update(DISPLAY=':77',XAUTHORITY=str(authority),HYBRIS_EGLPLATFORM='x11',HYBRIS_X11_DISABLE_SHM='1',HYBRIS_EGL_REPORT_RENDERER='1',G955N_ANDROID_PRIVATE_RUNTIME='1')
     client_args=['--run-x11-pixel-trial',boot]
    if package.get('client_kind')=='gnome-x11':
     home=runtime/'gnome-home';home.mkdir(mode=0o700);os.chown(home,1000,1000)
     config=home/'config';config.mkdir(mode=0o700);os.chown(config,1000,1000)
     monitors=config/'monitors.xml'
     width,height=package.get('gnome_geometry','480x800').split('x')
     randr=subprocess.run(['/usr/bin/xrandr','--verbose'],env={**server_env,'DISPLAY':':77'},capture_output=True,text=True,timeout=2,preexec_fn=lambda:legacy.setup_child(parent,True))
     report['xrandr_before_gnome']=randr.stdout
     mode=re.search(r'^\s+'+width+'x'+height+r'\s+\([^)]*\)\s+([0-9.]+)MHz[^\n]*\*current[^\n]*\n[^\n]*total\s+(\d+)[^\n]*\n[^\n]*total\s+(\d+)',randr.stdout,re.M)
     if randr.returncode or mode is None:raise RuntimeError('Actual X11 geometry/rate differs')
     refresh=float(mode[1])*1000000/(int(mode[2])*int(mode[3]))
     report['gnome_requested_mode']={'width':int(width),'height':int(height),'refresh':refresh}
     monitors.write_text(f'<monitors version="2"><configuration><logicalmonitor><x>0</x><y>0</y><scale>1</scale><primary>yes</primary><monitor><monitorspec><connector>XWAYLAND0</connector><vendor>unknown</vendor><product>unknown</product><serial>unknown</serial></monitorspec><mode><width>{width}</width><height>{height}</height><rate>{refresh:.9f}</rate></mode></monitor></logicalmonitor></configuration></monitors>')
     monitors.chmod(0o600);os.chown(monitors,1000,1000)
     client_env.update(HOME=str(home),XDG_CACHE_HOME=str(home/'cache'),XDG_CONFIG_HOME=str(config),XDG_DATA_HOME=str(home/'share'),
      XDG_SESSION_TYPE='x11',GSETTINGS_BACKEND='memory',COGL_DRIVER='gles2',COGL_RENDERER='EGL_XLIB',COGL_DEBUG='winsys',
      GDK_BACKEND='x11',GDK_GL='gles',GSK_RENDERER='gl',GTK_A11Y='none',MUTTER_DEBUG_DUMMY_MODE_SPECS='480x800')
     client_path='/usr/bin/dbus-run-session'
     client_args=['--','/usr/bin/gnome-shell','--x11','--replace','--sm-disable']
    client_command=['/usr/bin/stdbuf','-oL','-eL',client_path,*client_args]
    if package.get('client_preload'):
     client_env['LD_PRELOAD']=str(BASE/'trace-client-gl.so')
     client_command=[client_path,*client_args]
    if package.get('client_debugger'):
     client_command=['/usr/bin/gdb','--batch','--nx','-ex','set auto-load off','-ex','set pagination off',
      '-ex','set startup-with-shell off','-ex','run','-ex','info proc mappings',
      '-ex','thread apply all bt','-ex','info registers','-ex','x/32gx $sp',
      '--args',client_path,*client_args]
    client=launch(client_command,'client',True,client_env)
   if package.get('composite_probe') and client is not None and composite_probe is None:
    client_log=next(log for name,_,log in processes if name=='client')
    if b'GNOME Shell started' in os.pread(client_log.fileno(),legacy.MAX_TRACE,0):
     composite_probe=launch([str(BASE/'x11-pixel-probe'),'--run-x11-composite-trial' if package.get('popup_probe') else '--run-x11-composite-no-popup-trial',boot],'composite_probe',True,client_env)
   while True:
    try:message=android_log.recv(65536)
    except BlockingIOError:break
    captured_bytes+=len(message)
    if captured_bytes<=legacy.MAX_TRACE:captured.append(message.decode('utf-8','replace'))
   time.sleep(.05)
  while True:
   try:message=android_log.recv(65536)
   except BlockingIOError:break
   captured_bytes+=len(message)
   if captured_bytes<=legacy.MAX_TRACE:captured.append(message.decode('utf-8','replace'))
  report['android_log']=captured;report['android_log_complete']=captured_bytes<=legacy.MAX_TRACE
  android_log.close()
  report['display_irq_after']=display_irqs()
  report['display_irq_progressed']=all(report['display_irq_after'][key]>=value+3 for key,value in report['display_irq_before'].items())
  report['compositor_alive_8s']=compositor.poll() is None
  report['observation_seconds']=package['observation_seconds']
  if client is not None and not getattr(client,'is_remote',False) and Path('/proc',str(client.pid),'maps').exists():
   report['client_maps']=Path('/proc',str(client.pid),'maps').read_text()
  report['client_alive_at_end']=client is not None and client.poll() is None
  if package.get('client_kind') in ('x11-pixels','gnome-x11'):
   report['client_completed_ok']=client is not None and client.poll()==0
   report['xwayland_alive_at_end']=server.poll() is None
  if package.get('composite_probe'):report['composite_probe_exit_before_cleanup']=composite_probe.poll() if composite_probe else None
  report['compositor_exit_before_cleanup']=compositor.poll()
  if Path('/proc',str(compositor.pid),'limits').exists():report['compositor_limits']=Path('/proc',str(compositor.pid),'limits').read_text()
 except Exception as error:report['exception']=repr(error)
 finally:
  report['cleanup']={}
  for name,p,log in reversed(processes):
   report['cleanup'][name]=p.stop() if getattr(p,'is_remote',False) else legacy.stop_group(p);report[name+'_stdout']=legacy.read_log(log)
  for sig in (signal.SIGTERM,signal.SIGKILL):
   for pid in private_pids()-inherited_private:
    try:os.kill(pid,sig)
    except ProcessLookupError:pass
   time.sleep(.1)
  deadline=time.monotonic()+1
  while time.monotonic()<deadline:
   try:
    pid,_=os.waitpid(-1,os.WNOHANG)
    if not pid:time.sleep(.02)
   except ChildProcessError:break
  failure=Path('/run/g955n-compositor/composite-failure.ppm')
  if failure.is_file() and failure.stat().st_size<legacy.MAX_TRACE:report['composite_failure_ppm_base64']=base64.b64encode(failure.read_bytes()).decode()
  report['remaining_private_processes']=sorted(set(android_processes())-inherited)
  report['remaining_private_pids']=sorted(private_pids()-inherited_private)
  report['host_gui_cleanup_passed']=all(not info.get('remaining') and info.get('reaped') for name,info in report['cleanup'].items() if name=='client' and host_gui)
  report['cleanup_passed']=report['host_gui_cleanup_passed'] and not report['remaining_private_pids'] and not report['remaining_private_processes'] and all(p.poll() is not None for _,p,_ in processes)
  report['logs_complete']=all(os.fstat(log.fileno()).st_size<legacy.MAX_TRACE for log in handles)
  for log in handles:log.close()
 text=report.get('compositor_stdout','')
 report['diagnostic_debugger']=bool(package.get('diagnostic_debugger') or package.get('diagnostic_trace') or package.get('client_debugger') or package.get('client_preload'))
 report['client_gpu_passed']=bool(report.get('client_alive_at_end') and 'Mali-G71' in report.get('client_stdout',''))
 if package.get('client_kind')=='x11-pixels':
  report['client_gpu_passed']=bool(report.get('client_completed_ok') and report.get('xwayland_ready') and report.get('xwayland_alive_at_end') and 'Mali-G71' in report.get('client_stdout','') and 'G955N_X11_PIXEL_PASS frames=48 resize=passed repeated_egl=passed teardown=passed' in report.get('client_stdout',''))
 if package.get('client_kind')=='gnome-x11':
  report['client_gpu_passed']=bool(report['client_gpu_passed'] and report.get('xwayland_alive_at_end') and 'GNOME Shell started' in report.get('client_stdout',''))
 if package.get('composite_probe'):
  report['composite_pixels_passed']=bool(report.get('composite_probe_exit_before_cleanup')==0 and 'G955N_X11_COMPOSITE_PASS frames=6 overlay_pixels=passed' in report.get('composite_probe_stdout',''))
  report['client_gpu_passed']=report['client_gpu_passed'] and report['composite_pixels_passed']
  if package.get('popup_probe'):
   report['gnome_popup_passed']='G955N_GNOME_POPUP_PASS samples=20 stable=passed' in report.get('composite_probe_stdout','')
   report['client_gpu_passed']=report['client_gpu_passed'] and report['gnome_popup_passed']
 report['panel_presented']=bool(not report['diagnostic_debugger'] and report.get('android_log_complete') and report.get('compositor_alive_8s') and report.get('logs_complete') and report.get('display_irq_progressed') and 'Mali-G71' in text and 'G955N HWC present accepted=' in text and report['cleanup_passed'])
 if package.get('touch_input'):
  report['real_touch_attached']='G955N real touchscreen attached: sec_touchscreen' in text
  report['real_touch_down_count']=text.count('G955N real touch down id=')
  report['delivered_touch_down_count']=len(re.findall(r'G955N real touch down id=[0-9]+ serial=[1-9][0-9]* ',text))
  report['panel_presented']=report['panel_presented'] and report['real_touch_attached']
  if package['observation_seconds']==60:report['panel_presented']=report['panel_presented'] and report['delivered_touch_down_count']>0
 if package.get('client_probe'):report['panel_presented']=report['panel_presented'] and report['client_gpu_passed']
 return report

def display_irqs():
 result={}
 for line in Path('/proc/interrupts').read_text().splitlines():
  if '12870000.dsim' in line or ('12860000.decon_f' in line and re.search(r'GIC\s+(175|176)\s',line)):
   key,rest=line.split(':',1);values=[]
   for part in rest.split():
    if not part.isdigit():break
    values.append(int(part))
   result[key.strip()]=sum(values)
 if len(result)!=3:raise RuntimeError('Expected DSIM and two DECON frame interrupt counters')
 return result

def execute(path,sha):
 boot=identity();data,package=review(path,sha);identity(data['boot_id'])
 if build_id()!=data['kernel_build_id'] or int(Path('/proc/sys/kernel/tainted').read_text())!=0:raise RuntimeError('Exact fixed native-fb kernel/untainted baseline required')
 if UNIT not in Path('/proc/self/cgroup').read_text():raise RuntimeError('Use the bounded systemd launch mode')
 if Path('/sys/kernel/debug/binder/state').read_text().strip()!='binder state:' or android_processes():raise RuntimeError('Existing Android Binder clients')
 baseline=SourceFileLoader('panel_baseline',str(BASE/'run-property-trial.py')).load_module()
 logs=SourceFileLoader('panel_logs',str(BASE/'run-cpu-buffer-trial.py')).load_module()
 def panel_snapshot():
  snapshot=baseline.snapshot();gdm_dir='/run/user/'+str(pwd.getpwnam('gdm').pw_uid)
  lines=Path('/proc/self/mountinfo').read_text().splitlines()
  kept=[line for line in lines if not(line.split()[4]==gdm_dir or line.split()[4].startswith(gdm_dir+'/'))]
  snapshot['mountinfo_sha256']=hashlib.sha256(('\n'.join(kept)+'\n').encode()).hexdigest()
  return snapshot
 before=panel_snapshot();cursor=logs.cursor();result={'expected_mount_lifecycle':'Only greeter runtime /run/user/gdm-uid excluded from mount hash; display services intentionally restart','before':before,'kernel_before':logs.boot_state(),'desktop_qualified':False}
 saved={'boot_id':boot,'services':{u:active(u) for u in ('gdm.service','g955n-fb-display.service')},'restored':False};save_state(saved)
 process=None;raw=bytearray();child=None;authority_inode=None
 try:
  if not package.get('native_x11'):
   run('systemctl','stop','gdm.service',timeout=25);run('systemctl','stop','g955n-fb-display.service',timeout=10)
  if not package.get('native_x11'):
   tty=Path('/sys/class/tty/tty0/active').read_text().strip()
   if not re.fullmatch(r'tty[1-9][0-9]*',tty):raise RuntimeError('Unexpected active VT')
   fd=os.open('/dev/'+tty,os.O_RDWR|os.O_NOCTTY)
   try:
    mode=bytearray(4);fcntl.ioctl(fd,0x4b3b,mode,True);saved.update(tty='/dev/'+tty,tty_mode=struct.unpack('I',mode)[0]);save_state(saved);fcntl.ioctl(fd,0x4b3a,1)
   finally:os.close(fd)
  before=panel_snapshot();result['namespace_before']=before
  result['display_irq_before']=display_irqs()
  if package.get('native_x11'):result['native_xorg_before'],authority_inode=stage_native_authority(data)
  if package.get('native_host_client'):
   source=Path('/run/g955n-native-property-source');source.mkdir(mode=0o700);source.chmod(0o700)
   st=source.stat();saved['shared_property_source']=[st.st_dev,st.st_ino];save_state(saved)
   area=source/'properties';area.mkdir(mode=0o711);area.chmod(0o711)
  process=subprocess.Popen(['python3',str(BASE/'android-runtime-namespace.py'),'--run-trial','--runtime',str(BASE/'android-property-runtime'),
   '--property-info',str(BASE/'property_info'),'--stock-contexts',str(BASE/'android-stock-service-contexts'),'--seconds',str(package['observation_seconds']+20),
   *(['--include-ion-device','--include-mali-device'] if package.get('native_x11') else ['--include-display-devices']),'--include-composer-ipc',*(['--include-system-bus'] if package.get('native_system_bus') else []),*(['--include-touch-input'] if package.get('touch_input') else []),*(['--shared-properties-dir','/run/g955n-native-property-source/properties'] if package.get('native_host_client') else [])],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
  os.set_blocking(process.stdout.fileno(),False);watch=selectors.DefaultSelector();watch.register(process.stdout,selectors.EVENT_READ);invoked=False;deadline=time.monotonic()+package['observation_seconds']+35
  while time.monotonic()<deadline:
   for key,_ in watch.select(.1):
    part=os.read(key.fd,65536)
    if part:raw.extend(part)
    else:watch.unregister(key.fileobj)
   text=raw.decode(errors='replace');match=re.search(r'namespace_host_pid=(\d+)',text)
   if match:
    child=match[1]
    if saved.get('namespace_pid')!=int(child):saved['namespace_pid']=int(child);save_state(saved)
   ready=re.search(r'Real hwservicemanager readiness request committed: success=yes peer_pid=(\d+) supervised_pid=(\d+) serial=(\d+)',text)
   if ready and child and not invoked:
    invoked=True;evidence=baseline.collect_live(child,int(ready[2]),BASE);result.update(evidence)
    if ready[1]!=ready[2] or evidence['independent_property_client']['exit_code'] or 'value=true ' not in evidence['independent_property_client']['stdout'] or not evidence.get('verified_manager_processes') or not all(evidence.get('live_context_hashes_verified',{}).values()):raise RuntimeError('Real readiness failed')
    cmd=['nsenter','--target',child,'--mount','--pid','--root','--wdns=/','/usr/bin/setpriv','--bounding-set=-sys_admin,-mknod,-sys_rawio,-sys_module,-sys_boot','--inh-caps=-all','--ambient-caps=-all','--no-new-privs',
     '/usr/bin/env','-i','HOME=/home/ubuntu','PATH=/usr/sbin:/usr/bin:/sbin:/bin','G955N_ANDROID_PRIVATE_RUNTIME=1','G955N_PARENT_PID_NS='+os.readlink('/proc/self/ns/pid'),'G955N_PARENT_MOUNT_NS='+os.readlink('/proc/self/ns/mnt'),
     '/usr/bin/python3',str(BASE/'run-panel-trial.py'),'--inner','--reviewed-manifest',str(path),'--manifest-sha256',sha]
    if package.get('host_pid_client') or package.get('native_host_client'):
     broker=SourceFileLoader('panel_outer_host_gui',str(BASE/'host-pid-gui.py')).load_module()
     p,cleanup=broker.run_inner(cmd,package['observation_seconds']+8,child,path,sha);result['host_gui_cleanup']=cleanup
    else:p=subprocess.run(cmd,capture_output=True,text=True,timeout=package['observation_seconds']+8)
    result['inner_exit']=p.returncode;result['inner_stdout']=p.stdout;result['inner_stderr']=p.stderr
    if p.stdout.strip():result['panel']=json.loads(p.stdout)
    result['display_irq_after']=display_irqs()
    result['display_irq_progressed']=all(result['display_irq_after'][key]>value for key,value in result['display_irq_before'].items())
    result['runtime_ended_after_completed_trial']=True
    break
   if process.poll() is not None and not watch.get_map():break
  result['runtime_exit']=process.poll()
 except Exception as error:result['exception']=repr(error)
 finally:
  if process and process.poll() is None:
   process.terminate()
   try:process.wait(timeout=5)
   except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
  if package.get('native_host_client'):
   try:result['shared_property_source_cleaned']=cleanup_shared_property_source(saved)
   except Exception as error:result['shared_property_cleanup_error']=repr(error)
  result['runtime_stdout']=raw.decode(errors='replace');result['after']=panel_snapshot();result['kernel_after']=logs.boot_state()
  try:result['kernel_delta']=logs.kernel_delta(cursor)
  except Exception as error:result['kernel_collection_error']=repr(error);result['kernel_delta']={'complete':False,'fault_signatures':[]}
  if package.get('native_x11'):
   try:
    result['native_xorg_after']=native_xorg_identity(data);result['native_xorg_unchanged']=result['native_xorg_after']==result.get('native_xorg_before')
   except Exception as error:result['native_xorg_recheck_error']=repr(error)
   result['authority_cleanup_passed']=authority_inode is None
   if authority_inode is not None:
    authority=BASE/'native-Xauthority'
    try:
     st=authority.lstat()
     if (st.st_dev,st.st_ino)!=authority_inode or not stat.S_ISREG(st.st_mode):raise RuntimeError('Staged authority changed')
     authority.unlink();result['authority_cleanup_passed']=True
    except Exception as error:result['authority_cleanup_error']=repr(error)
  result['parent_state_unchanged']=result['after']==before
  if child:result['namespace_child_gone']=not Path('/proc',child).exists()
  try:restore();result['display_restored']=json.loads(STATE.read_text()).get('restored')
  except Exception as error:result['restore_error']=repr(error)
  result['passed']=bool((result.get('panel',{}).get('native_x11_passed') and result.get('native_xorg_unchanged') and result.get('authority_cleanup_passed') and (not package.get('native_host_client') or result.get('shared_property_source_cleaned')) if package.get('native_x11') else result.get('panel',{}).get('panel_presented') and result.get('display_irq_progressed')) and result.get('display_restored') and result.get('namespace_child_gone') and result['parent_state_unchanged'] and result['kernel_after']['boot_id']==boot and result['kernel_after']['taint']==0 and not result['kernel_delta']['fault_signatures'] and result['kernel_delta']['complete'])
  directory=Path('/var/lib/g955n/panel-trials');directory.mkdir(parents=True,exist_ok=True,mode=0o700)
  output=directory/(boot+'-'+str(time.time_ns())+'.json');output.write_text(json.dumps(result,indent=2));output.chmod(0o600)
  print(json.dumps(result,indent=2),flush=True)
 return result['passed']

def main():
 p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group();mode.add_argument('--launch',action='store_true');mode.add_argument('--run',action='store_true');mode.add_argument('--inner',action='store_true');mode.add_argument('--restore',action='store_true')
 p.add_argument('--host-gui-fd',type=int);p.add_argument('--reviewed-manifest',type=Path);p.add_argument('--manifest-sha256');a=p.parse_args()
 if a.restore:
  os.umask(0o077);restore();return 0
 if not(a.launch or a.run or a.inner):p.print_help();return 0
 if not a.reviewed_manifest or not re.fullmatch(r'[0-9a-f]{64}',a.manifest_sha256 or ''):p.error('Exact reviewed manifest/hash required')
 os.umask(0o077)
 if a.launch:
  identity();_,package=review(a.reviewed_manifest,a.manifest_sha256)
  return subprocess.run(['systemd-run','--unit=g955n-panel-trial','--wait','--collect','--property=RuntimeMaxSec='+str(max(85,package['observation_seconds']+65)),'--property=TimeoutStopSec=5','--property=KillMode=control-group',
   '--property=ExecStopPost=/usr/bin/python3 '+str(BASE/'run-panel-trial.py')+' --restore','/usr/bin/python3',str(BASE/'run-panel-trial.py'),'--run','--reviewed-manifest',str(a.reviewed_manifest),'--manifest-sha256',a.manifest_sha256]).returncode
 if a.inner:
  data,package=review(a.reviewed_manifest,a.manifest_sha256);identity(data['boot_id'])
  if bool(package.get('host_pid_client') or package.get('native_host_client'))!=(a.host_gui_fd is not None):raise RuntimeError('Unexpected host GUI channel')
  package['host_gui_fd']=a.host_gui_fd
  package['diagnostic_debugger']=data.get('diagnostic_debugger') is True
  package['diagnostic_trace']=data.get('diagnostic_trace') is True
  report=inner(data['boot_id'],package);print(json.dumps(report,indent=2));return 0 if report.get('native_x11_passed') or report.get('panel_presented') else 1
 return 0 if execute(a.reviewed_manifest,a.manifest_sha256) else 1
if __name__=='__main__':raise SystemExit(main())
