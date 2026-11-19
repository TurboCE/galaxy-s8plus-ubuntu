#!/usr/bin/env python3
"""Execute actual safe-fault handler with snapshot logging enabled/disabled."""
import argparse
from pathlib import Path
import subprocess
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--before',type=Path,required=True);p.add_argument('--after',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
pre=r'''
#include <assert.h>
#include <string.h>
#include <stdio.h>
#define SZ_16 16
#define SZ_32 32
#define ESS_SIGN_SAFE_FAULT 0xfafa
#define unlikely(x) (x)
static struct {int enabled;} ess_base;
static int cpu,resets,reason,dumps,stage;static unsigned reset_count;
static char message[32];
static int get_current_cpunum(void){return cpu;}
static void exynos_ss_report_reason(int value){assert(stage==0);stage=1;reason=value;}
static void exynos_ss_dump_panic(const char*text,size_t len){assert(stage==1);stage=2;dumps++;assert(len<sizeof(message));memcpy(message,text,len);message[len]=0;}
static int s3c2410wdt_set_emergency_reset(unsigned value){if(ess_base.enabled)assert(stage==2);else assert(stage==0);resets++;reset_count=value;return 0;}
'''
main=r'''
int main(void){
 // The real caller waits indefinitely after return, so request reset even
 // when optional logging is disabled. No new fault is deliberately triggered.
 ess_base.enabled=0;exynos_ss_panic_handler_safe();assert(resets==1&&reset_count==100&&dumps==0&&reason==0);
 for(cpu=0;cpu<8;cpu++){
  ess_base.enabled=1;stage=reason=0;exynos_ss_panic_handler_safe();
  char expected[32];snprintf(expected,sizeof(expected),"safe panic handler at cpu %d",cpu);
  assert(!strcmp(message,expected));assert(reason==ESS_SIGN_SAFE_FAULT&&reset_count==100);
 }
 assert(resets==9&&dumps==8);puts("Disabled-logging recovery and all eight CPU enabled-logging paths passed");return 0;
}
'''
for variant,path in [('fixed',a.after),('old',a.before)]:
 c=a.output/(variant+'.c');c.write_text(pre+path.read_text()+main);exe=c.with_suffix('')
 subprocess.run(['clang','-O1','-fsanitize=address,undefined',str(c),'-o',str(exe)],check=True)
 r=subprocess.run([str(exe)],capture_output=True,text=True);(a.output/(variant+'.log')).write_text(r.stdout+r.stderr)
 if variant=='fixed' and r.returncode:raise SystemExit(r.stderr)
 if variant=='old' and r.returncode==0:raise SystemExit('Original did not reproduce missing watchdog request')
print('Actual handler recovery cases passed; original skipped reset with logging disabled')
