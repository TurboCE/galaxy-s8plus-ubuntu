# GNOME direct panel output

The current SM-G955N GNOME session uses the vendor Mali-G71 EGL driver. The
X11 platform's queue path waits for the producer, locks the gralloc buffer and
submits pixels using XPutImage. Xorg's fbdev path and the panel commit pump
then present through the Samsung DECON driver. This is the CPU transfer that
direct output needs to remove. See patch 0013 in compat/compositor-build.

The running kernel32 exposes /dev/mali0 and no /dev/dri. Its build config has
CONFIG_DRM disabled. The pinned tree's Exynos DRM drivers do not match an
Exynos8895 panel controller. Enabling DRM alone therefore provides no matching
display backend for Mutter. The existing Samsung DPU driver accepts shared
scanout buffers and synchronization fences through S3CFB_WIN_CONFIG. The earlier
isolated HWC trials reached that path on hardware, including a nested GNOME
session. The nested session's X11 bridge still used XPutImage to transport
GNOME's buffers, so those trials did not achieve this end-to-end goal.

A direct GNOME implementation needs one output owner that receives the final
Mutter output as a shared buffer and submits it through HWC/DECON with producer
and release synchronization. It also needs to hand ownership back at logout,
power down and failure. A Mutter native backend through KMS requires an
Exynos8895 display driver and a vendor EGL/GBM buffer sharing integration.
Another route is a dedicated Mutter backend for the already verified HWC
interface. Both routes need a buffer lifetime contract from compositor output
through display completion. Independently starting the existing HWC demo
alongside the framebuffer presenter would give two owners of the same panel.

## Drag baseline for comparison

Use the normal unlocked GNOME X11 session with the panel active, unchanged
window settings and the same background app workload for each comparison.
The fixture makes its own window, sends GNOME's Super + primary mouse drag,
samples the X window geometry, releases the input and destroys the window.
The runner refuses a different mouse modifier, locked desktop or changed
boot/taint status. Geometry changes are a window-manager responsiveness
measurement. A panel acceptance trial must additionally measure physical
motion or panel presentation timing.

Build the fixture on the existing ARM64 Ubuntu device, then run the runner
as root so it can select the owner desktop and drop to its UID for the test.

```sh
cc -O2 -Wall -Wextra -Werror drag-baseline.c -o drag-baseline -lX11 -l:libXtst.so.6
sudo python3 measure-drag.py --fixture ./drag-baseline
```

Three live baseline trials requested 180 positions each and observed nine
distinct position changes each. Whole-device CPU busy was 20.28%, 21.29% and
20.80% including fixture setup. Median intervals between observed geometry
changes were 300.5, 291 and 279 ms. Longest intervals were 532, 536 and 552 ms.
The fixture's X queries and synthetic input are included in these results.
Boot identity and taint stayed unchanged. No direct GNOME path or comparative
performance improvement was demonstrated.

## Downstream submission code

`compat/native-gnome/direct-panel/decon-output.c` implements the last stage
for the pinned Exynos8895 ABI. It accepts a verified linear full-panel DMA-BUF
and its optional acquire fence, builds a single-window submission, and returns
the driver's completion fence. It checks the allocation size using DMA-BUF
seek semantics. It never maps the buffer or copies pixels. The caller must
verify the actual allocation layout and own the panel exclusively.

Both the helper and an independent fixture extracted from the pinned Samsung
kernel declarations compiled for AArch64 with warnings treated as errors.
The fixture checked the window size, source offset, ioctl payload size and
RGB format enum values. No panel ioctl was executed by this build check.
The remaining integration work is the GNOME producer hook, verification of
the gralloc layout, and ownership across framebuffer handoff, blanking and
fence completion. Completing the new frame does not authorize immediate
reuse of that same frame. The previous buffer can be retired after a verified
replacement. The installed X11 session has not been modified by this helper.
