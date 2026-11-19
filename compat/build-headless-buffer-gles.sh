#!/usr/bin/env bash
# Build-only lazy plugin; no Mali library is linked or loaded during build.
set -euo pipefail
SOURCE_DIR=$(cd "$(dirname "$0")" && pwd)
BIONIC=${1:?Usage: build-headless-buffer-gles.sh BIONIC LIBCXX PUBLIC_ANDROID9_HEADERS OPENGL_HEADERS OWN_LIBS OUTPUT}
LIBCXX=${2:?}; PUBLIC_HEADERS=${3:?}; OPENGL_HEADERS=${4:?}; OWN_LIBS=${5:?}
OUTPUT_PATH=$(realpath -m "${6:?Private staging output}")
case "$OUTPUT_PATH" in /dev/*|/proc/*|/sys/*|/efs/*|/system/*|/vendor/*|/usr/*|/bin/*|/sbin/*|/etc/*|/boot/*) exit 2 ;; esac
${CXX:-clang++} --target=aarch64-linux-android28 -std=c++14 -O2 -Wall -Wextra -Werror \
  -fno-exceptions -fno-rtti -fPIC -fstack-protector-strong -mno-outline-atomics -nostdinc++ -nostdlibinc \
  -isystem "$LIBCXX/include" -isystem "$BIONIC/libc/include" -isystem "$BIONIC/libc/kernel/uapi" \
  -isystem "$BIONIC/libc/kernel/uapi/asm-arm64" -isystem "$BIONIC/libc/kernel/android/uapi" \
  -isystem "$PUBLIC_HEADERS" -isystem "$OPENGL_HEADERS" \
  -shared -fuse-ld=lld -nostdlib -Wl,-z,relro,-z,now,-z,noexecstack,--no-undefined,--allow-shlib-undefined \
  "$SOURCE_DIR/headless-buffer-gles.cpp" "$OWN_LIBS/libc++.so" "$OWN_LIBS/libc.so" "$OWN_LIBS/libdl.so" -o "$OUTPUT_PATH"
readelf -d "$OUTPUT_PATH" | grep NEEDED
if readelf -d "$OUTPUT_PATH" | grep -qiE 'NEEDED.*(mali|EGL|GLES)'; then rm "$OUTPUT_PATH"; exit 1; fi
if readelf -SW "$OUTPUT_PATH" | grep -qE '\.(init_array|preinit_array|fini_array) '; then rm "$OUTPUT_PATH"; exit 1; fi
printf 'Built only: no driver loaded: %s\n' "$OUTPUT_PATH"
