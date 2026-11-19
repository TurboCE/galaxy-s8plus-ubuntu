import hashlib
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE=SourceFileLoader('panel_review',str(Path(__file__).resolve().parents[1]/'compat/run-panel-trial.py')).load_module()

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

class PanelReviewGuard(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
  self.before=(MODULE.BASE,MODULE.PREFIX)
  MODULE.BASE=self.root/'staged';MODULE.BASE.mkdir();MODULE.PREFIX=self.root/'prefix';MODULE.PREFIX.mkdir()
  for name in MODULE.FILES:(MODULE.BASE/name).write_bytes(('reviewed fixture '+name).encode())
  library=MODULE.PREFIX/'lib';library.mkdir();(library/'private.so.1').write_bytes(b'not executed fixture')
  (library/'private.so').symlink_to('private.so.1')
  package={'target':'SM-G955N','destination':str(MODULE.PREFIX),'files':{'lib/private.so.1':{'sha256':sha(library/'private.so.1')}},'symlinks':{'lib/private.so':'private.so.1'}}
  self.package=MODULE.PREFIX/'manifest.json';self.package.write_text(json.dumps(package))
  self.data={'target':'SM-G955N','scope':'exclusive-hwc-panel-8s','files':{n:sha(MODULE.BASE/n) for n in MODULE.FILES},'compositor_manifest_sha256':sha(self.package)}
  self.manifest=self.root/'review.json';self.write()
 def tearDown(self):
  MODULE.BASE,MODULE.PREFIX=self.before;self.temp.cleanup()
 def write(self):self.manifest.write_text(json.dumps(self.data));self.expected=sha(self.manifest)
 def verify(self):return MODULE.review(self.manifest,self.expected)
 def test_exact_scope_and_all_source_library_links(self):self.verify()
 def test_source_mutation_rejected(self):
  (MODULE.BASE/'android-runtime-namespace.py').write_text('changed')
  with self.assertRaisesRegex(RuntimeError,'Changed reviewed input'):self.verify()
 def test_library_mutation_rejected(self):
  (MODULE.PREFIX/'lib/private.so.1').write_bytes(b'changed')
  with self.assertRaisesRegex(RuntimeError,'Changed compositor ELF'):self.verify()
 def test_library_link_escape_rejected(self):
  link=MODULE.PREFIX/'lib/private.so';link.unlink();link.symlink_to('../../outside')
  with self.assertRaisesRegex(RuntimeError,'Changed/escaping'):self.verify()
 def test_other_scope_and_missing_source_rejected(self):
  self.data['scope']='cpu-buffer-64x64-no-display';self.write()
  with self.assertRaisesRegex(RuntimeError,'Wrong/incomplete'):self.verify()
  self.data['scope']='exclusive-hwc-panel-8s';self.data['files'].pop('run-panel-trial.py');self.write()
  with self.assertRaisesRegex(RuntimeError,'Wrong/incomplete'):self.verify()
 def test_client_fixture_verified_before_display_change(self):
  client=MODULE.BASE/'es2gears-wayland-safe';client.write_bytes(b'reviewed client')
  self.data.update(client_probe='es2gears-wayland-safe',client_probe_sha256=sha(client));self.write()
  _,package=self.verify();self.assertEqual(package['client_command_path'],str(client))
  client.write_bytes(b'changed')
  with self.assertRaisesRegex(RuntimeError,'Changed client fixture'):self.verify()
 def test_arbitrary_client_path_rejected(self):
  self.data.update(client_probe='/usr/bin/arbitrary',client_probe_sha256='0'*64);self.write()
  with self.assertRaisesRegex(RuntimeError,'Changed client fixture'):self.verify()
 def test_longer_scope_cannot_run_without_its_fixed_gtk_client(self):
  self.data['scope']='exclusive-hwc-panel-gtk20s';self.write()
  with self.assertRaisesRegex(RuntimeError,'GTK20 scope'):self.verify()
 def test_gnome_scope_requires_its_fixed_client(self):
  self.data['scope']='exclusive-hwc-panel-gnome20s';self.write()
  with self.assertRaisesRegex(RuntimeError,'GNOME20 scope'):self.verify()
 def test_system_bus_rejected_for_pattern_scope(self):
  self.data['native_system_bus']=True;self.write()
  with self.assertRaisesRegex(RuntimeError,'Native system bus'):self.verify()
 def test_touch_cannot_enable_input_in_pattern_scope(self):
  self.data['touch_input']=True;self.write()
  with self.assertRaisesRegex(RuntimeError,'Touch requires reviewed GNOME'):self.verify()
 def gnome_review(self,scope,touch=False,host=False):
  package=json.loads(self.package.read_text());package['features']={'private_x11_candidate':True};self.package.write_text(json.dumps(package))
  self.data.update(scope=scope,client_probe='gnome-x11',client_probe_sha256='a'*64,xwayland_sha256='a'*64,dbus_run_session_sha256='a'*64,native_system_bus=True,compositor_manifest_sha256=sha(self.package))
  if host:self.data['host_pid_client']=True
  if touch:
   (MODULE.BASE/'seatd').write_bytes(b'fixed seat broker');self.data.update(touch_input=True,seatd_sha256=sha(MODULE.BASE/'seatd'))
  self.write();original=MODULE.digest
  with patch.object(MODULE,'digest',side_effect=lambda p:'a'*64 if str(p) in ('/usr/bin/gnome-shell','/usr/bin/Xwayland','/usr/bin/dbus-run-session') else original(p)):
   return self.verify()
 def test_gnome20_accepts_explicit_real_bus(self):
  _,package=self.gnome_review('exclusive-hwc-panel-gnome20s');self.assertTrue(package['native_system_bus']);self.assertEqual(package['observation_seconds'],20)
 def test_gnome60_requires_real_touch(self):
  with self.assertRaisesRegex(RuntimeError,'GNOME60 scope'):self.gnome_review('exclusive-hwc-panel-gnome60s')
 def test_gnome60_accepts_reviewed_broker_and_touch(self):
  _,package=self.gnome_review('exclusive-hwc-panel-gnome60s',True);self.assertTrue(package['touch_input']);self.assertEqual(package['observation_seconds'],60)
 def test_popup_proof_requires_its_composite_fixture(self):
  self.data['popup_probe']=True;self.write()
  with self.assertRaisesRegex(RuntimeError,'Popup proof'):self.verify()
 def test_host_pid_flag_rejected_outside_its_scope(self):
  self.data['host_pid_client']=True;self.write()
  with self.assertRaisesRegex(RuntimeError,'Host PID entry'):self.verify()
 def test_host_scope_requires_explicit_host_client(self):
  with self.assertRaisesRegex(RuntimeError,'Host PID entry'):self.gnome_review('exclusive-hwc-panel-host-gnome20s',True)
 def test_host_scope_requires_real_input(self):
  with self.assertRaisesRegex(RuntimeError,'Host GUI requires'):self.gnome_review('exclusive-hwc-panel-host-gnome20s',False,True)
 def test_host_scope_accepts_reviewed_input_and_client(self):
  _,package=self.gnome_review('exclusive-hwc-panel-host-gnome20s',True,True);self.assertTrue(package['host_pid_client']);self.assertEqual(package['observation_seconds'],20)
 def native_review(self,process_pin=True,diagnostic=False):
  package=json.loads(self.package.read_text());package['features']={'private_x11_candidate':True};self.package.write_text(json.dumps(package))
  client=MODULE.BASE/'x11-pixel-probe';client.write_bytes(b'fixed native pixel fixture')
  self.data.update(scope='native-x11-pixels-8s',client_probe='native-x11-pixels',client_probe_sha256=sha(client),native_xorg_sha256='a'*64,compositor_manifest_sha256=sha(self.package))
  if process_pin:self.data.update(native_xorg_pid=123,native_xorg_starttime='456')
  if diagnostic:self.data['client_debugger']=True
  self.write();original=MODULE.digest
  with patch.object(MODULE,'digest',side_effect=lambda p:'a'*64 if str(p)=='/usr/lib/xorg/Xorg' else original(p)):return self.verify()
 def test_native_x_requires_fixed_fixture(self):
  self.data['scope']='native-x11-pixels-8s';self.write()
  with self.assertRaisesRegex(RuntimeError,'Native X11 requires'):self.verify()
 def test_native_x_requires_pinned_server_process(self):
  with self.assertRaisesRegex(RuntimeError,'process pin'):self.native_review(False)
 def test_native_x_rejects_interposed_qualification(self):
  with self.assertRaisesRegex(RuntimeError,'excludes diagnostic'):self.native_review(True,True)
 def test_native_x_review_keeps_headless_scope(self):
  _,package=self.native_review();self.assertTrue(package['native_x11']);self.assertFalse(package['native_system_bus']);self.assertEqual(package['observation_seconds'],8)
if __name__=='__main__':unittest.main()
