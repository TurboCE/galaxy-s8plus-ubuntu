// SPDX-License-Identifier: GPL-2.0-only
#include <linux/slab.h>

#include "aid-source/dimming.h"
#include "aid-source/s6e3ha6/dream2-a3.h"

#define DREAM2_GAMMA_LEN 35

int g955n_aid_verify(const u8 *mtp);

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

int g955n_aid_verify(const u8 *mtp)
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
