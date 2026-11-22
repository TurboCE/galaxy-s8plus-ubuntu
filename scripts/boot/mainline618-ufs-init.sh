#!/bin/busybox sh
# SPDX-License-Identifier: GPL-2.0-only
# SM-G955N Linux 6.18 embedded UFS bootstrap.
set -u
BB=/bin/busybox
export PATH=/bin:/sbin:/usr/bin:/usr/sbin

log() {
    printf '%s\n' "$*"
    printf '<6>g955n-ufs: %s\n' "$*" > /dev/kmsg
}

stop() {
    log "$*"
    if [ -r /proc/cmdline ] && [ -x /sbin/reboot-recovery ]; then
        case " $("$BB" cat /proc/cmdline) " in
            *" g955n.ufs_return=1 "*)
                log 'Returning to recovery'
                "$BB" sleep 3
                /sbin/reboot-recovery
                log 'Recovery restart unavailable'
                ;;
        esac
    fi
    while :; do "$BB" sleep 3600; done
}

partdev() {
    local entry path name found=''
    for entry in /sys/class/block/*/uevent; do
        path=$("$BB" readlink -f "$entry") || continue
        case "$path" in */11120000.ufs/*) ;; *) continue ;; esac
        "$BB" grep -qx "PARTNAME=$1" "$entry" || continue
        name=$("$BB" sed -n 's/^DEVNAME=//p' "$entry")
        [ -n "$name" ] && [ -b "/dev/$name" ] || continue
        [ -z "$found" ] || return 1
        found="/dev/$name"
    done
    [ -n "$found" ] || return 1
    printf '%s\n' "$found"
}

"$BB" mount -t devtmpfs devtmpfs /dev || stop 'Missing devtmpfs'
"$BB" mount -t proc proc /proc || stop 'Missing procfs'
"$BB" mount -t sysfs sysfs /sys || stop 'Missing sysfs'
"$BB" mount -t tmpfs tmpfs /run || stop 'Missing /run'
[ "$("$BB" tr -d '\000' < /proc/device-tree/model)" = 'Samsung Galaxy S8+ (SM-G955N)' ] ||
    stop 'Unexpected board model'
log 'SM-G955N UFS INIT'

rootdev=''
attempt=0
while [ "$attempt" -lt 30 ]; do
    rootdev=$(partdev USERDATA) && break
    attempt=$((attempt + 1))
    "$BB" sleep 1
done
[ -n "$rootdev" ] || stop 'UFS USERDATA unavailable'
log 'UFS USERDATA found'
blk=$("$BB" basename "$rootdev")
sectors=$("$BB" cat "/sys/class/block/$blk/size")
[ "$sectors" -gt 0 ] || stop 'Invalid USERDATA capacity'
log "USERDATA capacity: $sectors sectors"
"$BB" mount -t ext4 -o ro,noload "$rootdev" /newroot ||
    stop 'Read-only ext4 mount failed'
[ "$("$BB" cat /newroot/etc/hostname)" = g955n-ubuntu ] ||
    stop 'Unexpected root filesystem'
[ -x /newroot/sbin/init ] || stop 'Ubuntu init missing'
log 'SM-G955N UFS UBUNTU ROOT OK (read-only)'

case " $("$BB" cat /proc/cmdline) " in
    *" g955n.ufs_boot=1 "*) ;;
    *) stop 'Read-only check complete' ;;
esac

# Mount the verified Ubuntu filesystem afresh so ext4 can replay its journal.
efsdev=$(partdev EFS) || stop 'UFS EFS unavailable'
"$BB" umount /newroot || stop 'Cannot unmount read-only root'
"$BB" mount -t ext4 -o rw,noatime "$rootdev" /newroot ||
    stop 'Ubuntu root mount failed'
for dir in dev proc sys run efs; do
    [ -d "/newroot/$dir" ] || stop "Missing Ubuntu mountpoint $dir"
done
"$BB" mount -t ext4 -o ro,noload "$efsdev" /newroot/efs ||
    stop 'Read-only EFS mount failed'
log 'Handing PID 1 to Ubuntu systemd'
for dir in proc sys run dev; do
    "$BB" mount --move "/$dir" "/newroot/$dir" ||
        stop "Cannot move $dir to Ubuntu root"
done
exec "$BB" switch_root /newroot /sbin/init
