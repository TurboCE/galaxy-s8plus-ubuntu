/* SPDX-License-Identifier: MIT
 * Parse-only test against the real ALSA library; no control/PCM open API used. */
#include <alsa/asoundlib.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void)
{
    const char *texts[]={
      "ctl.g955n_native { type hw card \"Exynos8895Mader\" }",
      "ctl.g955n_native { type hw card \"0\" }",
      "pcm.g955n_native { type hw card 0 device 0 subdevice 0 }"};
    for(unsigned int i=0;i<3;i++){
      snd_config_t *config=NULL,*value=NULL;const char *type=NULL;
      assert(snd_config_load_string(&config,texts[i],0)==0);
      assert(snd_config_search(config,i<2?"ctl.g955n_native.type":"pcm.g955n_native.type",&value)==0);
      assert(snd_config_get_string(value,&type)==0&&!strcmp(type,"hw"));
      assert(snd_config_search(config,"@hooks",&value)<0);
      if(i==2){long card=-1;assert(snd_config_search(config,"pcm.g955n_native.card",&value)==0);
        assert(snd_config_get_integer(value,&card)==0&&card==0);}
      snd_config_delete(config);
    }
    puts("PASS: three isolated type-hw roots parsed, no hooks, no device access");return 0;
}
