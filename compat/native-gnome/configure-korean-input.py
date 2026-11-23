#!/usr/bin/python3
"""Enable two-set Hangul in the SM-G955N owner's GNOME session."""

import argparse
import os
import shlex
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from gi.repository import Gio, GLib


def install_engine(binary):
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    root = data / "g955n-hangul-osk"
    component_dir = root / "component"
    component_path = f"{component_dir}:/usr/share/ibus/component"
    if not root.is_absolute() or any(char in str(root) for char in ':\\"\n\r'):
        raise SystemExit("The IBus component path cannot be represented safely.")

    engine = root / "ibus-engine-hangul"
    component = ET.parse("/usr/share/ibus/component/hangul.xml")
    command = component.find("exec")
    if command is None or command.text != "/usr/libexec/ibus-engine-hangul --ibus":
        raise SystemExit("The Ubuntu Hangul component layout has changed.")
    command.text = f"{shlex.quote(str(engine))} --ibus"

    component_dir.mkdir(parents=True, exist_ok=True)
    staging = root / "ibus-engine-hangul.new"
    shutil.copyfile(binary, staging)
    staging.chmod(0o755)
    staging.replace(engine)
    component.write(component_dir / "hangul.xml", encoding="utf-8")

    service = "org.freedesktop.IBus.session.GNOME.service"
    dropin = config / "systemd/user" / f"{service}.d" / "59-g955n-hangul-osk.conf"
    dropin.parent.mkdir(parents=True, exist_ok=True)
    escaped_path = component_path.replace("%", "%%")
    dropin.write_text(f'[Service]\nEnvironment="IBUS_COMPONENT_PATH={escaped_path}"\n')
    subprocess.run(
        ["ibus", "write-cache"],
        env={**os.environ, "IBUS_COMPONENT_PATH": component_path},
        check=True,
    )
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "restart", service], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, help="the locally built OSK-compatible engine")
    args = parser.parse_args()
    if os.geteuid() == 0 or not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        raise SystemExit("Run as the logged-in Ubuntu desktop user.")
    if b"SM-G955N" not in Path("/proc/device-tree/model").read_bytes():
        raise SystemExit("This configuration targets the SM-G955N.")

    hangul = Gio.Settings.new("org.freedesktop.ibus.engine.hangul")
    hangul.set_string("hangul-keyboard", "2")
    hangul.set_string("initial-input-mode", "hangul")

    inputs = Gio.Settings.new("org.gnome.desktop.input-sources")
    sources = inputs.get_value("sources").unpack()
    source = ("ibus", "hangul")
    if source not in sources:
        inputs.set_value("sources", GLib.Variant("a(ss)", sources + [source]))
    Gio.Settings.sync()
    if args.engine:
        install_engine(args.engine)


if __name__ == "__main__":
    main()
