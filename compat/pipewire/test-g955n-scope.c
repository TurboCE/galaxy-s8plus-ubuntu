/* SPDX-License-Identifier: MIT
 * Fully mocked control/config/PCM API: never links libasound or opens devices. */
#include <assert.h>
#include <stdint.h>
#include <unistd.h>
static const char *scope_test_model_path;
#define G955N_SCOPE_MODEL_PATH scope_test_model_path
#include "g955n-scope.h"
#define policy(d,s) g955n_scope_pcm_audit(d,s,"mock",NULL)
static int selected, mock_error, open_count, global_count;
static bool wrong_identity, wrong_pcm;
static unsigned int requested_pcm, requested_sub;
static snd_pcm_stream_t requested_stream;
size_t snd_ctl_card_info_sizeof(void) { return 8; }
size_t snd_pcm_info_sizeof(void) { return 8; }
int snd_config_load_string(snd_config_t **c, const char *s, size_t n)
{ (void)n; assert(!strstr(s,"evil")); *c=(snd_config_t *)strdup(s);return *c?0:-ENOMEM; }
int snd_config_delete(snd_config_t *c) { free(c);return 0; }
int snd_ctl_open(snd_ctl_t **c,const char *n,int m)
{ (void)c;(void)n;(void)m;global_count++;return -EIO; }
int snd_pcm_open(snd_pcm_t **c,const char *n,snd_pcm_stream_t s,int m)
{ (void)c;(void)n;(void)s;(void)m;global_count++;return -EIO; }
int snd_ctl_open_lconf(snd_ctl_t **ctl, const char *name, int mode,snd_config_t *c)
{
    (void)mode;assert(!strcmp(name,"g955n_native"));
    const char *text=(const char *)c;
    assert(strstr(text,"ctl.g955n_native { type hw card "));
    if (mock_error) return mock_error;
    if (strstr(text,"\"0\"") || strstr(text,"\"Exynos8895Mader\"")) selected=0;
    else if (strstr(text,"\"1\"") || strstr(text,"\"aboxdump\"")) selected=1;
    else if (strstr(text,"\"2\"") || strstr(text,"\"USB\"")) selected=2;
    else return -ENODEV;
    *ctl=(snd_ctl_t *)(uintptr_t)1;return 0;
}
int snd_pcm_open_lconf(snd_pcm_t **h,const char *n,snd_pcm_stream_t s,int m,snd_config_t *c)
{
    (void)m;assert(!strcmp(n,"g955n_native"));
    const char *expected = s == SND_PCM_STREAM_PLAYBACK
        ? "pcm.g955n_native { type hw card 0 device 0 subdevice 0 }"
        : "pcm.g955n_native { type hw card 0 device 9 subdevice 0 }";
    assert(!strcmp((const char *)c, expected));
    open_count++;*h=(snd_pcm_t *)(uintptr_t)1;return 0;
}
int snd_ctl_card_info(snd_ctl_t *c,snd_ctl_card_info_t *i) { (void)c;(void)i;return 0; }
int snd_ctl_card_info_get_card(const snd_ctl_card_info_t *i) { (void)i;return selected; }
int snd_ctl_close(snd_ctl_t *c) { (void)c;return 0; }
const char *snd_ctl_card_info_get_driver(const snd_ctl_card_info_t *i)
{ (void)i;return selected==0?"Exynos8895-Made":selected==1?"abox_dump":"USB-Audio"; }
const char *snd_ctl_card_info_get_name(const snd_ctl_card_info_t *i)
{ (void)i;return selected==0?"Exynos8895-Madera":selected==1?"abox_dump":"USB"; }
const char *snd_ctl_card_info_get_longname(const snd_ctl_card_info_t *i)
{ if(wrong_identity)return "mismatched";return snd_ctl_card_info_get_name(i); }
const char *snd_ctl_card_info_get_id(const snd_ctl_card_info_t *i)
{ (void)i;return selected==0?"Exynos8895Mader":selected==1?"aboxdump":"USB"; }
void snd_pcm_info_set_device(snd_pcm_info_t *i,unsigned int d) { (void)i;requested_pcm=d; }
void snd_pcm_info_set_subdevice(snd_pcm_info_t *i,unsigned int d) { (void)i;requested_sub=d; }
void snd_pcm_info_set_stream(snd_pcm_info_t *i,snd_pcm_stream_t s) { (void)i;requested_stream=s; }
int snd_ctl_pcm_info(snd_ctl_t *c,snd_pcm_info_t *i)
{
    (void)c;(void)i;
    assert(requested_sub == 0);
    assert((requested_stream == SND_PCM_STREAM_PLAYBACK && requested_pcm == 0) ||
           (requested_stream == SND_PCM_STREAM_CAPTURE && requested_pcm == 9));
    return 0;
}
int snd_pcm_info_get_card(const snd_pcm_info_t *i) { (void)i;return selected; }
unsigned int snd_pcm_info_get_device(const snd_pcm_info_t *i) { (void)i;return requested_pcm; }
unsigned int snd_pcm_info_get_subdevice(const snd_pcm_info_t *i) { (void)i;return requested_sub; }
snd_pcm_stream_t snd_pcm_info_get_stream(const snd_pcm_info_t *i) { (void)i;return requested_stream; }
const char *snd_pcm_info_get_id(const snd_pcm_info_t *i)
{
    (void)i;
    if (wrong_pcm) return "WDMA0 (*)";
    return requested_stream == SND_PCM_STREAM_PLAYBACK ? "RDMA0 (*)" : "WDMA1 (*)";
}
const char *snd_pcm_info_get_name(const snd_pcm_info_t *i) { (void)i;return ""; }
unsigned int snd_pcm_info_get_subdevices_count(const snd_pcm_info_t *i) { (void)i;return 1; }
int main(void)
{
    char model[]="/tmp/g955n-scope-test-XXXXXX";int fd=mkstemp(model);assert(fd>=0);
    assert(write(fd,"Samsung SM-G955N\0",17)==17);close(fd);scope_test_model_path=model;
    assert(g955n_scope_index(0)==G955N_PRIMARY);assert(g955n_scope_index(1)==G955N_DEBUG);
    assert(g955n_scope_index(2)==G955N_OTHER);
    const char *ok[]={"hw:0,0","hw:Exynos8895Mader,0","hw:0,0,0",
      "_ucm0001.hw:Exynos8895Mader,0", "_ucm0002.hw:0,0",
      "_ucm000A.hw:0,0,0", "_ucmFFFF.hw:0,0"};
    const char *bad[]={"hw:0,1","hw:0,4","hw:0,7","hw:0,8","hw:0,0,1",
      "hw:1,0","hw:aboxdump,0","hw:2,3","hw:USB,1","default","plughw:0,0",
      "plug:SLAVE='hw:0,0'","hw:0","hw:,0","hw:0,-1","hw:0,0,","hw:0,0x",
      "hw:0,0,0,1","hw:CARD=Exynos8895Mader,DEV=0","hw:0,9999999999999999999999999999999999",
      "_ucm1.hw:0,0", "_ucm00001.hw:0,0", "_ucm00000000.hw:0,0",
      "_ucm10000.hw:0,0", "_ucmFFFFFFFF.hw:0,0", "_ucm100000000.hw:0,0", "_ucm000a.hw:0,0", "_UCM0001.hw:0,0",
      "_ucm0001hw:0,0", "_ucm0001..hw:0,0", "_ucm0001.default",
      "_ucm0001.plughw:0,0", "_ucm0001._ucm0002.hw:0,0",
      "_ucm0001.hw:1,0", "_ucm0001.hw:USB,0", "_ucm0001.hw:0,7",
      "_ucm0002.hw:0,8", "_ucm0001.hw:0,0,1"};
    for(size_t i=0;i<sizeof(ok)/sizeof(ok[0]);i++)assert(policy(ok[i],SND_PCM_STREAM_PLAYBACK)==0);
    for(size_t i=0;i<sizeof(bad)/sizeof(bad[0]);i++)assert(policy(bad[i],SND_PCM_STREAM_PLAYBACK)<0);
    for(int i=0;i<32;i++){
      char path[32];
      snprintf(path,sizeof(path),"hw:0,%d",i);
      assert((policy(path,SND_PCM_STREAM_CAPTURE)==0)==(i==9));
      snprintf(path,sizeof(path),"_ucm0002.hw:0,%d",i);
      assert((policy(path,SND_PCM_STREAM_CAPTURE)==0)==(i==9));
    }
    assert(policy("hw:0,9",SND_PCM_STREAM_PLAYBACK)<0);
    assert(policy("hw:0,9,1",SND_PCM_STREAM_CAPTURE)<0);
    assert(policy("hw:aboxdump,9",SND_PCM_STREAM_CAPTURE)<0);
    wrong_identity=true;assert(g955n_scope_index(0)<0);assert(policy("hw:0,0",SND_PCM_STREAM_PLAYBACK)<0);wrong_identity=false;
    wrong_pcm=true;assert(policy("hw:0,0",SND_PCM_STREAM_PLAYBACK)<0);
    assert(policy("hw:0,9",SND_PCM_STREAM_CAPTURE)<0);wrong_pcm=false;
    mock_error=-EACCES;assert(policy("hw:0,0",SND_PCM_STREAM_PLAYBACK)==-EACCES);mock_error=0;
    setenv("ALSA_CONFIG_PATH","/tmp/evil-asoundrc",1);
    snd_pcm_t *h=NULL;
    for(size_t i=0;i<sizeof(ok)/sizeof(ok[0]);i++) {
      assert(g955n_scope_open(&h,ok[i],SND_PCM_STREAM_PLAYBACK,0,"mock-open")==0);
      assert(open_count==(int)i+1&&global_count==0);
    }
    int allowed=open_count;
    for(size_t i=0;i<sizeof(bad)/sizeof(bad[0]);i++) {
      assert(g955n_scope_open(&h,bad[i],SND_PCM_STREAM_PLAYBACK,0,"mock-open")<0);
      assert(open_count==allowed&&global_count==0);
    }
    assert(g955n_scope_open(&h,"_ucm0001.hw:0,0",SND_PCM_STREAM_CAPTURE,0,"mock-open")<0);
    assert(open_count==allowed&&global_count==0);
    assert(g955n_scope_open(&h,"_ucm0001.hw:Exynos8895Mader,9",SND_PCM_STREAM_CAPTURE,0,"mock-open")==0);
    assert(open_count==allowed+1&&global_count==0);
    FILE *f=fopen(model,"w");assert(f);fputs("Other device",f);fclose(f);
    assert(!g955n_scope_model());assert(policy("default",SND_PCM_STREAM_CAPTURE)==-ENODEV);assert(g955n_scope_index(0)==-ENODEV);
    unlink(model);puts("PASS: exact playback and capture scope, isolated lconf and zero global opens");return 0;
}
