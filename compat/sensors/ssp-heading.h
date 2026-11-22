/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef G955N_SSP_HEADING_H
#define G955N_SSP_HEADING_H

#include <math.h>
#include <stdbool.h>
#include <stdint.h>

static inline bool
ssp_heading(const int32_t q[4], double *heading)
{
    const double x = q[0], y = q[1], z = q[2], w = q[3];
    const double norm = x*x + y*y + z*z + w*w;

    /* The Exynos8895 SSP rotation vector uses approximately 10^6 units
     * for a unit quaternion. Check the wire range before normalizing. */
    if (norm < 9e11 || norm > 1.1e12)
        return false;

    /* East and north projections of the device's positive Y axis.
     * Android's rotation-vector frame is east, magnetic north, up. */
    const double east = 2.0 * (x*y - z*w);
    const double north = norm - 2.0 * (x*x + z*z);
    if (hypot(east, north) < norm * 0.01)
        return false; /* Heading is undefined with the top edge vertical. */

    double degrees = atan2(east, north) * (180.0 / acos(-1.0));
    if (degrees < 0.0)
        degrees += 360.0;
    *heading = degrees >= 360.0 ? 0.0 : degrees;
    return true;
}

#endif
