# Unapplied proposals

The build runner applies only `patches/*.patch`. Files here are intentionally
excluded from normal builds. The hidepid alias candidate retains this old
kernel's PID-namespace-wide policy and does not provide the per-mount isolation
expected by modern systemd ProtectProc. Do not apply it as a complete fix.

The diagnostic builder selects reviewed subsets explicitly. Proposal0053 is
opted in only on the Korean SM-G955N DT by `--usb-gadget-sleep-quiesce` and keeps
the existing host-mode policy. Kernel55 USB acceptance is recorded in
`docs/VALIDATION.md`; USB resume success alone does not qualify the GNOME
presentation path or all phone hardware.
