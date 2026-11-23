#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ] ||
    [ "$(tr -d '\000' < /proc/device-tree/model)" != 'Samsung Galaxy S8+ (SM-G955N)' ]; then
    echo 'Run as root on the SM-G955N' >&2
    exit 1
fi

source_dir=/system/etc/wifi
firmware_dir=/usr/lib/firmware/brcm
prefix=brcmfmac4361b0-pcie

set -- bcmdhd_sta.bin_b0 bin nvram.txt_r02j_b0 txt bcmdhd_clm.blob clm_blob
while [ "$#" -gt 0 ]; do
    source_file=$source_dir/$1
    destination=$firmware_dir/$prefix.$2
    if [ ! -s "$source_file" ]; then
        echo "Missing or empty Samsung firmware file: $source_file" >&2
        exit 1
    fi
    if [ -s "$destination" ] && ! cmp -s "$source_file" "$destination"; then
        echo "Existing firmware differs: $destination" >&2
        exit 1
    fi
    shift 2
done

install -d -m 0755 "$firmware_dir"
staging=$(mktemp -d "$firmware_dir/.g955n-wlan.XXXXXXXX")
trap 'rm -rf -- "$staging"' EXIT
trap 'exit 1' HUP INT TERM

set -- bcmdhd_sta.bin_b0 bin nvram.txt_r02j_b0 txt bcmdhd_clm.blob clm_blob
while [ "$#" -gt 0 ]; do
    source_file=$source_dir/$1
    filename=$prefix.$2
    if ! cmp -s "$source_file" "$firmware_dir/$filename"; then
        install -m 0644 "$source_file" "$staging/$filename"
        cmp -s "$source_file" "$staging/$filename"
        mv -fT -- "$staging/$filename" "$firmware_dir/$filename"
    fi
    shift 2
done
