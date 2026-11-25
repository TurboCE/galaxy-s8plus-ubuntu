/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef G955N_WIRED_JACK_H
#define G955N_WIRED_JACK_H

struct g955n_wired_jack;
struct snd_soc_pcm_runtime;

struct g955n_wired_jack *g955n_wired_jack_init(struct snd_soc_pcm_runtime *rtd);
void g955n_wired_jack_exit(struct g955n_wired_jack *jack);

#endif
