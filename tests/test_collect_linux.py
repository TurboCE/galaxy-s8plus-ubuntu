import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import collect_linux
from serial_shell import SerialShell


class CollectLinuxTest(unittest.TestCase):
    def collect(self, wifi_boot):
        argv = ['collect_linux.py', '--host', 'usb', '--wifi-host', 'wifi',
                '--known-hosts', 'known-hosts', '--host-key-alias', 'g955n']
        requested = []

        def remote(args, **kwargs):
            host, command = args[-2:]
            requested.append((host, command))
            if command == collect_linux.IDENTIFY:
                boot = 'original' if host == 'usb' else wifi_boot
                output = f'6.18.0-g955n-usb-r58\nSamsung Galaxy S8+ (SM-G955N)\n{boot}\n'
                return subprocess.CompletedProcess(args, 0, output, '')
            code = 255 if host == 'usb' else 0
            return subprocess.CompletedProcess(args, code, '', '')

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with (patch.object(sys, 'argv', argv),
                  patch.object(collect_linux, 'ROOT', root),
                  patch.object(collect_linux.subprocess, 'run', side_effect=remote),
                  contextlib.redirect_stdout(io.StringIO())):
                collect_linux.main()
            report_path, = root.glob('inventory/*/linux.json')
            return json.loads(report_path.read_text()), requested

    def test_mainline_capture_resumes_over_wifi_on_same_boot(self):
        report, requested = self.collect('original')
        self.assertEqual(report['transport'], 'wifi_fallback')
        self.assertEqual(report['checks']['dmesg']['exit_code'], 0)
        self.assertEqual(requested[2:4], [
            ('wifi', collect_linux.IDENTIFY), ('wifi', 'dmesg --raw')])
        self.assertNotIn('original', report['identity']['stdout'])

    def test_capture_does_not_mix_logs_from_different_boots(self):
        report, requested = self.collect('replacement')
        self.assertEqual(report['transport'], 'ssh')
        self.assertEqual(report['checks']['dmesg']['exit_code'], 255)
        self.assertEqual(requested[-1], ('wifi', collect_linux.IDENTIFY))

    def test_mainline_usb_serial_is_accepted_without_matching_the_s9(self):
        with patch('serial_shell.os.open', side_effect=OSError('test open')) as open_port:
            with self.assertRaises(OSError):
                SerialShell('/dev/cu.usbmodemG955N6181')
            with self.assertRaises(ValueError):
                SerialShell('/dev/cu.usbmodemS9PLUS_00011')
        open_port.assert_called_once()
