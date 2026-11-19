#!/usr/bin/env python3
"""Build-only check of the initramfs bytes linked into the actual kernel Image."""
import argparse
import json
from pathlib import Path
import runpy


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel-dir', type=Path, required=True)
    a = p.parse_args()
    pack = runpy.run_path(str(Path(__file__).with_name('pack_boot.py')))
    try:
        kernel = (a.kernel_dir/'Image.unqualified').read_bytes()
        config = (a.kernel_dir/'kernel.config').read_bytes()
        pack['verify_embedded_config'](kernel, config)
        result = pack['verify_builtin_initramfs'](kernel, config, (a.kernel_dir/'System.map').read_text())
    except (ValueError, OSError) as error:
        print(json.dumps({'validated': False, 'error': str(error)}))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
