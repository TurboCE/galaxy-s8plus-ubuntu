#!/usr/bin/env bash
# Build-only from the pinned public Android9 schemas; no device or downloads.
set -euo pipefail
GENERATOR=${1:?Usage: generate-headless-buffer-headers.sh HOST_HIDL_GEN LIBHIDL HARDWARE_INTERFACES OUTPUT}
LIBHIDL=$(realpath "${2:?}"); HARDWARE=$(realpath "${3:?}")
OUTPUT_PATH=$(realpath -m "${4:?Private staging output}")
case "$OUTPUT_PATH" in /dev/*|/proc/*|/sys/*|/efs/*|/system/*|/vendor/*|/usr/*|/bin/*|/sbin/*|/etc/*|/boot/*) exit 2 ;; esac
if [ -e "$OUTPUT_PATH" ]; then echo 'Use a new output directory' >&2; exit 2; fi
mkdir -p "$OUTPUT_PATH"
for package in android.hidl.base@1.0 android.hidl.manager@1.0 android.hardware.graphics.common@1.0 android.hardware.graphics.mapper@2.0 android.hardware.graphics.allocator@2.0; do
  "$GENERATOR" -Lc++-headers -o "$OUTPUT_PATH/" -randroid.hidl:"$LIBHIDL/transport" -randroid.hardware:"$HARDWARE" "$package"
done
