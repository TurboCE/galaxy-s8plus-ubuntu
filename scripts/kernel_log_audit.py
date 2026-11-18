#!/usr/bin/env python3
"""Audit a captured dmesg --raw log; never certify untested hardware."""
import argparse
import json
from pathlib import Path
import re

PRIORITY = re.compile(r'^<(\d+)>')
FAILURE = re.compile(r'Kernel panic|Internal error:|Unable to handle kernel|BUG:|Oops:|Call trace:|WARNING:|soft lockup|hard LOCKUP|rcu.*stall', re.I)


def audit(text):
    errors, warnings, traces = [], [], []
    priorities = 0
    for number, line in enumerate(text.splitlines(), 1):
        match = PRIORITY.match(line)
        if match:
            priorities += 1
            level = int(match.group(1)) % 8
            if level <= 3:
                errors.append(number)
            elif level == 4:
                warnings.append(number)
        if FAILURE.search(line):
            traces.append(number)
    boot_start = bool(re.search(r'\bLinux version\s+\d', text))
    incomplete = not priorities or not boot_start
    status = ('findings' if errors or warnings or traces else
              'incomplete' if incomplete else 'no_findings_in_capture')
    return dict(status=status, error_lines=errors, warning_lines=warnings,
                trace_lines=traces, priority_entries=priorities,
                boot_start_present=boot_start,
                scope='Captured log only; not a hardware, suspend, or long-term stability qualification')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    args = parser.parse_args()
    report = audit(args.log.read_text(errors='replace'))
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'no_findings_in_capture' else 1


if __name__ == '__main__':
    raise SystemExit(main())
