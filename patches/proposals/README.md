# Unapplied proposals

The build runner applies only `patches/*.patch`. Files here are intentionally
excluded from normal builds. The hidepid alias candidate retains this old
kernel's PID-namespace-wide policy and does not provide the per-mount isolation
expected by modern systemd ProtectProc. Do not apply it as a complete fix.
