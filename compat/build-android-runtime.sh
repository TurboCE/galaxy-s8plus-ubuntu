#!/usr/bin/env bash
# Build only. Does not run the resulting program, mount filesystems or start a daemon.
set -euo pipefail
SOURCE_DIR=$(cd "$(dirname "$0")" && pwd)
LIBC_INPUT=${1:?Usage: build-android-runtime.sh OWN_ANDROID9_LIBC OUTPUT}
OUTPUT_PATH=$(realpath -m "${2:?Specify a private staging output}")
COMPILER=${CC:-gcc}
case "$("$COMPILER" -dumpmachine)" in aarch64*-linux-gnu*) ;; *) echo 'Requires an AArch64 Linux-targeting GCC' >&2; exit 2 ;; esac
case "$OUTPUT_PATH" in /dev/*|/proc/*|/sys/*|/efs/*|/system/*|/vendor/*|/usr/*|/bin/*|/sbin/*|/etc/*|/boot/*) echo 'Use private staging output' >&2; exit 2 ;; esac
if [ -e "$OUTPUT_PATH" ] && [ ! -f "$OUTPUT_PATH" ]; then echo 'Output must be a regular file' >&2; exit 2; fi
test -r "$LIBC_INPUT"
readelf -h "$LIBC_INPUT" | grep -q 'Machine:.*AArch64'
OBJ_DIR=$(mktemp -d)
trap 'rm -rf "$OBJ_DIR"' EXIT
COMMON=(-std=gnu11 -Wall -Wextra -Werror -O2 -ffreestanding -fPIE)
"$COMPILER" "${COMMON[@]}" -fno-stack-protector -c "$SOURCE_DIR/android-cli-start.c" -o "$OBJ_DIR/start.o"
"$COMPILER" "${COMMON[@]}" -fstack-protector-strong -c "$SOURCE_DIR/android-property-runtime.c" -o "$OBJ_DIR/runtime.o"
"$COMPILER" "${COMMON[@]}" -fstack-protector-strong -c "$SOURCE_DIR/android-property-server.c" -o "$OBJ_DIR/server.o"
"$COMPILER" -nostdlib -pie -Wl,-e,_start,--dynamic-linker=/system/bin/linker64,-z,relro,-z,now,-z,noexecstack,--allow-shlib-undefined \
  "$OBJ_DIR/start.o" "$OBJ_DIR/runtime.o" "$OBJ_DIR/server.o" "$LIBC_INPUT" -o "$OUTPUT_PATH"
readelf -l "$OUTPUT_PATH" | grep 'Requesting program interpreter'
readelf -d "$OUTPUT_PATH" | grep NEEDED
printf 'Built Android/Bionic helper only: %s\n' "$OUTPUT_PATH"
