# GNOME direct panel output

The SM-G955N GNOME session uses the vendor Mali-G71 EGL driver. The new
DRM/KMS/PRIME implementation is documented in
[the native display driver](../compat/drm-kms/README.md). The sections below
retain the earlier CPU-copy and Samsung-ioctl development evidence.

The original X11 platform queue path waited for the producer, locked the
gralloc buffer and submitted pixels using XPutImage. Xorg's fbdev path and the panel commit pump
then present through the Samsung DECON driver. This was the CPU transfer that direct output removed. See patch 0013 in compat/compositor-build.

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

A separate direct-output test repeated DPMS off/on 18 times. Every cycle
resuspended and reactivated DECON, then advanced its timeline by 141–181
points in the same GNOME process and boot. Taint stayed 0 and normal output
was restored when the test ended.

### Default GNOME output on the SM-G955N

The controller can install the same reviewed EGL module for subsequent
ordinary GNOME logins with `--candidate PATH --sha256 HASH --enable-default`.
GDM keeps the framebuffer presenter until the owner GNOME Shell takes the
panel lease. The boot service recreates the lease on kernel32 only after
verifying the installed library, manifest and session launcher against the
persistent install record. A changed module, incompatible kernel or
interrupted trial brings back the saved original output files. The installed
controller also accepts `--restore` to return to the original path.

A controlled reboot with the default set brought up GDM and recreated the
verified lease. Replayed contact events on the actual `sec_touchscreen` evdev
device selected the account, opened the GDM password field, entered the
credential through GNOME's screen keyboard, and reached the actual PAM owner
session. This exercises GNOME's touchscreen input path from evdev onward.
It does not measure the digitizer hardware or physical touch latency.

Eight subsequent DPMS off/on cycles on that login resumed the same
GNOME Shell and advanced the DECON timeline by 170–180 points each.
The boot ID was constant and kernel taint stayed 0.

For the persistent install, copy the two files from
`compat/native-gnome/direct-panel/shell-policy/` into
`/opt/g955n-native-gpu/direct-shell/gnome-shell/extensions/g955n-direct-panel@local/`
as root-owned files first. The controller makes a private copy of the
installed Ubuntu GNOME mode and appends the shell extension. The ordinary
Ubuntu theme, session and enabled extensions are retained. The default
configuration validates the private mode and both extension files at boot.

Mutter can normally unredirect an opaque fullscreen X11 client after
sustained full-window damage. That removes its output from the GNOME
overlay that this port sends to DECON. The small shell extension
inhibits this bypass in the direct session. The real device reproduced
152 samples with an empty GNOME overlay in the fullscreen fixture
before the extension. After installation and a clean boot, the same
fixture stayed fullscreen with zero empty overlay samples and the
DECON timeline advanced by 170 points.

The first persistent configuration stayed active for 260 seconds with nine
workload samples, stable GNOME PID and boot, DECON progress on every sample
and taint 0. The run was deliberately interrupted to install the fullscreen
correction. An extended run of the corrected configuration is still pending.

The first system suspend request was refused because the stock Ubuntu image
masks sleep.target and suspend.target. A subsequent bounded test temporarily
enabled suspend-to-idle (freeze), scheduled a 24-second RTC alarm, and armed
policy restoration both by timer and on the next boot. Neither network nor
USB console returned by the end of the observation. A host USB port
re-enumeration did not restore access. This is a failed system suspend test.
The last reached kernel power stage and any retained crash trace need to be
collected after the phone is accessible. Deep system suspend was not tested.

### Kernel36 direct output and touch authentication

The controller recognizes the linked kernel36 build notes from the exact
tested image. It applies the fullscreen policy to supervised trials as well
as persistent sessions. An explicit restore cancels the old timer so another
trial can start without a stale systemd unit.

On a normal kernel36 boot, replayed contacts on the actual touchscreen input
node selected the GDM account, switched the on-screen keyboard to numbers,
entered the password, and reached the real GNOME session. A warm reboot
recreated the verified direct-output lease and passed the same touch login.
The opaque fullscreen fixture showed zero empty overlay samples and
continued DECON timeline progress. This is an input-path test from evdev
through PAM. Physical digitizer latency was not measured.

Eight display off/on cycles passed before reboot and eight afterward.
Each cycle confirmed X11 and panel runtime states, then submitted new
compositor work. A separate 129-second workload kept the same GNOME Shell
and boot with taint 0 and 175 to 179 DECON retirements per sample. System
sleep targets stayed masked. CPU idle entry counters increased in all
three observed idle states under the ondemand governor.

### Kernel50 output recovery and performance

The live owner GNOME was using Mali-G71 EGL and Exynos gralloc, but its
session had no direct-output flag and the direct-output snapshot was absent.
The kernel allow check accepted only kernel32 and the linked kernel36.
The boot recovery policy restores the saved X11 output on other builds.
Consequently GPU rendering remained enabled while final presentation
returned to CPU transfer.

Compared the running kernel50 ELF notes with the local linked vmlinux
and added that exact image to the checked controller. The existing v6
EGL candidate matched the previously tested file byte for byte. A normal
login on kernel50 then held the panel lease, opened fb0 from GNOME, loaded
Mali-G71, and logged 60 retired GNOME frames without CPU pixel transfer.
The controller logs explicitly when it restores the CPU-copy path.

Three synthetic X11 drags on the copy path used an average 17.00% of
whole-machine CPU, with median window-position gaps of 501, 519 and
501 ms. Three trials on direct output averaged 10.91%, with all three
median gaps at 33 ms. This is about 36% less total CPU activity in that
workload. Deterministic window-move trials averaged 14.26% before and
11.05% after, with 17 ms geometry gaps in both cases. Geometry reporting
does not measure panel FPS or physical touch latency.

The fallback presenter now backs off while GNOME owns the direct-output
lease. The fullscreen fixture kept the overlay composed with zero hidden
samples and continued DECON retirement.

The legacy pixel probe reads the X11 overlay backing image and fails
after final composition is submitted directly to DECON. It cannot
qualify the direct panel pixels. Optical correctness remains separate
from these buffer-ownership, fence and response measurements.

The current integration still qualifies individual kernel images.
Moving DECON to DRM/KMS with PRIME import and matching Mali EGL/GBM
support is a separate driver and compositor integration task. That path
would expose buffer formats, planes and page-flip synchronization through
the standard display UAPI. It must preserve DMA-BUF import, scanout
lifetimes and suspend/resume before replacing the present direct path.

During the current qualification one system-suspend run caused the
GNOME process to exit with bridge status 33 and restart within the same
session. A fence-diagnostic comparison did not reproduce it. The
installed library was returned to reviewed v6 afterward. This finding
leaves direct-output system-suspend stability open.
