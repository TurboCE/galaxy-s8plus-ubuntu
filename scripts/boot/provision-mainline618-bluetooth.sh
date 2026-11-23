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

firmware_dir=/usr/lib/firmware/brcm
nvram=$firmware_dir/brcmfmac4361b0-pcie.txt
source_file=$stock/vendor/firmware/bcm4361B0_semco.hcd
filename=BCM.samsung,dream2lteks.hcd
destination=$firmware_dir/$filename

# The r02j NVRAM identifies the qualified Semco E32 board variant.
printf '%s  %s\n' 56c7c64290132add7720ce98a0e0ee55a73452c6f41fba5c23d3eea3b2cc5a49 "$nvram" |
    sha256sum -c --status
printf '%s  %s\n' 343fb252959cf643dde61e16967aaeea82012301b5033262cb3547a8736d5a92 "$source_file" |
    sha256sum -c --status

if [ -L "$destination" ] ||
    { [ -e "$destination" ] && ! cmp -s "$source_file" "$destination"; }; then
    echo 'Existing Bluetooth firmware differs' >&2
    exit 1
fi

staging=$(mktemp -d "$firmware_dir/.g955n-bluetooth.XXXXXXXX")
trap 'rm -rf -- "$staging"' EXIT
trap 'exit 1' HUP INT TERM
install -m 0644 "$source_file" "$staging/$filename"
cmp -s "$source_file" "$staging/$filename"
mv -nT -- "$staging/$filename" "$destination"
cmp -s "$source_file" "$destination"
echo "Verified $filename"
