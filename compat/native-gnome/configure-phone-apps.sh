#!/bin/sh
set -eu

# Apply to the owner of the active Ubuntu desktop, never to GDM.
if [ "$(id -u)" -eq 0 ] || [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]; then
    echo 'Run as the logged-in Ubuntu desktop user.' >&2
    exit 1
fi
case "$(tr -d '\000' < /proc/device-tree/model)" in
    *SM-G955N*) ;;
    *) echo 'This configuration targets the SM-G955N.' >&2; exit 1 ;;
esac

font='DejaVu Sans Mono'
if [ "$(fc-match -f '%{family}' "$font")" != "$font" ]; then
    echo 'The DejaVu Sans Mono font must be installed.' >&2
    exit 1
fi
profile_id=$(gsettings get org.gnome.Terminal.ProfilesList default | tr -d "'")
if ! printf '%s\n' "$profile_id" | grep -Eq '^[a-f0-9-]{36}$'; then
    echo 'The default Terminal profile could not be determined.' >&2
    exit 1
fi
profile="org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/legacy/profiles:/:${profile_id}/"

# GTK 4.14's legacy GL renderer keeps Panfrost acceleration and avoids
# the text and opacity corruption observed with this handset's NGL path.
directory="${XDG_CONFIG_HOME:-$HOME/.config}/environment.d"
renderer="$directory/59-g955n-gtk4.conf"
marker='# SM-G955N GTK4 renderer'
if [ -L "$renderer" ] || { [ -e "$renderer" ] &&
        ! grep -Fxq "$marker" "$renderer"; }; then
    echo 'The renderer configuration path is already in use.' >&2
    exit 1
fi

mkdir -p "$directory"
staged=$(mktemp "$directory/.g955n-gtk4.XXXXXX")
trap 'rm -f "$staged"' EXIT
printf '%s\n' "$marker" 'GSK_RENDERER=gl' > "$staged"
chmod 0644 "$staged"
mv -f "$staged" "$renderer"
export GSK_RENDERER=gl
dbus-update-activation-environment --systemd GSK_RENDERER

# Retire the temporary System Monitor-only launcher if it was installed.
launcher="${XDG_DATA_HOME:-$HOME/.local/share}/applications/org.gnome.SystemMonitor.desktop"
if [ -f "$launcher" ] && [ ! -L "$launcher" ] &&
        grep -qx 'X-G955N-Cairo=true' "$launcher"; then
    rm "$launcher"
fi

gsettings set "$profile" font "$font 10"
gsettings set "$profile" default-size-columns 64
gsettings set "$profile" use-system-font false
