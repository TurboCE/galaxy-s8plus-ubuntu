#!/usr/bin/env python3
"""Exercise RAM bounds, actual packed kernel ABI and failure propagation."""
import ctypes
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

spec = importlib.util.spec_from_file_location('cp_boot', Path(__file__).resolve().parents[1] / 'compat/modem/cp_boot.py')
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def inputs():
    image = bytearray(16384)
    def entry(i, name, off, addr, size, crc, section):
        m.TOC.pack_into(image, i * 32, name, off, addr, size, crc, section)
    entry(0, b'TOC', 0, 0, 512, 0, 5)
    for i, name in enumerate((b'BOOT', b'MAIN', b'VSS'), 1):
        data = bytes([i]) * 512
        off = i * 4096
        image[off:off+len(data)] = data
        entry(i, name, off, m.CP_BASE + (i-1)*0x1000000, len(data), zlib.crc32(data), i)
    entry(4, b'NV', 0, m.CP_BASE+0x5000000, 1024*1024, 0, 4)
    entry(5, b'OFFSET', 0, 0, 0, 0, 5)
    return image, b'\x01'*(1024*1024)


class TrialTests(unittest.TestCase):
    def test_shutdown_still_powers_off_after_reset_or_log_failure(self):
        class Transport:
            powered=True
            def __init__(self):self.calls=[]
            def command(self,n):
                self.calls.append(n)
                if n==0x21:raise OSError('reset failed')
        def broken_log(step):raise OSError('log unavailable')
        t=Transport()
        with self.assertRaisesRegex(OSError,'reset failed'):m.shutdown_trial(t,broken_log)
        self.assertEqual(t.calls,[0x21,0x20])

    def test_boot_inhibits_before_preflight_not_only_before_ioctl(self):
        order=[]
        @contextmanager
        def inhibitor():
            order.append('inhibit')
            try:yield
            finally:order.append('release')
        def preflight(*args):
            order.append('preflight')
            raise RuntimeError('stop before hardware')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'inventory.json';p.write_text('{}')
            with patch.object(sys,'argv',['cp_boot.py','--private-inventory',str(p),'--boot-trial']),patch.object(m,'preflight',side_effect=preflight),patch.object(m,'sleep_inhibitor',inhibitor):
                with self.assertRaisesRegex(RuntimeError,'before hardware'):m.main()
        self.assertEqual(order,['inhibit','preflight','release'])

    def test_partition_input_handles_short_reads_and_eintr_without_tty_probe(self):
        with patch.object(m.os,'open',return_value=7) as opened,patch.object(m.os,'read',side_effect=[InterruptedError(),b'ab',b'c',b'']),patch.object(m.os,'close') as closed,patch.object(m.fcntl,'ioctl') as ioctl:
            self.assertEqual(m.partition_input('/test/RADIO',retain=True),(3,m.sha256(b'abc'),b'abc'))
            opened.assert_called_once_with('/test/RADIO',m.os.O_RDONLY|m.os.O_CLOEXEC)
            closed.assert_called_once_with(7);ioctl.assert_not_called()

    def test_partition_input_closes_on_failure(self):
        with patch.object(m.os,'open',return_value=7),patch.object(m.os,'read',side_effect=OSError('read failed')),patch.object(m.os,'close') as closed:
            with self.assertRaises(OSError):m.partition_input('/test/EFS')
            closed.assert_called_once_with(7)

    def test_partition_input_real_file_streaming(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'data';data=b'abc'*(1024*1024);p.write_bytes(data)
            self.assertEqual(m.partition_input(p),(len(data),m.sha256(data),None))

    def test_inhibitor_child_holds_pipe_until_cleanup(self):
        actual=m.subprocess.Popen
        children=[]
        def start(args,**kwargs):
            self.assertIn('--what=sleep:idle',args)
            child=actual(['/bin/cat'],**kwargs);children.append(child);return child
        with patch.object(m.subprocess,'Popen',side_effect=start):
            with m.sleep_inhibitor():self.assertIsNone(children[0].poll())
        self.assertEqual(children[0].returncode,0)

    def test_failed_inhibitor_prevents_trial_body(self):
        actual=m.subprocess.Popen
        def start(args,**kwargs):
            return actual([sys.executable,'-c','import sys; sys.stdin.readline()'],**kwargs)
        entered=False
        with patch.object(m.subprocess,'Popen',side_effect=start):
            with self.assertRaisesRegex(RuntimeError,'inhibitor'):
                with m.sleep_inhibitor():entered=True
        self.assertFalse(entered)

    def test_existing_nv_requires_both_backup_pin_and_salted_companion(self):
        nv=inputs()[1]
        checksum=m.hashlib.md5(nv+b'Samsung_Android_RIL').hexdigest()
        m.validate_nv(nv,m.sha256(nv),checksum)
        with self.assertRaises(RuntimeError):m.validate_nv(nv,'0'*64,checksum)
        with self.assertRaises(RuntimeError):m.validate_nv(nv,m.sha256(nv),m.hashlib.md5(nv).hexdigest())

    def test_missing_or_bad_data_never_qualifies(self):
        radio, nv = inputs()
        self.assertEqual([s.name for s in m.plan(radio, nv)], ['BOOT','MAIN','VSS','NV'])
        with self.assertRaises(ValueError): m.plan(radio, b'')
        radio[8192] ^= 1
        with self.assertRaisesRegex(ValueError, 'CRC'): m.plan(radio, nv)

    def test_out_of_ram_and_overlapping_sections(self):
        for address in (m.CP_BASE-1, m.CP_BASE+m.BOOT_LIMIT-100, m.CP_BASE):
            radio,nv=inputs()
            struct.pack_into('<I',radio,2*32+16,address)
            with self.assertRaises(ValueError): m.plan(radio,nv)

    def test_extended_table_not_silently_treated_as_legacy(self):
        radio,nv=inputs()
        struct.pack_into('<I',radio,16,0x100000)
        with self.assertRaisesRegex(ValueError,'security'): m.plan(radio,nv)

    def test_real_ioctl_layout_and_pointer_lifetime(self):
        data=b'normal signed modem payload'
        stage=m.Stage('MAIN',0x10000,data)
        def ioctl(fd,request,arg):
            self.assertEqual(request,0x6f40)
            self.assertIsInstance(arg,bytearray)  # must retain numeric ioctl result
            self.assertEqual(len(arg),28)
            ptr,size,offset,fileoff,mode,length=struct.unpack('<QIIIII',arg)
            self.assertEqual((size,offset,fileoff,mode,length),(len(data),0x10000,0,0,len(data)))
            self.assertEqual(ctypes.string_at(ptr,length),data)
            return 0
        with patch.object(m.fcntl,'ioctl',side_effect=ioctl):
            m.NativeTransport(7).load(stage,0,data)
        with patch.object(m.fcntl,'ioctl',return_value=3):
            with self.assertRaises(OSError): m.NativeTransport(7).load(stage,0,data)

    def test_kernel_positive_security_result_is_not_success(self):
        with patch.object(m.fcntl,'ioctl',return_value=11):
            t=m.NativeTransport(7)
            t.security(2,0,0)
            with self.assertRaises(OSError):t.security(0,10,20)
        with self.assertRaises(ValueError):m.NativeTransport(7).security(7,0,0)
        with self.assertRaises(ValueError):m.NativeTransport(7).command(0x35)

    def test_transfer_failure_prevents_power_and_handshake(self):
        class Fake:
            def __init__(self):self.calls=[]
            def security(self,*args):self.calls.append(('security',args))
            def load(self,*args):self.calls.append(('load',));raise OSError('short transfer')
            def command(self,*args):self.calls.append(('command',args))
            def exchange(self,*args):self.calls.append(('exchange',args))
        t=Fake()
        with self.assertRaises(OSError):m.load_and_handshake(t,m.plan(*inputs()))
        self.assertEqual([v[0] for v in t.calls],['security','load'])

    def test_complete_sequence_verifies_before_power(self):
        class Fake:
            def __init__(self):self.calls=[]
            def security(self,*args):self.calls.append(('security',args))
            def load(self,stage,done,data):self.calls.append(('load',stage.name))
            def command(self,*args):self.calls.append(('command',args))
            def exchange(self,*args):self.calls.append(('exchange',args))
        t=Fake();m.load_and_handshake(t,m.plan(*inputs()))
        verify=t.calls.index(('security',(0,512,512)))
        power=t.calls.index(('command',(0x19,)))
        self.assertLess(verify,power)
        self.assertTrue(all(c[0]=='load' for c in t.calls[1:verify]))
        self.assertEqual(t.calls[power+1:],[('command',(0x22,)),('command',(0x28,)),('exchange',(0x900d,0xa00d)),('exchange',(0x9f00,0xaf00)),('command',(0x23,)),('command',(0x24,))])

    def test_truncated_handshake_is_failure(self):
        class Poll:
            def register(self,*args):pass
            def poll(self,*args):return [(7,m.select.POLLIN)]
        with patch.object(m.os,'write',return_value=4),patch.object(m.os,'read',return_value=b'\x0d\xa0'),patch.object(m.select,'poll',Poll):
            with self.assertRaisesRegex(OSError,'incomplete'):m.NativeTransport(7).exchange(0x900d,0xa00d)


if __name__=='__main__':unittest.main()
