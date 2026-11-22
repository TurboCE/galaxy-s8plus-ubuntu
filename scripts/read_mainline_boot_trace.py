#!/usr/bin/env python3
"""Read the SM-G955N mainline boot trace from a verified TWRP connection."""

import argparse
import os
from pathlib import Path
import re
import subprocess


TRACE_HEADER = b"G955N61\n"
STAGES = {
    b"LOADER1\n": "uniLoader relocation entry",
    b"LOADER2\n": "uniLoader C entry",
    b"SOC-OK!\n": "board initialization returned",
    b"FB-NEXT\n": "framebuffer probe about to start",
    b"FDT-OK!\n": "device tree prepared",
    b"HANDOFF\n": "kernel handoff",
    b"LINUX!!\n": "ARM64 kernel entry",
}
PMSG_PATH = "/sys/fs/pstore/pmsg-ramoops-0"
PMSG_CAPACITY = 16 * 1024


def stages(data):
    results = []
    _, header, records = data.rpartition(TRACE_HEADER)
    if header:
        for offset in range(0, len(records), 8):
            name = STAGES.get(records[offset : offset + 8])
            if not name:
                break
            results.append(name)
    if re.search(rb"\bLinux version 6\.18(?:\b|[-.])", data):
        results.append("Linux 6.18 console")
    if b"SM-G955N INITRAMFS OK" in data or b"SM-G955N UFS INIT" in data:
        results.append("Linux 6.18 initramfs")
    if b"g955n-ufs: UFS USERDATA found" in data:
        results.append("embedded UFS USERDATA detected")
    if b"SM-G955N UFS UBUNTU ROOT OK (read-only)" in data:
        results.append("installed Ubuntu root verified read-only")
    return results


def read_pmsg(adb):
    subprocess.run(
        adb + ["shell", 'test "$(id -u)" = 0 && test -n "$(getprop ro.twrp.version)" '
               '&& getprop ro.bootloader | grep -q "^G955N"'],
        capture_output=True, check=True, timeout=10,
    )
    probe = subprocess.run(
        adb + ["shell", f"test -r {PMSG_PATH}"],
        capture_output=True, timeout=10,
    )
    if probe.returncode == 1:
        return None
    probe.check_returncode()
    data = subprocess.run(
        adb + ["exec-out", "head", "-c", str(PMSG_CAPACITY + 1), PMSG_PATH],
        capture_output=True, check=True, timeout=10,
    ).stdout
    if len(data) > PMSG_CAPACITY:
        raise ValueError("Recovery pmsg exceeds the verified SM-G955N capacity")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", required=True)
    parser.add_argument("--save", type=Path, help="save raw recovery output to a new private file")
    args = parser.parse_args()
    try:
        data = read_pmsg([args.adb, "-s", args.serial])
    except (OSError, ValueError, subprocess.SubprocessError):
        raise SystemExit("Could not read pmsg from the verified SM-G955N TWRP device")

    if data is None:
        print("TWRP has no readable previous-boot pmsg record")
        return
    if args.save:
        fd = os.open(args.save, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(data)
    found = stages(data)
    print(" → ".join(found) if found else "Recovery pmsg has no SM-G955N 6.18 stage markers")


if __name__ == "__main__":
    main()
