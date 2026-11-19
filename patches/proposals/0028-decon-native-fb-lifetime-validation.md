# Native framebuffer lifetime candidate

The boot fb allocation is initially placed in win->dma_buf_data[0]. HWC updates
replace these slots and release the prior mapping/ION handle. ion_handle_destroy
drops its kernel-map references, while fb_info.screen_base and fix.smem_start
remain. Retaining a distinct boot allocation prevents that native fbcon/mmap/pan
reference from following a replaceable HWC slot. This is not attributed to the
prior kernel22 crashes, which occurred before HWC buffer trials.

Actual changed ownership/release helpers and mmap selection were extracted
into tests/check_decon_fb_lifetime.py's GCC ASan/UBSan model. The fixed version
passed128 three-plane transitions, persistent fb access/selection, teardown,
failed-probe and non-console cases. The unmodified ownership counterfactual
produces heap-use-after-free. Hardware timing/MMIO/fence behavior is not modeled.

Strict application uses the actual mmap-offset patch23 and full baseline
chain. Kernel24 compiled from a fresh Linux volume, with identical config and DT
to the earlier candidate. The packed BOOT passed device/readback checks and
native boot with matching GNU build-id; GDM, native mmap presenter and Wi-Fi
returned, taint0. Full HWC handoff/presentation is still pending at this checkpoint.

The source remains an explicit proposal, not automatically selected by the
regular experimental patch glob. build_diagnostic_kernel.py --native-fb-owner
selects it deliberately. Source/binaries/logs and actual deployment receipts are
tracked separately; private addresses/identifiers/backups stay out of Git.

Later checkpoint: two bounded native HWC panel runs completed with real present
fences, active DECON/DSIM frames, restored CPU desktop and unchanged taint0.
This exercises the native-to-HWC ownership transition but not long-term stability.
