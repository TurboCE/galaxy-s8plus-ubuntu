#!/bin/busybox sh
# SPDX-License-Identifier: GPL-2.0-only
# SM-G955N Linux 6.18 embedded UFS bootstrap.
set -u
BB=/bin/busybox
export PATH=/bin:/sbin:/usr/bin:/usr/sbin
diag_pid=''
usb_handoff_done=''

log() {
    printf '%s\n' "$*"
    printf '<6>g955n-ufs: %s\n' "$*" > /dev/kmsg
}

boot_timing() {
    local uptime

    read -r uptime _ < /proc/uptime
    log "SM-G955N BOOT TIME $1 $uptime seconds"
}

log_g3d_snapshot() {
    local snapshot="/proc/device-tree/chosen/samsung,g955n-g3d-$1-snapshot"
    local value

    [ -r "$snapshot" ] || return 0
    value=$("$BB" od -An -v -tx1 "$snapshot" | "$BB" tr -d ' \n')
    case "$value" in
        *[!f]*)
            log "G3D $1: $2 (BE32) $value"
            ;;
        *)
            log "G3D $1: loader snapshot unavailable"
            ;;
    esac
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
            continue)
                if [ -e /run/g955n-usb-handoff.wait ]; then
                    "$BB" mv /run/g955n-usb-handoff.wait /run/g955n-usb-handoff.ready
                fi
                ;;
            recovery)
                printf 'SM-G955N RECOVERY REQUESTED\n'
                "$BB" sync
                /sbin/reboot-recovery
                ;;
        esac
    done
}

wait_for_usb_handoff() {
    local attempt=0
    local result=0

    case " $("$BB" cat /proc/cmdline) " in
        *" g955n.usb_handoff=1 "*)
            while [ ! -e /run/g955n-usb-handoff.ready ] && [ "$attempt" -lt 120 ]; do
                "$BB" sleep 0.1
                attempt=$((attempt + 1))
            done
            [ -e /run/g955n-usb-handoff.ready ] || result=1
            ;;
        *)
            "$BB" sleep 12
            ;;
    esac
    "$BB" rm -f /run/g955n-usb-handoff.wait /run/g955n-usb-handoff.ready
    return "$result"
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
        "$BB" ln -s "$gadget/functions/acm.g955n" "$gadget/configs/c.1/" || return 1

    case " $("$BB" cat /proc/cmdline) " in
        *" g955n.usb_ether=1 "*)
            if "$BB" mkdir "$gadget/functions/ecm.g955n" &&
                printf '%s\n' 02:55:00:00:00:02 > "$gadget/functions/ecm.g955n/dev_addr" &&
                printf '%s\n' 02:55:00:00:00:01 > "$gadget/functions/ecm.g955n/host_addr" &&
                "$BB" ln -s "$gadget/functions/ecm.g955n" "$gadget/configs/c.1/"; then
                if printf '%s\n' "$udc" > "$gadget/UDC"; then
                    log 'USB ACM and CDC Ethernet bound'
                    return 0
                fi
                "$BB" rm "$gadget/configs/c.1/ecm.g955n" || return 1
            fi
            if [ -d "$gadget/functions/ecm.g955n" ]; then
                "$BB" rmdir "$gadget/functions/ecm.g955n" || return 1
            fi
            log 'USB CDC Ethernet unavailable, trying ACM'
            ;;
    esac
    printf '%s\n' "$udc" > "$gadget/UDC"
}

prepare_ubuntu_services() {
    "$BB" mkdir -p /run/g955n-trial || return 1
    if [ -r /bin/g955n-pcie-wlan.ko ]; then
        "$BB" cp /bin/g955n-pcie-wlan.ko /run/g955n-trial/pcie-wlan.ko || return 1
    fi
    if [ -x /bin/g955n-kernel-evidence ] && [ -r /bin/g955n-kernel-evidence.service ]; then
        "$BB" cp /bin/g955n-kernel-evidence /run/g955n-trial/kernel-evidence || return 1
        "$BB" mkdir -p /run/systemd/system/g955n-kernel-evidence.service.d || return 1
        {
            printf '[Service]\nExecStart=\nExecStart=/run/g955n-trial/kernel-evidence\n'
            "$BB" sed -n '/^Type=/p; /^RuntimeMaxSec=/p' /bin/g955n-kernel-evidence.service
        } > /run/systemd/system/g955n-kernel-evidence.service.d/50-g955n-trial.conf || return 1
    fi
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

# Keep the framebuffer session scoped to GDM on the 6.18 boot.
prepare_ubuntu_desktop() {
    local desktop=/run/g955n-mainline-desktop
    local units=/run/systemd/system/gdm.service.d

    [ -c /dev/fb0 ] || {
        log 'Ubuntu desktop fallback unavailable: no framebuffer device'
        return 1
    }
    "$BB" mkdir -p "$desktop" "$units" || return 1
    "$BB" cat > "$desktop/gdm.conf" <<'EOF' || return 1
[daemon]
WaylandEnable=false
AutomaticLoginEnable=false
DefaultSession=ubuntu-xorg.desktop
EOF
    "$BB" cat > "$desktop/xorg.conf" <<'EOF' || return 1
Section "Device"
    Identifier "SM-G955N framebuffer"
    Driver "fbdev"
    Option "fbdev" "/dev/fb0"
    Option "ShadowFB" "true"
EndSection
Section "Screen"
    Identifier "SM-G955N screen"
    Device "SM-G955N framebuffer"
EndSection
EOF
    "$BB" cat > "$units/50-g955n-mainline-desktop.conf" <<'EOF' || return 1
[Service]
BindReadOnlyPaths=/run/g955n-mainline-desktop/gdm.conf:/etc/gdm3/custom.conf
BindReadOnlyPaths=/run/g955n-mainline-desktop/xorg.conf:/etc/X11/xorg.conf.d/10-g955n-fbdev.conf
BindReadOnlyPaths=-/usr/share/xsessions/ubuntu-xorg.desktop:/usr/share/xsessions/ubuntu-g955n.desktop
EOF
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
}

start_ufs_hs_module() {
    [ -r /bin/ufs-exynos.ko ] || stop 'UFS HS module unavailable'
    (
        log 'Starting UFS HS module'
        if ! "$BB" insmod /bin/ufs-exynos.ko exynos8895_hs_trial=1; then
            log 'UFS HS module load failed'
        fi
    ) &
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

probe_panfrost_render() (
    local node driver render='' mounts='' dir output result

    for node in /sys/class/drm/renderD*; do
        driver=$("$BB" readlink "$node/device/driver") || continue
        [ "${driver##*/}" = panfrost ] || continue
        [ -c "/dev/dri/${node##*/}" ] || continue
        render="/dev/dri/${node##*/}"
        break
    done
    [ -n "$render" ] || { log 'Panfrost probe: no render node'; exit 1; }
    "$BB" cp /bin/g955n-panfrost-render /run/g955n-panfrost-render || exit 1
    trap 'for dir in $mounts; do "$BB" umount "/newroot/$dir"; done' EXIT
    for dir in dev proc sys run; do
        "$BB" mount --bind "/$dir" "/newroot/$dir" || exit 1
        mounts="$dir $mounts"
    done
    set -- /run/g955n-panfrost-render "$render"
    case " $("$BB" cat /proc/cmdline) " in
        *" g955n.panfrost_linear_dmabuf=1 "*) set -- "$@" --linear-dmabuf ;;
    esac
    if [ -x /bin/g955n-strace ]; then
        "$BB" cp /bin/g955n-strace /run/g955n-strace || exit 1
        set -- /run/g955n-strace --kill-on-exit -f -tt -T \
            -e trace=openat,mmap,ioctl,futex,poll,ppoll \
            -o /run/g955n-panfrost.strace "$@"
    fi
    result=0
    "$BB" timeout -s KILL 90 "$BB" chroot /newroot /usr/bin/env \
        MESA_SHADER_CACHE_DISABLE=true \
        __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json \
        "$@" > /run/g955n-panfrost-render.log 2>&1 || result=$?
    while IFS= read -r output; do log "$output"; done < /run/g955n-panfrost-render.log
    if [ "$result" -ne 0 ]; then
        log "Panfrost probe exit status $result"
        if [ -s /run/g955n-panfrost.strace ]; then
            "$BB" tail -n 16 /run/g955n-panfrost.strace |
                while IFS= read -r output; do log "Panfrost trace: $output"; done
        fi
    fi
    return "$result"
)

"$BB" mount -t devtmpfs devtmpfs /dev || stop 'Missing devtmpfs'
"$BB" mount -t proc proc /proc || stop 'Missing procfs'
"$BB" mount -t sysfs sysfs /sys || stop 'Missing sysfs'
"$BB" mount -t tmpfs tmpfs /run || stop 'Missing /run'
[ "$("$BB" tr -d '\000' < /proc/device-tree/model)" = 'Samsung Galaxy S8+ (SM-G955N)' ] ||
    stop 'Unexpected board model'
log 'SM-G955N UFS INIT'
boot_timing initramfs
log_g3d_snapshot power 'BUCK6_CTRL OUT1 OUT2 LDO9_CTRL PMU_STATUS'
log_g3d_snapshot clock 'REF_MUX SWITCH_MUX PLL_CTRL PLL_OPTIONS BUSD_MUX BUSP_DIV AGPU_GATE'
case " $("$BB" cat /proc/cmdline) " in
    *" g955n.usb_diag=1 "*|*" g955n.usb_login=1 "*)
        if start_usb_gadget; then
            log 'USB ACM gadget bound'
            case " $("$BB" cat /proc/cmdline) " in
                *" g955n.usb_diag=1 "*)
                    case " $("$BB" cat /proc/cmdline) " in
                        *" g955n.usb_handoff=1 "*) : > /run/g955n-usb-handoff.wait ;;
                    esac
                    usb_diagnostics &
                    diag_pid=$!
                    ;;
            esac
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

case " $("$BB" cat /proc/cmdline) " in
    *" g955n.ufs_module_hs_trial=1 "*)
        [ -n "$diag_pid" ] || stop 'UFS module trial requires USB diagnostics'
        [ -e /run/g955n-usb-handoff.wait ] || [ -e /run/g955n-usb-handoff.ready ] ||
            stop 'UFS module trial requires USB handoff'
        wait_for_usb_handoff || stop 'UFS module trial did not receive host acknowledgement'
        usb_handoff_done=1
        start_ufs_hs_module
        ;;
    *" g955n.ufs_hs_boot=1 "*)
        start_ufs_hs_module
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
boot_timing root-verified

case " $("$BB" cat /proc/cmdline) " in
    *" g955n.ufs_read_diag=1 "*)
        boot_timing ufs-read-start
        if "$BB" timeout -s KILL 35 "$BB" dd if="$rootdev" of=/dev/null \
            bs=1M count=8 iflag=direct 2>/dev/null; then
            boot_timing ufs-read-8MiB-complete
        else
            log 'UFS direct read diagnostic failed'
        fi
        ;;
esac

case " $("$BB" cat /proc/cmdline) " in
    *" g955n.panfrost_diag=1 "*) probe_panfrost_render || true ;;
esac

case " $("$BB" cat /proc/cmdline) " in
    *" g955n.ufs_boot=1 "*) ;;
    *) stop 'Read-only check complete' ;;
esac
if [ -n "$diag_pid" ]; then
    [ -n "$usb_handoff_done" ] || wait_for_usb_handoff || true
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
prepare_ubuntu_services || stop 'Cannot stage Ubuntu services'
case " $("$BB" cat /proc/cmdline) " in
    *" g955n.ubuntu_return=1 "*) prepare_ubuntu_trial_return || stop 'Cannot stage Ubuntu return timer' ;;
esac
case " $("$BB" cat /proc/cmdline) " in
    *" g955n.desktop=1 "*) prepare_ubuntu_desktop || log 'Cannot stage Ubuntu framebuffer desktop' ;;
esac
log 'Handing PID 1 to Ubuntu systemd'
boot_timing switch-root
for dir in proc sys run dev; do
    "$BB" mount --move "/$dir" "/newroot/$dir" ||
        stop "Cannot move $dir to Ubuntu root"
done
exec "$BB" switch_root /newroot /sbin/init
