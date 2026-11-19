#!/usr/bin/env bash
# Build-only Android9 shared object from public headers/sources and own .so inputs.
# No binary execution, Binder calls, hardware opens, install or service startup.
set -euo pipefail
WORK=${1:?Specify dedicated private compositor workspace}
test "$WORK" = /work || { echo "Use dedicated container /work volume" >&2; exit 2; }
ROOT=$(cd "$(dirname "$0")" && pwd)
PATCH="$ROOT/patches/0004-libhybris-hwc2-sideband-c-abi.patch"
if patch -d "$WORK/input/libhybris" -p1 --forward --batch --dry-run --silent < "$PATCH"; then
 patch -d "$WORK/input/libhybris" -p1 --forward --batch < "$PATCH"
elif ! patch -d "$WORK/input/libhybris" -p1 --reverse --batch --dry-run --silent < "$PATCH"; then
 echo "Unrecognized HWC2 ABI patch state" >&2; exit 1
fi
BIONIC="$WORK/input/aosp/bionic"
CORE="$WORK/input/aosp/system/core"
NATIVE="$WORK/input/aosp/frameworks/native"
HARDWARE="$WORK/public/hardware-interfaces"
FRAMEWORKS="$WORK/public/frameworks-hardware-interfaces"
HIDL="$WORK/public/libhidl"
LIBCXX="$WORK/public/libcxx"
OWN="$WORK/input/own-libs"
SOURCE="$WORK/input/libhybris/compat/hwc2"
GENERATED="$WORK/generated-composer"
OUTPUT="$WORK/hwc2-android9"
mkdir -p "$GENERATED" "$OUTPUT"
GENERATOR="$WORK/input/hidl-host2/hidl-gen"
for package in android.hidl.base@1.0 android.hidl.manager@1.0 \
 android.hardware.graphics.common@1.0 android.hardware.graphics.common@1.1 \
 android.hardware.graphics.allocator@2.0 android.hardware.graphics.mapper@2.0 \
 android.hardware.graphics.composer@2.1 android.hardware.graphics.composer@2.2 \
 android.hardware.media@1.0 android.hardware.graphics.bufferqueue@1.0 android.hidl.token@1.0 \
 android.hardware.configstore@1.0 android.frameworks.vr.composer@1.0; do
 "$GENERATOR" -Lc++-headers -o "$GENERATED/" \
  -randroid.hidl:"$HIDL/transport" -randroid.hardware:"$HARDWARE" \
  -randroid.frameworks:"$FRAMEWORKS" "$package"
done
FLAGS=(--target=aarch64-linux-android28 -std=c++17 -O2 -fPIC -fstack-protector-strong
 -mno-outline-atomics -fno-exceptions -fno-rtti -nostdlibinc -nostdinc++
 -DANDROID_VERSION_MAJOR=9 -DANDROID_VERSION_MINOR=0 -DANDROID_VERSION_PATCH=0
 -DGL_GLEXT_PROTOTYPES -UNDEBUG -Wno-unused-parameter -Wno-deprecated-declarations
 -isystem "$LIBCXX/include" -isystem "$BIONIC/libc/include" -isystem "$BIONIC/libc/kernel/uapi"
 -isystem "$BIONIC/libc/kernel/uapi/asm-arm64" -isystem "$BIONIC/libc/kernel/android/uapi"
 -isystem "$GENERATED"
 -isystem "$HIDL/base/include" -isystem "$HIDL/transport/include"
 -isystem "$HIDL/transport/token/1.0/utils/include"
 -isystem "$WORK/public/libhwbinder/include"
 -isystem "$CORE/libutils/include" -isystem "$CORE/libcutils/include"
 -isystem "$CORE/base/include" -isystem "$CORE/liblog/include"
 -isystem "$CORE/libsystem/include" -isystem "$CORE/libsync/include"
 -isystem "$NATIVE/include" -isystem "$NATIVE/libs/ui/include"
 -isystem "$NATIVE/libs/gui/include" -isystem "$NATIVE/libs/math/include"
 -isystem "$NATIVE/libs/binder/include" -isystem "$NATIVE/libs/nativewindow/include"
 -isystem "$NATIVE/libs/nativebase/include" -isystem "$NATIVE/libs/arect/include" -isystem "$NATIVE/libs/geometry/include"
 -isystem "$NATIVE/opengl/include" -isystem "$WORK/public/libfmq/include"
 -isystem "$WORK/input/aosp/hardware/libhardware/include"
 -isystem "$HARDWARE/graphics/composer/2.1/utils/command-buffer/include"
 -isystem "$HARDWARE/graphics/composer/2.2/utils/command-buffer/include"
 -isystem "$HARDWARE/configstore/utils/include"
 -I"$WORK/input/libhybris/hybris/include" -I"$SOURCE")
for unit in HWC2 HidlComposerHal ComposerHal hwc2_compatibility_layer; do
 clang++ "${FLAGS[@]}" -c "$SOURCE/$unit.cpp" -o "$OUTPUT/$unit.o"
done
LIBS=(android.frameworks.vr.composer@1.0 android.hardware.graphics.allocator@2.0
 android.hardware.graphics.composer@2.1 android.hardware.graphics.composer@2.2
 android.hardware.configstore@1.0 android.hardware.configstore-utils
 libcutils liblog libfmq libhardware libhidlbase libhidltransport libhwbinder
 libutils libEGL libGLESv1_CM libGLESv2 libbinder libui libgui libsync libbase
 libc++ libc libm libdl)
LINK=()
for lib in "${LIBS[@]}"; do test -f "$OWN/$lib.so"; LINK+=("$OWN/$lib.so"); done
clang++ --target=aarch64-linux-android28 -fuse-ld=lld -nostdlib -shared \
 -Wl,-soname,libhwc2_compat_layer.so,-z,relro,-z,now,-z,noexecstack,-z,defs,--allow-shlib-undefined \
 "$OUTPUT/"*.o "${LINK[@]}" -o "$OUTPUT/libhwc2_compat_layer.so"
readelf -h "$OUTPUT/libhwc2_compat_layer.so" | grep -E 'Class:|Machine:|Type:'
readelf -d "$OUTPUT/libhwc2_compat_layer.so" | grep NEEDED
sha256sum "$OUTPUT/libhwc2_compat_layer.so"
echo 'Built only; Android/HIDL/HWC2 runtime and presentation are untested.'
