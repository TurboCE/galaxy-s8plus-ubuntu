#!/usr/bin/env python3
"""Build-only fresh baseline/ESS candidate. No device access, packaging or install."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--builder', default='s9-g965n-builder:24.04.3')
    args = parser.parse_args()
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
    patchfiles.append(ROOT/'patches/proposals/0027-ess-work-tail-on-panic.patch')
    plan = {'target':'SM-G955N','source':expected,'builder':args.builder,'volume':volume,
            'patches':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in patchfiles},
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
        'cp /work/out/.config /output/kernel.config',
        'make O=/work/out -j4 HOSTCFLAGS="-O2 -fcommon" KCFLAGS="-Wno-error" KBUILD_BUILD_VERSION=23 Image dtbs',
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
