FROM ubuntu:24.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential gcc-aarch64-linux-gnu binutils-aarch64-linux-gnu bc bison flex \
    libssl-dev libelf-dev libncurses-dev python3 git cpio xz-utils \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
