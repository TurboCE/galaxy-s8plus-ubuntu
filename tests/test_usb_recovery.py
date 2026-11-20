#!/usr/bin/env python3
"""Failure/unplug boundaries of the explicit peripheral recovery operation."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('usb_recovery',
    Path(__file__).resolve().parents[1]/'compat/suspend/recover-usb.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.gadget, self.fsm = self.root/'gadget', self.root/'fsm'
        self.gadget.mkdir(); self.fsm.mkdir()
        self.online = self.root/'online'; self.online.write_text('1')
        for name, value in {'functions': 'cdc_ethernet,acm', 'enable': '1'}.items():
            (self.gadget/name).write_text(value)
        for name, value in {'id': '1', 'b_sess': '1', 'state': 'b_peripheral'}.items():
            (self.fsm/name).write_text(value)

    def reset(self, pause):
        return recovery.reset_peripheral(self.gadget, self.fsm, self.online, pause)

    def test_failed_wait_restores_peripheral(self):
        def failure(_):
            self.assertEqual((self.fsm/'b_sess').read_text(), '0')
            raise OSError('Injected wait failure')
        with self.assertRaises(OSError):
            self.reset(failure)
        self.assertEqual((self.fsm/'b_sess').read_text(), '1')

    def test_actual_unplug_or_host_swap_is_not_overwritten(self):
        for path in (self.online, self.fsm/'id'):
            self.online.write_text('1'); (self.fsm/'id').write_text('1')
            (self.fsm/'b_sess').write_text('1')
            self.assertFalse(self.reset(lambda _: path.write_text('0')))
            self.assertEqual((self.fsm/'b_sess').read_text(), '0')

    def test_wrong_function_or_role_refused_before_write(self):
        for path, value in ((self.gadget/'functions', 'mtp'), (self.fsm/'id', '0')):
            original = path.read_text(); path.write_text(value)
            with self.assertRaises(RuntimeError):
                self.reset(lambda _: self.fail('Unexpected pause'))
            self.assertEqual((self.fsm/'b_sess').read_text(), '1')
            path.write_text(original)


if __name__ == '__main__':
    unittest.main()
