# Current seven-requirement evidence audit

This is an incomplete-goal checkpoint. No requirement is removed or weakened by
this audit. The latest confirmed live kernel is27; neither packed28 nor29 is
installed. No active build remains. Worktree changes and evidence are preserved.

| Owner requirement | Evidence actually available | Remaining acceptance |
| --- | --- | --- |
| Boot, select account and enter GNOME by touch | Owner confirmed manual account/password/desktop after repaired GDM and a26 reboot; authentication/autologin settings unchanged | Repeated stable boots and long use; power-hang failures prevent overall pass |
| Real accelerated GNOME and fast touch response | Actual normal GNOME Mali-G71, EGL/Exynos gralloc, no swrast; three26 composition/popup passes; real27 Mali login | Physical response/latency and sustained application/display-power workload; commits/sec are not FPS |
| No kernel errors; fix real driver defects | Reproduced/fixed DPP metadata lifetime, pan/power serialization, QoS ordering and Ondemand lifetime source bugs; private real RCU/stack-check fault records | Actual initiating corruption remains unresolved.26/27 still hang;28/29 not deployed. Proposal32 improves a recovery path only |
| Accel, magnetic, pedometer and ambient-light operation | Earlier native accel/gyro records; pinned magnetic/step/light decoders; uninstalled accel/light SensorProxy prototype | Boot-time genuine firmware/calibration, reliable claims/cleanup, live magnetic/step/ALS and physical motion/light acceptance |
| Microphone and speaker | Bounded selected speaker PCM progress; scoped audio policy experiment | Acoustic speaker and microphone acceptance, stable routing and safe default policy. WirePlumber remains masked |
| LTE modem without driver errors | Original protected RADIO/calibration preserved; modem device nodes; no SIM supplied | Actual modem bootstrap/driver checks; native modem control. Later SIM registration, mobile-only data/reconnect; no-SIM is not a modem pass |
| Automatic rotation/brightness and normal Ubuntu toggles | Packed sensor backend work, raw backlight interface, checked Xorg/fbdev rotation source | Runtime screen rotation with correct touch mapping, genuine light response/backlight control, and actual Ubuntu enable/disable behavior |

Supporting state: docs/VALIDATION.md, greeter-touch-validation.md,
kernel26-power-investigation.md, ondemand-panel-lifetime.md,
compiler-reference-comparison.md, panic-decoder-and-safe-recovery.md and
native-rotation-requirements.md. Device records/images and addresses remain in
ignored private artifacts, not this document.

## Actual blocking condition

Repeated current checks find the dedicated G955N USB device but no console
prompt. Pinned SSH on both last-known Wi-Fi and USB networking times out.
Console interrupt, serial-carrier reset and an earlier mDNS lookup did not
restore a usable path. This is a connection/recovery block, not a live job wait.
The owner is away and explicitly cannot provide physical recovery for now.

No further BOOT write may proceed without live model/boot identity, a fresh
matching backup and protected-partition/readback checks. Those are unavailable
while the phone does not respond. Source fixes, matched28/29 images, decoder and
sanitizer fixtures are ready; more passing host tests would not validate the
missing hardware behavior or identify a new corrupting writer by themselves.

After genuine recovery/reconnection, first capture actual identity/previous
fault evidence and guard the staging interval against automatic screen blank.
Review and install one candidate with full BOOT verification, then test actual
GNOME/display-power behavior with a foreground host kernel capture and a reviewed
recovery guard. Preserve the separate28/29 source/config/compiler comparison.
Do not infer recovery from a visible USB descriptor alone.

HDMI/DisplayPort is deferred. S9+ remains separately managed; no S9+ operation is
part of this session. The seven core requirements above remain unfinished.
