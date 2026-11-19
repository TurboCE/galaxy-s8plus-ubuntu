#!/usr/bin/env bash
# Offline Linux host build from existing pinned public Android9 sources only.
# No downloads, device access or modification of source input trees.
set -euo pipefail
TOOLS_HIDL=$(realpath "${1:?Usage: generate-hidl-query-headers.sh TOOLS_HIDL CORE LIBHIDL OUTPUT}")
CORE=$(realpath "${2:?}")
LIBHIDL=$(realpath "${3:?}")
OUTPUT_PATH=$(realpath -m "${4:?Specify private staging output}")
case "$OUTPUT_PATH" in /dev/*|/proc/*|/sys/*|/efs/*|/system/*|/vendor/*|/usr/*|/bin/*|/sbin/*|/etc/*|/boot/*) echo 'Use private staging output' >&2; exit 2 ;; esac
if [ -e "$OUTPUT_PATH" ]; then echo 'Use a new output directory' >&2; exit 2; fi
OBJ_DIR=$(mktemp -d)
trap 'rm -rf "$OBJ_DIR"' EXIT
cd "$OBJ_DIR"
# Modern bison's C++ GLR parser is intrinsically pure; old %pure-parser now
# errors. Modern flex also needs explicit aliases after the parser include.
# These are host-tool compatibility transformations, not HAL/schema changes.
sed '/^%pure-parser$/d' "$TOOLS_HIDL/hidl-gen_y.yy" > hidl-gen_y.yy
bison --defines=hidl-gen_y.h -o hidl-gen_y.cpp hidl-gen_y.yy
sed '/#include "hidl-gen_y.h"/a #define YYSTYPE yy::parser::semantic_type\n#define YYLTYPE yy::parser::location_type' \
  "$TOOLS_HIDL/hidl-gen_l.ll" > hidl-gen_l.ll
flex -o hidl-gen_l.cpp hidl-gen_l.ll
# The old host source relied on standard headers including each other.
g++ -std=c++17 -O0 -Wno-deprecated-declarations -include limits -include cstdint -include cstring \
  -I. -I"$TOOLS_HIDL" -I"$TOOLS_HIDL/include_hash" -I"$TOOLS_HIDL/include_hash/hidl-hash" \
  -I"$TOOLS_HIDL/utils/include" -I"$TOOLS_HIDL/utils/include/hidl-util" \
  -I"$CORE/base/include" -I"$CORE/libutils/include" -I"$CORE/libcutils/include" \
  "$TOOLS_HIDL"/*.cpp "$TOOLS_HIDL"/utils/*.cpp hidl-gen_y.cpp hidl-gen_l.cpp \
  "$CORE/base/logging.cpp" "$CORE/base/strings.cpp" "$CORE/base/stringprintf.cpp" \
  "$CORE/base/file.cpp" "$CORE/base/errors_unix.cpp" -lcrypto -lpthread -o hidl-gen
mkdir -p "$OUTPUT_PATH"
for package in android.hidl.base@1.0 android.hidl.manager@1.0; do
  ./hidl-gen -Lc++-headers -o "$OUTPUT_PATH/" -randroid.hidl:"$LIBHIDL/transport" "$package"
done
test -f "$OUTPUT_PATH/android/hidl/manager/1.0/IServiceManager.h"
printf 'Generated public Android9 query headers only: %s\n' "$OUTPUT_PATH"
