#!/usr/bin/env bash
# Build/install only into the handset user's private prefix; no sudo or flashing.
set -euo pipefail
test "$(id -u)" != 0
test "$(uname -s)" = Linux
test "$(uname -m)" = aarch64
grep -q SM-G955N /proc/device-tree/model
WORKSPACE=${1:-$HOME/g955n-compat-build}
INSTALL_PREFIX=${2:-$HOME/g955n-compat-install}
case "$INSTALL_PREFIX" in "$HOME/"*) ;; *) echo 'Use a private home prefix' >&2; exit 1 ;; esac
test -f "$WORKSPACE/android9-headers/android-version.h"
cd "$WORKSPACE/libhybris/hybris"
autoreconf -fi
./configure --prefix="$INSTALL_PREFIX" \
  --with-android-headers="$WORKSPACE/android9-headers" --enable-arch=arm64 \
  --enable-mali-quirks --enable-property-cache --enable-wayland \
  --with-default-egl-platform=null
make -j4
make install
