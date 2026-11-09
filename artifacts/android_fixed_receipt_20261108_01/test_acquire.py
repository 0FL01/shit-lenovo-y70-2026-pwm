#!/usr/bin/env python3
"""Offline fake bytes only; no device, socket, subprocess, or source mutation."""
import contextlib
import io
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
import acquire as a

BOOT = '01234567-89ab-cdef-0123-456789abcdef'
def frame(channel,data):
    return struct.pack('<BI',channel,len(data))+data
class Sock:
    def __init__(self,data): self.data=data; self.requests=[]
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def settimeout(self,n): pass
    def recv(self,n):
        self.requests.append(n)
        data,self.data=self.data[:n],self.data[n:]
        return data
class Fake:
    def __init__(self,data): self.sock=Sock(data)
    def selected(self,*args): return self.sock
class Tests(unittest.TestCase):
    def test_check_no_transport_or_write(self):
        for args in ([],['--check']):
            with patch.object(sys,'argv',['acquire.py']+args), patch.object(a,'GuardedADB',side_effect=AssertionError('transport')), patch.object(Path,'write_text',side_effect=AssertionError('write')), patch.object(Path,'write_bytes',side_effect=AssertionError('write')), patch.object(Path,'mkdir',side_effect=AssertionError('mkdir')), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(a.main(),0)
    def test_access_denied_stops_before_capture(self):
        class Guard:
            def __init__(self): self.identities={}
            def preflight(self): pass
            def host(self,*args):
                return b'target device device:avr transport_id:1\ncamera device device:Galaga transport_id:2\n'
            def bind(self,t): self.identities[str(t)]=str(t)
        outputs = [b'Galaga\nROW\nA001\n',
            b'XT2611-1\nW3WWS36.65-64-4-1\n_b\n6.12.58-android16-6-g09eda8c8505a-dirty-ab15950084-4k\nEnforcing\navr\n',
            b'0\n',b'boe_ili97701A_682_1440x3168_dsc_cmd_v4\n',
            (a.MODULE+'  /vendor/lib/modules/msm_drm.ko\n').encode(),b'',
            (BOOT+'\n').encode(),b'2000\n',b'0\n',b'2000\n',b'',
            b'1000:1000:771\n0:0:751\n2000:2000:771\n',b'',b'RESERVED\n']
        for bad in ((1,b'',b''),(0,b'x',b''),(0,b'',b'x')):
            results=[(0,o,b'') for o in outputs]+[bad]
            with patch.object(sys,'argv',['acquire.py','--execute']), patch.object(a,'GuardedADB',Guard), patch.object(a,'bounded_shell',side_effect=results) as dispatch, patch.object(Path,'exists',return_value=False), patch.object(Path,'is_symlink',return_value=False), patch.object(Path,'mkdir'), patch.object(Path,'write_text'), patch.object(Path,'write_bytes'), patch.object(a.os,'umask'), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(a.main(),2)
                self.assertEqual(dispatch.call_count,15)
                last=dispatch.call_args.args[2]
                self.assertIn('test -r '+a.BASE+'/source/producer.sh',last)
                self.assertIn('test -w '+a.BASE+'/work',last)
    def test_pin_change_rejected(self):
        with patch.object(a,'PINSET','0'*64), self.assertRaises(RuntimeError): a.pins()
    def test_render_fixed_and_bounded(self):
        r=a.render(BOOT)
        for phase,(data,command) in r.items():
            self.assertIn(b'ROOT_UID=0\nSHELL_UID=2000',data)
            self.assertIn(b'PATH=/system/bin',data)
            self.assertNotIn(b'@',data)
            self.assertLess(len(command.encode()),a.COMMAND_CAP)
            self.assertIn(BOOT.encode(),data)
        self.assertFalse(r['capture'][1].startswith('su '))
        self.assertTrue(r['seal'][1].startswith('su '))
    def test_bad_boot(self):
        for boot in ('x',BOOT+'\n',BOOT+"'; id"):
            with self.assertRaises(RuntimeError): a.render(boot)
    def test_command_cap_and_nul(self):
        for command in ('x'*(a.COMMAND_CAP+1),'\0'):
            with self.assertRaises(RuntimeError): a.command_limit(command)
    def test_fixed_receipt(self):
        r=a.expected_receipt(BOOT)
        self.assertIn(b'actual_rc=7\nproducer_outcome=EXPECTED_NEGATIVE\n',r)
        self.assertIn(b'stdout=2:'+a.sha(b'\n\0').encode(),r)
        self.assertEqual(r.count(b'boot='),1)
    def test_sequence_success_no_repeat(self):
        s=a.Sequence()
        for phase,result in [('reserve',(0,b'RESERVED\n',b'')),('capture',(7,b'',b'')),('seal',(0,b'SEALED_EXPECTED_NEGATIVE\n',b''))]:
            self.assertEqual(s.run(phase,lambda:result),result)
        with self.assertRaises(RuntimeError): s.run('reserve',lambda:self.fail('write'))
    def test_bad_capture_no_seal_no_retry(self):
        for result in ((0,b'',b''),(7,b'\n',b''),(7,b'',b'x'),(90,b'',b'')):
            s=a.Sequence();s.run('reserve',lambda:(0,b'RESERVED\n',b''))
            with self.assertRaises(RuntimeError): s.run('capture',lambda:result)
            for phase in ('capture','seal','reserve'):
                with self.assertRaises(RuntimeError): s.run(phase,lambda:self.fail('write'))
    def test_unknown_capture_no_write(self):
        s=a.Sequence();s.run('reserve',lambda:(0,b'RESERVED\n',b''))
        def fail(): raise TimeoutError()
        with self.assertRaises(TimeoutError): s.run('capture',fail)
        with self.assertRaises(RuntimeError): s.run('seal',lambda:self.fail('write'))
    def test_out_of_order_consumes(self):
        s=a.Sequence()
        with self.assertRaises(RuntimeError): s.run('seal',lambda:self.fail('write'))
        with self.assertRaises(RuntimeError): s.run('reserve',lambda:self.fail('write'))
    def test_caught_access_gate_failure_latches_hold(self):
        s=a.Sequence();s.run('reserve',lambda:(0,b'RESERVED\n',b''))
        def fail(): raise RuntimeError('access denied')
        with self.assertRaises(RuntimeError): s.access_gate(fail)
        for phase in ('capture','seal','reserve'):
            with self.assertRaises(RuntimeError): s.run(phase,lambda:self.fail('write'))
    def test_reserve_failure_consumes(self):
        s=a.Sequence()
        with self.assertRaises(RuntimeError): s.run('reserve',lambda:(1,b'',b''))
        with self.assertRaises(RuntimeError): s.run('reserve',lambda:self.fail('write'))
    def test_shell_binary_exit(self):
        g=Fake(frame(1,b'\n\0')+frame(2,b'diagnostic\n\0')+frame(3,b'\x07'))
        self.assertEqual(a.bounded_shell(g,1,'fixed',cap=14),(7,b'\n\0',b'diagnostic\n\0'))
    def test_cap_before_payload(self):
        g=Fake(struct.pack('<BI',1,1000000)+b'x'*50)
        with self.assertRaises(RuntimeError): a.bounded_shell(g,1,'fixed',cap=14)
        self.assertEqual(g.sock.requests,[5])
    def test_partial_only_complete_frames(self):
        observed=[];g=Fake(frame(1,b'ok')+struct.pack('<BI',2,5)+b'bad')
        with self.assertRaises(RuntimeError): a.bounded_shell(g,1,'fixed',partial=lambda o,e:observed.append((o,e)))
        self.assertEqual(observed,[(b'ok',b'')])
    def test_invalid_exit(self):
        with self.assertRaises(RuntimeError): a.bounded_shell(Fake(frame(3,b'xx')),1,'fixed')
    def test_deadline_before_read(self):
        with patch.object(a.time,'monotonic',side_effect=[0,10]), self.assertRaises(RuntimeError):
            a.bounded_shell(Fake(frame(3,b'\0')),1,'fixed',timeout=1)
    def test_late_recv_not_accepted(self):
        with patch.object(a.time,'monotonic',side_effect=[0,0,2]), self.assertRaises(RuntimeError):
            a.bounded_shell(Fake(frame(3,b'\0')),1,'fixed',timeout=1)
if __name__=='__main__': unittest.main()
