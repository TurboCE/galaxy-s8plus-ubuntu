#!/usr/bin/env python3
"""Bounded GUI broker and fixed host-PID entry point; default prints help only.

Android HAL/compositor retain their private PID/proc view. The Linux GUI alone
gets a fresh read-only host-PID proc view before dropping every capability and
entering the fixed unprivileged GNOME command. No flash/global GL/login change.
"""
import argparse
import array
import ctypes
import json
import os
from pathlib import Path
import resource
import selectors
import signal
import socket
import stat
import subprocess
import time
from importlib.machinery import SourceFileLoader

BASE=Path(__file__).resolve().parent
UNIT='g955n-panel-trial.service'
MAXIMUM=16384

def rpc(sock,action,env=None,fd=None):
 data={'action':action}
 if env is not None:data['environment']=env
 ancillary=[] if fd is None else [(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[fd]))]
 payload=json.dumps(data).encode()
 if len(payload)>MAXIMUM:raise RuntimeError('GUI request too large')
 sock.sendmsg([payload],ancillary)
 response=json.loads(sock.recv(MAXIMUM))
 if response.get('error'):raise RuntimeError(response['error'])
 return response

class RemoteGui:
 def __init__(self,sock,env,log):
  self.sock=sock;self.pid=rpc(sock,'launch',env,log.fileno())['host_pid'];self.is_remote=True
 def poll(self):return rpc(self.sock,'poll')['returncode']
 def stop(self):return rpc(self.sock,'stop')['cleanup']

class Broker:
 def __init__(self,child,manifest,sha):
  self.child=str(child);self.manifest=manifest;self.sha=sha;self.process=None;self.mount_ns=None
  self.host_pid_ns=os.readlink('/proc/self/ns/pid');self.host_mount_ns=os.readlink('/proc/self/ns/mnt')
  self.android_mount_ns=os.readlink('/proc/'+self.child+'/ns/mnt');self.last_cleanup=None
 def update_namespace(self):
  if self.process:
   try:
    value=os.readlink('/proc/'+str(self.process.pid)+'/ns/mnt')
    if value not in (self.host_mount_ns,self.android_mount_ns):self.mount_ns=value
   except FileNotFoundError:pass
 def matching(self,pid):
  if not self.mount_ns or self.mount_ns in (self.host_mount_ns,self.android_mount_ns):return False
  try:return os.readlink('/proc/'+str(pid)+'/ns/mnt')==self.mount_ns and UNIT in Path('/proc',str(pid),'cgroup').read_text()
  except (FileNotFoundError,ProcessLookupError,PermissionError):return False
 def stop(self):
  if not self.process:return {'reaped':True,'remaining':[]}
  self.update_namespace()
  for sig in (signal.SIGTERM,signal.SIGKILL):
   # Recheck namespace/cgroup before each signal to avoid unrelated PID reuse.
   for p in Path('/proc').glob('[0-9]*'):
    pid=int(p.name)
    if self.matching(pid):
     try:os.kill(pid,sig)
     except ProcessLookupError:pass
   if self.process.poll() is None:
    try:os.killpg(self.process.pid,sig)
    except ProcessLookupError:pass
   time.sleep(.1)
  try:self.process.wait(timeout=1)
  except subprocess.TimeoutExpired:pass
  remaining=[int(p.name) for p in Path('/proc').glob('[0-9]*') if self.matching(int(p.name))]
  self.last_cleanup={'wrapper_exit':self.process.poll(),'reaped':self.process.poll() is not None,'remaining':remaining,'host_mount_namespace':self.mount_ns}
  return self.last_cleanup
 def dispatch(self,sock):
  payload,ancillary,flags,_=sock.recvmsg(MAXIMUM,socket.CMSG_SPACE(4))
  fds=[]
  try:
   if not payload or flags&(socket.MSG_TRUNC|socket.MSG_CTRUNC):raise RuntimeError('Incomplete GUI request')
   for level,kind,data in ancillary:
    if level!=socket.SOL_SOCKET or kind!=socket.SCM_RIGHTS:raise RuntimeError('Unexpected GUI control descriptor')
    values=array.array('i');values.frombytes(data[:len(data)//values.itemsize*values.itemsize]);fds.extend(values)
   message=json.loads(payload);action=message.get('action')
   if action=='launch':
    if self.process or len(fds)!=1:raise RuntimeError('GUI already launched or missing stdout descriptor')
    info=os.fstat(fds[0])
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_nlink:raise RuntimeError('GUI log must be a private unlinked root file')
    env=message.get('environment')
    if not isinstance(env,dict) or any(not isinstance(k,str) or not isinstance(v,str) or '\0' in k+v or '=' in k for k,v in env.items()):raise RuntimeError('Invalid unprivileged environment')
    # Root setup never inherits GL/linker paths from the unprivileged payload.
    clean={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','G955N_HOST_PID_NS':self.host_pid_ns,
     'G955N_HOST_MOUNT_NS':self.host_mount_ns,'G955N_ANDROID_MOUNT_NS':self.android_mount_ns,
     'G955N_GUI_PARENT':str(os.getpid())}
    read_fd,write_fd=os.pipe()
    try:
     os.write(write_fd,json.dumps(env).encode());os.close(write_fd);write_fd=None
     command=['nsenter','--target',self.child,'--mount','--root','--wdns=/','unshare','--mount','--propagation','unchanged',
      '/usr/bin/python3','-I',str(BASE/'host-pid-gui.py'),'--enter','--environment-fd',str(read_fd),
      '--reviewed-manifest',str(self.manifest),'--manifest-sha256',self.sha]
     self.process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=fds[0],stderr=fds[0],env=clean,
      pass_fds=(read_fd,),start_new_session=True,close_fds=True)
    finally:
     os.close(read_fd)
     if write_fd is not None:os.close(write_fd)
    deadline=time.monotonic()+2
    while not self.mount_ns and time.monotonic()<deadline and self.process.poll() is None:
     self.update_namespace();time.sleep(.01)
    if not self.mount_ns:raise RuntimeError('Host GUI mount provenance was not observed')
    response={'host_pid':self.process.pid}
   elif action=='poll':
    if fds or not self.process:raise RuntimeError('GUI poll without a launched process')
    self.update_namespace();response={'returncode':self.process.poll()}
   elif action=='stop':
    if fds:raise RuntimeError('Unexpected stop descriptor')
    response={'cleanup':self.stop()}
   else:raise RuntimeError('Unknown GUI operation')
   sock.send(json.dumps(response).encode())
  except Exception as error:
   sock.send(json.dumps({'error':str(error)}).encode())
  finally:
   for fd in fds:os.close(fd)

def run_inner(command,timeout,child,manifest,sha):
 parent,inner=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
 broker=Broker(child,manifest,sha);process=None;out=bytearray();err=bytearray()
 try:
  process=subprocess.Popen([*command,'--host-gui-fd',str(inner.fileno())],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
   stdin=subprocess.DEVNULL,pass_fds=(inner.fileno(),),start_new_session=True)
  inner.close();watch=selectors.DefaultSelector();watch.register(parent,selectors.EVENT_READ,'control')
  for name,pipe in [('out',process.stdout),('err',process.stderr)]:
   os.set_blocking(pipe.fileno(),False);watch.register(pipe,selectors.EVENT_READ,name)
  deadline=time.monotonic()+timeout
  while time.monotonic()<deadline:
   for key,_ in watch.select(.05):
    if key.data=='control':
     if parent.recv(1,socket.MSG_PEEK):broker.dispatch(parent)
     else:watch.unregister(parent)
    else:
     payload=os.read(key.fd,65536)
     if payload:(out if key.data=='out' else err).extend(payload)
     else:watch.unregister(key.fileobj)
   if len(out)>16*1024*1024 or len(err)>4*1024*1024:raise RuntimeError('GUI coordinator log bound exceeded')
   if process.poll() is not None and not any(key.data!='control' for key in watch.get_map().values()):break
  else:raise subprocess.TimeoutExpired(command,timeout)
  return subprocess.CompletedProcess(command,process.returncode,out.decode(errors='replace'),err.decode(errors='replace')),broker.stop()
 finally:
  broker.stop()
  if process and process.poll() is None:
   try:os.killpg(process.pid,signal.SIGKILL)
   except ProcessLookupError:pass
   process.wait(timeout=2)
  parent.close();inner.close()

def main():
 p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group()
 mode.add_argument('--enter',action='store_true');mode.add_argument('--post-drop',action='store_true')
 p.add_argument('--environment-fd',type=int);p.add_argument('--reviewed-manifest',type=Path);p.add_argument('--manifest-sha256')
 a=p.parse_args()
 if not(a.enter or a.post_drop):p.print_help();return 0
 expected_parent=int(os.environ.get('G955N_GUI_PARENT','0'))
 if expected_parent<=1 or os.getppid()!=expected_parent:raise RuntimeError('Wrong GUI supervisor')
 if a.enter:
  if os.geteuid()!=0 or not a.reviewed_manifest or a.environment_fd is None:raise RuntimeError('Reviewed root setup only')
  panel=SourceFileLoader('host_gui_review',str(BASE/'run-panel-trial.py')).load_module()
  data,package=panel.review(a.reviewed_manifest,a.manifest_sha256);panel.identity(data['boot_id'])
  if not package.get('host_pid_client'):raise RuntimeError('Host PID client was not reviewed')
  if os.getcwd()!='/' or os.stat('.').st_ino!=os.stat('/').st_ino:raise RuntimeError('GUI private root/CWD missing')
  payload=os.read(a.environment_fd,MAXIMUM+1);os.close(a.environment_fd)
  if len(payload)>MAXIMUM:raise RuntimeError('Unprivileged environment too large')
  env=json.loads(payload)
  if env.get('DISPLAY')!=':77' or env.get('HYBRIS_EGLPLATFORM')!='x11' or env.get('COGL_RENDERER')!='EGL_XLIB':raise RuntimeError('Fixed GNOME environment missing')
  # The inherited Android view is already recursively private. Its chroot
  # directory is not itself a mount point; operate on the actual proc mount.
  subprocess.run(['mount','--make-private','/proc'],check=True)
  subprocess.run(['mount','-t','proc','-o','ro,nosuid,nodev,noexec','proc','/proc'],check=True)
  if os.readlink('/proc/self/ns/pid')!=os.environ['G955N_HOST_PID_NS']:raise RuntimeError('GUI did not retain host PIDs')
  if os.readlink('/proc/self/ns/mnt') in (os.environ['G955N_HOST_MOUNT_NS'],os.environ['G955N_ANDROID_MOUNT_NS']):raise RuntimeError('GUI mount namespace was not separated')
  if any(' shared:' in line or ' master:' in line for line in Path('/proc/self/mountinfo').read_text().splitlines()):raise RuntimeError('GUI contains propagated mounts')
  if not os.statvfs('/proc').f_flag&os.ST_RDONLY:raise RuntimeError('GUI procfs is not read-only')
  resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_FSIZE,(128*1024*1024,128*1024*1024))
  env.update({k:v for k,v in os.environ.items() if k.startswith('G955N_') and k in ('G955N_HOST_PID_NS','G955N_HOST_MOUNT_NS','G955N_ANDROID_MOUNT_NS','G955N_GUI_PARENT')})
  arguments=['setpriv','--reuid=1000','--regid=1003','--groups=1026','--bounding-set=-all','--inh-caps=-all',
   '--ambient-caps=-all','--no-new-privs','/usr/bin/env','-i',*[k+'='+v for k,v in env.items()],
   '/usr/bin/python3','-I',str(BASE/'host-pid-gui.py'),'--post-drop']
  os.execve('/usr/bin/setpriv',arguments,{'PATH':'/usr/sbin:/usr/bin:/sbin:/bin'})
 if os.getuid()!=1000 or os.getgid()!=1003:raise RuntimeError('GUI identity not dropped')
 fields=dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
 if any(int(fields[k],16) for k in ('CapEff','CapPrm','CapBnd','CapAmb')) or ctypes.CDLL(None).prctl(39,0,0,0,0)!=1:raise RuntimeError('GUI capabilities/NNP differ')
 if os.readlink('/proc/self/ns/pid')!=os.environ['G955N_HOST_PID_NS']:raise RuntimeError('GUI host-PID provenance changed')
 if ctypes.CDLL(None).prctl(1,signal.SIGKILL,0,0,0) or os.getppid()!=expected_parent:raise RuntimeError('GUI parent-death cleanup failed')
 print('G955N host-PID GUI verified uid=1000 capabilities=0 proc=read-only pid='+str(os.getpid()),flush=True)
 os.execve('/usr/bin/dbus-run-session',['dbus-run-session','--','/usr/bin/gnome-shell','--x11','--replace','--sm-disable'],os.environ)

if __name__=='__main__':raise SystemExit(main())
