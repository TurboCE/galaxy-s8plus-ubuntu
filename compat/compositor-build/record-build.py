#!/usr/bin/env python3
"""Record private cross-build ELF metadata; never execute target programs."""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess

p = argparse.ArgumentParser()
p.add_argument('--work', default='/work')
p.add_argument('--scripts', default='/scripts')
a = p.parse_args()
w, s = pathlib.Path(a.work), pathlib.Path(a.scripts)
assert w == pathlib.Path('/work'), 'Use dedicated private build volume'
paths = [w/'hwc2-android9/libhwc2_compat_layer.so', w/'prefix/lib/libwlroots.so.12a',
         w/'prefix/bin/tinywl-g955n-candidate', w/'prefix/lib/libdroid-0.so.1',
         w/'prefix/lib/libhybris-hwcomposerwindow.so', w/'prefix/lib/libhwc2.so']

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def defined_symbols(path):
    lines = subprocess.check_output(['readelf', '--dyn-syms', '-W', str(path)], text=True).splitlines()
    return {line.split()[-1] for line in lines if ' UND ' not in line and len(line.split()) >= 8}

hwc_symbols = defined_symbols(paths[0])
wlroots = next((w/'sources').glob('droidian-wlroots-*'))
required = set()
for f in (wlroots/'backend/hwcomposer').glob('*.c'):
    required.update(re.findall(r'\b(hwc2_compat_\w+)\s*\(', f.read_text()))
assert required and not (required - hwc_symbols), sorted(required - hwc_symbols)
assert 'hwc2_compat_layer_set_sideband_stream' in hwc_symbols
artifacts = []
for f in paths:
    header = subprocess.check_output(['readelf', '-h', str(f)], text=True)
    assert 'AArch64' in header, f
    dynamic = subprocess.check_output(['readelf', '-d', str(f)], text=True)
    assert '(TEXTREL)' not in dynamic, f
    artifacts.append({'path': str(f), 'sha256': sha(f), 'bytes': f.stat().st_size,
                      'elf_header': header, 'dynamic': dynamic})
record = {'schema': 1, 'device_target': 'SM-G955N/dream2lteks Android9 API28',
          'status': 'cross-linked only; not installed or executed; no hardware qualification',
          'sources': json.loads((s/'sources.json').read_text()),
          'build_files': {str(f.relative_to(s)): sha(f) for f in sorted(s.rglob('*'))
                          if f.is_file() and '__pycache__' not in f.parts},
          'artifacts': artifacts,
          'wlroots_hwc2_required_c_exports': sorted(required),
          'bionic_hwc2_defined_c_exports': sorted(x for x in hwc_symbols if x.startswith('hwc2_compat_')),
          'unsupported_wrapper_api_not_used_by_pinned_wlroots': ['hwc2_compat_display_present_or_validate'],
          'hybris_build_source_hashes': {str(f.relative_to(w/'input/libhybris')): sha(f)
              for f in sorted((w/'input/libhybris').rglob('*')) if f.is_file()
              and (f.suffix in ('.c', '.cpp', '.h', '.S', '.am', '.ac'))},
          'own_link_inputs': {f.name: sha(f) for f in sorted((w/'input/own-libs').glob('*.so'))},
          'compiler': subprocess.check_output(['aarch64-linux-gnu-gcc', '--version'], text=True),
          'packages': subprocess.check_output(['dpkg-query','-W','-f=${Package}:${Architecture} ${Version}\n'], text=True)}
(w/'compositor-build-record.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps({x['path']:x['sha256'] for x in artifacts}, indent=2))
