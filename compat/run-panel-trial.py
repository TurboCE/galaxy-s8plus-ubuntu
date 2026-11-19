#!/usr/bin/env python3
"""Explicit bounded HWC panel trial; default/help never changes a service.

Use --launch only from the verified phone, with an exact reviewed manifest.
The systemd unit owns the deadline and an independent ExecStopPost restoration.
No flashing, partition write, global GL replacement or automatic login.
"""
import argparse
import socket
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
       'android-property-runtime','headless-buffer-probe'}
COMMANDS=('/system/bin/servicemanager','/system/bin/hwservicemanager',
 '/vendor/bin/hw/android.hardware.graphics.allocator@2.0-service',
 '/vendor/bin/hw/android.hardware.graphics.composer@2.1-service',str(PREFIX/'bin/tinywl-g955n-candidate'),'/usr/bin/es2gears_wayland',str(BASE/'es2gears-wayland-safe'))


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
 if data.get('target')!='SM-G955N' or data.get('scope') not in ('exclusive-hwc-panel-8s','exclusive-hwc-panel-gtk20s') or set(data.get('files',{}))!=FILES:
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
 if data.get('client_probe'):
  clients={'es2gears-wayland':Path('/usr/bin/es2gears_wayland'),'es2gears-wayland-safe':BASE/'es2gears-wayland-safe','gtk4-zenity':Path('/usr/bin/zenity')}
  client_path=clients.get(data['client_probe'])
  if client_path is None or digest(client_path)!=data.get('client_probe_sha256'):raise RuntimeError('Changed client fixture')
  package['client_probe']=True
  package['client_command_path']=str(client_path)
  package['client_kind']=data['client_probe']
  package['client_debugger']=data.get('client_debugger') is True
  if data.get('client_preload_sha256'):
   if digest(BASE/'trace-client-gl.so')!=data['client_preload_sha256']:raise RuntimeError('Changed client diagnostic')
   package['client_preload']=True
 if data.get('scope')=='exclusive-hwc-panel-gtk20s' and data.get('client_probe')!='gtk4-zenity':raise RuntimeError('GTK20 scope requires its fixed client')
 package['observation_seconds']=20 if data.get('scope')=='exclusive-hwc-panel-gtk20s' else 8
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

def restore():
 boot=identity()
 if not STATE.exists():return
 st=STATE.stat()
 if st.st_uid!=0 or stat.S_IMODE(st.st_mode)!=0o600 or STATE.is_symlink():raise RuntimeError('Untrusted restore record')
 saved=json.loads(STATE.read_text())
 if saved['boot_id']!=boot:raise RuntimeError('Restore belongs to another boot')
 if saved.get('restored'):return
 if saved.get('namespace_pid') and Path('/proc',str(saved['namespace_pid'])).exists():raise RuntimeError('Private display namespace is still alive; refusing parallel owners')
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

def panel_guard(boot):
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
 if set(p.name for p in Path('/dev').iterdir())-allowed:raise RuntimeError('Unreviewed device entry')
 for p in ('/efs','/proc/1/root/efs','/dev/block','/dev/snd','/dev/dri','/dev/video0','/dev/input'):
  if Path(p).exists():raise RuntimeError('Forbidden panel device/path')
 for name,uid,gid,mode in [('binder',0,1003,0o660),('ashmem',0,1003,0o660),('hwbinder',0,1003,0o660),('ion',1000,1000,0o600),('mali0',0,1003,0o660),('fb0',0,1003,0o660),('graphics/fb0',0,1003,0o660)]:
  st=Path('/dev',name).lstat()
  if not stat.S_ISCHR(st.st_mode) or (st.st_uid,st.st_gid,stat.S_IMODE(st.st_mode))!=(uid,gid,mode):raise RuntimeError('Private node permissions differ: '+name)
 if not any(' /dev/shm ' in line and ' - tmpfs ' in line for line in Path('/proc/self/mountinfo').read_text().splitlines()):raise RuntimeError('Private compositor SHM mount missing')
 if Path('/dev/fb0').stat().st_rdev!=Path('/dev/graphics/fb0').stat().st_rdev:raise RuntimeError('Framebuffer aliases differ')
 if any(not os.statvfs(p).f_flag&os.ST_RDONLY for p in ('/proc','/sys','/system','/vendor','/home')):raise RuntimeError('Read-only context missing')
 return legacy

def inner(boot,package):
 inherited=set(android_processes())
 if len(inherited)!=1:raise RuntimeError('Expected only the supervised hardware manager')
 legacy=panel_guard(boot);ctypes.CDLL(None).prctl(36,1,0,0,0)
 parent=os.getpid();processes=[];report={'panel_presented':False,'desktop_qualified':False};handles=[]
 binary=BASE/'headless-buffer-probe'
 def listing():
  p=subprocess.run([str(binary),'--list-services-display',boot],env={**os.environ,'LD_LIBRARY_PATH':'/system/lib64:/vendor/lib64'},capture_output=True,text=True,timeout=3)
  if p.returncode:raise RuntimeError('Actual manager listing failed')
  return p.stdout
 def launch(command,name,system=False,env=None):
  log=tempfile.TemporaryFile(dir='/run');handles.append(log)
  p=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,close_fds=True,
   cwd='/',preexec_fn=lambda:legacy.setup_child(parent,system,128*1024*1024 if name=='compositor' else legacy.MAX_TRACE),env=env or {k:v for k,v in os.environ.items() if k not in ('LD_PRELOAD','LD_LIBRARY_PATH') and not k.startswith('HYBRIS_')})
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
  client=None
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
  if client is not None and Path('/proc',str(client.pid),'maps').exists():
   report['client_maps']=Path('/proc',str(client.pid),'maps').read_text()
  report['client_alive_at_end']=client is not None and client.poll() is None
  report['compositor_exit_before_cleanup']=compositor.poll()
  if Path('/proc',str(compositor.pid),'limits').exists():report['compositor_limits']=Path('/proc',str(compositor.pid),'limits').read_text()
 except Exception as error:report['exception']=repr(error)
 finally:
  report['cleanup']={}
  for name,p,log in reversed(processes):
   report['cleanup'][name]=legacy.stop_group(p);report[name+'_stdout']=legacy.read_log(log)
  deadline=time.monotonic()+1
  while time.monotonic()<deadline:
   try:
    pid,_=os.waitpid(-1,os.WNOHANG)
    if not pid:time.sleep(.02)
   except ChildProcessError:break
  report['remaining_private_processes']=sorted(set(android_processes())-inherited)
  report['cleanup_passed']=not report['remaining_private_processes'] and all(p.poll() is not None for _,p,_ in processes)
  report['logs_complete']=all(os.fstat(log.fileno()).st_size<legacy.MAX_TRACE for log in handles)
  for log in handles:log.close()
 text=report.get('compositor_stdout','')
 report['diagnostic_debugger']=bool(package.get('diagnostic_debugger') or package.get('diagnostic_trace') or package.get('client_debugger') or package.get('client_preload'))
 report['client_gpu_passed']=bool(report.get('client_alive_at_end') and 'Mali-G71' in report.get('client_stdout',''))
 report['panel_presented']=bool(not report['diagnostic_debugger'] and report.get('android_log_complete') and report.get('compositor_alive_8s') and report.get('logs_complete') and report.get('display_irq_progressed') and 'Mali-G71' in text and 'G955N HWC present accepted=' in text and report['cleanup_passed'])
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
 process=None;raw=bytearray();child=None
 try:
  run('systemctl','stop','gdm.service',timeout=25);run('systemctl','stop','g955n-fb-display.service',timeout=10)
  tty=Path('/sys/class/tty/tty0/active').read_text().strip()
  if not re.fullmatch(r'tty[1-9][0-9]*',tty):raise RuntimeError('Unexpected active VT')
  fd=os.open('/dev/'+tty,os.O_RDWR|os.O_NOCTTY)
  try:
   mode=bytearray(4);fcntl.ioctl(fd,0x4b3b,mode,True);saved.update(tty='/dev/'+tty,tty_mode=struct.unpack('I',mode)[0]);save_state(saved);fcntl.ioctl(fd,0x4b3a,1)
  finally:os.close(fd)
  before=panel_snapshot();result['namespace_before']=before
  result['display_irq_before']=display_irqs()
  process=subprocess.Popen(['python3',str(BASE/'android-runtime-namespace.py'),'--run-trial','--runtime',str(BASE/'android-property-runtime'),
   '--property-info',str(BASE/'property_info'),'--stock-contexts',str(BASE/'android-stock-service-contexts'),'--seconds','40',
   '--include-display-devices','--include-composer-ipc'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
  os.set_blocking(process.stdout.fileno(),False);watch=selectors.DefaultSelector();watch.register(process.stdout,selectors.EVENT_READ);invoked=False;deadline=time.monotonic()+55
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
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=28);result['inner_exit']=p.returncode;result['inner_stdout']=p.stdout;result['inner_stderr']=p.stderr
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
  result['runtime_stdout']=raw.decode(errors='replace');result['after']=panel_snapshot();result['kernel_after']=logs.boot_state()
  try:result['kernel_delta']=logs.kernel_delta(cursor)
  except Exception as error:result['kernel_collection_error']=repr(error);result['kernel_delta']={'complete':False,'fault_signatures':[]}
  result['parent_state_unchanged']=result['after']==before
  if child:result['namespace_child_gone']=not Path('/proc',child).exists()
  try:restore();result['display_restored']=json.loads(STATE.read_text()).get('restored')
  except Exception as error:result['restore_error']=repr(error)
  result['passed']=bool(result.get('panel',{}).get('panel_presented') and result.get('display_irq_progressed') and result.get('display_restored') and result.get('namespace_child_gone') and result['parent_state_unchanged'] and result['kernel_after']['boot_id']==boot and result['kernel_after']['taint']==0 and not result['kernel_delta']['fault_signatures'] and result['kernel_delta']['complete'])
  directory=Path('/var/lib/g955n/panel-trials');directory.mkdir(parents=True,exist_ok=True,mode=0o700)
  output=directory/(boot+'-'+str(time.time_ns())+'.json');output.write_text(json.dumps(result,indent=2));output.chmod(0o600)
  print(json.dumps(result,indent=2),flush=True)
 return result['passed']

def main():
 p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group();mode.add_argument('--launch',action='store_true');mode.add_argument('--run',action='store_true');mode.add_argument('--inner',action='store_true');mode.add_argument('--restore',action='store_true')
 p.add_argument('--reviewed-manifest',type=Path);p.add_argument('--manifest-sha256');a=p.parse_args()
 if a.restore:
  os.umask(0o077);restore();return 0
 if not(a.launch or a.run or a.inner):p.print_help();return 0
 if not a.reviewed_manifest or not re.fullmatch(r'[0-9a-f]{64}',a.manifest_sha256 or ''):p.error('Exact reviewed manifest/hash required')
 os.umask(0o077)
 if a.launch:
  identity();review(a.reviewed_manifest,a.manifest_sha256)
  return subprocess.run(['systemd-run','--unit=g955n-panel-trial','--wait','--collect','--property=RuntimeMaxSec=85','--property=TimeoutStopSec=5','--property=KillMode=control-group',
   '--property=ExecStopPost=/usr/bin/python3 '+str(BASE/'run-panel-trial.py')+' --restore','/usr/bin/python3',str(BASE/'run-panel-trial.py'),'--run','--reviewed-manifest',str(a.reviewed_manifest),'--manifest-sha256',a.manifest_sha256]).returncode
 if a.inner:
  data,package=review(a.reviewed_manifest,a.manifest_sha256);identity(data['boot_id'])
  package['diagnostic_debugger']=data.get('diagnostic_debugger') is True
  package['diagnostic_trace']=data.get('diagnostic_trace') is True
  report=inner(data['boot_id'],package);print(json.dumps(report,indent=2));return 0 if report['panel_presented'] else 1
 return 0 if execute(a.reviewed_manifest,a.manifest_sha256) else 1
if __name__=='__main__':raise SystemExit(main())
