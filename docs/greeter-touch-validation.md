# GDM touch login checkpoint, 2026-11-19

The owner reproduced an account tap that focused the row without revealing the
password prompt. Account-tile-only instrumentation confirmed button press,
leave/re-entry (pressed true/false/true), then release with no clicked signal.
The stock St.Button pointer-device lifetime explains this failed release.

A GDM-only pinned resource repair handles a still-pressed primary-button release
only when the corresponding press came from the same device, release is inside
the mapped/reactive tile and no native click occurred. Authentication is intact.
Ten event fixtures and generated JavaScript syntax checks passed.

After installing this repair and restarting GDM, the owner confirmed touch
account selection, password entry and desktop login. The overlay is persistent;
a separate cold-boot touchscreen regression is still pending. No automated Return
key or autologin was used in this acceptance. Private account-event and login
records remain under artifacts/greeter.

The resulting desktop session was ubuntu-g955n but its GLES preflight failed
(eglGetDisplay), so the existing software fallback started. This login pass is
not a GPU acceptance. Investigating the cold-boot graphics readiness failure is
separate, ongoing work. Kernel taint was zero at this checkpoint; that does not
qualify long-term kernel stability.

The subsequent GPU failure was traced to original SYSTEM not being mounted after
reboot, leaving the existing vendor library symlinks dangling. Enabling the
read-only GPU preparation unit before display-manager restored the real GLES
helper: exit0, actual Mali-G71. The already-running software desktop was not
replaced during this check. A new full login/cold-boot GPU session remains to
verify; this helper pass is not evidence that the old running shell changed.

After the deliberate kernel26 reboot, the owner confirmed smooth account/password
entry by touch and desktop login again. Boot ordering of read-only SYSTEM
preparation was verified before GDM. This new ordinary GNOME shell reports
Mali-G71, loads private EGL/Mali/Exynos gralloc without swrast, and passes three
client/overlay/calendar trials. The former software-fallback boundary above
applies to the earlier kernel25 login, not this kernel26 session.
