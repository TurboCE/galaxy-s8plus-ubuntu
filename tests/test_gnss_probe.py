import importlib.util
from pathlib import Path
import hashlib
import os
from tempfile import TemporaryDirectory
import unittest
from unittest import mock
from xml.etree import ElementTree

probe = Path(__file__).resolve().parents[1] / 'compat/gnss/run-probe.py'
spec = importlib.util.spec_from_file_location('g955n_gnss_probe', probe)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

SOURCE = '''<?xml version="1.0" encoding="utf-8"?>
<glgps xmlns="http://www.glpals.com/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       xsi:schemaLocation="http://www.glpals.com/ glconfig.xsd">
  <hal PortName="lhd" NvStorageDir="/data/vendor/gps/" SuplEnable="true" />
  <gll WarmStandbyTimeout1Seconds="300" />
</glgps>
'''


class GnssConfiguration(unittest.TestCase):
    def test_vendor_namespace_is_not_reserialized(self):
        updated = module.make_config(SOURCE, Path('/run/g955n-example'))
        self.assertEqual(SOURCE.split('<hal ')[0], updated.split('<hal ')[0])
        self.assertIn('<gll WarmStandbyTimeout1Seconds="300" />', updated)
        self.assertNotIn('ns0:', updated)
        hal = ElementTree.fromstring(updated).find('{http://www.glpals.com/}hal')
        self.assertEqual(hal.attrib['NvStorageDir'], '/data/vendor/gps/')
        self.assertEqual(hal.attrib['CtrlPipe'], '/run/g955n-example/ctrl')
        self.assertEqual(hal.attrib['SuplEnable'], 'false')
        self.assertEqual(hal.attrib['SensorsEnable'], 'false')

    def test_refuses_to_open_the_hubs_serial_port(self):
        with self.assertRaisesRegex(ValueError, 'shared location hub'):
            module.make_config(SOURCE.replace('PortName="lhd"', 'PortName="/dev/ttyBCM"'),
                               Path('/run/g955n-example'))


class LtoCache(unittest.TestCase):
    def test_only_the_phones_configured_fresh_data_is_accepted(self):
        path = probe.with_name('lto.py')
        lto_spec = importlib.util.spec_from_file_location('gnss_lto', path)
        lto = importlib.util.module_from_spec(lto_spec)
        lto_spec.loader.exec_module(lto)
        config = b'XTRA_SERVER_1=http://gllto1.glpals.com/4day/v5/latest/lto2.dat\n'
        data = b'x' * 600
        metadata = {
            'config_sha256': hashlib.sha256(config).hexdigest(),
            'sha256': hashlib.sha256(data).hexdigest(),
            'source': 'https://gllto1.glpals.com/4day/v5/latest/lto2.dat',
            'downloaded_at': 99,
            'modified_at': 98,
        }
        self.assertTrue(lto.valid_metadata(metadata, data, config, 100))
        self.assertFalse(lto.valid_metadata(metadata, data, config, 100 + lto.VALIDITY))
        self.assertFalse(lto.valid_metadata(metadata, data + b'x', config, 100))
        with self.assertRaises(RuntimeError):
            lto.sources(b'XTRA_SERVER_1=http://unreviewed.invalid/4day/v5/latest/lto2.dat\n')


class HubReadiness(unittest.TestCase):
    def test_cold_start_waits_for_the_shared_fifo(self):
        lto = mock.Mock()
        with mock.patch.dict('sys.modules', {'lto': lto, 'run_probe': module}):
            serve_spec = importlib.util.spec_from_file_location('gnss_serve', probe.with_name('serve.py'))
            serve = importlib.util.module_from_spec(serve_spec)
            serve_spec.loader.exec_module(serve)

        with TemporaryDirectory() as temporary:
            state = mock.MagicMock(spec=Path)
            state.is_symlink.return_value = False
            state.stat.return_value.st_uid = 0
            fifo = Path(temporary) / 'hub.fifo'
            state.__truediv__.return_value = fifo
            with self.assertRaisesRegex(SystemExit, 'did not create'):
                serve.wait_for_hub(state, timeout=0)
            with mock.patch.object(serve.time, 'sleep', side_effect=lambda _: os.mkfifo(fifo)) as sleep:
                serve.wait_for_hub(state)
                sleep.assert_called_once()

            fifo.unlink()
            fifo.touch()
            with self.assertRaisesRegex(SystemExit, 'Unexpected type'):
                serve.wait_for_hub(state)


if __name__ == '__main__':
    unittest.main()
