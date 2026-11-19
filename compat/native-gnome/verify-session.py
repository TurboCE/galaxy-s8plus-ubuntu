#!/usr/bin/python3
"""Explicit, bounded verification of a real logged-in SM-G955N GNOME session.

Runs the fixed GPU pixel/compositor fixture; no login/authentication changes.
Raw reports stay private under /var/lib/g955n; never commit them.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
PREFIX=Path('/opt/g955n-native-gpu')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--verify',action='store_true');p.add_argument('--probe-sha256');a=p.parse_args()
 if not a.verify:p.print_help();return 0
 if os.getuid()!=0 or b'SM-G955N' not in Path('/proc/device-tree/model').read_bytes():raise RuntimeError('Wrong target/root')
 probe=PREFIX/'bin/session-x11-pixel-probe';st=probe.stat()
 if st.st_uid!=0 or st.st_mode&0o022 or hashlib.sha256(probe.read_bytes()).hexdigest()!=a.probe_sha256:raise RuntimeError('Unreviewed fixture')
 shells=[]
 for proc in Path('/proc').glob('[0-9]*'):
  try:
   if proc.stat().st_uid==1000 and (proc/'cmdline').read_bytes().split(b'\0')[0]==b'/usr/bin/gnome-shell':shells.append(proc)
  except (FileNotFoundError,ProcessLookupError):pass
 if len(shells)!=1:raise RuntimeError('Exactly one owner GNOME shell required')
 proc=shells[0];start=(proc/'stat').read_text().split()[21];env=dict(x.split('=',1) for x in (proc/'environ').read_bytes().decode().split('\0') if '=' in x)
 if env.get('XDG_SESSION_DESKTOP')!='ubuntu-g955n' or env.get('COGL_RENDERER')!='EGL_XLIB':raise RuntimeError('Not the normal GPU login')
 # Visibility assertions are invalid behind the lock-screen compositor.
 # Query the real owner session; do not unlock it or change authentication.
 visible=subprocess.run(['setpriv','--reuid=1000','--regid=1000','--init-groups','--no-new-privs','/usr/bin/gdbus','call','--session','--dest','org.gnome.ScreenSaver','--object-path','/org/gnome/ScreenSaver','--method','org.gnome.ScreenSaver.GetActive'],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5)
 if visible.returncode or visible.stdout.strip()!='(false,)':
  print(json.dumps({'status':'incomplete','reason':'owner desktop locked or visibility unavailable','trials_run':0}),flush=True)
  return 2
 maps=(proc/'maps').read_text();boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 checks={'mali_driver_loaded':'libGLES_mali.so' in maps,'exynos_gralloc_loaded':'gralloc.exynos5.so' in maps,'private_egl_loaded':str(PREFIX/'lib/libEGL') in maps,'no_swrast':'swrast_dri.so' not in maps,'no_property_daemon':not Path('/dev/__properties__').exists()}
 if not all(checks.values()):raise RuntimeError('Wrong actual loaded graphics stack: '+str(checks))
 since=time.strftime('%Y-%m-%d %H:%M:%S',time.localtime());report={'boot_id':boot,'shell_pid':int(proc.name),'checks':checks,'trials':[]}
 for i in range(3):
  r=subprocess.run(['setpriv','--reuid=1000','--regid=1000','--init-groups','--no-new-privs',str(probe),'--run-session-x11-composite-trial',boot],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=35)
  report['trials'].append({'exit':r.returncode,'output':r.stdout})
  if r.returncode or 'G955N_X11_COMPOSITE_PASS' not in r.stdout or 'G955N_GNOME_POPUP_PASS' not in r.stdout:break
  print('Normal GNOME GPU composite/popup trial',i+1,'passed',flush=True)
 report['same_shell']=(proc/'stat').read_text().split()[21]==start
 report['same_boot']=Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot
 report['taint']=Path('/proc/sys/kernel/tainted').read_text().strip()
 report['kernel_log']=subprocess.check_output(['journalctl','-k','--since',since,'--no-pager'],text=True)
 report['new_faults']=bool(re.search(r'BUG:|Oops:|Kernel panic|use-after-free|translation fault|GPU fault|MMU fault',report['kernel_log'],re.I))
 report['renderer_log']=subprocess.check_output(['journalctl','_PID='+proc.name,'--no-pager','-g','Hybris actual GL_RENDERER'],text=True)
 report['passed']=len(report['trials'])==3 and all(r['exit']==0 and 'G955N_X11_COMPOSITE_PASS' in r['output'] and 'G955N_GNOME_POPUP_PASS' in r['output'] for r in report['trials']) and report['same_shell'] and report['same_boot'] and report['taint']=='0' and not report['new_faults'] and 'Mali-G71' in report['renderer_log']
 out=Path('/var/lib/g955n/native-gpu');out.mkdir(mode=0o700,exist_ok=True);path=out/('session-'+time.strftime('%Y%m%dT%H%M%S')+'.json');path.write_text(json.dumps(report,indent=2));path.chmod(0o600)
 print(json.dumps({'passed':report['passed'],'checks':checks,'same_shell':report['same_shell'],'same_boot':report['same_boot'],'taint':report['taint'],'new_kernel_faults':report['new_faults'],'report':str(path)}),flush=True)
 return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
