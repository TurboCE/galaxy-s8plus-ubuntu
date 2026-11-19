import importlib.util
from pathlib import Path
import unittest
import tempfile
p=Path(__file__).resolve().parents[1]/'scripts/decode_kernel_panic.py'
s=importlib.util.spec_from_file_location('decoder',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
B=b'Linux version 4.4.111-g955n-ubuntu (builder) #27'
MAP=m.map_symbols('ffffff8008001000 T first\nffffff8008001100 T safe\nffffff8008001200 T next\nffffff8008001300 T last\n')
class PanicDecoder(unittest.TestCase):
 def test_latest_banner_mismatch_never_uses_older_matching(self):
  r=m.analyze(B+b'\nKernel panic old\nLinux version other #28\n',B,MAP);self.assertEqual(r['status'],'unmatched')
 def test_old_faults_and_following_loader_excluded(self):
  raw=b'Linux version old\nKernel panic old\n'+B+b'\nokay\n[0: 0.43] Samsung S-Boot 4.0\nKernel panic loader-residue\n'
  r=m.analyze(raw,B,MAP);self.assertEqual(r['faults'],[]);self.assertEqual(r['older_banners_excluded'],1)
 def test_corrupt_or_missing_banner_refused(self):
  for raw in (b'Kernel panic without banner',B.replace(b'version',b'versioN')):
   self.assertEqual(m.analyze(raw,B,MAP)['status'],'unmatched')
 def test_no_offset_does_not_guess(self):
  r=m.analyze(B+b'\nKernel panic in: ffffff8008003000\n',B,MAP);self.assertEqual(r['relocation_status'],'unavailable');self.assertEqual(r['panic_callers'],[])
 def test_canary_return_boundary_resolves_previous_function(self):
  raw=B+b'\nKernel loaded at: 0x80170000, offset from compile-time address 2000\nKernel panic - not syncing: stack-protector: Kernel stack is corrupted in: ffffff8008003200\n'
  r=m.analyze(raw,B,MAP);self.assertEqual(r['panic_callers'][0]['callsite']['symbol'],'safe');self.assertEqual(r['panic_callers'][0]['callsite']['offset'],'0xfc')
 def test_conflicting_explicit_offsets_refused(self):
  raw=B+b'\nKernel loaded at: 0x8000, offset from compile-time address 2000\nKernel loaded at: 0x8000, offset from compile-time address 3000\n'
  self.assertEqual(m.analyze(raw,B,MAP)['relocation_status'],'conflicting-or-invalid-evidence')
 def test_unaligned_offset_refused(self):
  raw=B+b'\nKernel loaded at: 0x8000, offset from compile-time address 2001\n'
  self.assertEqual(m.analyze(raw,B,MAP)['relocation_status'],'conflicting-or-invalid-evidence')
 def test_two_symbol_relocation_agreement(self):
  raw=B+b'\nPC is at first+0x14/0x100\nLR is at safe+0x18/0x100\npc : [<ffffff8008003014>] lr : [<ffffff8008003118>] pstate: 0\n'
  r=m.analyze(raw,B,MAP);self.assertEqual(r['relocation_status'],'verified');self.assertEqual(r['relocation'],'0x2000')
 def test_disagreeing_pc_lr_refused(self):
  raw=B+b'\nPC is at first+0x14/0x100\nLR is at safe+0x18/0x100\npc : [<ffffff8008003014>] lr : [<ffffff8008004118>]\n'
  self.assertEqual(m.analyze(raw,B,MAP)['relocation_status'],'conflicting-pc-lr-evidence')
 def test_later_boot_with_damaged_banner_cannot_select_older_boot(self):
  raw=B+b'\nKernel panic old\n[0: 0.43] Samsung S-Boot 4.0\nLinUx versioN damaged\nKernel panic newer\n[0: 0.43] Samsung S-Boot 4.0\n'
  self.assertEqual(m.analyze(raw,B,MAP)['status'],'unmatched')
 def test_report_cannot_replace_raw_capture(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   with self.assertRaises(ValueError):m.validate_output(root/'capture',root/'kernel',root/'capture')
 def test_report_cannot_change_matching_image(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'kernel').mkdir()
   with self.assertRaises(ValueError):m.validate_output(root/'capture',root/'kernel',root/'kernel'/'System.map')
 def test_report_outside_matching_image_is_allowed(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);m.validate_output(root/'capture',root/'kernel',root/'report.json')
 def test_unknown_symbol_cannot_supply_relocation(self):
  raw=B+b'\nPC is at absent+0x14/0x100\nLR is at safe+0x18/0x100\npc : [<ffffff8008003014>] lr : [<ffffff8008003118>]\n'
  self.assertEqual(m.analyze(raw,B,MAP)['relocation_status'],'unavailable')
if __name__=='__main__':unittest.main()
