# Desktop dragging: measured bottlenecks and presentation fallback

The logged-in desktop remains CPU/llvmpipe rendered. The damage-driven
presenter below reduced measured presentation overhead but did not remove the
owner-reported lag. Three later kernel-22 crashes invalidate any stability claim.
Their cause has not been attributed to the presenter or any specific driver.

The live phone was returned to the exact original presenter before the BOOT-only
kernel-15 rollback. Source now defaults to the original synchronous CRC loop;
the experimental branch requires explicit `G955N_FB_XDAMAGE=1` and is quarantined.
It must not be enabled by an ordinary image build. The measurements below are
historical, not the current installed mode. GPU/ION trials remain on hold.

## Measurements on kernel #22

The actual logged-in GNOME process uses DISPLAY=:1 and its UID1000 GDM authority
path. `glxinfo -B` on that session exits0 with empty stderr and reports Mesa25.2.8
llvmpipe(LLVM20.1.2), **Accelerated:no**. “direct rendering:Yes” does not mean Mali
acceleration. Xorg is using the existing fbdev/ShadowFB configuration at
1440×2960×32bpp, stride5760; xrandr's 0.00Hz and gamma-size warning describe the
fbdev metadata limitation, not physical panel FPS.

During one 5-second natural/mostly idle sample, CPU time per one core was:

| Process | CPU |
| --- | ---: |
| Python framebuffer presenter | 43.59% |
| GNOME Shell | 0.80% |
| Xorg | 0.00% |

This is not a controlled window-drag workload. It nevertheless exposes a large
idle presentation cost. The installed presenter reads the entire framebuffer
with zlib.crc32 before each sleep(0.2). A frame is17,049,600 bytes; the sleep
alone limits detection to at most5Hz, and CRC/pan time reduces it further.
Increasing this unchanged loop to30Hz would request511,488,000 bytes/s of CPU
framebuffer reads, before ShadowFB/compositing/scanout traffic. Framebuffer
mapping/cache behavior can make this cost worse than ordinary RAM bandwidth.
Do not infer an exact CRC duration or achieved FPS from the CPU sample alone.

A separate 5-second idle observation saw one initial XDamage event then no
subsequent damage, DECON frame-done/DSIM counters unchanged and300 TE interrupts.
Thus panel timing continues near60Hz while the displayed image is static. TE
interrupt rate, root-damage notification rate and completed-frame rate are
separate quantities.

Private evidence: `inventory/kernel22-display-profile.json` and
`inventory/kernel22-display-damage.json`. No framebuffer image was captured.

## Working observer helper

`compat/xdamage-monitor.py` implements this integration API:

```python
monitor = DamageMonitor()
try:
    dirty = monitor.poll()  # nonblocking; True only for new damage while ready
    if monitor.ready:
        pass  # coalesce dirty and PAN in the framebuffer owner's own loop
    # monitor.last_events: ready/damaged/failed dictionaries
    # monitor.counts: notification/failure totals, including subsequent events
    # monitor.reconnect(): asynchronous actual-session rediscovery
finally:
    monitor.close()
```

The parent keeps the framebuffer fd. The helper never opens framebuffer/DRM/GPU/
input nodes, captures pixels, injects input or modifies existing windows. It
reads the actual active GNOME-shell process's DISPLAY/XAUTHORITY/XDG_SESSION_ID,
checks logind activity when available and reconnects when process/auth/session
identity changes. It reads authority metadata, not cookie contents. Xlib opens
its own connection under the selected session UID.

Session discovery and Xlib run in isolated processes so a slow session query or
Xlib's fatal server-I/O handler cannot exit/block the presenter. The parent API
only drains nonblocking pipes. Each observer owns one root XDamageReportNonEmpty
object, subtracts/acknowledges its own damage after each notification, and destroys
that object/closes the connection on normal termination. A lost server reclaims
its client objects; the supervisor retries with bounded delay. close() terminates
only the helper's own separate process group. No server/input grab or shared
event-mask change is used. Failure clears ready and returnsFalse.

## Actual subsequent-draw proof

The observer was tested with one independently owned64×64 window, mapped,
drawn/moved20 times over about2 seconds, then destroyed in finally. GNOME
composition generated867 **subsequent** root-damage notifications, separate from
two initial notifications over an explicit observer reconnect. There were zero
failed events, and reconnect returned ready. Across420 parent polls, p95 latency
was0.903ms and maximum4.939ms; boot ID stayed identical and taint remained0.
The test's X connection and all observers were closed. This demonstrates actual
post-initial drawing notifications; notification count is not a frame count and
must be coalesced before pan. Raw evidence is privately retained in
`inventory/kernel22-display-damage-stimulus.json`.

Real GDM logout/X-server restart is still a separate qualification case. The own-worker-failure test killed only its freshly created/verified observer
PID (matching command and private process group). It cleared ready, returned a
failed event, restarted a new observer and became ready again; parent poll max
was1.524ms. Both workers and the supervisor were absent after close, taint0.
Evidence: `inventory/kernel22-display-damage-failure.json`. Xorg/GNOME were not
signalled. This checks abnormal-worker recovery, not an actual server restart.

## Presenter integration recommendation

On damage, retain a pending-dirty boolean and pan at most once per monotonic
1/30-second deadline. Drain/coalesce all notifications instead of panning once
per rectangle or trying to replay a backlog. Keep the existing geometry checks,
exclusive framebuffer ownership and cleanup. Track notification, pan and fallback
counts and measure CPU again during both idle and real dragging.

A low-frequency full-CRC safety check is justified until all GNOME/session paths
are qualified. Every2 seconds costs about8.52MB/s of reads at this geometry,
rather than511MB/s for30 full scans. If damage monitoring is unavailable, preserve
the prior bounded CRC fallback and clearly expose the failed/ready state. Sparse
pixel/page sampling can miss small edits and is not a correctness substitute for
full fallback scans; a missed password-field redraw already mattered to this
port. Do not remove the fallback merely because initial damage or one test passed.

This can reduce presentation latency and idle CPU while the desktop is still
software rendered. Mali offscreen acceleration and the future HWC2/gralloc
presentation/compositor route remain distinct; increasing framebuffer updates
does not make GNOME GPU accelerated.

## First post-integration observation (locked-screen limitation)

Root installed the damage-driven presenter separately. The service remained in
xdamage-30hz mode with stable parent PID and no restart, same boot/taint0. Its
named-systemd cgroup contained presenter, supervisor and Xlib observer. There is
no per-unit CPU-controller path, so process/thread CPU plus reaped-child ticks
were summed across all unit members without enabling CPU accounting.

Over5.087s mostly idle, total unit CPU was14.74% of one core (presenter10.81%,
supervisor3.93%, observer0), versus the earlier43.59% single-presenter sample.
These are indicative, not a controlled identical-scene benchmark. The second
owned64×64 window completed20 updates/cleanup and raised Xorg/GNOME CPU, but
DECON frame-done/DSIM counters did not advance; TE remained near60Hz. The60s
service counter covering this interval reported only2 PAN requests/2 damage
batches, so this trial **did not prove visible window presentation**.

Read-only follow-up explained why: active sessionc18 had IdleHint=yes,
LockedHint=yes and GNOME ScreenSaver.GetActive=true. The test window was behind
the lock screen, which was correctly not repainting for a hidden window. No
unlock/input was attempted. A visible-desktop recheck after root/user handles
that state is required; do not call the observer broken or the presentation
qualified from this obscured stimulus. Evidence:
`inventory/kernel22-display-after-damage.json`.

## Unlocked post-integration update proof

After the owner confirmed unlocking, a single bounded test first rechecked both
logind LockedHint=no and GNOME ScreenSaver=false; both remained unlocked after
the test. One owned64×64 window drew/moved20 times over approximately2 seconds.
A separate pure observer saw871 subsequent damage notifications and zero errors.
The actual presenter's ioctl-only trace recorded38 FBIOPAN_DISPLAY calls, all
returning0, during a3.277-second sampling interval. DSIM and both DECON frame-done
interrupt counters each increased by38; TE increased196. This establishes the
damage→PAN→driver-completion path under real visible-desktop drawing, rather
than relying solely on source configuration or initial damage. It is not a
claim of fixed30FPS, optical panel timing or GPU composition.

The presenter PID8613 remained unchanged, boot stayed identical and taint0.
The temporary window, extra observer and ioctl tracer were all closed/detached
(the tracer was intentionally stopped with SIGINT, recorded exit -2);
no existing window/input/session was modified. Whole presenter-unit CPU was
29.91% of one core during this stimulated/traced sample, which is not an idle
or GPU benchmark and includes tracing effects. The earlier14.74% idle sample
remains the separate idle-cost observation. Evidence:
`inventory/kernel22-display-visible-update.json`. No additional UI tests followed.
