#!/usr/bin/env python3
"""Build-only optional private X11 bridge; no handset access or runtime execution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--base-archive',type=Path,required=True)
p.add_argument('--reference-patch',type=Path,required=True)
a=p.parse_args();scripts=Path(__file__).resolve().parent;work=Path('/work');hybris=work/'input/libhybris';prefix=work/'prefix'
pin=json.loads((scripts/'sources.json').read_text())['x11-platform-reference']
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
if sha(a.base_archive)!=pin['base_archive_sha256'] or sha(a.reference_patch)!=pin['reference_patch_sha256']:raise SystemExit('Pinned public source checksums differ')
relative=Path('hybris/egl/platforms/x11');names={'Makefile.am','eglplatform_x11.cpp','x11_window.cpp','x11_window.h','xcb_drihybris.c','xcb_drihybris.h'}
x11_has_direct_patch=False
with tempfile.TemporaryDirectory() as temporary:
 root=Path(temporary)
 with tarfile.open(a.base_archive) as archive:
  for name in names:
   try:member=archive.getmember('libhybris-'+pin['base_commit']+'/'+str(relative/name))
   except KeyError:continue  # The reference adds these as complete new files.
   if not member.isfile():raise SystemExit('Unexpected source archive member')
   target=root/relative/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.extractfile(member).read())
 parts=a.reference_patch.read_text().split('diff --git ')
 selected=''.join('diff --git '+v for v in parts[1:] if v.startswith('a/'+str(relative)+'/'))
 if selected.count('diff --git ')!=len(names):raise SystemExit('Changed X11 reference file set')
 subprocess.run(['patch','--fuzz=0','-p1','--forward','--batch','-d',str(root)],input=selected,text=True,check=True)
 patch=next((scripts/'patches').glob('0013-*.patch'))
 subprocess.run(['patch','--fuzz=0','-p1','--forward','--batch','-d',str(root)],input=patch.read_bytes(),check=True)
 hashes={name:sha(root/relative/name) for name in names}
 for name in names:
  source=root/relative/name;target=hybris/relative/name
  if target.exists():
   if sha(target)!=hashes[name]:
    # Accept a repaired source only by exact reviewed reconstruction.
    repaired=root/'hybris/egl/platforms/x11'/name
    if name!='x11_window.cpp':raise SystemExit('Unreviewed existing X11 source: '+name)
    repair=next((scripts/'patches').glob('0019-*.patch')).read_text()
    subprocess.run(['patch','--fuzz=0','-p1','--forward','--batch','-d',str(root)],input=repair,text=True,check=True)
    if sha(target)!=sha(repaired):
     layout=next((scripts/'patches').glob('0024-*.patch')).read_text()
     subprocess.run(['patch','--fuzz=0','-p1','--forward','--batch','-d',str(root)],input=layout,text=True,check=True)
     if sha(target)!=sha(repaired):
      direct=next((scripts/'patches').glob('0025-*.patch')).read_text()
      subprocess.run(['patch','--fuzz=0','-p1','--forward','--batch','-d',str(root)],input=direct,text=True,check=True)
      if sha(target)!=sha(repaired):raise SystemExit('Unreviewed repaired X11 source: '+name)
      x11_has_direct_patch=True
  else:target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
for number in ['0014','0015','0018','0019','0021','0022','0023','0024','0025']:
 if x11_has_direct_patch and number in ('0019','0024','0025'):continue
 patch=next((scripts/'patches').glob(number+'-*.patch'))
 command=['patch','--fuzz=0','-p1','--batch','--silent','-d',str(hybris)]
 if subprocess.run([*command,'--forward','--dry-run'],input=patch.read_bytes()).returncode==0:
  subprocess.run([*command,'--forward'],input=patch.read_bytes(),check=True)
 elif subprocess.run([*command,'--reverse','--dry-run'],input=patch.read_bytes()).returncode:
  raise SystemExit('Unreviewed X11 core integration state')
license_file=scripts/'references/s8-x11-LICENSE'
if sha(license_file)!=pin['reference_license_sha256']:raise SystemExit('Changed reference license')
license_target=work/'sources/s8-x11-reference'/ 'LICENSE'
license_target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(license_file,license_target)
subprocess.run(['make','-C',str(hybris/'hybris'),'-j4'],check=True)
subprocess.run(['make','-C',str(hybris/'hybris'),'install'],check=True)
build=work/'build-x11-platform';build.mkdir(exist_ok=True);source=hybris/relative
includes=[hybris/'hybris',hybris/'hybris/common',hybris/'hybris/include',hybris/'hybris/egl',
 hybris/'hybris/egl/platforms/common',hybris/'hybris/platforms/common',work/'input/android9-headers']
common=['-fPIC','-O2','-g',*[item for path in includes for item in ['-I',str(path)]]]
env={**os.environ,'PKG_CONFIG_LIBDIR':'/usr/lib/aarch64-linux-gnu/pkgconfig:/usr/share/pkgconfig'}
packages=['x11','x11-xcb','xcb','xcb-present','xext','pixman-1']
flags=subprocess.check_output(['pkg-config','--cflags','--libs',*packages],env=env,text=True).split()
panel=scripts.parent/'native-gnome/direct-panel'
panel_object=build/'decon-output.o'
subprocess.run(['aarch64-linux-gnu-gcc','-std=c11','-fPIC','-O2','-Wall','-Wextra','-Werror',
                '-c',str(panel/'decon-output.c'),'-o',str(panel_object)],check=True)
common += ['-I',str(panel)]
objects=[str(panel_object)]
for name in ['eglplatform_x11.cpp','x11_window.cpp','xcb_drihybris.c']:
 obj=build/(name+'.o');objects.append(str(obj));cxx=name.endswith('.cpp')
 subprocess.run(['aarch64-linux-gnu-g++' if cxx else 'aarch64-linux-gnu-gcc',*common,*(['-std=c++17'] if cxx else []),'-Wall','-Wextra','-c',str(source/name),'-o',str(obj),*flags],check=True)
binary=prefix/'lib/libhybris/eglplatform_x11.so'
subprocess.run(['aarch64-linux-gnu-g++','-shared','-Wl,--no-undefined,-z,relro,-z,now',*objects,'-L'+str(prefix/'lib'),'-Wl,-rpath-link,'+str(prefix/'lib'),
 '-lhybris-eglplatformcommon','-lhybris-platformcommon','-lgralloc','-lsync','-lEGL','-lhybris-common','-lpthread','-ldl',*flags,'-o',str(binary)],check=True)
header=subprocess.check_output(['readelf','-h',str(binary)],text=True);dynamic=subprocess.check_output(['readelf','-d',str(binary)],text=True)
if 'AArch64' not in header or '(TEXTREL)' in dynamic:raise SystemExit('Unexpected X11 target ELF')
probe=build/'x11-pixel-probe'
subprocess.run(['aarch64-linux-gnu-gcc','-std=gnu11','-O2','-g','-Wall','-Wextra','-Werror',str(scripts/'x11-pixel-probe.c'),
 '-I'+str(prefix/'include'),'-L'+str(prefix/'lib'),'-Wl,-rpath-link,'+str(prefix/'lib'),'-lX11','-lEGL','-lGLESv2','-ldl','-o',str(probe)],check=True)
record={'pixel_probe_sha256':sha(probe),'pixel_probe_source_sha256':sha(scripts/'x11-pixel-probe.c'),'source':pin,'adaptation_sha256':sha(next((scripts/'patches').glob('0013-*.patch'))),'core_integration_sha256':sha(next((scripts/'patches').glob('0014-*.patch'))),'submission_order_sha256':sha(next((scripts/'patches').glob('0019-*.patch'))),'buffer_age_sha256':sha(next((scripts/'patches').glob('0018-*.patch'))),'gralloc_ownership_sha256':sha(next((scripts/'patches').glob('0015-*.patch'))),'gralloc_lifetime_sha256':sha(next((scripts/'patches').glob('0023-*.patch'))),'native_property_snapshot_sha256':sha(next((scripts/'patches').glob('0022-*.patch'))),'legacy_property_hooks_sha256':sha(next((scripts/'patches').glob('0021-*.patch'))),'direct_panel_trial_sha256':sha(next((scripts/'patches').glob('0025-*.patch'))),'overlay_layout_report_sha256':sha(next((scripts/'patches').glob('0024-*.patch'))),'source_hashes':{name:sha(hybris/relative/name) for name in names},'binary_sha256':sha(binary),'decon_submit_source_sha256':sha(panel/'decon-output.c'),'decon_submit_header_sha256':sha(panel/'decon-output.h'),'status':'built only; default XPutImage; opt-in supervised DECON trial'}
(build/'build.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
