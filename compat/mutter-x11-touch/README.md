# X11 touch replay in Mutter 46

The SM-G955N uses sec_touchscreen, Linux evdev, libinput, Xorg XI2 and Mutter
before GNOME Shell handles the resulting event. The installed Ubuntu Mutter
already includes [the upstream repick fix](https://gitlab.gnome.org/GNOME/mutter/-/merge_requests/4322),
which treats incoming pointer-emulated touchscreen events as absolute input.

Cursor visibility can cause a separate Clutter repick without an input event.
During a touch-emulated press, that repick loses the absolute-input flag even
though the press still owns an implicit grab. Clearing the actor sends a leave
and cancels the click before Xorg delivers release. The patch keeps the
absolute-input decision for automatic repicks while an emulated press is
active. It stores the state with the grab and clears it when the grab is
cleaned up. The picker still tests the actual coordinates and handles a
genuine actor change. GNOME Shell can continue to use its normal click and
login handlers.

The patch applies after the Ubuntu 24.04 patches for Mutter
46.2-1ubuntu0.24.04.18. Obtain the matching [Ubuntu source package](https://launchpad.net/ubuntu/+source/mutter/46.2-1ubuntu0.24.04.18).
The build helper verifies all three source files, extracts and applies the
patch, then builds only the Clutter shared library and its dependencies.
Run it in an Ubuntu 24.04 ARM64 builder with the Mutter build dependencies,
or on amd64 with the ARM64 development libraries and the repository's cross
compiler configuration. Use separate source-archive and new output directories.

```sh
compat/mutter-x11-touch/build.sh SOURCE_ARCHIVE_DIR NEW_OUTPUT_DIR
python3 tests/check_mutter_x11_touch.py UNMODIFIED_UBUNTU_SOURCE_TREE
```

The fixture exercises the original and patched conditions for a repick with
no input event, real input, native touch, and a completed press.

The deployment helper expects the matching stock library on the SM-G955N.
It verifies the current package/version, source library hash and exported
ELF interface, keeps a stock backup and uses atomic replacement. Use the
candidate's reviewed SHA256 with `install.py --install LIBRARY --sha256 HASH`.
The next normal graphical session loads the candidate. Use
`install.py --restore --sha256 HASH` to restore the saved stock library.
Mutter package upgrades may replace this local patch. The installer requires
review for a new package version, and the repository does not ship binaries.
