#!/usr/bin/env bash
# Build only. No USB, privileged container, device mount or flash operations.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
if [ "${G955N_SCRIPT_SNAPSHOT:-0}" != 1 ]; then
  exec python3 "$ROOT/scripts/run_build.py" "$@"
fi
MODE=${1:-config}
case "$MODE" in config|image) ;; *) echo 'Usage: build_kernel.sh [config|image]' >&2; exit 2 ;; esac
SOURCE="$ROOT/upstream/kernel"
if [ -d "$ROOT/upstream/kernel.git" ]; then SOURCE="$ROOT/upstream/kernel.git"; fi
EXPECTED=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["sources"]["kernel"]["commit"])' "$ROOT/sources.json")
test "$(git -C "$SOURCE" rev-parse HEAD)" = "$EXPECTED"
BUILDER=${G955N_BUILDER:-g955n-ubuntu-builder:24.04}
VOLUME=g955n-ubuntu-build
if [ -n "$(docker ps --filter "volume=$VOLUME" --format '{{.ID}}')" ]; then
  echo 'Kernel build volume is already in use' >&2
  exit 1
fi
docker volume create "$VOLUME" >/dev/null
# git archive exports committed objects, avoiding macOS case-collided checkout
# files. Both source extraction and compilation happen on a Linux filesystem.
git -C "$SOURCE" archive HEAD | docker run --rm -i --network none \
  -v "$VOLUME:/work" "$BUILDER" sh -ec 'mkdir -p /work/src; tar -x -C /work/src'
mkdir -p "$ROOT/artifacts"
OUTPUT=$(mktemp -d "$ROOT/artifacts/build-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
echo "Artifacts: $OUTPUT"
docker run --rm --network none -v "$VOLUME:/work" \
  -v "$ROOT/config:/port-config:ro" -v "$OUTPUT:/artifacts" \
  -v "$ROOT/patches:/port-patches:ro" \
  -e PORT_MODE="$MODE" -e ARCH=arm64 -e CROSS_COMPILE=aarch64-linux-gnu- \
  "$BUILDER" bash -euc '
    cd /work/src
    for patch_file in /port-patches/*.patch; do
      git apply --check "$patch_file"
      git apply "$patch_file"
    done
    # Makefile command changes do not invalidate existing generated assembly.
    # Remove only derived firmware assembly in this dedicated output directory.
    if [ -d /work/out/firmware ]; then
      find /work/out/firmware -name "*.gen.S" -delete
    fi
    make O=/work/out HOSTCFLAGS="-O2 -fcommon" g950x_defconfig
    scripts/kconfig/merge_config.sh -m -O /work/out /work/out/.config \
      arch/arm64/configs/g955x_kor_defconfig /port-config/ubuntu-bringup.fragment
    make O=/work/out HOSTCFLAGS="-O2 -fcommon" olddefconfig
    cp /work/out/.config /artifacts/kernel.config
    if [ "$PORT_MODE" = image ]; then
      make O=/work/out -j4 HOSTCFLAGS="-O2 -fcommon" KCFLAGS="-Wno-error" Image dtbs
      cp /work/out/arch/arm64/boot/Image /artifacts/Image.unqualified
      cp /work/out/arch/arm64/boot/dts/exynos/exynos8895-dream2lte_kor_10.dtb /artifacts/
    fi
  '
