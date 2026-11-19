import hashlib
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import tempfile
import unittest

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
if __name__=='__main__':unittest.main()
