#!/usr/bin/env python3
"""Build-only regression from the pinned SSP sysfs functions; no device access."""
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    start = source.index('static ssize_t ' + name + '(')
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


HARNESS = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <stdint.h>
#include <sys/types.h>
#define PAGE_SIZE 4096
#define scnprintf snprintf
#define pr_err(...) ((void)0)
struct device {int unused;};
struct device_attribute {int unused;};
struct iio_dev {const char *name;};
struct ssp_data {long long adDelayBuf[32];};
static struct iio_dev iio={"fixture_sensor"};
static struct ssp_data state;
static int selected;
static struct iio_dev *dev_to_iio_dev(struct device *d){(void)d;return &iio;}
static struct ssp_data *dev_get_drvdata(struct device *d){(void)d;return &state;}
static int get_index_by_name(struct iio_dev *i,struct ssp_data *s){(void)i;(void)s;return selected;}
static int kstrtoll(const char *text,int base,int64_t *out){
 char *end;errno=0;long long value=strtoll(text,&end,base);
 if(errno||end==text||(*end&&strcmp(end,"\n")))return -EINVAL;
 *out=value;return 0;
}
static void change_sensor_delay(struct ssp_data *s,int index,int64_t value){s->adDelayBuf[index]=value;}
FUNCTIONS
int main(void){
 struct device d={0};struct device_attribute a={0};char buf[4096]={0};
 selected=0;state.adDelayBuf[0]=200000000;
 ssize_t read_count=show_sensor_delay(&d,&a,buf);
 ssize_t write_count=set_sensor_delay(&d,&a,"100000000\n",10);
 long long changed=state.adDelayBuf[0];
 selected=-1;
 ssize_t bad_read=show_sensor_delay(&d,&a,buf);
 ssize_t bad_write=set_sensor_delay(&d,&a,"50000000\n",9);
 selected=0;
 ssize_t bad_parse=set_sensor_delay(&d,&a,"invalid",7);
 printf("{\"read_count\":%ld,\"write_count\":%ld,\"changed_period\":%lld,\"unknown_read\":%ld,\"unknown_write\":%ld,\"bad_parse\":%ld,\"final_period\":%lld}\n",(long)read_count,(long)write_count,changed,(long)bad_read,(long)bad_write,(long)bad_parse,state.adDelayBuf[0]);
 return 0;
}
'''


def main():
    original = subprocess.check_output(['git', '-C', str(ROOT/'upstream/kernel.git'), 'show', 'HEAD:drivers/sensorhub/brcm/ssp_sysfs.c'], text=True)
    results = {}
    with tempfile.TemporaryDirectory(prefix='g955n-ssp-sysfs-') as directory:
        temp = Path(directory)
        path = temp/'drivers/sensorhub/brcm/ssp_sysfs.c'
        path.parent.mkdir(parents=True)
        path.write_text(original)
        subprocess.run(['patch', '-s', '-p1', '-i', str(ROOT/'patches/0026-ssp-poll-delay-sysfs-count.patch')], cwd=temp, check=True)
        for label, source in [('original', original), ('fixed', path.read_text())]:
            funcs = '\n'.join(function(source, n) for n in ('show_sensor_delay', 'set_sensor_delay'))
            c = temp/(label+'.c')
            c.write_text(HARNESS.replace('FUNCTIONS', funcs))
            binary = temp/label
            subprocess.run(['cc', '-std=c11', '-O1', '-g', '-fsanitize=address,undefined', '-Wall', '-Wextra', '-Wno-unused-parameter', str(c), '-o', str(binary)], check=True)
            results[label] = json.loads(subprocess.check_output([str(binary)], text=True))
    assert results['original']['read_count'] == results['original']['write_count'] == 0
    assert results['original']['changed_period'] == 100000000
    assert results['fixed'] == dict(read_count=10, write_count=10, changed_period=100000000,
                                   unknown_read=-22, unknown_write=-22, bad_parse=-22,
                                   final_period=100000000)
    print(json.dumps({'original_zero_count_defect_reproduced':True,'patched_counts_and_errors_passed':True,'sanitizers':'address,undefined','results':results}, indent=2))


if __name__ == '__main__':
    main()
