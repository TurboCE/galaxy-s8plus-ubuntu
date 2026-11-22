#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
set -eu

built_for=46.0-1ubuntu1.24.04.1
candidate=/opt/g955n-ambient-brightness/gsd-power
version=$(dpkg-query -W -f='${Version}' gnome-settings-daemon 2>/dev/null) || version=
if [ "$version" = "$built_for" ] && [ -x "$candidate" ]; then
    exec "$candidate" "$@"
fi
exec /usr/libexec/gsd-power "$@"
