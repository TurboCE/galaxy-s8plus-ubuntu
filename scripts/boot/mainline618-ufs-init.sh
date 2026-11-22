#!/bin/busybox sh
# SPDX-License-Identifier: GPL-2.0-only
# SM-G955N Linux 6.18 embedded UFS bootstrap.
set -u
BB=/bin/busybox
export PATH=/bin:/sbin:/usr/bin:/usr/sbin
diag_pid=''

log() {
    printf '%s\n' "$*"
    printf '<6>g955n-ufs: %s\n' "$*" > /dev/kmsg
}

stop() {
    log "$*"
    if [ -r /proc/cmdline ] && [ -x /sbin/reboot-recovery ]; then
        case " $("$BB" cat /proc/cmdline) " in
            *" g955n.ufs_return=1 "*)
                if [ -n "$diag_pid" ]; then
                    log 'USB diagnostic window open for 40 seconds'
                    "$BB" sleep 40
                    usb_gadget_state | while IFS= read -r line; do log "USB: $line"; done
                fi
                log 'Returning to recovery'
                "$BB" sync
                /sbin/reboot-recovery
                log 'Recovery restart unavailable'
                ;;
        esac
    fi
    while :; do "$BB" sleep 3600; done
}

usb_diagnostics() {
    local cmd

    while [ ! -c /dev/ttyGS0 ]; do "$BB" sleep 1; done
    exec </dev/ttyGS0 >/dev/ttyGS0 2>&1
    while IFS= read -r cmd; do
        case "$cmd" in
            status)
                printf 'SM-G955N USB DIAG %s\n' "$("$BB" uname -r)"
                ;;
            log)
                printf 'SM-G955N LOG BEGIN\n'
                "$BB" dmesg
                printf 'SM-G955N LOG END\n'
                ;;
            recovery)
                printf 'SM-G955N RECOVERY REQUESTED\n'
                "$BB" sync
                /sbin/reboot-recovery
                ;;
        esac
    done
}

usb_gadget_state() {
    local state_file
    for state_file in /sys/class/udc/*/state; do
        [ -r "$state_file" ] || continue
        printf 'gadget state: %s\n' "$("$BB" cat "$state_file")"
    done
    "$BB" grep -E 'dwc3|10c00000\.usb' /proc/interrupts || true
}

start_usb_gadget() {
    local udc='10c00000.usb' gadget='/sys/kernel/config/usb_gadget/g955n618'
    local attempt=0

    while [ ! -d "/sys/class/udc/$udc" ] && [ "$attempt" -lt 5 ]; do
        "$BB" sleep 1
        attempt=$((attempt + 1))
    done
    [ -d "/sys/class/udc/$udc" ] || return 1

    "$BB" mount -t configfs configfs /sys/kernel/config || return 1
    "$BB" mkdir "$gadget" || return 1
    printf '0x0525\n' > "$gadget/idVendor" &&
        printf '0xa4a7\n' > "$gadget/idProduct" &&
        "$BB" mkdir -p "$gadget/strings/0x409" "$gadget/configs/c.1" &&
        printf 'G955N618\n' > "$gadget/strings/0x409/serialnumber" &&
        printf 'SM-G955N Ubuntu diagnostic\n' > "$gadget/strings/0x409/product" &&
        "$BB" mkdir "$gadget/functions/acm.g955n" &&
        "$BB" ln -s "$gadget/functions/acm.g955n" "$gadget/configs/c.1/" &&
        printf '%s\n' "$udc" > "$gadget/UDC"
}

prepare_ubuntu_trial_return() {
    "$BB" mkdir -p /run/systemd/system/timers.target.wants /run/g955n-trial || return 1
    "$BB" cat > /run/g955n-trial/check <<'EOF' || return 1
#!/bin/sh
state=$(systemctl is-system-running 2>/dev/null)
target=$(systemctl is-active multi-user.target 2>/dev/null)
root=$(findmnt -n -o SOURCE,OPTIONS /)
read -r uptime _ < /proc/uptime
if [ "$target" != active ] && [ "${uptime%%.*}" -lt 300 ]; then
    exit 0
fi
printf 'SM-G955N UBUNTU SYSTEMD state=%s multi-user=%s root=%s\n' "$state" "$target" "$root"
if [ -s /run/g955n-trial/usb-start.log ]; then
    cat /run/g955n-trial/usb-start.log
fi
if [ "$target" != active ]; then
    systemctl list-jobs --no-pager
else
    case " $(cat /proc/cmdline) " in
        *" g955n.netns_diag=1 "*)
            if timeout 20 systemd-run --quiet --wait --pipe --collect -p PrivateNetwork=yes \
                /bin/sh -c 'test "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" && ip link show dev lo >/dev/null'; then
                printf 'SM-G955N UBUNTU PRIVATE NETWORK OK\n'
            else
                printf 'SM-G955N UBUNTU PRIVATE NETWORK FAILED\n'
            fi
            ;;
    esac
fi

case " $(cat /proc/cmdline) " in
    *" g955n.hardware_diag=1 "*)
        for dev in /sys/bus/i2c/drivers/stmfts/*-0049; do
            [ -L "$dev" ] || continue
            printf 'SM-G955N TOUCH STMFTS chip=%s\n' "$(cat "$dev/chip_id")"
        done
        for input in /sys/class/input/event*; do
            [ -r "$input/device/name" ] || continue
            printf 'SM-G955N INPUT %s %s\n' "${input##*/}" "$(cat "$input/device/name")"
        done
        for dev in /sys/class/drm/card[0-9] /sys/class/drm/renderD*; do
            [ -L "$dev/device/driver" ] || continue
            driver=$(readlink "$dev/device/driver")
            printf 'SM-G955N DRM %s %s\n' "${dev##*/}" "${driver##*/}"
        done
        for dev in /sys/class/ieee80211/phy*; do
            [ -d "$dev" ] && printf 'SM-G955N WLAN %s\n' "${dev##*/}"
        done
        if [ -r /proc/asound/cards ]; then
            printf 'SM-G955N ALSA cards\n'
            cat /proc/asound/cards
        fi
        if [ -r /sys/power/state ]; then
            printf 'SM-G955N SLEEP %s\n' "$(cat /sys/power/state)"
        fi
        ;;
esac
exec systemctl reboot --reboot-argument=recovery
EOF
    "$BB" cat > /run/systemd/system/g955n-trial-return.service <<'EOF' || return 1
[Unit]
Description=Record SM-G955N Ubuntu trial and return to recovery

[Service]
Type=oneshot
ExecStart=/bin/sh /run/g955n-trial/check
StandardOutput=kmsg
StandardError=kmsg
EOF
    "$BB" cat > /run/systemd/system/g955n-trial-return.timer <<'EOF' || return 1
[Unit]
Description=Allow Ubuntu to reach multi-user before recovery

[Timer]
OnActiveSec=10s
OnUnitInactiveSec=10s
AccuracySec=1s
EOF
    "$BB" ln -s ../g955n-trial-return.timer /run/systemd/system/timers.target.wants/ || return 1

    case " $("$BB" cat /proc/cmdline) " in
        *" g955n.usb_login=1 "*)
            if [ -c /dev/ttyGS0 ] && [ -f /newroot/usr/lib/systemd/system/serial-getty@.service ]; then
                "$BB" mkdir -p /run/systemd/system/getty.target.wants || return 1
                "$BB" ln -s /usr/lib/systemd/system/serial-getty@.service \
                    /run/systemd/system/getty.target.wants/serial-getty@ttyGS0.service || return 1
            else
                log 'USB serial login unavailable'
            fi
            ;;
    esac
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
case " $("$BB" cat /proc/cmdline) " in
    *" g955n.usb_diag=1 "*)
        if start_usb_gadget; then
            log 'USB ACM gadget bound'
            usb_diagnostics &
            diag_pid=$!
        else
            log 'USB ACM gadget bind failed'
        fi
        "$BB" mkdir -p /run/g955n-trial
        {
            "$BB" dmesg | "$BB" grep -E 'dwc3|configfs|10e00000|ttyGS0' | "$BB" tail -n 12
            usb_gadget_state
        } > /run/g955n-trial/usb-start.log
        while IFS= read -r line; do log "USB: $line"; done < /run/g955n-trial/usb-start.log
        ;;
esac

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
if [ -n "$diag_pid" ]; then
    "$BB" sleep 12
    kill "$diag_pid" 2>/dev/null || true
fi

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
case " $("$BB" cat /proc/cmdline) " in
    *" g955n.ubuntu_return=1 "*) prepare_ubuntu_trial_return || stop 'Cannot stage Ubuntu return timer' ;;
esac
log 'Handing PID 1 to Ubuntu systemd'
for dir in proc sys run dev; do
    "$BB" mount --move "/$dir" "/newroot/$dir" ||
        stop "Cannot move $dir to Ubuntu root"
done
exec "$BB" switch_root /newroot /sbin/init
