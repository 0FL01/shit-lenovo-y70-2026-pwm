"""Offline only: fixed query, parsing, bounds assumptions, cleanup and refusal."""
import importlib.util
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

import capture_ddic_c1 as c

N='aabbccddeeff'


def fixture(rawcount=9,header=None):
    h=0x00031c
    if header is None: header=h | c.ecc(h)<<24
    lines=['STATE 3600 120.00001','C1 0x00 0x00 0x65','TRACE_BEGIN']
    def row(name, data):
        lines.append(f' sh-123 [004] d... 12345.1: {name}_{N}: '+data)
    row('hardware',f'hw_status=0x{rawcount<<16:x} read_bytes=16 mrps=3')
    row('header',f'header=0x{header:x} requested=3 count=9 allocation=16 disp_op=0')
    for value in (0,3,0,0): row('ctrl',f'rc={value}')
    for _ in range(3): row('tx','rc=0')
    lines+=['TRACE_END','PROFILE_BEGIN']
    for name in ('header','hardware','ctrl','tx'):lines.append(f'{name}_{N} 1 0')
    lines+=['PROFILE_END','CLEANUP_OK']
    return '\n'.join(lines)+'\n'


class CaptureTests(unittest.TestCase):
    def test_accepts_long3_and_ack_prefix_count(self):
        for count in (9,13):
            r=c.validate_capture(fixture(count),N,3600,120)
            self.assertEqual(r['data'],[0,0,0x65])
            self.assertTrue(r['framing_qualified'])
            self.assertIsNone(r['pwm_hz'])

    def test_rejects_uncertain_or_wrong_framing(self):
        base=fixture()
        mutations=[('CLEANUP_OK','RECOVERY_REQUIRED 31'),('count=9','count=7'),
                   ('requested=3','requested=40'),('allocation=16','allocation=48'),
                   ('disp_op=0','disp_op=1'),('mrps=3','mrps=10'),('read_bytes=16','read_bytes=4'),
                   ('hw_status=0x90000','hw_status=0x70000'),('rc=3','rc=-1'),
                   ('C1 0x00 0x00 0x65','C1 0x00 0x00'),(' 1 0\n',' 1 1\n'),
                   ('STATE 3600','STATE 3601'),('120.00001','90.0'),
                   ('TRACE_BEGIN','TRACE_BEGIN\nLOST 1 EVENTS')]
        for a,b in mutations:
            with self.subTest(a=a),self.assertRaises(ValueError):
                c.validate_capture(base.replace(a,b),N,3600,120)
        for h in (0x21,0x22,0x00011c,0x00021c,0x00031a):
            with self.subTest(h=h),self.assertRaises(ValueError):
                c.validate_capture(fixture(header=h|c.ecc(h)<<24),N,3600,120)

    def test_rejects_corrupt_ecc_and_duplicate_events(self):
        h=0x00031c|c.ecc(0x00031c)<<24
        with self.assertRaises(ValueError):c.validate_capture(fixture(header=h^0x01000000),N,3600,120)
        text=fixture(); line=next(x for x in text.splitlines() if ': header_' in x)
        with self.assertRaises(ValueError):c.validate_capture(text+line+'\n',N,3600,120)
        with self.assertRaises(ValueError):c.validate_capture(text.replace('sh-123 [004] d... 12345.1: hardware','sh-124 [004] d... 12345.1: hardware'),N,3600,120)

    def test_script_fixed_width_and_cleanup(self):
        command=c.reader_script(N,3600,120)
        parts=shlex.split(command)
        self.assertEqual(parts[:8],['timeout','-k','3','30','unshare','-m','/system/bin/sh','-c'])
        body=parts[8]
        self.assertEqual(body.count("'3 0x06 1 0 1 0 0 1 0xC1'"),1)
        self.assertIn('mkdir -m 700 "$LOCK"',body)
        self.assertIn('trap cleanup EXIT',body)
        self.assertIn("trap 'exit 30' HUP INT TERM",body)
        self.assertIn('printf reg_read > "$E"',body)
        self.assertIn('if [ "$s" = 0 ]; then',body)
        self.assertNotIn('reboot',body)
        self.assertNotIn('settings put',body)
        self.assertNotIn('rm -rf',body)
        self.assertIn(c.MODULE_SHA,body)
        self.assertEqual(subprocess.run(['sh','-n'],input=body,text=True,capture_output=True).returncode,0)

    def test_inherited_lock_not_acquired_or_removed(self):
        body=shlex.split(c.reader_script(N,3600,144,'parent_token'))[8]
        self.assertNotIn('mkdir -m 700 "$LOCK"',body)
        self.assertNotIn('owned=1',body)
        self.assertIn('cat "$LOCK/owner"',body)

    def test_argument_refusal_and_optimized_python(self):
        for nonce in ('../bad','1234','a'*13):
            with self.assertRaises(ValueError):c.reader_script(nonce,3600,120)
        with self.assertRaises(ValueError):c.reader_script(N,0,120)
        with self.assertRaises(ValueError):c.reader_script(N,3600,60)
        with self.assertRaises(ValueError):c.reader_script(N,3600,120,'a; rm')
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'new.json'
            r=subprocess.run(['python3','-O',str(Path(c.__file__)),'1','--dbv','3600','--refresh','120','--output',str(out),'--offline-check'],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertFalse(out.exists())
            out.write_text('preserve')
            r=subprocess.run(['python3','-O',str(Path(c.__file__)),'1','--dbv','3600','--refresh','120','--output',str(out),'--offline-check'],capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0)
            self.assertEqual(out.read_text(),'preserve')

    def test_conditional_receive_bounds(self):
        # Exact target sizing for request3, one16-byte helper store. A real
        # long1/2 can return CRC bytes; malformed long0 remains a panic risk.
        allocation=max(16,(3+9)&~3)
        self.assertEqual(allocation,16)
        for payload,remaining in [(0,2),(1,3),(2,4),(3,5)]:
            count=payload+6; header=16-count
            self.assertEqual(allocation-header-4,remaining)
            self.assertEqual(remaining<3,payload==0)


if __name__=='__main__':unittest.main()
