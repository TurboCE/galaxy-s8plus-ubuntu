#!/usr/bin/env python3
"""Sanitize actual Ondemand panel callback against foreign governor state."""
import argparse
from pathlib import Path
import subprocess
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--before',type=Path,required=True);p.add_argument('--after',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
def function(s,name):
 pos=s.index(name+'(');start=s.rfind('\n',0,pos)+1;brace=s.index('{',pos);depth=1;end=brace+1
 while depth:depth+=(s[end]=='{')-(s[end]=='}');end+=1
 return s[start:end]
pre=r'''
#include <stdlib.h>
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
struct od_dbs_tuners {int policy_nr,up_threshold,boost,sampling_rate,up_threshold_suspend,boost_suspend,sampling_rate_suspend,up_threshold_resume,boost_resume,sampling_rate_resume;};
struct common_dbs_data {int mutex;};static struct common_dbs_data od_dbs_cdata;
struct dbs_data {struct common_dbs_data*cdata;int min_sampling_rate,usage_count;void*tuners;};
struct cpufreq_policy {int rwsem;void*governor;void*governor_data;};
struct shared {struct cpufreq_policy *policy;};struct od_cpu_dbs_info_s {struct {struct shared*shared;} cdbs;};
static int cpufreq_gov_ondemand,foreign_governor,hmp_slow_cpu_mask=0,hmp_fast_cpu_mask=4;
static struct cpufreq_policy policies[2];static struct od_cpu_dbs_info_s od_cpu_dbs_info[8];static struct shared shared[2];
static int refs,reads,mutexes,updates;static bool is_suspend;
#define per_cpu(name,cpu) (name[cpu])
#define for_each_cpu(cpu,mask) for(cpu=*(mask);cpu==*(mask);cpu++)
static int cpu_online(int cpu){(void)cpu;return 1;}
static struct cpufreq_policy*cpufreq_cpu_get(int cpu){refs++;return &policies[cpu==4];}
static void cpufreq_cpu_put(struct cpufreq_policy*p){(void)p;refs--;}
static void down_read(int*p){(void)p;reads++;}
static void up_read(int*p){(void)p;reads--;}
static void mutex_lock(int*p){(void)p;mutexes++;}
static void mutex_unlock(int*p){(void)p;mutexes--;}
static void update_down_threshold(struct od_dbs_tuners*t){assert(t->policy_nr==0||t->policy_nr==4);updates++;}
'''
main=r'''
int main(void){
 struct dbs_data dbs[2];struct od_dbs_tuners tuners[2];
 for(int i=0;i<2;i++){
  shared[i].policy=&policies[i];od_cpu_dbs_info[i*4].cdbs.shared=&shared[i];
  dbs[i]=(struct dbs_data){.cdata=&od_dbs_cdata,.tuners=calloc(1,1)};
  policies[i]=(struct cpufreq_policy){.governor=&foreign_governor,.governor_data=&dbs[i]};
 }
 // Foreign governor storage is deliberately smaller than Ondemand tuners.
 // The original callback blindly writes into it; the fixed one never touches it.
 update_gov_tunables();assert(updates==0&&refs==0&&reads==0&&mutexes==0);
 for(int i=0;i<2;i++){
  free(dbs[i].tuners);tuners[i]=(struct od_dbs_tuners){.up_threshold_suspend=95,.boost_suspend=0,.sampling_rate_suspend=40,.up_threshold_resume=80,.boost_resume=1,.sampling_rate_resume=20};
  dbs[i].tuners=&tuners[i];policies[i].governor=&cpufreq_gov_ondemand;
 }
 is_suspend=true;update_gov_tunables();assert(updates==2);
 for(int i=0;i<2;i++)assert(tuners[i].up_threshold==95&&tuners[i].boost==0&&tuners[i].sampling_rate==40);
 is_suspend=false;update_gov_tunables();assert(updates==4);
 for(int i=0;i<2;i++)assert(tuners[i].up_threshold==80&&tuners[i].boost==1&&tuners[i].sampling_rate==20);
 policies[0].governor_data=NULL;dbs[1].cdata=NULL;update_gov_tunables();assert(updates==4);
 assert(refs==0&&reads==0&&mutexes==0);puts("Foreign, normal suspend/resume and teardown-state cases passed");return 0;
}
'''
for variant,path in [('fixed',a.after),('old',a.before)]:
 source=path.read_text();body=(function(source,'od_update_policy_tunables')+'\n') if variant=='fixed' else ''
 body+=function(source,'update_gov_tunables');c=a.output/(variant+'.c');c.write_text(pre+body+main);exe=c.with_suffix('')
 subprocess.run(['clang','-O1','-g','-fsanitize=address,undefined',str(c),'-o',str(exe)],check=True)
 r=subprocess.run([str(exe)],capture_output=True,text=True);(a.output/(variant+'.log')).write_text(r.stdout+r.stderr)
 if variant=='fixed' and r.returncode:raise SystemExit(r.stderr)
 if variant=='old' and (r.returncode==0 or 'heap-buffer-overflow' not in r.stderr):raise SystemExit('Original did not reproduce foreign-tuners overflow')
print('Fixed actual callback passed; original reproduced ASan heap-buffer-overflow on foreign governor storage')
