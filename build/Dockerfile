FROM ubuntu:24.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential gcc-aarch64-linux-gnu binutils-aarch64-linux-gnu bc bison flex \
    libssl-dev libelf-dev libncurses-dev python3 git cpio xz-utils \
    debootstrap qemu-user-static e2fsprogs openssh-client ca-certificates \
    ubuntu-keyring file curl lz4 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
