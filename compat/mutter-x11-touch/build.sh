#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
# Run in an Ubuntu 24.04 build environment with Mutter build dependencies.
set -eu

if [ "$#" -ne 2 ]; then
    printf 'Usage: %s SOURCE_ARCHIVE_DIR NEW_OUTPUT_DIR\n' "$0" >&2
    exit 2
fi
scripts=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
archives=$(CDPATH= cd -- "$1" && pwd)
mkdir "$2"
destination=$(CDPATH= cd -- "$2" && pwd)
version=46.2-1ubuntu0.24.04.18
cd "$archives"
sha256sum -c <<'CHECKSUMS'
2a0565e69ca3bb46c71e11706b772b409a14176a86b138d2df79e55956b09c8f  mutter_46.2-1ubuntu0.24.04.18.dsc
009baa77f8362612caa2e18c338a1b3c8aad3b5fe2964c2fef7824d321228983  mutter_46.2.orig.tar.xz
ce9d9e5c90edff03dc858a92b8da0227d90548393f726a085420acc6acd7bbb3  mutter_46.2-1ubuntu0.24.04.18.debian.tar.xz
CHECKSUMS
cd "$destination"
dpkg-source -x "$archives/mutter_${version}.dsc" source
cd source
patch --batch --fuzz=0 -p1 < "$scripts/0001-clutter-preserve-emulated-press-picking.patch"
if [ "$(dpkg --print-architecture)" = arm64 ]; then
    build_dir=obj-aarch64-linux-gnu
    DEB_BUILD_OPTIONS=nocheck debian/rules override_dh_auto_configure
else
    cross_file="$scripts/../compositor-build/cross-arm64.ini"
    build_dir=build
    CFLAGS='-O2 -fstack-protector-strong -Wformat -Werror=format-security' \
    LDFLAGS='-Wl,-z,relro -Wl,-z,now' \
    meson setup "$build_dir" --cross-file "$cross_file" --prefix=/usr \
        --libdir=lib/aarch64-linux-gnu --buildtype=plain -Dauto_features=enabled \
        -Degl_device=true -Dremote_desktop=true -Dwayland_eglstream=true \
        -Dlibdisplay_info=disabled -Dintrospection=false -Ddocs=false \
        -Dtests=false -Dcogl_tests=false -Dclutter_tests=false -Dcore_tests=false \
        -Dnative_tests=false -Dudev_dir=/usr/lib/udev -Dxwayland_path=/usr/bin/Xwayland
fi
target=clutter/clutter/libmutter-clutter-14.so.0.0.0
ninja -j "${G955N_BUILD_JOBS:-4}" -C "$build_dir" "$target"
library="$build_dir/$target"
cp "$library" "$destination/"
installed="$destination/$(basename "$target")"
# Apply the same installed search path Meson uses when packaging this library.
python3 - "$installed" <<'PY'
import sys
from mesonbuild.scripts.depfixer import Elf, fix_elf

library = sys.argv[1]
with Elf(library, False) as elf:
    dirs = {path.encode() for value in (elf.get_rpath(), elf.get_runpath())
            if value for path in value.split(':')}
fix_elf(library, dirs, b'/usr/lib/aarch64-linux-gnu/mutter-14', False)
PY
readelf -h "$installed"
readelf -d "$installed"
