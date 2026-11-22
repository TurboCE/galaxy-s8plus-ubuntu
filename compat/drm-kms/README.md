# Exynos8895 native-panel DRM/KMS

The SM-G955N DECON panel is exposed as a display-only DRM card. Mali still
renders through the owner's vendor EGL/Exynos gralloc and the existing Ubuntu
GNOME X11 session. This is a KMS/PRIME presentation bridge, not a GBM renderer,
a mainline kernel conversion, or a native Mutter Wayland backend.

The final GNOME composition buffer follows this path:

```
Mali GLES -> linear gralloc DMA-BUF -> DRM PRIME/GEM -> KMS page flip
          -> DECON/DPP IOMMU scanout -> DSIM -> built-in panel
```

The production path never maps or copies pixels on the CPU. The CPU still
submits work, manages references and mappings, and handles completion events.
Applications may independently use software rendering or X11 buffer copies.
The bridge does not add a GPU blit of GNOME's final composition.

## Kernel

`0052-g955n-decon-drm-scanout.patch` connects `decon_drm.c` and its header to the
pinned Samsung DECON driver. The builder copies those two sources from this
directory and records their hashes. `CONFIG_DRM_EXYNOS8895_NATIVE` and the
SM-G955N board's `samsung,drm-scanout` property are both required. The primary
DSI panel alone is registered; no external-display feature is added.

The card provides one CRTC/primary plane/DSI connector, the fixed panel mode,
PRIME import/export, GEM handles, AddFB2, asynchronous page flips, DPMS and
ION-backed dumb buffers. It uses the existing panel, DPP, clock/QoS and power
sequences. Imported DMA-BUFs use the generic attachment/scatterlist/IOMMU path;
they are never cast to an ION exporter object. Legacy fd-based ION submissions
keep their original mapping path. Native fbdev remains the recovery output.

Each accepted flip holds its framebuffer and vblank reference. The ordered
worker waits for the producer's reservation fence and the real DECON frame
start. Only successful hardware completion sends the flip event and retires
the old framebuffer. A real failure returns poll error, preserving the last
confirmed framebuffer; it never announces a successful flip.

ABI 1.1 also mirrors actual framebuffer power through the connector's standard
DPMS property. If fbcon/suspend blanks the panel after accepting a flip, the
worker retains the buffer/event and resubmits after unblank. There is no
fabricated off-panel completion. File close, master drop and teardown cancel
deferred events before their destination file can disappear.

Build the full existing stability profile plus KMS, without device access:

```sh
python3 scripts/build_diagnostic_kernel.py --build \
  --builder g955n-kernel-gcc7-reference:18.04-amd64-lz4 --build-version 55 \
  --audio-safety --native-fb-owner --native-panel-safety --native-panel-qos \
  --native-ondemand-safety --ssp-sysfs-counts --abox-suspend-irq-order \
  --suspend-battery-diagnostic --pmic-wake-irq --dpp-shared-dma \
  --desktop-charger-touch --dhd-pcie-suspend-order --mif-int-suspend-comparison \
  --dhd-cancel-pending-pm-work --freeze-voltage-dvfs --fts-desktop-suspend \
  --exynos-wlan-pci-sleep-ownership --strict-noirq-power-domain \
  --exynos-suspend-unwind --exynos-restore-failed-domain-off \
  --dhd-system-suspend-drain --dhd-defer-wowlan-pm-work \
  --dhd-init-wowlan-defaults --dhd-system-wlan-wake-opt-in \
  --dpu0-system-sleep-retention --bt-uart-sleep-pinctrl --drm-native-scanout \
  --usb-gadget-sleep-quiesce
```

Packaging and BOOT-only installation remain separate operations with the
repository's model, recovery, backup and readback checks.

## Existing GNOME integration

Compositor patch 0026 adds the standard libdrm presenter in
`compat/native-gnome/direct-panel/drm-output.c`. It imports gralloc DMA-BUFs,
caches at most eight framebuffer IDs by GEM handle, and waits for real flip
events before recycling old buffers. A DMA-BUF fd number or anonymous inode is
not used as its identity. The helper retains ambiguous submissions.
Patch 0027 returns control to GNOME when DPMS reports a blank panel. It
retains the last scanout and at most one outstanding flip. A new frame may
be skipped while the panel is blank. X11 keeps three buffers so Mutter can
continue to render and process input while the two display buffers are held.

A returned pending flip gets a fresh powered wait when rendering resumes.
The powered wait samples DPMS in bounded poll intervals and can grant one
extra budget after a genuine sleep interval observed with BOOTTIME. The
presenter retires a buffer only after an actual KMS event for its replacement.
The production-method fixture exercises blank before submission, blank
after acceptance, wake completion, suspend clocks and a powered timeout.

The X11 prefix builder now builds the presenter and `bin/drm-kms-probe`; the
prefix packager includes the probe and records its dependencies. Install the
root-owned `99-g955n-kms-bridge.rules` from `compat/native-gnome/direct-panel`
under `/etc/udev/rules.d/`, then reload rules and restart GDM separately. It
keeps Xorg/logind's unused GPU probe from holding this card's DRM master. The
real fbdev display, touchscreen and normal GDM/PAM login stay on seat0. This
bridge-specific seat rule should be removed if migrating to a native KMS/GBM
compositor that acquires the display through logind.

The existing direct-panel controller selects the route explicitly:

```
python3 /usr/local/sbin/g955n-direct-panel-trial \
  --candidate REVIEWED_MODULE --sha256 REVIEWED_SHA256 --drm-kms
```

The trial retains its phone-local rollback timer. Default activation remains a
separate explicit `--enable-default` option after hardware checks. The launcher
sets both `G955N_DIRECT_PANEL_TRIAL=1` and `G955N_DRM_KMS=1`; the panel lease and
fullscreen composition policy remain required. Other X11 windows keep their
existing transport. Logout releases the DRM file and restores native fbdev.

Reboot recovery hashes the installed module, launcher, manifest, shell policy
and capability probe. For this route it checks driver ABI 1.x with minor >=1, PRIME import,
connected native DSI mode and DPMS, rather than a kernel-number allowlist. A
compatible kernel must still carry this DECON DRM driver and board option.
Missing capabilities or changed files explicitly restore the saved CPU-copy
session. Legacy Samsung-ioctl output retains its strict kernel qualification.
Compatibility checks do not certify an arbitrary future kernel's stability.

## Verification

* `tests/check_drm_output.c` runs the actual presenter against fake KMS calls:
  DMA-BUF identity, bounded caching, page-event retirement, off-panel waiting,
  and ambiguous/failing submissions.
* `tests/check_drm_flip_lifetime.py` executes the production kernel callbacks
  against a fake panel: no off-panel success, resume, cancellation on close,
  queued work after cancellation and failure reference accounting.
* `scanout-test.c` is a hardware-only fixture. It CPU-fills three test buffers
  once, imports them through PRIME and presents 90 frames. Its deliberate
  test-pattern writes are not part of the production presentation path.
* Python tests cover capability-based boot retention, changed probe detection,
  missing-interface recovery and the existing legacy kernel guards.

Actual device results and remaining limits are in
[`docs/VALIDATION.md`](../../docs/VALIDATION.md). Kernel build success, CPU
measurements and flip events do not establish optical frame rate or physical
finger-to-panel latency.
