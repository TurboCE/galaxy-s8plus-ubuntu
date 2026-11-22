import importlib.util
from pathlib import Path
import struct
import unittest
p=Path(__file__).resolve().parents[1]/'compat/sensor-iio-probe.py'
s=importlib.util.spec_from_file_location('ssp_probe',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class SensorRecords(unittest.TestCase):
 def test_accel_signed_xyz(self):
  r=m.decode_record('accelerometer_sensor',struct.pack('<3hQ',-4096,1,32767,123))
  self.assertEqual(r,{'raw_xyz':[-4096,1,32767],'timestamp_ns':123})
 def test_gyro_uses_s32(self):
  self.assertEqual(m.decode_record('gyro_sensor',struct.pack('<3iQ',-100000,200000,0,123))['raw_xyz'],[-100000,200000,0])
 def test_magnetic_accuracy_overflow(self):
  r=m.decode_record('geomagnetic_sensor',struct.pack('<3hBBQ',-3,5,7,2,1,123));self.assertEqual(r['raw_xyz'],[-3,5,7]);self.assertEqual((r['accuracy'],r['overflow']),(2,1))
 def test_lux_first_u32(self):
  r=m.decode_record('light_sensor',struct.pack('<I',1234)+b'\xff'*14+struct.pack('<Q',123));self.assertEqual(r['mcu_lux'],1234)
 def test_rotation_vector_preserves_signed_components_and_accuracy(self):
  sample=struct.pack('<4iBQ',-536870912,268435456,0,805306368,2,456)
  self.assertEqual(m.decode_record('rotation_vector_sensor',sample),
                   {'raw_quaternion':[-536870912,268435456,0,805306368],
                    'accuracy':2,'timestamp_ns':456})
 def test_step_total_u64_not_diff(self):
  self.assertEqual(m.decode_record('step_cnt_sensor',struct.pack('<QQ',2**40+17,123))['step_total'],2**40+17)
 def test_bad_layout_rejected(self):
  for name in m.SENSORS:
   with self.assertRaises(ValueError):m.decode_record(name,b'')
 def test_on_change_not_continuous(self):
  self.assertEqual(m.stream_status('step_cnt_sensor',[]),'not-observed')
  self.assertEqual(m.stream_status('accelerometer_sensor',[]),'missing-continuous-stream')
  self.assertEqual(m.stream_status('light_sensor',[bytes(18)+struct.pack('<Q',123)]),'records-observed')
 def test_timestamp_regression(self):
  self.assertEqual(m.stream_status('step_cnt_sensor',[struct.pack('<QQ',1,123),struct.pack('<QQ',2,122)]),'invalid-timestamps')
if __name__=='__main__':unittest.main()
