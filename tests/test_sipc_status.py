#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest

p=Path(__file__).resolve().parents[1]/'compat/modem/sipc_status.py'
spec=importlib.util.spec_from_file_location('status',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class StatusTests(unittest.TestCase):
 def test_fragmented_and_coalesced_messages(self):
  a=m.FMT.pack(8,0,0,1,1,3)+b'\x01';b=m.FMT.pack(9,0,2,5,1,2)+b'\x80\x00'
  r=m.Frames(m.FMT)
  self.assertEqual(r.feed(a[:2]),[])
  frames=r.feed(a[2:]+b[:4]);self.assertEqual(len(frames),1)
  frames+=r.feed(b[4:]);self.assertEqual(len(frames),2)
  self.assertEqual(m.reply_status(*frames[1],{2:0x0501}),{'sim':'not-present'})
  self.assertEqual(r.pending,b'')
 def test_notification_or_wrong_sequence_is_not_query_success(self):
  f=(9,0,2,5,1,3)
  self.assertIsNone(m.reply_status(f,b'\x80\x00',{2:0x0501}))
  self.assertIsNone(m.reply_status((9,0,1,5,1,2),b'\x80\x00',{2:0x0501}))
 def test_bad_lengths(self):
  with self.assertRaises(ValueError):m.Frames(m.FMT).feed(b'\x01\x00'+b'\x00'*5)
  with self.assertRaises(ValueError):m.Frames(m.RFS).feed(m.RFS.pack(m.MAX_FRAME+1,1,2))
 def test_requests_do_not_enable_radio_or_write_nv(self):
  self.assertEqual(m.request(0x0501,2),b'\x07\x00\x02\xff\x05\x01\x02')
  for cmd in (0x0101,0x0102,0x4202,0x0503):
   with self.assertRaises(ValueError):m.request(cmd,1)
 def test_short_or_unexpected_status_not_decoded(self):
  self.assertIsNone(m.reply_status((8,0,2,5,1,2),b'\x80',{2:0x0501}))
  self.assertEqual(m.reply_status((8,0,1,1,7,2),b'\xfe',{1:0x0107}),{'power':'unknown'})

if __name__=='__main__':unittest.main()
