#!/bin/sh
set -eu

if [ "$#" -ne 1 ] || [ "$(id -u)" -ne 0 ] ||
    [ "$(tr -d '\000' < /proc/device-tree/model)" != 'Samsung Galaxy S8+ (SM-G955N)' ]; then
    echo 'Run as root on the SM-G955N with its read-only SYSTEM mountpoint' >&2
    exit 1
fi

stock=$1
source_dev=$(findmnt -n -M "$stock" -o SOURCE)
options=$(findmnt -n -M "$stock" -o OPTIONS)
if [ "$(readlink -f "$source_dev")" != "$(readlink -f /dev/disk/by-partlabel/SYSTEM)" ]; then
    echo 'The source must be the handset SYSTEM partition' >&2
    exit 1
fi
case ",$options," in
    *,ro,*) ;;
    *) echo 'The handset SYSTEM mount must be read-only' >&2; exit 1 ;;
esac

source_dir=$stock/vendor/firmware
firmware_dir=/usr/lib/firmware
set -- calliope_sram.bin calliope_dram.bin calliope_iva.bin
for filename do
    source_file=$source_dir/$filename
    destination=$firmware_dir/$filename
    if [ ! -f "$source_file" ] || [ ! -s "$source_file" ] || [ -L "$source_file" ]; then
        echo "Invalid Samsung firmware file: $filename" >&2
        exit 1
    fi
    if [ -L "$destination" ] ||
        { [ -e "$destination" ] && ! cmp -s "$source_file" "$destination"; }; then
        echo "Existing firmware differs: $filename" >&2
        exit 1
    fi
done

staging=$(mktemp -d "$firmware_dir/.g955n-audio.XXXXXXXX")
trap 'rm -rf -- "$staging"' EXIT
trap 'exit 1' HUP INT TERM
for filename do
    install -m 0644 "$source_dir/$filename" "$staging/$filename"
    cmp -s "$source_dir/$filename" "$staging/$filename"
done
for filename do
    destination=$firmware_dir/$filename
    mv -nT -- "$staging/$filename" "$destination"
    cmp -s "$source_dir/$filename" "$destination"
    echo "Verified $filename"
done
