#!/usr/bin/env bash
# Build-only Xorg driver. Does not open an X display or access the handset.
set -euo pipefail
archive=${1:?Usage: build.sh UBUNTU_FBDEV_ARCHIVE FRESH_OUTPUT_DIRECTORY}
output=${2:?Usage: build.sh UBUNTU_FBDEV_ARCHIVE FRESH_OUTPUT_DIRECTORY}
project=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
archive=$(realpath "$archive")
[[ $(sha256sum "$archive" | cut -d ' ' -f 1) == a31f62db237a5c25bb087713a22a867a9b7680833ce3b644ecd712887b7b1d62 ]]
mkdir "$output"
output=$(realpath "$output")
tar -xf "$archive" -C "$output"
cd "$output/xf86-video-fbdev-0.5.0"
patch --batch --forward --fuzz=0 -p1 < "$project/0001-g955n-native-randr.patch"
export PKG_CONFIG_LIBDIR=/usr/lib/aarch64-linux-gnu/pkgconfig:/usr/share/pkgconfig
./configure --host=aarch64-linux-gnu --disable-static
make -j4
aarch64-linux-gnu-readelf -h src/.libs/fbdev_drv.so | grep -q 'Machine:.*AArch64'
cp src/.libs/fbdev_drv.so "$output/"
