#!/usr/bin/env python3
"""Fake bytes only; no ADB/device calls or filesystem writes."""
import contextlib
import io
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch
sys.dont_write_bytecode=True
import acquire as a

def policy(): return struct.pack('<II',0xf97cff8c,8)+b'SE Linux'+struct.pack('<II',33,0)+b'fake-body'
def frame(c,data): return struct.pack('<BI',c,len(data))+data
class Sock:
    def __init__(self,data): self.data=data; self.requests=[]
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def settimeout(self,n): pass
    def recv(self,n):
        self.requests.append(n); data,self.data=self.data[:n],self.data[n:]; return data
class Fake:
    def __init__(self,data): self.sock=Sock(data)
    def selected(self,*args): return self.sock
class Tests(unittest.TestCase):
    def test_check_no_transport_write(self):
        for args in ([],['--check']):
            with patch.object(sys,'argv',['acquire.py']+args), patch.object(a,'GuardedADB',side_effect=AssertionError('transport')), patch.object(Path,'mkdir',side_effect=AssertionError('write')), patch.object(Path,'write_text',side_effect=AssertionError('write')), patch.object(Path,'write_bytes',side_effect=AssertionError('write')), contextlib.redirect_stdout(io.StringIO()): self.assertEqual(a.main(),0)
    def test_context_exact_terminal_nul(self):
        self.assertEqual(a.parse_context(b'u:r:shell:s0\0'),'u:r:shell:s0')
        self.assertEqual(a.parse_context(b'u:r:shell:s0:c0.c1023\0'),'u:r:shell:s0:c0.c1023')
    def test_context_ambiguous_terminators_rejected(self):
        for raw in (b'u:r:shell:s0',b'u:r:shell:s0\n',b'u:r:shell:s0\0\n',b'u:r:shell:s0\n\0',b'u:r:shell:s0\0\0',b'u:r:shell\0:s0\0',b'\0',b'u:r:shell:s0\r\0'):
            with self.assertRaises(RuntimeError): a.parse_context(raw)
    def test_transport_pin(self):
        with patch.object(a,'TRANSPORT_PIN','0'*64),self.assertRaises(RuntimeError): a.pins()
    def test_explicit_gate(self):
        with patch.object(sys,'argv',['acquire.py','--other']),patch.object(a,'GuardedADB',side_effect=AssertionError('transport')),self.assertRaises(RuntimeError): a.main()
    def test_nonmeaningful_stat_not_empty(self): self.assertEqual(a.validate_policy_header(policy(),0),33)
    def test_size_exact(self): self.assertEqual(a.validate_policy_header(policy(),len(policy())),33)
    def test_size_mismatch(self):
        with self.assertRaises(RuntimeError): a.validate_policy_header(policy(),len(policy())+1)
    def test_empty_truncated_header(self):
        for data in (b'',policy()[:3],policy()[:14],policy()[:23]):
            with self.assertRaises(RuntimeError): a.validate_policy_header(data,0)
    def test_unsupported_header(self):
        for data in (b'x'*40,policy()[:4]+struct.pack('<I',9)+policy()[8:],policy()[:16]+struct.pack('<I',99)+policy()[20:]):
            with self.assertRaises(RuntimeError): a.validate_policy_header(data,0)
    def test_header_is_not_full_parse(self):
        # A valid-looking header plus fake body is deliberately NOT parse proof.
        self.assertEqual(a.validate_policy_header(policy(),0),33)
    def test_complete_binary(self):
        self.assertEqual(a.bounded_shell(Fake(frame(1,b'\0\n')+frame(3,b'\0')),1,'fixed',cap=2),(0,b'\0\n',b''))
    def test_cap_before_read(self):
        g=Fake(struct.pack('<BI',1,a.POLICY_CAP+1))
        with self.assertRaises(RuntimeError): a.bounded_shell(g,1,'fixed',cap=a.POLICY_CAP)
        self.assertEqual(g.sock.requests,[5])
    def test_partial_complete_frames_only(self):
        seen=[];g=Fake(frame(1,b'first')+struct.pack('<BI',1,10)+b'partial')
        with self.assertRaises(RuntimeError): a.bounded_shell(g,1,'fixed',partial=lambda o,e:seen.append((o,e)))
        self.assertEqual(seen,[(b'first',b'')])
    def test_missing_exit(self):
        with self.assertRaises(RuntimeError): a.bounded_shell(Fake(frame(1,b'data')),1,'fixed')
    def test_late_recv(self):
        with patch.object(a.time,'monotonic',side_effect=[0,0,2]),self.assertRaises(RuntimeError): a.bounded_shell(Fake(frame(3,b'\0')),1,'fixed',timeout=1)
    def test_command_cap(self):
        with self.assertRaises(RuntimeError): a.command_limit('x'*(a.COMMAND_CAP+1))
if __name__=='__main__': unittest.main()
