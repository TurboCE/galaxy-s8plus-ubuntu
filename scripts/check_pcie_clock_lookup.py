#!/usr/bin/env python3
"""Host-only fault injection against the extracted, patched PCIe lookup function.

No kernel build/install, phone, clock, MMIO or IRQ access. Also confirms that the
old enable/disable helpers (including optional BUG_ON policy) stay byte-identical.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

STUB = r'''
#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>
struct clk { int id; };
struct device { void *of_node; };
struct pcie_port { struct device *dev; };
struct exynos_pcie_clks { struct clk *pcie_clks[10]; struct clk *phy_clks[3]; };
struct exynos_pcie { struct pcie_port pp; struct exynos_pcie_clks clks; int pcie_clk_num, phy_clk_num; };
#define to_exynos_pcie(p) ((struct exynos_pcie *)((char *)(p)-offsetof(struct exynos_pcie, pp)))
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
static struct clk clocks[13];
static int fail_at, lookups, enable_calls, disable_calls;
static char last_log[256];
static void dev_err(struct device *d,const char *fmt,...) {
    va_list args;(void)d;va_start(args,fmt);vsnprintf(last_log,sizeof(last_log),fmt,args);va_end(args);
}
static struct clk *of_clk_get(void *node,int i) {
    (void)node;if(i != lookups++ || i<0 || i>=13) abort();
    return i==fail_at ? (struct clk *)(intptr_t)-EIO : &clocks[i];
}
#define VERIFY(c) do {if(!(c)){fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#c);exit(1);}}while(0)
'''
MAIN = r'''
static void reset(struct exynos_pcie *p,int pc,int ph,int fail) {
    static struct device dev;memset(p,0,sizeof(*p));p->pp.dev=&dev;
    p->pcie_clk_num=pc;p->phy_clk_num=ph;fail_at=fail;lookups=0;last_log[0]=0;
}
int main(void) {
    struct exynos_pcie p;int cases=0;
    /* A failed PHY lookup after a valid PCIe handle must not pass. */
    reset(&p,1,1,1);VERIFY(exynos_pcie_clock_get(&p.pp)==-ENODEV);
    VERIFY(lookups==2);VERIFY(strstr(last_log,"phy clock[0]")!=NULL);cases++;
    /* Every possible failure slot: first/middle/last and mixed valid/ERR_PTR. */
    for(int failure=0;failure<13;failure++) {
        char index[80];reset(&p,10,3,failure);
        VERIFY(exynos_pcie_clock_get(&p.pp)==-ENODEV);VERIFY(lookups==failure+1);
        snprintf(index,sizeof(index),failure<10?"pcie clock[%d]":"phy clock[%d]",failure<10?failure:failure-10);
        VERIFY(strstr(last_log,index)!=NULL);cases++;
    }
    int valid[][2]={{0,0},{1,0},{0,3},{1,3},{10,3}};
    for(size_t k=0;k<ARRAY_SIZE(valid);k++) {
        reset(&p,valid[k][0],valid[k][1],-1);
        VERIFY(exynos_pcie_clock_get(&p.pp)==0);VERIFY(lookups==valid[k][0]+valid[k][1]);
        for(int i=0;i<valid[k][0];i++)VERIFY(p.clks.pcie_clks[i]==&clocks[i]);
        for(int i=0;i<valid[k][1];i++)VERIFY(p.clks.phy_clks[i]==&clocks[valid[k][0]+i]);cases++;
    }
    int invalid[][2]={{-1,0},{0,-1},{11,0},{0,4},{INT_MAX,INT_MAX},{INT_MIN,0}};
    for(size_t k=0;k<ARRAY_SIZE(invalid);k++) {
        reset(&p,invalid[k][0],invalid[k][1],-1);
        VERIFY(exynos_pcie_clock_get(&p.pp)==-EINVAL);VERIFY(lookups==0);
        VERIFY(strstr(last_log,"Invalid clock counts:")!=NULL);cases++;
    }
    VERIFY(enable_calls==0&&disable_calls==0);
    printf("PASS: %d actual-function cases; ASan/UBSan; no clocks enabled/disabled\n",cases);return 0;
}
'''


def function(source, name, following):
    start = source.index('static int ' + name + '(')
    end = source.index('\nstatic int ' + following + '(', start)
    return source[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', default='cc')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    relative = Path('drivers/pci/host/pci-exynos.c')
    original = (root / 'upstream/kernel' / relative).read_text()
    header = (root / "upstream/kernel/drivers/pci/host/pci-exynos.h").read_text()
    assert "*pcie_clks[10]" in header and "*phy_clks[3]" in header, "Update stub array layout for the reviewed source"
    with tempfile.TemporaryDirectory(prefix='g955n-pcie-clock-') as tmp:
        work = Path(tmp)
        target = work / relative
        target.parent.mkdir(parents=True)
        target.write_text(original)
        for patch in ('0024-pcie-success-diagnostics.patch', '0025-pcie-clock-lookup-bounds.patch'):
            subprocess.run(['patch', '--batch', '-p1', '-i', str(root / 'patches' / patch)],
                           cwd=work, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if patch.startswith('0024'):
                baseline = target.read_text()
        fixed = target.read_text()
        for name, following in [('exynos_pcie_clock_enable','exynos_pcie_phy_clock_enable')]:
            assert function(baseline, name, following) == function(fixed, name, following)
        start = baseline.index('static int exynos_pcie_phy_clock_enable(')
        end = baseline.index('\nvoid exynos_pcie_print_link_history', start)
        assert baseline[start:end] == fixed[fixed.index('static int exynos_pcie_phy_clock_enable('):fixed.index('\nvoid exynos_pcie_print_link_history')]
        for variant, source in [('baseline',baseline),('fixed',fixed)]:
            code = work / (variant + '.c')
            code.write_text(STUB + function(source,'exynos_pcie_clock_get','exynos_pcie_clock_enable') + MAIN)
            executable = work / variant
            subprocess.run([args.cc,'-std=gnu11','-Wall','-Wextra','-Werror',
                            '-fsanitize=address,undefined','-g','-O1',str(code),'-o',str(executable)],check=True)
            result = subprocess.run([str(executable)],text=True,capture_output=True)
            if variant == 'baseline':
                if result.returncode == 0:
                    raise SystemExit('Regression check failed: original bug was not detected')
                print('PASS: uncorrected function rejected by mixed valid/ERR_PTR regression case')
            else:
                if result.returncode:
                    raise SystemExit(result.stdout + result.stderr)
                print(result.stdout.strip())
        print('PASS: PCIe/PHY enable helpers and CONFIG_SEC_PANIC_PCIE_ERR code unchanged')


if __name__ == '__main__':
    main()
