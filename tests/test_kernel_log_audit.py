import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('audit', Path(__file__).resolve().parents[1] / 'scripts/kernel_log_audit.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class KernelLogAudit(unittest.TestCase):
    def test_unavailable_logs_are_not_clean(self):
        for text in ('', 'dmesg: klogctl: Permission denied', '<6>[99.0] late capture'):
            self.assertEqual(module.audit(text)['status'], 'incomplete')

    def test_error_at_notice_priority_is_caught_by_trace(self):
        text = '<6>[0] Linux version 4.4.111\n<6>[5] Internal error: Oops: 96000004\n'
        self.assertEqual(module.audit(text)['status'], 'findings')

    def test_warnings_require_review(self):
        result = module.audit('<6>[0] Linux version 4.4.111\n<4>[1] regulator: supply missing\n<3>[2] probe failed\n')
        self.assertEqual(result['warning_lines'], [2])
        self.assertEqual(result['error_lines'], [3])

    def test_capture_without_findings_is_scoped(self):
        result = module.audit('<6>[0] Linux version 4.4.111\n<6>[1] boot completed\n')
        self.assertEqual(result['status'], 'no_findings_in_capture')
        self.assertIn('Captured log only', result['scope'])
