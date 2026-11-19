import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[1]/'scripts/build_diagnostic_kernel.py';s=importlib.util.spec_from_file_location('diag_kernel',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class DiagnosticConfig(unittest.TestCase):
 def test_only_cmdline_changes_and_slashes_survive(self):
  old='CONFIG_SMP=y\nCONFIG_CMDLINE="console=tty0 firmware_class.path=/vendor/firmware"\nCONFIG_PANIC_ON_OOPS=y\n'
  new=m.make_wfi_config(old);self.assertEqual(new.replace(' cpuidle.off=1',''),old);self.assertIn('/vendor/firmware',new)
 def test_existing_override_rejected(self):
  with self.assertRaises(ValueError):m.make_wfi_config('CONFIG_CMDLINE="cpuidle.off=0"\n')
 def test_no_or_duplicate_cmdline_rejected(self):
  for text in ['CONFIG_SMP=y\n','CONFIG_CMDLINE="a"\nCONFIG_CMDLINE="b"\n']:
   with self.assertRaises(ValueError):m.make_wfi_config(text)
if __name__=='__main__':unittest.main()
