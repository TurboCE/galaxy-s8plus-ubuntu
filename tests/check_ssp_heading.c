/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "../compat/sensors/ssp-heading.h"
#include <assert.h>
#include <stdio.h>

static void check(double azimuth, double tilt)
{
    const double radians = acos(-1.0) / 180.0;
    const double yaw = -azimuth * radians / 2.0;
    const double pitch = tilt * radians / 2.0;
    const int32_t q[] = {
        lround(1e6 * cos(yaw) * sin(pitch)),
        lround(1e6 * sin(yaw) * sin(pitch)),
        lround(1e6 * sin(yaw) * cos(pitch)),
        lround(1e6 * cos(yaw) * cos(pitch)),
    };
    double heading;
    assert(ssp_heading(q, &heading));
    assert(heading >= 0.0 && heading < 360.0);
    assert(fabs(remainder(heading - azimuth, 360.0)) < 0.001);
}

int main(void)
{
    const double points[] = {0, 45, 90, 180, 270, 359};
    for (unsigned int i = 0; i < sizeof(points) / sizeof(points[0]); i++) {
        check(points[i], 0);
        check(points[i], 45);
    }

    double heading;
    const int32_t zero[] = {0, 0, 0, 0};
    const int32_t invalid[] = {INT32_MAX, INT32_MAX, INT32_MAX, INT32_MAX};
    const int32_t vertical[] = {707107, 0, 0, 707107};
    assert(!ssp_heading(zero, &heading));
    assert(!ssp_heading(invalid, &heading));
    assert(!ssp_heading(vertical, &heading));
    puts("SSP headings, tilt and invalid rotation vectors passed");
}
