#!/usr/bin/env bash
# Offline only; reuse the completed builder's private volume, never a phone.
set -euo pipefail
R=/work/rootfs
test -x "$R/sbin/init"
test "$(cat "$R/etc/hostname")" = g955n-ubuntu
profile=${G955N_ROOTFS_PROFILE:-legacy}
built_profile=legacy
if [ -f "$R/etc/g955n-rootfs-profile" ]; then
  built_profile=$(cat "$R/etc/g955n-rootfs-profile")
fi
test "$built_profile" = "$profile" || { echo 'Rootfs build and finalization profiles differ' >&2; exit 1; }
overlay_options=()
if [ "$profile" = mainline618 ]; then
  overlay_options+=(--exclude=./etc/systemd/user/wireplumber.service)
fi
tar -C /source/image/rootfs-overlay "${overlay_options[@]}" -cf - . | tar -C "$R" --keep-directory-symlink -xpf -
# Stage these only when the builder is supplied the matched local artifacts.
hardware_args=(--rootfs "$R")
if [ "$profile" = mainline618 ]; then
  hardware_args+=(--mainline618)
  if [ -d /adapters/modules ]; then
    hardware_args+=(--mainline-modules /adapters/modules/*)
  fi
else
  # On the Samsung 4.4 kernel the guarded SPA plugin scopes unsafe ABOX PCM probes.
  test "$(readlink "$R/etc/systemd/user/wireplumber.service")" = /dev/null
  install -D -m 755 /source/compat/pipewire/g955n-wireplumber "$R/usr/local/libexec/g955n-wireplumber"
  install -D -m 644 /source/compat/pipewire/10-g955n-validated-plugin.conf "$R/etc/systemd/user/wireplumber.service.d/10-g955n-validated-plugin.conf"
  install -D -m 644 /source/compat/pipewire/10-g955n-validated-core.conf "$R/etc/systemd/user/pipewire.service.d/10-g955n-validated-plugin.conf"
fi
if [ -f /adapters/sensor-proxy ]; then
  hardware_args+=(--sensor-daemon /adapters/sensor-proxy)
fi
if [ -f /adapters/gsd-power ]; then
  hardware_args+=(--ambient-power-daemon /adapters/gsd-power)
fi
if [ -d /adapters/audio ]; then
  hardware_args+=(--audio-build /adapters/audio)
fi
if [ -f /adapters/gnss-client ]; then
  hardware_args+=(--gnss-client /adapters/gnss-client)
fi
python3 /source/image/stage-ubuntu-hardware.py "${hardware_args[@]}"
chmod 755 "$R/usr/local/sbin/g955n-hardware"
chmod 755 "$R/usr/local/sbin/g955n-grow-root"
chmod 755 "$R/usr/local/sbin/g955n-android-bsp"
chmod 755 "$R/usr/local/sbin/g955n-fb-display"
install -D -m 644 /source/compat/xdamage-monitor.py "$R/usr/local/lib/g955n/g955n_xdamage.py"
chmod 755 "$R/usr/local/sbin/g955n-location-hub"
chmod 755 "$R/usr/local/sbin/g955n-bluetooth-address"
chmod 755 "$R/usr/local/sbin/g955n-kernel-evidence"
chroot "$R" systemctl enable g955n-grow-root.service g955n-kernel-evidence.service serial-getty@ttyGS0.service
if [ "$profile" = legacy ]; then
  chroot "$R" systemctl enable g955n-hardware.service g955n-fb-display.service g955n-bluetooth-rom.service
fi
chroot "$R" dconf update
chroot "$R" systemctl set-default graphical.target
if [ -s /inputs/ubuntu-password ]; then
  python3 - <<'PY'
from pathlib import Path
import subprocess
password = Path('/inputs/ubuntu-password').read_text().removesuffix('\n')
if not password or '\n' in password or '\r' in password or '\0' in password:
    raise SystemExit('Local password input must be a single nonempty line')
subprocess.run(['chroot', '/work/rootfs', 'chpasswd'], input='ubuntu:' + password + '\n',
               text=True, check=True)
PY
fi
for group in video audio input render dialout; do
  if chroot "$R" getent group "$group" >/dev/null; then
    chroot "$R" usermod -aG "$group" ubuntu
  fi
done
# Match the gadget MAC so predictable interface naming does not break USB SSH.
sed -i 's/^Name=usb0$/MACAddress=02:55:00:00:00:02/' "$R/etc/systemd/network/10-g955n-usb.network"
sed -i 's/^LinkLocalAddressing=ipv6$/LinkLocalAddressing=no/' "$R/etc/systemd/network/10-g955n-usb.network"
if ! grep -q '^Address=fe80::55:ff:fe00:2/64$' "$R/etc/systemd/network/10-g955n-usb.network"; then
  sed -i '/^Address=192.168.55.2\/24$/a Address=fe80::55:ff:fe00:2/64' "$R/etc/systemd/network/10-g955n-usb.network"
fi
printf '[keyfile]\nunmanaged-devices=mac:02:55:00:00:00:02\n' > "$R/etc/NetworkManager/conf.d/10-g955n-usb.conf"
# Never ship the build container's private resolver into a physical handset.
rm -f "$R/etc/resolv.conf"
printf '# Managed by NetworkManager after network activation.\n' > "$R/etc/resolv.conf"
printf 'SM-G955N\n' > "$R/etc/g955n-target"
# Unique private build keys allow host-key pinning before the first connection.
chroot "$R" ssh-keygen -A
printf '192.168.55.2 ' > /outputs/g955n-known-hosts
cat "$R/etc/ssh/ssh_host_ed25519_key.pub" >> /outputs/g955n-known-hosts
chmod 600 /outputs/g955n-known-hosts
mkdir -p "$R/run/sshd"
chroot "$R" /usr/sbin/sshd -t
package_audit=$(chroot "$R" dpkg --audit)
if [ -n "$package_audit" ]; then
  printf '%s\n' "$package_audit" >&2
  exit 1
fi
IMAGE=/work/g955n-rootfs.next.img
rm -f "$IMAGE"
truncate -s 8192M "$IMAGE"
mkfs.ext4 -F -L g955n-root -O ^metadata_csum_seed,^orphan_file,^64bit -d "$R" "$IMAGE"
e2fsck -fn "$IMAGE"
# Populate ext4 on Linux storage; publish sequentially only after fsck passes.
cp --sparse=always "$IMAGE" /outputs/g955n-rootfs.next.img
mv -f /outputs/g955n-rootfs.next.img /outputs/g955n-rootfs.unqualified.img
sha256sum /outputs/g955n-rootfs.unqualified.img /outputs/busybox-arm64-static > /outputs/SHA256SUMS
echo 'ROOTFS_FINALIZE_OK (still requires hardware validation)'
