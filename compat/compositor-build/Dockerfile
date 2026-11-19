# Host-only amd64 compiler with arm64 target headers/libraries. No device mounts.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN dpkg --add-architecture arm64 \
    && sed -i '/^Types: deb$/a Architectures: amd64' /etc/apt/sources.list.d/ubuntu.sources \
    && printf '%s\n' 'Types: deb' 'URIs: http://ports.ubuntu.com/ubuntu-ports' \
       'Suites: noble noble-updates noble-security' 'Components: main universe' \
       'Architectures: arm64' 'Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg' \
       > /etc/apt/sources.list.d/arm64.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git build-essential clang lld binutils file \
    gcc-aarch64-linux-gnu g++-aarch64-linux-gnu \
    meson ninja-build pkg-config autoconf automake libtool flex bison libssl-dev \
    python3 e2fsprogs libwayland-dev libglib2.0-dev-bin \
    libltdl-dev:arm64 libwayland-dev:arm64 wayland-protocols \
    libdrm-dev:arm64 libgbm-dev:arm64 libegl-dev:arm64 libgles-dev:arm64 \
    libpixman-1-dev:arm64 libinput-dev:arm64 libseat-dev:arm64 libudev-dev:arm64 \
    libsystemd-dev:arm64 libglib2.0-dev:arm64 libgudev-1.0-dev:arm64 \
    libxkbcommon-dev:arm64 libcap-dev:arm64 libffi-dev:arm64 libdecor-0-dev:arm64 \
    libx11-dev:arm64 libx11-xcb-dev:arm64 libxcb-present-dev:arm64 libxcb-shm0-dev:arm64 libxext-dev:arm64 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
# libhybris's Wayland client platform needs the official private-backend header.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libwayland-egl-backend-dev:arm64 && rm -rf /var/lib/apt/lists/*
