#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
# Ubuntu 24.04 with the ARM64 GNOME Settings Daemon build dependencies.
set -eu

if [ "$#" -ne 2 ]; then
    printf 'Usage: %s SOURCE_ARCHIVE_DIR NEW_OUTPUT_DIR\n' "$0" >&2
    exit 2
fi

scripts=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
archives=$(CDPATH= cd -- "$1" && pwd)
mkdir "$2"
destination=$(CDPATH= cd -- "$2" && pwd)
cd "$archives"
sha256sum -c <<'CHECKSUMS'
462e25665159cbf56a430849797cecf59a28e13a8c90434aecd844e013b4b1e4  gnome-settings-daemon_46.0-1ubuntu1.24.04.1.dsc
0b9a0f64fa18a8e7e09b4c95a3f754fa033c2cdbd2dc35701f0618572c1cb3d7  gnome-settings-daemon_46.0.orig.tar.xz
b1c33ac4eda60bd5f54531e67cca1b865234a6fc9b853ecfd26f3f33f3773f3a  gnome-settings-daemon_46.0-1ubuntu1.24.04.1.debian.tar.xz
CHECKSUMS
cd "$destination"
dpkg-source -x "$archives/gnome-settings-daemon_46.0-1ubuntu1.24.04.1.dsc" source
cd source
patch --batch --fuzz=0 -p1 < "$scripts/0001-ramp-ambient-backlight.patch"

export DEB_BUILD_MAINT_OPTIONS=hardening=+all
export DEB_LDFLAGS_MAINT_APPEND='-Wl,-z,defs -Wl,-O1 -Wl,--warn-unresolved-symbols'
export DEB_LDFLAGS_MAINT_STRIP='-Wl,-Bsymbolic-functions'
eval "$(DEB_HOST_ARCH=arm64 dpkg-buildflags --export=sh)"
set --
if [ "$(dpkg --print-architecture)" != arm64 ]; then
    # CUPS detection uses an executable config tool and is only needed by printing.
    set -- --cross-file "$scripts/../compositor-build/cross-arm64.ini" -Dcups=false
fi
meson setup build "$@" --prefix=/usr --libdir=/usr/lib --libexecdir=/usr/libexec \
    --sysconfdir=/etc --buildtype=plain -Dudev_dir=/usr/lib/udev
ninja -C build -j "${G955N_BUILD_JOBS:-4}" plugins/power/gsd-power
install -m 755 build/plugins/power/gsd-power "$destination/gsd-power"
/usr/bin/python3 - "$destination/gsd-power" <<'PY'
import sys
from mesonbuild.scripts.depfixer import Elf, fix_elf

binary = sys.argv[1]
with Elf(binary, False) as elf:
    paths = {path.encode() for value in (elf.get_rpath(), elf.get_runpath())
             if value for path in value.split(':')}
fix_elf(binary, paths, b'/usr/lib/gnome-settings-daemon-46', False)
PY
readelf -h -d "$destination/gsd-power"
