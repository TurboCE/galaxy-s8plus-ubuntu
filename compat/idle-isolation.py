#!/usr/bin/python3
"""Reversible C2-only fault isolation on SM-G955N. This is not a stability fix."""
import argparse
import json
import os
import stat
from pathlib import Path
RECORD=Path('/var/lib/g955n/idle-diagnostic.json')
def main():
 p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group();m.add_argument('--isolate-c2',action='store_true');m.add_argument('--restore',action='store_true');a=p.parse_args()
 if not(a.isolate_c2 or a.restore):p.print_help();return 0
 if os.getuid()!=0 or b'SM-G955N' not in Path('/proc/device-tree/model').read_bytes() or 'g955n-ubuntu' not in os.uname().release:raise RuntimeError('Wrong target/root')
 boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 nodes={}
 for cpu in Path('/sys/devices/system/cpu').glob('cpu[0-7]'):
  for state in cpu.glob('cpuidle/state*'):
   if state.name=='state1' and (state/'desc').read_text().strip()=='c2' and (state/'name').read_text().strip() in ('bootcl-cpu-slee','nobootcl-cpu-sl'):nodes[str(state/'disable')]=(state/'disable').read_text().strip()
 if len(nodes)!=8:raise RuntimeError('Expected exactly eight actual C2 states; no changes')
 if a.restore:
  st=RECORD.lstat()
  if not stat.S_ISREG(st.st_mode):raise RuntimeError('Untrusted restore record')
  r=json.loads(RECORD.read_text())
  if st.st_uid or st.st_mode&0o077 or r['boot_id']!=boot or set(r['original'])!=set(nodes):raise RuntimeError('Wrong diagnostic restore record')
  for path,value in r['original'].items():
   if value not in ('0','1'):raise RuntimeError('Invalid original C2 state')
  for path,value in r['original'].items():Path(path).write_text(value)
  RECORD.unlink();print('Original C2 settings restored');return 0
 if RECORD.exists():raise RuntimeError('Restore the existing diagnostic first')
 RECORD.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 info=RECORD.parent.stat()
 if info.st_uid or info.st_mode&0o022:raise RuntimeError('Untrusted diagnostic directory')
 fd=os.open(RECORD,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'w') as output:
  json.dump({'boot_id':boot,'original':nodes,'diagnostic_only':True},output);output.flush();os.fsync(output.fileno())
 try:
  for path in nodes:Path(path).write_text('1')
  if any(Path(path).read_text().strip()!='1' for path in nodes):raise RuntimeError('C2 readback mismatch')
 except BaseException:
  for path,value in nodes.items():Path(path).write_text(value)
  RECORD.unlink();raise
 print('Only C2 isolated on eight CPUs for diagnosis; WFI/governors unchanged; not a fix; reverts at boot or --restore')
if __name__=='__main__':raise SystemExit(main())
