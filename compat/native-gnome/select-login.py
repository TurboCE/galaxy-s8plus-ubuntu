#!/usr/bin/python3
"""Explicit selection of an already installed/qualified native GPU session.

Default prints help. Does not install binaries, restart GDM, flash or reboot.
Run the staged session.py --check and real-session verifier separately.
"""
import argparse
import configparser
import os
from pathlib import Path
import shutil
import subprocess
import time

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--select-default',action='store_true');a=p.parse_args()
 if not a.select_default:p.print_help();return 0
 if os.getuid()!=0 or b'SM-G955N' not in Path('/proc/device-tree/model').read_bytes():raise RuntimeError('Wrong root/target')
 for path in ['/opt/g955n-native-gpu/session.py','/opt/g955n-native-gpu/device-properties','/usr/share/xsessions/ubuntu-g955n.desktop']:
  s=Path(path).stat()
  if s.st_uid!=0 or s.st_mode&0o022:raise RuntimeError('GPU session inputs must be root-owned')
 backup=Path('/var/lib/g955n/native-gpu-login-backup')/time.strftime('%Y%m%dT%H%M%S');backup.mkdir(parents=True,mode=0o700)
 conf=Path('/etc/gdm3/custom.conf');shutil.copy2(conf,backup/'custom.conf')
 old=Path('/var/lib/AccountsService/users/ubuntu')
 if old.exists():shutil.copy2(old,backup/'accounts-ubuntu')
 c=configparser.ConfigParser();c.optionxform=str;c.read_string(conf.read_text());c.setdefault('daemon',{});c['daemon']['DefaultSession']='ubuntu-g955n.desktop';c['daemon']['AutomaticLoginEnable']='false'
 temporary=conf.with_suffix('.g955n-new')
 with temporary.open('w') as f:c.write(f)
 temporary.chmod(0o644);temporary.replace(conf)
 for method,value in [('SetXSession','ubuntu-g955n'),('SetSession','ubuntu-g955n'),('SetSessionType','x11')]:
  subprocess.run(['gdbus','call','--system','--dest','org.freedesktop.Accounts','--object-path','/org/freedesktop/Accounts/User1000','--method','org.freedesktop.Accounts.User.'+method,value],check=True)
 print('Default GPU session selected with manual authentication; existing session continues; backup='+str(backup))
if __name__=='__main__':raise SystemExit(main())
