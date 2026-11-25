#!/bin/sh
set -eu

if [ "$#" -lt 3 ] || [ "$#" -gt 4 ] ||
   { [ "$#" -eq 4 ] && [ "$4" != "--receiver" ]; }; then
    echo "Usage: $0 KERNEL_SOURCE KERNEL_BUILD OUTPUT_DIRECTORY [--receiver]" >&2
    exit 2
fi

source=$(cd "$1" && pwd)
build=$(cd "$2" && pwd)
mkdir -p "$3"
output=$(cd "$3" && pwd)
here=$(cd "$(dirname "$0")" && pwd)
patches="$here/../../patches/proposals"

test "$output" != "$source"
test "$output" != "$build"
test -s "$build/Module.symvers"

native="$source/sound/soc/samsung/g955n-abox-speaker.c"
module_source="$output/g955n-abox-speaker-native.c"
cp "$here/Makefile.alsa" "$output/Makefile"
if [ "${4:-}" = "--receiver" ]; then
    patch --batch --forward --silent --fuzz=0 \
        -i "$patches/0131-mainline-sm-g955n-receiver-pcm.patch" -o "$module_source" "$native"
    patch --batch --forward --silent --fuzz=0 \
        -i "$patches/0133-mainline-sm-g955n-calliope-with-receiver.patch" "$module_source"
    patch --batch --forward --silent --fuzz=0 \
        -i "$patches/0135-mainline-sm-g955n-kernel58-speaker-geometry.patch" "$module_source"
    patch --batch --forward --silent --fuzz=0 \
        -i "$patches/0144-mainline-sm-g955n-wired-jack-detect.patch" "$module_source"
    cp "$here/g955n-wired-jack.c" "$here/g955n-wired-jack.h" "$output/"
    printf '%s\n' 'g955n-abox-speaker-y += g955n-wired-jack.o' >> "$output/Makefile"
else
    patch --batch --forward --silent --fuzz=0 \
        -i "$patches/0128-mainline-sm-g955n-alsa-calliope.patch" -o "$module_source" "$native"
fi
cp "$here/calliope.h" "$here/g955n-calliope-stage.c" "$here/g955n-calliope-boot.c" "$output/"
make -C "$source" O="$build" M="$output" modules
