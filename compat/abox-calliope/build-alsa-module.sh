#!/bin/sh
set -eu

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 KERNEL_SOURCE KERNEL_BUILD OUTPUT_DIRECTORY" >&2
    exit 2
fi

source=$(cd "$1" && pwd)
build=$(cd "$2" && pwd)
mkdir -p "$3"
output=$(cd "$3" && pwd)
here=$(cd "$(dirname "$0")" && pwd)
patch="$here/../../patches/proposals/0128-mainline-sm-g955n-alsa-calliope.patch"

test "$output" != "$source"
test "$output" != "$build"
test -s "$build/Module.symvers"

native="$source/sound/soc/samsung/g955n-abox-speaker.c"
patch --batch --forward --silent --fuzz=0 -i "$patch" -o "$output/g955n-abox-speaker-native.c" "$native"
cp "$here/Makefile.alsa" "$output/Makefile"
cp "$here/calliope.h" "$here/g955n-calliope-stage.c" "$here/g955n-calliope-boot.c" "$output/"
make -C "$source" O="$build" M="$output" modules
