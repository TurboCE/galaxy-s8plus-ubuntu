#!/usr/bin/env python3
"""Package a private linked prefix; never execute binaries or contact a handset."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--work',type=Path,default=Path('/work'))
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
if a.work != Path('/work') or a.output.exists():raise SystemExit('Use dedicated /work and fresh output')
prefix=a.work/'prefix'; a.output.mkdir(parents=True,mode=0o700)
required=['bin/tinywl-g955n-candidate','lib/libEGL.so.1','lib/libGLESv2.so.2',
          'lib/libhardware.so.2','lib/libgralloc.so.1','lib/libhwc2.so.1']
# Actual upstream plugin names and versions are checked rather than invented.
required += ['lib/libhybris/eglplatform_'+name+'.so' for name in ('null','hwcomposer','wayland')]
required += [str(f.relative_to(prefix)) for f in (prefix/'lib/libhybris/linker').glob('*.so')]
seen=set(); external=set(); elf={}
def copy(relative):
    if relative in seen:return
    seen.add(relative);src=prefix/relative;dst=a.output/relative
    if not src.exists():raise SystemExit('Required linked input absent: '+relative)
    dst.parent.mkdir(parents=True,exist_ok=True)
    if src.is_symlink():
        target=src.readlink()
        resolved=src.resolve()
        if not resolved.is_relative_to(prefix):raise SystemExit('Prefix link escapes: '+relative)
        dst.symlink_to(target if not target.is_absolute() else Path(__import__('os').path.relpath(resolved,src.parent)))
        immediate = Path(__import__('os').path.normpath(str(src.parent/target))) if not target.is_absolute() else resolved
        copy(str(immediate.relative_to(prefix)));return
    shutil.copy2(src,dst)
    dynamic=subprocess.check_output(['readelf','-d',str(src)],text=True)
    header=subprocess.check_output(['readelf','-h',str(src)],text=True)
    if 'AArch64' not in header or '(TEXTREL)' in dynamic:raise SystemExit('Unexpected ELF')
    deps=re.findall(r'\(NEEDED\).*\[(.*?)\]',dynamic)
    elf[relative]={'sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'needed':deps,'bytes':src.stat().st_size}
    for dep in deps:
        match=prefix/'lib'/dep
        if match.exists():copy('lib/'+dep)
        else:external.add(dep)
for name in required:copy(name)
for link in a.output.rglob('*'):
    if link.is_symlink() and not link.exists():raise SystemExit('Broken packaged link: '+str(link))
android=a.output/'android';android.mkdir()
src=a.work/'hwc2-android9/libhwc2_compat_layer.so'
shutil.copy2(src,android/src.name)
elf['android/'+src.name]={'sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'abi':'Bionic Android9; private Android loader path only'}
base='/home/ubuntu/g955n-compositor'
env={'LD_LIBRARY_PATH':base+'/lib','HYBRIS_EGLPLATFORM':'hwcomposer','HYBRIS_ANDROID_SDK_VERSION':'28',
     'HYBRIS_EGLPLATFORM_DIR':base+'/lib/libhybris','HYBRIS_LINKER_DIR':base+'/lib/libhybris/linker',
     'HYBRIS_LD_LIBRARY_PATH':base+'/android:/system/lib64:/vendor/lib64',
     'LIBEGL':'/vendor/lib64/egl/libGLES_mali.so','LIBGLESV2':'/vendor/lib64/egl/libGLES_mali.so',
     'WLR_BACKENDS':'hwcomposer','WLR_RENDERER':'gles2'}
record={'target':'SM-G955N','status':'packaged only; not executed; not hardware qualified','destination':base,
        'files':elf,'symlinks':{str(f.relative_to(a.output)):str(f.readlink()) for f in a.output.rglob('*') if f.is_symlink()},
        'external_linux_dependencies':sorted(external),'process_private_environment':env,
        'requires':'independently supervised Android manager/allocator/composer plus exclusive display and restoration watchdog'}
(a.output/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'file_count':len(elf),'external':sorted(external),'output':str(a.output)},indent=2))
