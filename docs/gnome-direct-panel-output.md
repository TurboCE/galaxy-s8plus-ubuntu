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
The subsequent GNOME integration and device results are below.


## Direct output on the ordinary Ubuntu GNOME session

The X11 EGL backend identifies the fullscreen child of the X Composite overlay
in the actual GNOME Shell process. The live Exynos gralloc handle was one
DMA-BUF plus 46 words, with linear RGBX8888, 1440-pixel stride and 1440×2960
visible dimensions. The direct path accepts only that verified layout after
the EGL producer fence has completed. Other X11 surfaces use the existing
window transport. The match is gated by the root-owned runtime trial lease.

The first direct submit uncovered a wire layout defect. The kernel's
8-byte-aligned window union starts four bytes after the state member, so equal
outer struct sizes alone had hidden the misplaced fd and format. The live
kernel reported an import of fd -1. Fixed those offsets and added an
independent AArch64 comparison against all accessed vendor members, register
formats and the ioctl number.

The primary DSI timeline begins at one, and the point returned for frame N is
signaled after N+1. Waiting on the just-submitted fence stalled the first
replacement. The bridge now queues the replacement, waits on the preceding
frame's fence and retains the current buffer. It aborts a trial after an
ambiguous submission or retirement. The old framebuffer service only skips its
pan when the same lease is held. The mobile panel stays available to GDM before
GNOME takes over. A phone-local timer restores the original prefix and restarts
the ordinary greeter after the trial.

The real kernel32 device reported 60 retired GNOME buffers and sustained
timeline progress with the framebuffer pan paused by the lease. In a sampled
interval the primary DECON start and finish interrupts both advanced by 17,
with DSIM interrupts increasing by 28 and an outstanding replacement fence.
Kernel taint stayed 0. This establishes that the real display path processed
GNOME buffers. The test does not observe rendered pixels optically or certify
X11 cursor drawing, long-term display power behavior or suspend.

The same-boot A/B trial ran the same fixture three times per path. CPU usage is
whole-device busy time including fixture setup, averaged over three trials.

| Workload | X11 CPU transfer | Direct DECON |
| --- | ---: | ---: |
| Synthetic GNOME drag CPU | 16.04% | 11.15% |
| Drag median of trial median X window update gaps | 501.5 ms | 33 ms |
| Drag changes observed out of 180 commands | 8, 7, 6 | 94, 92, 77 |
| Scripted window moves CPU | 17.85% | 11.15% |
| Scripted move median X window update gap | 17 ms | 17 ms |

The geometry intervals measure GNOME's response to input, not panel FPS or
physical finger-to-photon latency. One earlier direct drag run did not grab the
window and was excluded. The same-boot A/B followed successful grabs in each
of its six drag trials. The direct path is a supervised candidate. The
ordinary X11 output is restored after the trial.

A reproducible, explicit trial entry point is provided in
`compat/native-gnome/direct-panel/trial.py`. It expects the rebuilt private
EGL module and a root-owned installation of the supervisor and the updated
framebuffer service. The candidate stays outside the public repository.

### Screen power and boot recovery

With the GPU GNOME desktop active on kernel32, three forced DPMS off/on
cycles put DECON into runtime suspend and brought it back to active.
After each resume, the same GNOME Shell submitted new frames and the
DECON timeline advanced by 179, 178 and 176 points respectively.
The boot ID stayed constant and taint stayed 0.

Install `trial.py` as `/usr/local/sbin/g955n-direct-panel-trial` and install
and enable the adjacent `g955n-direct-panel-recover.service` before arming
the trial. Before changing the active files the controller writes a durable
snapshot. The timed rollback restores the desktop during the current boot.
If the phone reboots with a pending snapshot, the recovery service restores
the original library, launcher and manifest before GDM starts.

A controlled reboot while the tracked trial controller was armed exercised the
boot service on the SM-G955N. All three file hashes matched the baseline,
the pending snapshot and lease were cleared, and the GDM and framebuffer
services were active on the new boot. Kernel taint was 0.
