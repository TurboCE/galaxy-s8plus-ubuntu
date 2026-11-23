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

The key handler blanks the panel before requesting system suspend, while the
session can still process X11 requests. It verifies hardware blanking within
two seconds and cancels the request if blanking fails. A rejected suspend
request restores display power. Resume resets the X11 screen-saver idle counter
before forcing DPMS on, so the old idle time cannot immediately blank it again.
Neither action clears the GNOME screen lock or submits credentials.

Before blanking, the power-key handler honors Ubuntu's lock-on-suspend and
lockdown settings, requests the active session's normal logind lock if needed
and waits for its actual `LockedHint`. ScreenSaver.GetActive alone can be false
while credentials are still required. An incomplete lock cancels sleep and
restores the display. The sleep request uses logind's Suspend method so desktop
PrepareForSleep notifications and delay inhibitors remain part of the path.
No password, autologin setting or authentication result is changed.

## Linux 6.18 Wayland

The mainline GPIO key device uses `platform-gpio-keys-event` in
`/dev/input/by-path`. The power-key service reads the DECON DSI connector's
enabled state to confirm Mutter has blanked the panel before requesting sleep.
The service installer and syntax are shared with the Samsung kernel path.

Boot the mainline trial with `g955n.desktop_suspend=1` and omit
`systemd.mask=g955n-power-key.service` when enabling this service. The
qualification uses an RTC alarm for each short-press suspend test. A press
on a panel that has already resumed and lit up starts a new suspend cycle.

## Explicit USB recovery

`recover-usb.py --reset-peripheral` is a recovery operation, not a sleep hook
or a claim that the USB driver is fixed. Run it as root over the verified Wi-Fi
route after checking model, recovery materials and private backups. It requires
the powered SM-G955N peripheral role and exactly the existing Ethernet/serial
functions. It cycles the driver's peripheral/PHY path, preserves the enabled
functions and avoids forcing the peripheral back on after an unplug/host swap.
It never touches partitions, firmware, identifiers or calibration.

If launching over USB, use an independent systemd unit so loss of that transport
cannot interrupt cleanup, for example after installing the reviewed root-owned
file under `/usr/local/lib/g955n/`:

```
sudo systemd-run --collect --unit=g955n-usb-recover /usr/bin/python3 /usr/local/lib/g955n/recover-usb.py --reset-peripheral
```

Inspect its journal and verify USB from the host afterward. Device-side
`CONFIGURED` alone is insufficient: the host lost its interfaces in a real
kernel54 trial while the phone still reported configured. A composite-only
enable toggle failed; the full peripheral/PHY restart restored both the host
serial port and verified USB SSH without reboot. Resetting an already broken
controller still produced real command errors, which the tool reports. A
subsequent healthy reset produced zero new USB/kernel faults. Nothing is
silenced, and no unconditional reset is installed on every resume.
