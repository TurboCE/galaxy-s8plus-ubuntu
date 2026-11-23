#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
set -eu

read_state() {
    value=unavailable
    if [ -r "$1" ]; then
        IFS= read -r value < "$1" 2>/dev/null || value=unavailable
    fi
    printf '%s' "$value"
}

gnome_state() {
    if pgrep -u ubuntu -x gnome-shell >/dev/null 2>&1; then
        printf 'running'
    else
        printf 'absent'
    fi
}

exec 3>/dev/pmsg0
printf 'G955N TRANSPORT BEGIN kernel=%s\n' "$(uname -r)" >&3

# Stay within the verified 16 KiB pmsg region, including the loader markers.
sample=0
while [ "$sample" -lt 60 ]; do
    read -r uptime _ < /proc/uptime
    # Write the scheduler heartbeat first so that a blocked driver read can
    # be distinguished from a failure to schedule the observer.
    printf 'G955N TRANSPORT HEARTBEAT uptime=%s\n' "$uptime" >&3
    printf 'G955N TRANSPORT STATE udc=%s usb=%s wifi=%s gnome=%s\n' \
        "$(read_state /sys/class/udc/10c00000.usb/state)" \
        "$(read_state /sys/class/net/usb0/carrier)" \
        "$(read_state /sys/class/net/wlp1s0/operstate)" \
        "$(gnome_state)" >&3
    sample=$((sample + 1))
    sleep 5
done
