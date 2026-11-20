# Manual GNOME suspend on SM-G955N

Install the policy only after confirming that the running SM-G955N kernel
provides the WLAN wake opt-in and DPU0 retention properties listed in the
service drop-in. Verify the GPIO keys and RTC wakeup settings along with
an actual timed RTC wake on that kernel.

| File | Destination |
| --- | --- |
| `60-g955n-suspend-to-idle.conf` | `/etc/systemd/sleep.conf.d/` |
| `60-g955n-require-suspend-kernel.conf` | `/etc/systemd/system/systemd-suspend.service.d/` |
| `60-g955n-manual-suspend` | `/etc/dconf/db/local.d/` and `/etc/dconf/db/gdm.d/` |
| `60-g955n-wake-report` (optional, executable) | `/usr/lib/systemd/system-sleep/` |
| `g955n-power-key.py` | `/usr/local/lib/g955n/` |
| `g955n-power-key.service` | `/etc/systemd/system/` |

Run `dconf update` and check the effective GNOME power settings on both the
desktop and greeter before unmasking `sleep.target` and `suspend.target`.
User dconf overrides take precedence over these defaults. Manual GNOME
suspend uses the normal logind request and enters `freeze` via systemd.
The GNOME profile disables unattended suspend on AC and battery. It also
disables GNOME's power-button shutdown dialog. The kernel still uses the
physical button as a wake source. Display idle and screen locking are
separate GNOME settings.

Enable `g955n-power-key.service` to connect the hardware power key to the
active GNOME session. With the screen on, a short press requests system
suspend. From a display-only blank, it wakes the screen. Holding the button
for about 1.4 seconds opens a Zenity Power Off confirmation with Cancel
selected by default. The popup has no countdown and is subject to GNOME's
screen lock. Install Ubuntu's `zenity` package for the confirmation dialog.

The service shares the GPIO input device. Display wake and the dialog run
with the session user's privileges. X11 wake uses DPMS and Wayland wake
uses Mutter's display power property. The wake action preserves locking.
With the wake-report hook installed, a kernel-reported power-key wake
also schedules a display request after systemd has resumed the session.

The optional hook clears the reserved sleep console and limits messages
printed on it during the switch. Kernel messages remain in the ring
buffer, and the previous console level is restored after resume. The
hook also records the kernel-reported wake IRQ in
`journalctl -u systemd-suspend.service`. Pair it with the kernel suspend
entry, exit and RTC handler messages. A PMIC IRQ by itself does not
identify which PMIC event woke the handset.

The image builder retains the initial masks. To return an enabled handset to
that baseline, mask the two targets again and remove the installed GNOME
profile files followed by `dconf update`. The key service can be disabled
independently with `systemctl disable --now g955n-power-key.service`.
