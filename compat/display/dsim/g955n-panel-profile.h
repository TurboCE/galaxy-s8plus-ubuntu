/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef G955N_PANEL_PROFILE_H
#define G955N_PANEL_PROFILE_H

#include <linux/types.h>

struct g955n_panel_profile {
	u8 gamma[35];
	u8 aor[2];
	u8 elvss[24];
	u8 vint[2];
	u8 acl[7];
	u8 acl_enable[1];
	u8 poc[2];
	u8 irc[20];
};

int g955n_aid_verify(const u8 *mtp);
int g955n_aor_trial_value(const u8 saved[2], u8 trial[2]);
int g955n_build_panel_profile(const u8 *mtp, unsigned int brightness,
			      struct g955n_panel_profile *profile);

#endif
