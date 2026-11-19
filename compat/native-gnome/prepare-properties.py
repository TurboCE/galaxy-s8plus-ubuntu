#!/usr/bin/python3
"""Explicit root preparation of an own-device static property snapshot only."""
import argparse
import os
from pathlib import Path
import subprocess
PREFIX=Path('/opt/g955n-native-gpu')
def snapshot(system,vendor,cmdline):
 props={}
 for text in (system,vendor):
  for line in text.splitlines():
   if line.startswith('#') or '=' not in line:continue
   k,v=line.split('=',1)
   if k and len(v)<91:props.setdefault(k,v)
 for item in cmdline.split():
  if item.startswith('androidboot.') and '=' in item:
   k,v=item.split('=',1);props.setdefault('ro.'+k[12:],v)
 if props.get('ro.board.platform')!='exynos5' or props.get('ro.hardware')!='samsungexynos8895':raise RuntimeError('Original platform metadata differs')
 return ''.join(k+'='+v+'\n' for k,v in sorted(props.items()))
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');a=p.parse_args()
 if not a.prepare:p.print_help();return 0
 if os.getuid()!=0 or b'SM-G955N' not in Path('/proc/device-tree/model').read_bytes():raise RuntimeError('Wrong target/root')
 options=subprocess.check_output(['findmnt','-n','-o','OPTIONS','/android/system'],text=True).strip().split(',')
 if 'ro' not in options:raise RuntimeError('Original SYSTEM must be read-only')
 data=snapshot(Path('/system/build.prop').read_text(),Path('/android/system/vendor/build.prop').read_text(),Path('/proc/cmdline').read_text())
 temporary=PREFIX/'device-properties.new';temporary.write_text(data);temporary.chmod(0o644);temporary.replace(PREFIX/'device-properties')
 print('Own-device SYSTEM/vendor/full boot properties prepared; no Android service started')
if __name__=='__main__':raise SystemExit(main())
