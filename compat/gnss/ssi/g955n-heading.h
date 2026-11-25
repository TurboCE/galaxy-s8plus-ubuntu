/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef G955N_HEADING_H
#define G955N_HEADING_H

#include <linux/math64.h>
#include <linux/types.h>

/* Project the positive Y axis of the SSP rotation quaternion onto ENU. */
static inline bool g955n_heading_mdeg(const s32 q[4], int *heading)
{
	static const int angles[] = {
		45000, 26565, 14036, 7125, 3576, 1790, 895, 448,
		224, 112, 56, 28, 14, 7, 3, 2, 1,
	};
	const s64 x = q[0], y = q[1], z = q[2], w = q[3];
	s64 norm, east, north, projected_east, projected_north, limit;
	int degrees = 0;
	unsigned int i;

	for (i = 0; i < 4; i++) {
		if (q[i] < -1100000 || q[i] > 1100000)
			return false;
	}
	norm = x * x + y * y + z * z + w * w;
	if (norm < 900000000000LL || norm > 1100000000000LL)
		return false;
	east = 2 * (x * y - z * w);
	north = norm - 2 * (x * x + z * z);
	/* Reject a nearly vertical Y axis without squaring trillion-scale values. */
	projected_east = div_s64(east, 1000000);
	projected_north = div_s64(north, 1000000);
	limit = div_s64(norm, 100000000);
	if (projected_east * projected_east + projected_north * projected_north < limit * limit)
		return false;

	/* Integer CORDIC vectoring, with a half-turn for the western quadrants. */
	if (north < 0) {
		north = -north;
		east = -east;
		degrees = 180000;
	}
	for (i = 0; i < sizeof(angles) / sizeof(angles[0]) && east; i++) {
		s64 previous_north = north;

		if (east > 0) {
			north += east >> i;
			east -= previous_north >> i;
			degrees += angles[i];
		} else {
			north -= east >> i;
			east += previous_north >> i;
			degrees -= angles[i];
		}
	}

	*heading = (degrees + 360000) % 360000;
	return true;
}

#endif
