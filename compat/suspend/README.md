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

Run `dconf update` and check the effective GNOME power settings on both the
desktop and greeter before unmasking `sleep.target` and `suspend.target`.
User dconf overrides take precedence over these defaults. Manual GNOME
suspend uses the normal logind request and enters `freeze` via systemd.
The GNOME profile disables unattended suspend on AC and battery. It also
disables GNOME's power-button shutdown dialog. The kernel still uses the
physical button as a wake source. Display idle and screen locking are
separate GNOME settings.

The image builder retains the initial masks. To return an enabled handset to
that baseline, mask the two targets again and remove the installed GNOME
profile files followed by `dconf update`.
