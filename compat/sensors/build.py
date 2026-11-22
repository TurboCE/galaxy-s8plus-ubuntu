#!/usr/bin/env python3
"""Build-only Samsung SSP SensorProxy candidate; no handset/runtime access."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import tarfile
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
if hashlib.sha256(a.archive.read_bytes()).hexdigest()!='8689425f2287626a95d95b1e1e5b62e497d09dd08cf411084ed22166d4a49da5':raise SystemExit('Wrong Ubuntu 3.5 source archive')
if a.output.exists():raise SystemExit('Fresh output required')
a.output.mkdir(parents=True)
with tarfile.open(a.archive) as t:
 for m in t.getmembers():
  if not m.isfile() and not m.isdir():raise SystemExit('Unexpected source member')
  if Path(m.name).is_absolute() or '..' in Path(m.name).parts:raise SystemExit('Unsafe source archive')
 t.extractall(a.output,filter='data')
root=a.output/'iio-sensor-proxy-3.5';scripts=Path(__file__).resolve().parent
for name in ('drv-samsung-ssp.c', 'ssp-heading.h'):
 shutil.copy2(scripts/name, root/'src'/name)
p=root/'src/meson.build';s=p.read_text();assert s.count("  'drivers.c',")==1;s=s.replace("  'drivers.c',","  'drivers.c',\n  'drv-samsung-ssp.c',");p.write_text(s)
p=root/'src/drivers.h';p.write_text(p.read_text()+'\nextern SensorDriver samsung_ssp_accel;\nextern SensorDriver samsung_ssp_light;\nextern SensorDriver samsung_ssp_proximity;\nextern SensorDriver samsung_ssp_compass;\n')
p=root/'src/iio-sensor-proxy.c';s=p.read_text();assert s.count('static const SensorDriver * const drivers[] = {')==1;p.write_text(s.replace('static const SensorDriver * const drivers[] = {','static const SensorDriver * const drivers[] = {\n\t&samsung_ssp_accel,\n\t&samsung_ssp_light,\n\t&samsung_ssp_proximity,\n\t&samsung_ssp_compass,'))
patch=scripts/'0001-release-owned-claims-after-session-inactivation.patch'
subprocess.run(['patch','--fuzz=0','-p1','--forward','--batch','-d',str(root)],input=patch.read_bytes(),check=True)
subprocess.run(['meson','setup',str(a.output/'build'),str(root),'--cross-file',str(scripts/'cross-arm64.ini'),'--prefix=/opt/g955n-sensors','--libexecdir=libexec','--wrap-mode=nodownload','-Dgtk-tests=false','-Dtests=false','-Dgtk_doc=false','-Dudevrulesdir=/lib/udev/rules.d','-Dsystemdsystemunitdir=/lib/systemd/system'],check=True)
subprocess.run(['ninja','-C',str(a.output/'build'),'src/iio-sensor-proxy','src/monitor-sensor'],check=True)
for name in ['iio-sensor-proxy','monitor-sensor']:
 f=a.output/'build/src'/name
 if 'AArch64' not in subprocess.check_output(['readelf','-h',str(f)],text=True):raise SystemExit('Wrong target ELF')
print('AArch64 SensorProxy candidate built; not deployed/qualified')
