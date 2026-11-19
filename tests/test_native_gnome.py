import importlib.util
from pathlib import Path
import unittest
BASE=Path(__file__).resolve().parents[1]/'compat/native-gnome'
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
prepare=module('native_properties',BASE/'prepare-properties.py')
session=module('native_session',BASE/'session.py')
class NativeGnome(unittest.TestCase):
 def test_complete_cmdline_and_vendor_inputs(self):
  text=prepare.snapshot('ro.hardware.egl=mali\n','ro.board.platform=exynos5\n','x'*1600+' androidboot.hardware=samsungexynos8895')
  self.assertIn('ro.hardware=samsungexynos8895\n',text)
  self.assertIn('ro.board.platform=exynos5\n',text)
 def test_wrong_platform_rejected(self):
  with self.assertRaises(RuntimeError):prepare.snapshot('','ro.board.platform=other','androidboot.hardware=samsungexynos8895')
 def test_no_invented_ready_or_platform(self):
  with self.assertRaises(RuntimeError):prepare.snapshot('','ro.board.platform=exynos5','')
  text=prepare.snapshot('','ro.board.platform=exynos5','androidboot.hardware=samsungexynos8895')
  self.assertNotIn('hwservicemanager.ready',text)
 def test_gpu_environment_keeps_auth_and_removes_software_force(self):
  old={'XAUTHORITY':'/run/user/1000/gdm/Xauthority','LIBGL_ALWAYS_SOFTWARE':'1','LD_PRELOAD':'bad','DISPLAY':':0'}
  env=session.environment(old)
  self.assertEqual(env['XAUTHORITY'],old['XAUTHORITY']);self.assertEqual(env['COGL_RENDERER'],'EGL_XLIB')
  self.assertNotIn('LIBGL_ALWAYS_SOFTWARE',env);self.assertNotIn('LD_PRELOAD',env)
  self.assertEqual(old['LIBGL_ALWAYS_SOFTWARE'],'1')
 def test_no_blanket_vendor_ownership_or_musl_tls_quirk(self):
  self.assertNotIn('HYBRIS_GRALLOC1_RELEASE_IMPLY_DELETE',session.ENV)
  self.assertNotIn('HYBRIS_PTHREAD_KEY_ZERO_VALID',session.ENV)
if __name__=='__main__':unittest.main()
