#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Build a private diagnostic against AOSP Android 9 headers and own-device libc.
set -euo pipefail
if [ "$#" -ne 4 ]; then
    printf 'Usage: %s AOSP_TREE ANDROID_HEADERS OWN_LIBS OUTPUT_FILE\n' "$0" >&2
    exit 2
fi
scripts=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aosp=$(realpath "$1")
headers=$(realpath "$2")
libs=$(realpath "$3")
output=$(realpath -m "$4")
test -f "$headers/hardware/gps.h"
for library in libc.so libdl.so; do
    readelf -h "$libs/$library" | grep -q 'Machine:.*AArch64'
done
if [ -e "$output" ]; then
    printf 'Choose a new private output file.\n' >&2
    exit 2
fi
objects=$(mktemp -d)
trap 'rm -rf "$objects"' EXIT
bionic=$aosp/bionic
common=(--target=aarch64-linux-android28 -O2 -fPIE -fstack-protector-strong -nostdlibinc
    -isystem "$bionic/libc/include" -isystem "$bionic/libc/kernel/uapi"
    -isystem "$bionic/libc/kernel/uapi/asm-arm64" -isystem "$bionic/libc/kernel/android/uapi"
    -isystem "$headers" -isystem "$aosp/system/core/libcutils/include"
    -isystem "$aosp/system/core/include")
clang "${common[@]}" -fno-stack-protector -c "$scripts/../android-cli-start.c" -o "$objects/start.o"
clang "${common[@]}" -std=c11 -Wall -Wextra -Werror -c "$scripts/hal-probe.c" -o "$objects/probe.o"
clang --target=aarch64-linux-android28 -fuse-ld=lld -nostdlib -pie \
    -Wl,-e,_start,--dynamic-linker=/system/bin/linker64,-z,relro,-z,now,-z,noexecstack \
    "$objects/start.o" "$objects/probe.o" "$libs/libc.so" "$libs/libdl.so" -o "$output"
readelf -d "$output"
