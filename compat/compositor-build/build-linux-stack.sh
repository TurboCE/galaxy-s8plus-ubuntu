#!/usr/bin/env bash
# Offline cross-build/stage only. Never run a compositor, HAL, daemon or ldconfig.
set -euo pipefail
WORK=${1:-/work}
test "$WORK" = /work || { echo 'Use dedicated container /work volume' >&2; exit 2; }
SCRIPTS=$(cd "$(dirname "$0")" && pwd)
PREFIX="$WORK/prefix"
mkdir -p "$PREFIX/lib/pkgconfig" "$PREFIX/include"
export PKG_CONFIG_LIBDIR="$PREFIX/lib/pkgconfig:/usr/lib/aarch64-linux-gnu/pkgconfig:/usr/share/pkgconfig"
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig"
CROSS="$SCRIPTS/cross-arm64.ini"
GLIBUTIL=$(find "$WORK/sources" -maxdepth 1 -type d -name 'sailfishos-libglibutil-*' | head -1)
GBINDER=$(find "$WORK/sources" -maxdepth 1 -type d -name 'mer-hybris-libgbinder-*' | head -1)
DROID=$(find "$WORK/sources" -maxdepth 1 -type d -name 'droidian-libdroid-*' | head -1)
WLROOTS=$(find "$WORK/sources" -maxdepth 1 -type d -name 'droidian-wlroots-*' | head -1)
for dir in "$GLIBUTIL" "$GBINDER" "$DROID" "$WLROOTS"; do test -d "$dir"; done
for pair in "$GLIBUTIL:gutil" "$GBINDER:gbinder"; do
 SOURCE=${pair%:*}; INCLUDE=${pair##*:}
 make -C "$SOURCE" -j4 release pkgconfig CC=aarch64-linux-gnu-gcc \
    AR=aarch64-linux-gnu-ar STRIP=aarch64-linux-gnu-strip LIBDIR=work/prefix/lib
 make -C "$SOURCE" install-dev CC=aarch64-linux-gnu-gcc \
    LIBDIR=work/prefix/lib INSTALL_INCLUDE_DIR="$PREFIX/include/$INCLUDE" \
    STRIP=aarch64-linux-gnu-strip
 # These upstream Makefiles hardcode /usr/include in their pkg-config template.
 # Only private staged metadata is adjusted; global library config is untouched.
 sed -i "s|includedir=/usr/include|includedir=$PREFIX/include|" "$PREFIX/lib/pkgconfig/lib${INCLUDE/gutil/glibutil}.pc"
done
for patch_file in "$SCRIPTS/patches/"000[12]-*.patch; do
 if patch -d "$DROID" -p1 --forward --batch --dry-run --silent < "$patch_file"; then
  patch -d "$DROID" -p1 --forward --batch < "$patch_file"
 elif ! patch -d "$DROID" -p1 --reverse --batch --dry-run --silent < "$patch_file"; then
  echo "Unrecognized source/patch state: $patch_file" >&2; exit 1
 fi
done
DROID_RECONFIGURE=()
if test -f "$WORK/build-libdroid/meson-private/coredata.dat"; then DROID_RECONFIGURE=(--reconfigure --clearcache); fi
meson setup "${DROID_RECONFIGURE[@]}" "$WORK/build-libdroid" "$DROID" --cross-file "$CROSS" \
 --prefix="$PREFIX" --libdir=lib --wrap-mode=nodownload --buildtype=release -Dintrospection=disabled
ninja -C "$WORK/build-libdroid" src/libdroid-0.so.1
# Install only the library/development metadata: do not install HAL service units.
find "$WORK/build-libdroid/src" -maxdepth 1 \( -type f -o -type l \) -name "libdroid-0.so*" -exec cp -a {} "$PREFIX/lib/" \;
mkdir -p "$PREFIX/include/libdroid"
cp "$DROID/include/libdroid/"*.h "$WORK/build-libdroid/include/libdroid/libdroid-version.h" "$PREFIX/include/libdroid/"
cp "$WORK/build-libdroid/meson-private/libdroid-0.pc" "$PREFIX/lib/pkgconfig/"
patch_file="$SCRIPTS/patches/0003-libhybris-hwc-buffer-count.patch"
if patch -d "$WORK/input/libhybris" -p1 --forward --batch --dry-run --silent < "$patch_file"; then
 patch -d "$WORK/input/libhybris" -p1 --forward --batch < "$patch_file"
elif ! patch -d "$WORK/input/libhybris" -p1 --reverse --batch --dry-run --silent < "$patch_file"; then
 echo "Unrecognized libhybris patch state" >&2; exit 1
fi
cd "$WORK/input/libhybris/hybris"
autoreconf -fi
PKG_CONFIG_LIBDIR="$PKG_CONFIG_LIBDIR" ./configure \
 --host=aarch64-linux-gnu --build=x86_64-linux-gnu \
 CC=aarch64-linux-gnu-gcc CXX=aarch64-linux-gnu-g++ \
 --prefix="$PREFIX" --libdir="$PREFIX/lib" \
 --with-android-headers="$WORK/input/android9-headers" --enable-arch=arm64 \
 --enable-mali-quirks --enable-property-cache --enable-wayland \
 --with-default-egl-platform=null
make -j4
make install
# Existing extracted Android9 headers are a build-only pkg-config dependency.
# Droidian additionally includes android/nativebase and android/system paths.
# This points to the same public header tree, not replacement definitions.
mkdir -p "$WORK/android-include"
ln -sfn "$WORK/input/android9-headers" "$WORK/android-include/android"
cat > "$PREFIX/lib/pkgconfig/android-headers.pc" <<PC
Name: android-headers
Description: pinned public Android 9 headers
Version: 9.0.0
Cflags: -I$WORK/input/android9-headers -I$WORK/android-include
PC
WLROOTS_RECONFIGURE=()
if test -f "$WORK/build-wlroots/meson-private/coredata.dat"; then WLROOTS_RECONFIGURE=(--reconfigure --clearcache); fi
meson setup "${WLROOTS_RECONFIGURE[@]}" "$WORK/build-wlroots" "$WLROOTS" --cross-file "$CROSS" \
 --prefix="$PREFIX" --libdir=lib --wrap-mode=nodownload --buildtype=release \
 -Dbackends=hwcomposer,libinput -Drenderers=android,gles2 -Dallocators=[] \
 -Dxwayland=disabled -Dexamples=true -Dsession=enabled -Dc_link_args=-L/work/prefix/lib
meson configure -Dc_link_args=-L/work/prefix/lib "$WORK/build-wlroots"
ninja -C "$WORK/build-wlroots" -j4
# All destinations are the private prefix; no runtime binary is executed.
meson install -C "$WORK/build-wlroots" --no-rebuild
make -C "$WLROOTS/tinywl" CC=aarch64-linux-gnu-gcc CFLAGS="-Wl,-rpath-link,$PREFIX/lib"
cp "$WLROOTS/tinywl/tinywl" "$PREFIX/bin/tinywl-g955n-candidate"
readelf -h "$PREFIX/bin/tinywl-g955n-candidate" | grep -E 'Class:|Type:|Machine:'
echo 'Built only; no compositor/HAL/driver was run.'
