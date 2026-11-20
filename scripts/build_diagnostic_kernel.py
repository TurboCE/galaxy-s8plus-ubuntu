#!/usr/bin/env python3
"""Build-only fresh baseline/ESS candidate. No device access, packaging or install."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def append_builtin_argument(text, argument):
    lines=[line for line in text.splitlines() if line.startswith('CONFIG_CMDLINE=')]
    if len(lines)!=1:raise ValueError('Expected one built-in command line')
    old=lines[0];cmdline=json.loads(old.split('=',1)[1])
    name=argument.split('=',1)[0]
    if any(item.split('=',1)[0]==name for item in cmdline.split()):
        raise ValueError('Built-in command line already supplies '+name)
    new='CONFIG_CMDLINE='+json.dumps(cmdline+' '+argument)
    return text.replace(old+'\n',new+'\n',1)


def make_wfi_config(text):
    return append_builtin_argument(text, 'cpuidle.off=1')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--builder', default='s9-g965n-builder:24.04.3')
    parser.add_argument('--native-fb-owner',action='store_true',help='Include explicit mmap/native-fb lifetime proposals in build24')
    parser.add_argument('--wfi-only',action='store_true',help='Diagnostic only: append cpuidle.off=1 to the built-in CMDLINE before any vendor idle entry')
    parser.add_argument('--native-panel-safety',action='store_true',help='Include DPP metadata ownership and native pan/DPMS serialization proposal')
    parser.add_argument('--native-panel-qos',action='store_true',help='Include primary-panel pre-enable QoS ordering and error rollback')
    parser.add_argument('--native-ondemand-safety',action='store_true',help='Hold and check CPU governor private-data lifetime during display events')
    parser.add_argument('--ssp-sysfs-counts',action='store_true',help='Fix SSP IIO poll_delay sysfs EOF/no-progress return counts')
    parser.add_argument('--abox-suspend-irq-order', action='store_true',
                        help='Drain ABOX IRQs before power-off and use runtime ownership for system sleep')
    parser.add_argument('--suspend-battery-diagnostic', action='store_true',
                        help='Freeze battery work and enable bounded PM-stage tests')
    parser.add_argument('--pmic-wake-irq', action='store_true', help='Keep the Exynos8895 S2MPS17 wake IRQ available in suspend')
    parser.add_argument('--dpp-shared-dma', action='store_true', help='Map the shared Exynos8895 DPP DMA register block once')
    parser.add_argument('--desktop-charger-touch', action='store_true',
                        help='Allow SM-G955N FTS touch when this native image boots Ubuntu in charger mode')
    parser.add_argument('--dhd-pcie-suspend-order', action='store_true',
                        help='Suspend the Broadcom wireless layer before its PCIe transport')
    parser.add_argument('--mif-int-suspend-comparison', action='store_true',
                        help='Use the normal MIF and INT operating points in SM-G955N suspend tests')
    parser.add_argument('--dhd-cancel-pending-pm-work', action='store_true',
                        help='Cancel queued Broadcom station PM work before non-WoWLAN PCIe suspend')
    parser.add_argument('--freeze-voltage-dvfs', action='store_true',
                        help='Freeze Exynos voltage-policy polling before suspend disables I2C interrupts')
    parser.add_argument('--fts-desktop-suspend', action='store_true',
                        help='Preserve desktop touch users and opt in to touch wake explicitly')
    parser.add_argument('--exynos-wlan-pci-sleep-ownership', action='store_true',
                        help='Keep PCI system config access behind the Exynos WLAN host power state')
    parser.add_argument('--audio-safety',action='store_true',help='Include reviewed ABOX SRAM, DMA bounds and request-table fixes 17..20')
    parser.add_argument('--build-version',type=int,help='Explicit positive build number for a controlled compiler comparison')
    args = parser.parse_args()
    if args.build_version is not None and not 1 <= args.build_version <= 9999:parser.error('build version must be 1..9999')
    if args.native_ondemand_safety and not args.native_panel_qos:parser.error('--native-ondemand-safety requires --native-panel-qos')
    if args.native_panel_qos and not args.native_panel_safety:parser.error('--native-panel-qos requires --native-panel-safety')
    if args.native_panel_safety and (not args.native_fb_owner or args.wfi_only):parser.error('--native-panel-safety requires the normal-idle native-fb-owner baseline')
    if args.wfi_only and not args.native_fb_owner:parser.error('--wfi-only requires the native-fb-owner baseline')
    if args.dpp_shared_dma and (not args.native_panel_safety or not args.build_version):
        parser.error('--dpp-shared-dma requires --native-panel-safety and an explicit --build-version')
    if (args.pmic_wake_irq or args.suspend_battery_diagnostic) and not args.build_version:
        parser.error('Suspend candidates require an explicit --build-version')
    if args.abox_suspend_irq_order and (not args.audio_safety or not args.suspend_battery_diagnostic):
        parser.error('--abox-suspend-irq-order requires --audio-safety and --suspend-battery-diagnostic')
    if args.desktop_charger_touch and not args.build_version:
        parser.error('--desktop-charger-touch requires an explicit --build-version')
    if args.dhd_pcie_suspend_order and not args.build_version:
        parser.error('--dhd-pcie-suspend-order requires an explicit --build-version')
    if args.mif_int_suspend_comparison and not args.build_version:
        parser.error('--mif-int-suspend-comparison requires an explicit --build-version')
    if args.dhd_cancel_pending_pm_work and not args.dhd_pcie_suspend_order:
        parser.error('--dhd-cancel-pending-pm-work requires --dhd-pcie-suspend-order')
    if args.freeze_voltage_dvfs and not args.suspend_battery_diagnostic:
        parser.error('--freeze-voltage-dvfs requires --suspend-battery-diagnostic')
    if args.fts_desktop_suspend and not args.build_version:
        parser.error('--fts-desktop-suspend requires an explicit --build-version')
    if args.exynos_wlan_pci_sleep_ownership and not args.build_version:
        parser.error('--exynos-wlan-pci-sleep-ownership requires an explicit --build-version')
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
    if args.audio_safety:
        audio = sorted(p for p in (ROOT/'patches').glob('*.patch') if 17 <= int(p.name[:4]) <= 20)
        if len(audio) != 4:raise SystemExit('Requires exact ABOX safety patch chain 17..20')
        patchfiles += audio
    if args.native_fb_owner:
        patchfiles += [ROOT/'patches/0023-decon-mmap-page-offset.patch',ROOT/'patches/proposals/0028-decon-native-fb-lifetime.patch']
    if args.ssp_sysfs_counts:patchfiles.append(ROOT/'patches/0026-ssp-poll-delay-sysfs-count.patch')
    patchfiles.append(ROOT/'patches/proposals/0027-ess-work-tail-on-panic.patch')
    if args.native_panel_safety:patchfiles.append(ROOT/'patches/proposals/0029-dpp-config-lifetime-and-pan-power-lock.patch')
    if args.native_panel_qos:patchfiles.append(ROOT/'patches/proposals/0030-primary-panel-qos-transaction.patch')
    if args.native_ondemand_safety:patchfiles.append(ROOT/'patches/proposals/0031-ondemand-panel-policy-lifetime.patch')
    if args.dpp_shared_dma:
        patchfiles.append(ROOT/'patches/proposals/0032-dpp-shared-dma-registers.patch')
    if args.pmic_wake_irq:
        patchfiles.append(ROOT/'patches/proposals/0033-s2mps17-keep-wake-irq-enabled.patch')
    if args.suspend_battery_diagnostic:
        patchfiles.append(ROOT/'patches/proposals/0034-freeze-sec-battery-workqueue.patch')
    if args.abox_suspend_irq_order:
        patchfiles.append(ROOT/'patches/proposals/0035-abox-suspend-irq-order.patch')
    if args.desktop_charger_touch:
        patchfiles.append(ROOT/'patches/proposals/0036-fts-desktop-charger-touch.patch')
    if args.dhd_pcie_suspend_order:
        patchfiles.append(ROOT/'patches/proposals/0037-dhd-pcie-suspend-scan-order.patch')
    if args.mif_int_suspend_comparison:
        patchfiles.append(ROOT/'patches/proposals/0038-dream2lte-kor-suspend-opp-comparison.patch')
    if args.dhd_cancel_pending_pm_work:
        patchfiles.append(ROOT/'patches/proposals/0039-dhd-cancel-pending-pm-work-on-suspend.patch')
    if args.freeze_voltage_dvfs:
        patchfiles.append(ROOT/'patches/proposals/0040-freeze-exynos-voltage-dvfs-thread.patch')
    if args.fts_desktop_suspend:
        patchfiles.append(ROOT/'patches/proposals/0041-fts-preserve-desktop-input-across-suspend.patch')
    if args.exynos_wlan_pci_sleep_ownership:
        patchfiles.append(ROOT/'patches/proposals/0042-defer-exynos-wlan-pci-system-config.patch')
    version=args.build_version or (28 if args.native_ondemand_safety else 27 if args.native_panel_qos else 26 if args.native_panel_safety else 25 if args.wfi_only else 24 if args.native_fb_owner else 23)
    image_id=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',args.builder],text=True).strip()
    baseline=(ROOT/'artifacts/kernel-audio-proc/kernel.config').read_text()
    if 'CONFIG_RD_LZ4=y' in baseline.splitlines():
        subprocess.run(['docker','run','--rm','--network','none',args.builder,'lz4','--version'],check=True,stdout=subprocess.DEVNULL)
    compiler=subprocess.check_output(['docker','run','--rm','--network','none',args.builder,'aarch64-linux-gnu-gcc','-dumpfullversion'],text=True).strip()
    plan = {'target':'SM-G955N','source':expected,'builder':args.builder,'volume':volume,
            'patches':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in patchfiles},
            'build_version':version,'builder_image_id':image_id,'compiler_version':compiler,
            'ssp_sysfs_counts':args.ssp_sysfs_counts,
            'audio_safety':args.audio_safety,
            'abox_suspend_irq_order':args.abox_suspend_irq_order,
            'dpp_shared_dma':args.dpp_shared_dma,
            'desktop_charger_touch':args.desktop_charger_touch,
            'fts_desktop_suspend':args.fts_desktop_suspend,
            'dhd_pcie_suspend_order':args.dhd_pcie_suspend_order,
            'mif_int_suspend_comparison':args.mif_int_suspend_comparison,
            'dhd_cancel_pending_pm_work':args.dhd_cancel_pending_pm_work,
            'exynos_wlan_pci_sleep_ownership':args.exynos_wlan_pci_sleep_ownership,
            'freeze_voltage_dvfs':args.freeze_voltage_dvfs,
            'pmic_wake_irq':args.pmic_wake_irq,
            'suspend_battery_diagnostic':args.suspend_battery_diagnostic,
            'native_panel_safety':args.native_panel_safety,
            'native_panel_qos':args.native_panel_qos,
            'native_ondemand_safety':args.native_ondemand_safety,
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
    if args.wfi_only or args.desktop_charger_touch:
        boot_config=baseline
        if args.wfi_only:
            boot_config=make_wfi_config(boot_config)
        if args.desktop_charger_touch:
            boot_config=append_builtin_argument(boot_config, 'g955n.desktop_charger_touch=1')
        config_name='boot-options.config' if args.desktop_charger_touch else 'wfi.config'
        (output/config_name).write_text(boot_config)
        commands += [f'cp /output/{config_name} /work/out/.config',
                     'make O=/work/out HOSTCFLAGS="-O2 -fcommon" olddefconfig',
                     f'cmp /work/out/.config /output/{config_name}']
    if args.suspend_battery_diagnostic:
        commands += ['bash scripts/config --file /work/out/.config -e PM_DEBUG',
                     'make O=/work/out HOSTCFLAGS="-O2 -fcommon" olddefconfig']
    commands += [
        'cp /work/out/.config /output/kernel.config',
        'make O=/work/out -j4 HOSTCFLAGS="-O2 -fcommon" KCFLAGS="-Wno-error" KBUILD_BUILD_VERSION='+str(version)+' Image dtbs',
        'cp /work/out/arch/arm64/boot/Image /output/Image.unqualified',
        'cp /work/out/vmlinux /work/out/System.map /output/',
        'cp /work/out/arch/arm64/boot/dts/exynos/exynos8895-dream2lte_kor_10.dtb /output/']
    print('Build-only output:',output,flush=True)
    result=subprocess.run(['docker','run','--rm','--network','none','-v',volume+':/work','-v',str(ROOT)+':/port:ro',
        '-v',str(output)+':/output','-e','ARCH=arm64','-e','CROSS_COMPILE=aarch64-linux-gnu-',args.builder,
        'bash','-euc','\n'.join(commands)])
    plan['build_exit']=result.returncode
    if result.returncode == 0:
        check=subprocess.run(['python3',str(ROOT/'scripts/verify_kernel_initramfs.py'),'--kernel-dir',str(output)],capture_output=True,text=True)
        plan['builtin_initramfs_check']=json.loads(check.stdout)
        (output/'builtin-initramfs-check.json').write_text(check.stdout)
        if check.returncode:plan['build_exit']=check.returncode
    plan['artifacts']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.name!='plan.json'}
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    raise SystemExit(plan['build_exit'])

if __name__=='__main__':main()
