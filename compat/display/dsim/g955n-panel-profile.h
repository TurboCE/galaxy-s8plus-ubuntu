/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef G955N_PANEL_PROFILE_H
#define G955N_PANEL_PROFILE_H

#include <linux/types.h>

#define G955N_GAMMA_LEN 35
#define G955N_GAMMA_ROWS 74

struct g955n_gamma_table {
	u8 rows[G955N_GAMMA_ROWS][G955N_GAMMA_LEN];
};

struct g955n_panel_profile {
	u8 gamma[G955N_GAMMA_LEN];
	u8 aor[2];
	u8 elvss[24];
	u8 vint[2];
	u8 acl[7];
	u8 acl_enable[1];
	u8 poc[2];
	u8 irc[20];
};

int g955n_compile_gamma(const u8 *mtp, struct g955n_gamma_table *table);
int g955n_aor_trial_value(const u8 saved[2], u8 trial[2]);
int g955n_estimate_panel_brightness(const struct g955n_panel_profile *profile);
int g955n_build_panel_profile(const struct g955n_gamma_table *table, unsigned int brightness,
			      struct g955n_panel_profile *profile);

#endif
