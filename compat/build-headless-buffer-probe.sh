#!/usr/bin/env bash
# Build-only: no handset access, mounts, Binder calls, daemon/service activation.
# All inputs are existing public Android9 sources/generated headers and own libs.
set -euo pipefail
SOURCE_DIR=$(cd "$(dirname "$0")" && pwd)
BIONIC=${1:?Usage: build-headless-buffer-probe.sh BIONIC CORE LIBHIDL LIBCXX GENERATED OWN_LIBS OUTPUT}
CORE=${2:?}
LIBHIDL=${3:?}
LIBCXX=${4:?}
GENERATED=${5:?}
OWN_LIBS=${6:?}
OUTPUT_PATH=$(realpath -m "${7:?Specify private staging output}")
COMPILER=${CXX:-clang++}
case "$OUTPUT_PATH" in /dev/*|/proc/*|/sys/*|/efs/*|/system/*|/vendor/*|/usr/*|/bin/*|/sbin/*|/etc/*|/boot/*) echo 'Use private staging output' >&2; exit 2 ;; esac
if [ -e "$OUTPUT_PATH" ] && [ ! -f "$OUTPUT_PATH" ]; then echo 'Output must be a regular file' >&2; exit 2; fi
for file in android.hardware.graphics.mapper@2.0.so android.hardware.graphics.allocator@2.0.so libc++.so libhidlbase.so libhidltransport.so libutils.so libc.so libm.so libdl.so; do
  test -f "$OWN_LIBS/$file"
  readelf -h "$OWN_LIBS/$file" | grep -q 'Machine:.*AArch64'
done
test -f "$GENERATED/android/hardware/graphics/mapper/2.0/IMapper.h"
OBJ_DIR=$(mktemp -d)
trap 'rm -rf "$OBJ_DIR"' EXIT
COMMON=(--target=aarch64-linux-android28 -O2 -fPIE -fstack-protector-strong -nostdlibinc
        -isystem "$BIONIC/libc/include" -isystem "$BIONIC/libc/kernel/uapi"
        -isystem "$BIONIC/libc/kernel/uapi/asm-arm64" -isystem "$BIONIC/libc/kernel/android/uapi")
"$COMPILER" "${COMMON[@]}" -x c -fno-stack-protector -c "$SOURCE_DIR/android-cli-start.c" -o "$OBJ_DIR/start.o"
"$COMPILER" "${COMMON[@]}" -std=c++14 -Wall -Wextra -Werror -fno-exceptions -fno-rtti -nostdinc++ \
  -isystem "$LIBCXX/include" -isystem "$GENERATED" -isystem "$LIBHIDL/base/include" \
  -isystem "$LIBHIDL/transport/include" -isystem "$CORE/libutils/include" \
  -isystem "$CORE/libcutils/include" -isystem "$CORE/base/include" \
  -c "$SOURCE_DIR/headless-buffer-probe.cpp" -o "$OBJ_DIR/query.o"
"$COMPILER" --target=aarch64-linux-android28 -fuse-ld=lld -nostdlib -pie \
  -Wl,-e,_start,--dynamic-linker=/system/bin/linker64,-z,relro,-z,now,-z,noexecstack,--allow-shlib-undefined \
  "$OBJ_DIR/start.o" "$OBJ_DIR/query.o" \
  "$OWN_LIBS/android.hardware.graphics.mapper@2.0.so" "$OWN_LIBS/android.hardware.graphics.allocator@2.0.so" \
  "$OWN_LIBS/libhidltransport.so" "$OWN_LIBS/libhidlbase.so" "$OWN_LIBS/libutils.so" \
  "$OWN_LIBS/libc++.so" "$OWN_LIBS/libc.so" "$OWN_LIBS/libm.so" "$OWN_LIBS/libdl.so" -o "$OUTPUT_PATH"
# The minimal CRT intentionally has no C++ startup arrays. Reject global C++
# constructors instead of silently building an executable that omits them.
if readelf -SW "$OUTPUT_PATH" | grep -qE '\.(init_array|preinit_array|fini_array) '; then
  rm "$OUTPUT_PATH"
  echo 'Unexpected startup arrays: requires full matching Bionic CRT' >&2
  exit 1
fi
readelf -l "$OUTPUT_PATH" | grep 'Requesting program interpreter'
readelf -d "$OUTPUT_PATH" | grep NEEDED
printf 'Built only (not executed): %s\n' "$OUTPUT_PATH"
