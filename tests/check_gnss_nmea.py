#!/usr/bin/env python3
"""Exercise the production NMEA checksum and framing filter without hardware."""
from pathlib import Path
import subprocess
import tempfile

SOURCE = Path(__file__).resolve().parents[1] / 'compat/gnss/hal-probe.c'
code = SOURCE.read_text()
filter_code = code[code.index('static int hex_digit'):code.index('static void on_capabilities')]
fixture = r'''
#include <assert.h>
#include <errno.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
typedef int64_t GpsUtcTime;
static unsigned nmea_count;
static bool serving;
static volatile sig_atomic_t interrupted;
''' + filter_code + r'''
int main(void) {
    const char valid[] = "$GPGLL,4916.45,N,12311.12,W,225444,A,*1D\r\n";
    char invalid[sizeof(valid)];
    on_nmea(0, valid, sizeof(valid) - 1);
    assert(nmea_count == 1);
    memcpy(invalid, valid, sizeof(valid));
    invalid[7] ^= 1;
    on_nmea(0, invalid, sizeof(invalid) - 1);
    on_nmea(0, valid, sizeof(valid) - 2);
    assert(nmea_count == 2);
    on_nmea(0, valid, sizeof(valid) - 4);
    on_nmea(0, "not a GPS sentence", 18);
    assert(nmea_count == 2);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    source = root / 'nmea.c'
    program = root / 'check'
    source.write_text(fixture)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(source),'-o',str(program)],check=True)
    subprocess.run([program],check=True)
print('GNSS NMEA framing and checksum checks passed')
