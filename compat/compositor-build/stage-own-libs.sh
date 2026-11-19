#!/usr/bin/env bash
# Read an existing own-device SYSTEM image only; no phone/loop mounts/partitions.
set -euo pipefail
IMAGE=${1:?SYSTEM image required}
OUTPUT=${2:-/work/input/own-libs}
case "$OUTPUT" in /work/*) ;; *) echo 'Use dedicated /work staging' >&2; exit 2 ;; esac
PROPS=$(debugfs -R 'cat /build.prop' "$IMAGE" 2>/dev/null)
printf '%s\n' "$PROPS" | grep -qx 'ro.product.model=SM-G955N'
printf '%s\n' "$PROPS" | grep -qx 'ro.product.device=dream2lteks'
printf '%s\n' "$PROPS" | grep -qx 'ro.build.version.sdk=28'
mkdir -p "$OUTPUT"
LIBS=(libc++.so libc.so libm.so libdl.so libhidlbase.so libhidltransport.so libutils.so
 android.hardware.graphics.mapper@2.0.so android.hardware.graphics.allocator@2.0.so
 libgui.so libui.so libsync.so libbase.so liblog.so libcutils.so libbinder.so
 libhardware.so libhwbinder.so libfmq.so libEGL.so libGLESv1_CM.so libGLESv2.so
 libnativewindow.so android.hardware.graphics.composer@2.1.so
 android.hardware.graphics.composer@2.2.so android.frameworks.vr.composer@1.0.so
 android.hardware.configstore@1.0.so android.hardware.configstore-utils.so)
for name in "${LIBS[@]}"; do
 debugfs -R "dump /lib64/$name $OUTPUT/$name" "$IMAGE"
 test -s "$OUTPUT/$name"
 readelf -h "$OUTPUT/$name" | grep -q 'Machine:.*AArch64'
done
sha256sum "$IMAGE" > "$OUTPUT/source-image.sha256"
(cd "$OUTPUT"; sha256sum -- *.so > link-inputs.sha256)
printf '%s\n' 'SM-G955N / dream2lteks / SDK28; private link inputs only' > "$OUTPUT/source-model.txt"
echo 'Staged own-device library inputs only; no binaries were run.'
