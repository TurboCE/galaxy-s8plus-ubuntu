#!/usr/bin/env bash
# Offline only; reuse the completed builder's private volume, never a phone.
set -euo pipefail
R=/work/rootfs
test -x "$R/sbin/init"
test "$(cat "$R/etc/hostname")" = g955n-ubuntu
tar -C /source/image/rootfs-overlay -cf - . | tar -C "$R" --keep-directory-symlink -xpf -
chmod 755 "$R/usr/local/sbin/g955n-hardware"
chmod 755 "$R/usr/local/sbin/g955n-grow-root"
chroot "$R" systemctl enable g955n-hardware.service g955n-grow-root.service
for group in video audio input render dialout; do
  if chroot "$R" getent group "$group" >/dev/null; then
    chroot "$R" usermod -aG "$group" ubuntu
  fi
done
# Match the gadget MAC so predictable interface naming does not break USB SSH.
sed -i 's/^Name=usb0$/MACAddress=02:55:00:00:00:02/' "$R/etc/systemd/network/10-g955n-usb.network"
printf '[keyfile]\nunmanaged-devices=mac:02:55:00:00:00:02\n' > "$R/etc/NetworkManager/conf.d/10-g955n-usb.conf"
printf 'SM-G955N\n' > "$R/etc/g955n-target"
# Unique private build keys allow host-key pinning before the first connection.
chroot "$R" ssh-keygen -A
printf '192.168.55.2 ' > /outputs/g955n-known-hosts
cat "$R/etc/ssh/ssh_host_ed25519_key.pub" >> /outputs/g955n-known-hosts
chmod 600 /outputs/g955n-known-hosts
mkdir -p "$R/run/sshd"
chroot "$R" /usr/sbin/sshd -t
chroot "$R" dpkg --audit
IMAGE=/outputs/g955n-rootfs.unqualified.img
rm -f "$IMAGE"
truncate -s 3072M "$IMAGE"
mkfs.ext4 -F -L g955n-root -O ^metadata_csum_seed,^orphan_file,^64bit -d "$R" "$IMAGE"
e2fsck -fn "$IMAGE"
sha256sum "$IMAGE" /outputs/busybox-arm64-static > /outputs/SHA256SUMS
echo 'ROOTFS_FINALIZE_OK (still requires hardware validation)'
