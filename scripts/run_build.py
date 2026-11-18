#!/usr/bin/env python3
"""Execute an immutable snapshot of the build runner, without device access."""
import argparse
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('config', 'image'), default='config', nargs='?')
    args = parser.parse_args()
    script = Path(__file__).resolve().with_name('build_kernel.sh')
    environment = dict(os.environ, G955N_SCRIPT_SNAPSHOT='1')
    return subprocess.run(['bash', '-c', script.read_text(), str(script), args.mode],
                          env=environment).returncode


if __name__ == '__main__':
    raise SystemExit(main())
