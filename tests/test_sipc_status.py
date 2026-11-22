#!/usr/bin/env python3
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

p=Path(__file__).resolve().parents[1]/'compat/modem/sipc_status.py'
spec=importlib.util.spec_from_file_location('status',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class StatusTests(unittest.TestCase):
 def test_passive_mode_reads_real_pipe_without_sending_queries(self):
  fr,fw=os.pipe();rr,rw=os.pipe()
  steps=[]
  try:
   os.write(fw,m.FMT.pack(8,0,0,1,1,3)+b'\x01'+m.FMT.pack(9,0,0,5,1,3)+b'\x80\x00')
   os.write(rw,m.RFS.pack(m.RFS.size+1,1,1)+b'\x00')
   with patch.object(m.os,'write') as write:
    result=m.observe(fr,rr,seconds=.04,query=False,progress=steps.append)
    write.assert_not_called()
   self.assertTrue(result['power_up_notification'])
   self.assertFalse(result['queries_sent'])
   self.assertEqual(result['fmt_frames'],2)
   self.assertEqual(result['status_notifications'],{'sim':{'not-present':1}})
   self.assertEqual(result['rfs_commands'],{'01':1})
   self.assertEqual(result['replies'],{})
   self.assertEqual(steps,['status-receiver-ready','status-first-fmt-frame','status-observation-completed'])
  finally:
   for fd in (fr,fw,rr,rw):os.close(fd)

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
 def test_generic_ack_does_not_supply_sim_state(self):
  pending={2:0x0501}
  fields=(12,0,2,0x80,1,2)
  payload=m.GEN_RESULT.pack(5,1,2,0x8000)
  self.assertIsNone(m.reply_status(fields,payload,pending))
  self.assertEqual(m.query_acknowledgement(fields,payload,pending),
                   ('sim',0x8000))
  self.assertEqual(m.query_acknowledgement(fields,m.GEN_RESULT.pack(5,1,2,4),pending),
                   ('sim',4))

 def test_generic_ack_requires_matching_sequence_command_and_get_type(self):
  fields=(12,0,2,0x80,1,2)
  payload=m.GEN_RESULT.pack(5,1,2,0x8000)
  self.assertIsNone(m.query_acknowledgement(fields,payload,{1:0x0501}))
  self.assertIsNone(m.query_acknowledgement(fields,payload,{2:0x0107}))
  self.assertIsNone(m.query_acknowledgement(fields,m.GEN_RESULT.pack(5,1,3,0),{2:0x0501}))
  self.assertIsNone(m.query_acknowledgement(fields,payload[:-1],{2:0x0501}))

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
