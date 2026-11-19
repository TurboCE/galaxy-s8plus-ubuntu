#!/usr/bin/env python3
"""Build-only private Mesa client fixture; no handset access or runtime execution."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--archive',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();scripts=Path(__file__).resolve().parent
pin=json.loads((scripts/'sources.json').read_text())['mesa-demos-client-fixture']
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
if sha(a.archive)!=pin['archive_sha256'] or a.output.exists():raise SystemExit('Pinned archive and fresh output required')
a.output.mkdir(parents=True,mode=0o700);src=a.output/'source';src.mkdir()
files=['src/egl/eglut/'+s for s in ['eglut.c','eglut.h','eglutint.h','eglut_wayland.c']]
files+=['src/egl/opengles2/es2gears.c','src/util/matrix.c','src/util/matrix.h']
with tarfile.open(a.archive) as tar:
 for name in files:
  entry=tar.getmember('mesa-demos-9.0.0/'+name)
  if not entry.isfile():raise SystemExit('Not a regular source')
  target=src/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(tar.extractfile(entry).read())
for number in ['0009','0010']:
 patch=next((scripts/'patches').glob(number+'-*.patch'))
 subprocess.run(['patch','-p1','--forward','--batch','-d',str(src)],input=patch.read_bytes(),check=True)
env={**__import__('os').environ,'PKG_CONFIG_LIBDIR':'/usr/lib/aarch64-linux-gnu/pkgconfig:/usr/share/pkgconfig'}
flags=subprocess.check_output(['pkg-config','--cflags','--libs','egl','glesv2','wayland-client','wayland-egl','xkbcommon','libdecor-0'],env=env,text=True).split()
binary=a.output/'es2gears-wayland-safe'
subprocess.run(['aarch64-linux-gnu-gcc','-O2','-g','-D_GNU_SOURCE','-Isrc/egl/eglut','-Isrc/util',
 'src/egl/opengles2/es2gears.c','src/egl/eglut/eglut.c','src/egl/eglut/eglut_wayland.c','src/util/matrix.c',
 *flags,'-lm','-o',str(binary.resolve())],cwd=src,check=True)
header=subprocess.check_output(['readelf','-h',str(binary)],text=True)
if 'AArch64' not in header:raise SystemExit('Wrong target architecture')
record={'source':pin,'binary_sha256':sha(binary),'source_hashes':{f:sha(src/f) for f in files},'status':'built only; not executed'}
(a.output/'build.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
