#!/usr/bin/env python3
"""Read-only: describe a staged, reviewed plugin/config installation as JSON.

Prints to stdout; does not install files, change ownership or start a service.
The installer must write the resulting manifest root-owned and run guard --check.
"""
import argparse
import json
from pathlib import Path
import runpy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-record', type=Path, required=True)
    parser.add_argument('--stage-root', type=Path, default=Path('/'))
    parser.add_argument('--guard', type=Path,
                        default=Path(__file__).with_name('g955n-wireplumber'))
    args = parser.parse_args()
    guard = runpy.run_path(str(args.guard), run_name='g955n_guard_constants')
    record = json.loads(args.build_record.read_text())
    if (record.get('ubuntu_source_version') != '1.0.5-1ubuntu3.3'
            or record.get('feature') != 'api.acp.disable-pro-audio'
            or not record.get('exported_symbol_abi_matches')
            or record.get('hardware_open_scope') != 'g955n-rdma0-playback-ucm-v2'
            or len(record.get('scope_patch_sha256', '')) != 64):
        raise SystemExit('Build record does not match the reviewed candidate')
    stage = args.stage_root.resolve()
    hashes = {}
    for target in guard['REQUIRED']:
        actual = stage / str(target).lstrip('/')
        hashes[str(target)] = guard['digest'](actual)
    if hashes[str(guard['PLUGIN'])] != record['candidate_sha256']:
        raise SystemExit('Staged plugin does not match the reviewed build record')
    print(json.dumps(dict(
        ubuntu_source_version=record['ubuntu_source_version'],
        feature=record['feature'], upstream_backport=record['upstream_backport'],
        candidate_sha256=record['candidate_sha256'],
        original_plugin_sha256=record['original_plugin_sha256'],
        plugin_search_mode='private-only',
        hardware_open_scope=record['hardware_open_scope'],
        scope_patch_sha256=record['scope_patch_sha256'],
        patched_source_files=record['patched_source_files'], files=hashes), indent=2))


if __name__ == '__main__':
    main()
