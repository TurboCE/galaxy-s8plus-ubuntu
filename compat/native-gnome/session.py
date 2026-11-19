#!/usr/bin/python3
"""Own-device GNOME/X11 launcher. No action without --check or --session.

Uses mur44ev's opt-in Android9 property/X11 setup, adapted to glibc and
normal GDM/PAM. Never changes system GL, authentication, or device permissions.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

PREFIX=Path('/opt/g955n-native-gpu')
ENV={
 'LD_LIBRARY_PATH':str(PREFIX/'lib'),
 'HYBRIS_EGLPLATFORM':'x11','HYBRIS_EGLPLATFORM_DIR':str(PREFIX/'lib/libhybris'),
 'HYBRIS_LINKER_DIR':str(PREFIX/'lib/libhybris/linker'),
 'HYBRIS_LD_LIBRARY_PATH':'/system/lib64:/vendor/lib64','HYBRIS_ANDROID_SDK_VERSION':'28',
 'HYBRIS_FORCE_LEGACY_PROPERTIES':'1','HYBRIS_PROPERTY_FILE':str(PREFIX/'device-properties'),
 'HYBRIS_X11_DISABLE_SHM':'1','HYBRIS_EGL_REPORT_RENDERER':'1',
 'LIBEGL':'/vendor/lib64/egl/libGLES_mali.so','LIBGLESV2':'/vendor/lib64/egl/libGLES_mali.so',
 'LIBGLESV1':'/vendor/lib64/egl/libGLES_mali.so',
 'COGL_DRIVER':'gles2','COGL_RENDERER':'EGL_XLIB','GDK_BACKEND':'x11','GDK_GL':'gles',
 'GSK_RENDERER':'gl','GNOME_SHELL_SESSION_MODE':'ubuntu',
}
REMOVE=('LD_PRELOAD','LIBGL_ALWAYS_SOFTWARE','GALLIUM_DRIVER','MESA_LOADER_DRIVER_OVERRIDE')
def trusted(path):
 s=path.stat()
 if s.st_uid!=0 or s.st_mode&0o022:raise RuntimeError('Untrusted GPU input: '+str(path))
def verify():
 if os.getuid()!=1000 or os.getgid()!=1000 or b'SM-G955N' not in Path('/proc/device-tree/model').read_bytes():raise RuntimeError('Wrong target/account')
 if os.environ.get('XDG_SESSION_TYPE','x11')!='x11' or not os.environ.get('DISPLAY'):raise RuntimeError('Native X11 display required')
 trusted(PREFIX);trusted(PREFIX/'manifest.json');trusted(PREFIX/'device-properties')
 manifest=json.loads((PREFIX/'manifest.json').read_text())
 if manifest['target']!='SM-G955N' or manifest['destination']!=str(PREFIX):raise RuntimeError('Wrong prefix')
 for name,data in manifest['files'].items():
  path=PREFIX/name
  if not path.resolve().is_relative_to(PREFIX):raise RuntimeError('Escaping GPU file')
  trusted(path)
  if hashlib.sha256(path.read_bytes()).hexdigest()!=data['sha256']:raise RuntimeError('Changed GPU library: '+name)
 for name,target in manifest['symlinks'].items():
  path=PREFIX/name
  if not path.is_symlink() or str(path.readlink())!=target or not path.resolve().is_relative_to(PREFIX):raise RuntimeError('Changed GPU link')
 for name in ('ion','mali0'):
  if not os.access('/dev/'+name,os.R_OK|os.W_OK):raise RuntimeError('GPU node access unavailable')
def environment(original):
 env={k:v for k,v in original.items() if k not in REMOVE};env.update(ENV);return env
def preflight(env):
 r=subprocess.run(['/usr/libexec/gnome-session-check-accelerated-gles-helper','--print-renderer'],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=25)
 sys.stderr.write(r.stderr)
 if r.returncode or 'Mali-G71' not in r.stdout or 'llvmpipe' in r.stdout:raise RuntimeError('GNOME GLES preflight failed: status='+str(r.returncode)+' renderer='+r.stdout.strip())
 print('G955N GNOME preflight: actual renderer='+r.stdout.strip(),flush=True)
def clear_cache(env):
 # Delete stale results from the preceding GDM/software backend. The stock
 # checker will populate these from actual GL/GLES; never forge a success atom.
 for atom in ('_GNOME_SESSION_ACCELERATED','_GNOME_IS_SOFTWARE_RENDERING','_GNOME_SESSION_RENDERER'):
  subprocess.run(['xprop','-root','-remove',atom],env=env,stdout=subprocess.DEVNULL,check=True,timeout=3)
def restore_activation(original,env):
 keys=sorted(set(ENV)|set(REMOVE))
 # DBus's API has no unset operation: empty values restore the absence of
 # private loader paths. systemd supports genuine unsetting as well.
 restored=[k+'='+original.get(k,'') for k in keys]
 subprocess.run(['dbus-update-activation-environment',*restored],env=original,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
 subprocess.run(['systemctl','--user','unset-environment',*[k for k in keys if k not in original]],env=original,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
 existing=[k+'='+original[k] for k in keys if k in original]
 if existing:subprocess.run(['systemctl','--user','set-environment',*existing],env=original,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
def main():
 p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group();g.add_argument('--check',action='store_true');g.add_argument('--session',action='store_true');a=p.parse_args()
 if not(a.check or a.session):p.print_help();return 0
 original=dict(os.environ);env=environment(original)
 try:verify();preflight(env)
 except (RuntimeError,OSError,subprocess.SubprocessError) as error:
  print('G955N GPU unavailable: '+str(error),file=sys.stderr,flush=True)
  if a.check:return 1
  # The existing Ubuntu session remains a real software fallback.
  fallback={k:v for k,v in original.items() if k not in ENV and k not in REMOVE};fallback['GNOME_SHELL_SESSION_MODE']='ubuntu'
  os.execve('/usr/bin/gnome-session',['gnome-session','--session=ubuntu'],fallback)
 if a.check:return 0
 clear_cache(env)
 child=subprocess.Popen(['/usr/bin/gnome-session','--session=ubuntu'],env=env)
 def forward(number,frame):
  if child.poll() is None:child.send_signal(number)
 for sig in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):signal.signal(sig,forward)
 try:return child.wait()
 finally:
  try:restore_activation(original,env)
  except (OSError,subprocess.SubprocessError) as error:print('GPU activation cleanup: '+str(error),file=sys.stderr)
if __name__=='__main__':raise SystemExit(main())
