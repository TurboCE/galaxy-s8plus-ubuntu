// SPDX-License-Identifier: GPL-2.0-only
#include <linux/slab.h>

#include "aid-source/dimming.h"
#include "aid-source/s6e3ha6/dream2-a3.h"
#include "aid-source/s6e3ha6/dream2-a3-brightness.h"

#include "g955n-panel-profile.h"

#define DREAM2_GAMMA_LEN 35

int g955n_aor_trial_value(const u8 saved[2], u8 trial[2])
{
	unsigned int baseline = (saved[0] << 8) | saved[1];
	unsigned int best_delta = 65;
	unsigned int i;

	/* Increase AOR modestly to dim the panel at its existing gamma. */
	for (i = 0; i < ARRAY_SIZE(dream2_a3_sa_aor_table); i++) {
		const u8 *entry = dream2_a3_sa_aor_table[i];
		int delta = ((entry[0] << 8) | entry[1]) - (int)baseline;

		if (delta >= 32 && delta < best_delta) {
			best_delta = delta;
			memcpy(trial, entry, 2);
		}
	}

	return best_delta < 65 ? 0 : -ERANGE;
}

static void dream2_decode_mtp(struct tp *tp, const u8 *mtp)
{
	unsigned int pos = 0, color;
	int point;

	for (color = 0; color < MAX_COLOR; color++, pos += 2)
		tp[S6E3HA6_NR_TP - 1].offset[color] =
			(mtp[pos] & 1 ? -1 : 1) * mtp[pos + 1];

	for (point = S6E3HA6_NR_TP - 2; point > 0; point--) {
		for (color = 0; color < MAX_COLOR; color++, pos++)
			tp[point].offset[color] =
				(mtp[pos] & 0x80 ? -1 : 1) * (mtp[pos] & 0x7f);
	}

	tp[0].offset[RED] = mtp[pos] >> 4;
	tp[0].offset[GREEN] = mtp[pos] & 0x0f;
	tp[0].offset[BLUE] = mtp[pos + 1] & 0x0f;
}

static int g955n_generate_gamma(const u8 *mtp, unsigned int selected, u8 *output)
{
	struct dimming_tp_output *points;
	struct dimming_info *dim;
	u8 gamma[DREAM2_GAMMA_LEN], first[DREAM2_GAMMA_LEN];
	int row, ret = -ENOMEM;

	dim = kzalloc(sizeof(*dim), GFP_KERNEL);
	if (!dim)
		return ret;
	dim->tp = kmemdup(s6e3ha6_tp, sizeof(s6e3ha6_tp), GFP_KERNEL);
	dim->dim_lut = kmemdup(dream2_a3_sa_dimming_lut,
			       sizeof(dream2_a3_sa_dimming_lut), GFP_KERNEL);
	points = kvcalloc(S6E3HA6_NR_LUMINANCE * S6E3HA6_NR_TP, sizeof(*points), GFP_KERNEL);
	if (!dim->tp || !dim->dim_lut || !points)
		goto free;

	dim->nr_tp = S6E3HA6_NR_TP;
	dim->nr_luminance = S6E3HA6_NR_LUMINANCE;
	dim->target_luminance = S6E3HA6_TARGET_LUMINANCE;
	dim->target_g_curve_degree = GAMMA_2_20;
	/* Samsung Dream2 A3 reference voltage in Q24 and its VT table. */
	dim->vregout = 114085069LL;
	memcpy(dim->vt_voltage, (const u32[]){
		0, 12, 24, 36, 48, 60, 72, 84, 96, 108, 138, 148, 158, 168, 178, 186,
	}, sizeof(dim->vt_voltage));

	dream2_decode_mtp(dim->tp, mtp);
	for (row = 0; row < dim->nr_luminance; row++)
		dim->dim_lut[row].tpout = points + row * dim->nr_tp;
	ret = process_dimming(dim);
	if (ret)
		goto free;

	for (row = 0; row < dim->nr_luminance; row++) {
		memset(gamma, 0, sizeof(gamma));
		get_dimming_gamma_compact(dim, dim->dim_lut[row].luminance, gamma);
		if (!memchr_inv(gamma, 0, sizeof(gamma))) {
			ret = -ENODATA;
			goto free;
		}
		if (!row)
			memcpy(first, gamma, sizeof(first));
		if (output && row == selected)
			memcpy(output, gamma, sizeof(gamma));
	}
	if (!memcmp(first, gamma, sizeof(gamma))) {
		ret = -ENODATA;
		goto free;
	}

	pr_info("g955n-dsim: computed %d calibrated gamma rows (%u to %d nits)\n",
		dim->nr_luminance, dim->dim_lut[0].luminance, dim->target_luminance);
free:
	memzero_explicit(gamma, sizeof(gamma));
	memzero_explicit(first, sizeof(first));
	g955n_aid_release_orders();
	kvfree_sensitive(points, S6E3HA6_NR_LUMINANCE * S6E3HA6_NR_TP * sizeof(*points));
	kfree(dim->dim_lut);
	kfree_sensitive(dim->tp);
	kfree_sensitive(dim);
	return ret;
}

int g955n_aid_verify(const u8 *mtp)
{
	return g955n_generate_gamma(mtp, 0, NULL);
}

int g955n_build_panel_profile(const u8 *mtp, unsigned int brightness,
			      struct g955n_panel_profile *profile)
{
	unsigned int row = 0, step = 0, plane = 0;
	u8 tset = profile->elvss[0];
	int ret;

	if (brightness > 255)
		return -ERANGE;

	static_assert(ARRAY_SIZE(dream2_a3_sa_brt_tbl) == S6E3HA6_NR_LUMINANCE);
	static_assert(ARRAY_SIZE(dream2_a3_sa_brt_to_step_tbl) ==
		      ARRAY_SIZE(dream2_a3_sa_aor_table));
	static_assert(ARRAY_SIZE(dream2_a3_sa_brt_to_step_tbl) ==
		      ARRAY_SIZE(dream2_a3_sa_irc_table));

	/* Samsung uses the first entry at or above the scaled brightness. */
	while (dream2_a3_sa_brt_tbl[row] < brightness * 100)
		row++;
	while (dream2_a3_sa_brt_to_step_tbl[step] < brightness * 100)
		step++;

	ret = g955n_generate_gamma(mtp, row, profile->gamma);
	if (ret)
		return ret;

	memcpy(profile->aor, dream2_a3_sa_aor_table[step], sizeof(profile->aor));
	memcpy(profile->irc, dream2_a3_sa_irc_table[step], sizeof(profile->irc));
	if (tset & 0x80)
		plane = (tset & 0x7f) >= 15 ? 2 : 1;
	else if (!tset)
		plane = 1;
	profile->elvss[1] = dream2_a3_sa_dimming_lut[row].luminance <= 39 ? 0xcc : 0xdc;
	profile->elvss[2] = dream2_a3_sa_elvss_table[plane][row][0];
	profile->vint[1] = 0x17;
	/* Preserve boot ACL enable policy and select the OEM normal-brightness settings. */
	profile->acl[1] = profile->acl_enable[0] ? 0x55 : 0x44;
	profile->acl[2] = 0x7f;
	profile->acl[6] = 0x14;

	return 0;
}
