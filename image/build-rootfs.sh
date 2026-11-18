#!/usr/bin/env bash
# Build-only Ubuntu ARM64 filesystem. Container has no phone or USB access.
set -euo pipefail
R=/work/rootfs
MIRROR=https://ports.ubuntu.com/ubuntu-ports
test "$(id -u)" = 0
test -f /inputs/ssh.pub
test ! -e "$R/etc/os-release" || { echo 'Refusing to overwrite an existing rootfs'; exit 1; }
mkdir -p "$R"
debootstrap --arch=arm64 --variant=minbase --include=ca-certificates,ubuntu-keyring \
  --foreign --keyring=/usr/share/keyrings/ubuntu-archive-keyring.gpg noble "$R" "$MIRROR"
cp /usr/bin/qemu-aarch64-static "$R/usr/bin/"
chroot "$R" /debootstrap/debootstrap --second-stage
mkdir -p "$R/proc" "$R/sys" "$R/dev/pts" "$R/run"
cleanup() {
  for item in run dev/pts dev sys proc; do umount "$R/$item" 2>/dev/null || true; done
}
trap cleanup EXIT
mount -t proc proc "$R/proc"
mount -t sysfs sysfs "$R/sys"
mount --bind /dev "$R/dev"
mount -t devpts devpts "$R/dev/pts"
mount -t tmpfs tmpfs "$R/run"
cp /etc/resolv.conf "$R/etc/resolv.conf"
printf '#!/bin/sh\nexit 101\n' > "$R/usr/sbin/policy-rc.d"
chmod 755 "$R/usr/sbin/policy-rc.d"
cat > "$R/etc/apt/sources.list" <<EOF
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] $MIRROR noble main universe restricted multiverse
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] $MIRROR noble-updates main universe restricted multiverse
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] $MIRROR noble-security main universe restricted multiverse
EOF
chroot "$R" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get update
chroot "$R" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  systemd-sysv udev dbus openssh-server sudo busybox-static iproute2 iputils-ping \
  network-manager wpasupplicant iw bluez modemmanager gpsd gpsd-clients \
  iio-sensor-proxy alsa-utils e2fsprogs kmod ca-certificates curl tzdata \
  libegl1 libgles2 libgbm1 libdrm2 mesa-utils weston wayland-utils
chroot "$R" useradd -m -s /bin/bash -G sudo ubuntu
install -d -m 700 "$R/home/ubuntu/.ssh"
install -m 600 /inputs/ssh.pub "$R/home/ubuntu/.ssh/authorized_keys"
chroot "$R" chown -R ubuntu:ubuntu /home/ubuntu/.ssh
install -d "$R/etc/ssh/sshd_config.d" "$R/etc/sudoers.d"
printf 'ubuntu ALL=(ALL) NOPASSWD:ALL\n' > "$R/etc/sudoers.d/90-g955n-ubuntu"
chmod 440 "$R/etc/sudoers.d/90-g955n-ubuntu"
printf 'PasswordAuthentication no\nKbdInteractiveAuthentication no\nPermitRootLogin no\n' > "$R/etc/ssh/sshd_config.d/10-g955n.conf"
printf 'g955n-ubuntu\n' > "$R/etc/hostname"
printf '127.0.0.1 localhost\n127.0.1.1 g955n-ubuntu\n' > "$R/etc/hosts"
ln -sf /usr/share/zoneinfo/Asia/Seoul "$R/etc/localtime"
printf 'Asia/Seoul\n' > "$R/etc/timezone"
mkdir -p "$R/etc/systemd/network" "$R/etc/systemd/system" "$R/etc/udev/rules.d"
cat > "$R/etc/systemd/network/10-g955n-usb.network" <<'EOF'
[Match]
Name=usb0
[Network]
Address=192.168.55.2/24
Address=fe80::55:ff:fe00:2/64
DHCPServer=yes
LinkLocalAddressing=no
[DHCPServer]
PoolOffset=10
PoolSize=30
EmitDNS=no
EmitRouter=no
EOF
mkdir -p "$R/etc/NetworkManager/conf.d"
printf '[keyfile]\nunmanaged-devices=interface-name:usb0\n' > "$R/etc/NetworkManager/conf.d/10-g955n-usb.conf"
chroot "$R" systemctl enable ssh systemd-networkd NetworkManager bluetooth
# Bring-up precaution: automatic sleep is disabled until resume is validated.
for unit in sleep.target suspend.target hibernate.target hybrid-sleep.target; do
  ln -sf /dev/null "$R/etc/systemd/system/$unit"
done
# Avoid automatic QUERYCAP on unvalidated Samsung FIMC nodes during early boot.
# This does not fix or qualify camera drivers; manual camera validation remains.
ln -sf /dev/null "$R/etc/udev/rules.d/60-persistent-v4l.rules"
mkdir -p "$R/lib/firmware/samsung/g955n" "$R/vendor" "$R/system/etc/wifi"
cp -a /firmware/firmware/. "$R/lib/firmware/samsung/g955n/"
cp -a /firmware/wifi/. "$R/system/etc/wifi/"
ln -s /lib/firmware/samsung/g955n "$R/vendor/firmware"
printf '/dev/disk/by-label/g955n-root / ext4 defaults,noatime 0 0\n' > "$R/etc/fstab"
chroot "$R" dpkg-query -W > /outputs/packages.txt
cp "$R/bin/busybox" /outputs/busybox-arm64-static
rm -f "$R/usr/bin/qemu-aarch64-static" "$R/usr/sbin/policy-rc.d"
chroot "$R" apt-get clean
rm -f "$R/etc/ssh/ssh_host_"*
# OpenSSH service generates fresh host keys before starting on this device.
mkdir -p "$R/etc/systemd/system/ssh.service.d"
printf '[Service]\nExecStartPre=/usr/bin/ssh-keygen -A\n' > "$R/etc/systemd/system/ssh.service.d/10-host-keys.conf"
truncate -s 0 "$R/etc/machine-id"
cleanup
trap - EXIT
IMAGE=/work/g955n-rootfs.next.img
rm -f "$IMAGE"
truncate -s 3072M "$IMAGE"
mkfs.ext4 -F -L g955n-root -O ^metadata_csum_seed,^orphan_file,^64bit -d "$R" "$IMAGE"
e2fsck -fn "$IMAGE"
cp --sparse=always "$IMAGE" /outputs/g955n-rootfs.next.img
mv -f /outputs/g955n-rootfs.next.img /outputs/g955n-rootfs.unqualified.img
sha256sum /outputs/g955n-rootfs.unqualified.img /outputs/busybox-arm64-static > /outputs/SHA256SUMS
echo 'ROOTFS_BUILD_OK (not a phone boot or hardware qualification)'
