#!/usr/bin/env python3
"""Build-only fresh baseline/ESS candidate. No device access, packaging or install."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def make_wfi_config(text):
    lines=[line for line in text.splitlines() if line.startswith('CONFIG_CMDLINE=')]
    if len(lines)!=1:raise ValueError('Expected one built-in command line')
    old=lines[0];cmdline=json.loads(old.split('=',1)[1])
    if 'cpuidle.off=' in cmdline:raise ValueError('Existing idle override')
    new='CONFIG_CMDLINE='+json.dumps(cmdline+' cpuidle.off=1')
    return text.replace(old+'\n',new+'\n',1)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--builder', default='s9-g965n-builder:24.04.3')
    parser.add_argument('--native-fb-owner',action='store_true',help='Include explicit mmap/native-fb lifetime proposals in build24')
    parser.add_argument('--wfi-only',action='store_true',help='Diagnostic only: append cpuidle.off=1 to the built-in CMDLINE before any vendor idle entry')
    parser.add_argument('--native-panel-safety',action='store_true',help='Include DPP metadata ownership and native pan/DPMS serialization proposal')
    args = parser.parse_args()
    if args.native_panel_safety and (not args.native_fb_owner or args.wfi_only):parser.error('--native-panel-safety requires the normal-idle native-fb-owner baseline')
    if args.wfi_only and not args.native_fb_owner:parser.error('--wfi-only requires the native-fb-owner baseline')
    if not args.build:
        parser.print_help();return
    expected = json.loads((ROOT/'sources.json').read_text())['sources']['kernel']['commit']
    source = ROOT/'upstream/kernel.git'
    if subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()!=expected:
        raise SystemExit('Pinned kernel source mismatch')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    volume = 'g955n-baseline-ess-'+stamp.lower()
    output = ROOT/'artifacts'/('kernel-baseline-ess-'+stamp)
    output.mkdir(mode=0o700)
    patchfiles = sorted(p for p in (ROOT/'patches').glob('*.patch') if int(p.name[:4])<=16)
    if len(patchfiles)!=16:raise SystemExit('Requires exact baseline patch chain 1..16')
    if args.native_fb_owner:
        patchfiles += [ROOT/'patches/0023-decon-mmap-page-offset.patch',ROOT/'patches/proposals/0028-decon-native-fb-lifetime.patch']
    patchfiles.append(ROOT/'patches/proposals/0027-ess-work-tail-on-panic.patch')
    if args.native_panel_safety:patchfiles.append(ROOT/'patches/proposals/0029-dpp-config-lifetime-and-pan-power-lock.patch')
    plan = {'target':'SM-G955N','source':expected,'builder':args.builder,'volume':volume,
            'patches':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in patchfiles},
            'native_panel_safety':args.native_panel_safety,
            'idle_isolation':'built-in cpuidle.off=1; architectural WFI, not a fix' if args.wfi_only else None,
            'build_only':True,'deployed':False,'hardware_qualified':False}
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    subprocess.run(['docker','volume','create',volume],check=True)
    archive=subprocess.Popen(['git','-C',str(source),'archive',expected],stdout=subprocess.PIPE)
    unpack=subprocess.run(['docker','run','--rm','-i','--network','none','-v',volume+':/work',args.builder,
                         'bash','-ec','mkdir /work/src; tar -xf - -C /work/src'],stdin=archive.stdout)
    archive.stdout.close()
    if archive.wait() or unpack.returncode:raise SystemExit('Source export failed')
    commands=['cd /work/src']
    for p in patchfiles:
        relative=str(p.relative_to(ROOT))
        commands += [f'git apply --check /port/{relative}',f'git apply /port/{relative}']
    commands += ['mkdir /work/out',
        'cp /port/artifacts/kernel-audio-proc/kernel.config /work/out/.config',
        'make O=/work/out HOSTCFLAGS="-O2 -fcommon" olddefconfig',
        'cmp /work/out/.config /port/artifacts/kernel-audio-proc/kernel.config',
    ]
    if args.wfi_only:
        baseline=(ROOT/'artifacts/kernel-audio-proc/kernel.config').read_text()
        (output/'wfi.config').write_text(make_wfi_config(baseline))
        commands += ['cp /output/wfi.config /work/out/.config',
                     'make O=/work/out HOSTCFLAGS="-O2 -fcommon" olddefconfig',
                     'cmp /work/out/.config /output/wfi.config']
    commands += [
        'cp /work/out/.config /output/kernel.config',
        'make O=/work/out -j4 HOSTCFLAGS="-O2 -fcommon" KCFLAGS="-Wno-error" KBUILD_BUILD_VERSION='+('26' if args.native_panel_safety else '25' if args.wfi_only else '24' if args.native_fb_owner else '23')+' Image dtbs',
        'cp /work/out/arch/arm64/boot/Image /output/Image.unqualified',
        'cp /work/out/vmlinux /work/out/System.map /output/',
        'cp /work/out/arch/arm64/boot/dts/exynos/exynos8895-dream2lte_kor_10.dtb /output/']
    print('Build-only output:',output,flush=True)
    result=subprocess.run(['docker','run','--rm','--network','none','-v',volume+':/work','-v',str(ROOT)+':/port:ro',
        '-v',str(output)+':/output','-e','ARCH=arm64','-e','CROSS_COMPILE=aarch64-linux-gnu-',args.builder,
        'bash','-euc','\n'.join(commands)])
    plan['build_exit']=result.returncode
    plan['artifacts']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.name!='plan.json'}
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    raise SystemExit(result.returncode)

if __name__=='__main__':main()
