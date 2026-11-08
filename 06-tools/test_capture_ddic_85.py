"""Offline-only tests. Never connect to ADB or touch a phone."""
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import capture_ddic_85 as p
import capture_ddic_c1 as c1

N = 'aabbccddeeff'


def fixture(value=0x15, dt=0x21, reserved=0, rawcount=4):
    h = dt | value << 8 | reserved << 16
    h |= p.ecc(h) << 24
    lines = ['STATE 3600 120.00001', 'ESD_INITIAL reg_read',
             'ESD_ACTIVE esd_sw_sim_success', f'P85 0x{value:02x}',
             'ESD_RESTORED reg_read', 'TRACE_BEGIN']
    def row(name, fields, pid=123):
        lines.append(f' printf-{pid} [004] d... 12345.1: {name}_{N}: {fields}')
    row('ctrl', 'rc=0', 122); row('tx', 'rc=0', 122)
    row('hardware', f'hw_status=0x{rawcount << 16:x} read_bytes=16 mrps=3')
    row('header', f'header=0x{h:x} requested=3 count=4 allocation=16 disp_op=0')
    row('ctrl', 'rc=1')
    for pid in (124,125):
        row('ctrl', 'rc=0', pid); row('tx', 'rc=0', pid)
    lines += ['TRACE_END', 'PROFILE_BEGIN']
    for name,hits in [('header',1), ('hardware',1), ('ctrl',4), ('tx',3)]:
        lines.append(f'{name}_{N} {hits} 0')
    lines += ['PROFILE_END', 'CLEANUP_OK']
    return '\n'.join(lines) + '\n'


class P85Tests(unittest.TestCase):
    def test_accepts_short1_not_assumed_stock_value(self):
        for value in range(256):
            r = p.validate_capture(fixture(value), N, 3600, 120)
            self.assertEqual(r['data'], [value])
            self.assertEqual((r['requested_maximum'],r['returned']), (3,1))
            self.assertEqual(r['scratch_allocation'], 16)
            self.assertTrue(r['framing_qualified'])
            self.assertIsNone(r['pwm_hz'])

    def test_rejects_wrong_path_counts_and_state(self):
        mutations = [('CLEANUP_OK','RECOVERY_REQUIRED 31'),
                     ('ESD_INITIAL reg_read','ESD_INITIAL esd_sw_sim_success'),
                     ('ESD_ACTIVE esd_sw_sim_success','ESD_ACTIVE reg_read'),
                     ('ESD_RESTORED reg_read','ESD_RESTORED esd_sw_sim_success'),
                     ('count=4','count=8'), ('requested=3','requested=1'),
                     ('allocation=16','allocation=4'), ('disp_op=0','disp_op=1'),
                     ('read_bytes=16','read_bytes=4'), ('mrps=3','mrps=1'),
                     ('rc=1','rc=3'), ('P85 0x15','P85 0x15 0x00 0x00'),
                     ('P85 0x15','P85 0x14'), (' 1 0\n',' 1 1\n'),
                     ('STATE 3600','STATE 3601'), ('120.00001','90.0'),
                     ('TRACE_BEGIN','TRACE_BEGIN\nLOST 1 EVENTS')]
        for a,b in mutations:
            with self.subTest(a=a), self.assertRaises(ValueError):
                p.validate_capture(fixture().replace(a,b), N, 3600, 120)
        for count in range(17):
            if count != 4:
                with self.subTest(raw=count), self.assertRaises(ValueError):
                    p.validate_capture(fixture(rawcount=count), N, 3600, 120)

    def test_rejects_long_generic_short2_reserved_and_bad_ecc(self):
        for dt in (0x02,0x11,0x12,0x1a,0x1c,0x22,0x61):
            with self.subTest(dt=dt), self.assertRaises(ValueError):
                p.validate_capture(fixture(dt=dt), N, 3600, 120)
        with self.assertRaises(ValueError):
            p.validate_capture(fixture(reserved=1), N, 3600, 120)
        h = 0x1521 | p.ecc(0x1521) << 24
        with self.assertRaises(ValueError):
            p.validate_capture(fixture().replace(f'header=0x{h:x}',f'header=0x{h^0x01000000:x}'), N, 3600, 120)

    def test_rejects_duplicates_missing_or_extra_returns_and_pid_mismatch(self):
        base = fixture()
        for kind in ('header','hardware','ctrl','tx'):
            lines = base.splitlines()
            i = next(i for i,line in enumerate(lines) if ': '+kind+'_'+N+':' in line)
            for altered in (lines[:i]+lines[i+1:], lines[:i]+[lines[i]]+lines[i:]):
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    p.validate_capture('\n'.join(altered)+'\n', N, 3600, 120)
        for kind in ('hardware','ctrl'):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                p.validate_capture(base.replace('printf-123 [004] d... 12345.1: '+kind,
                                                'printf-999 [004] d... 12345.1: '+kind), N, 3600, 120)
        with self.assertRaises(ValueError):
            p.validate_capture(base+'STATE 3600 120\n', N, 3600, 120)
        with self.assertRaises(ValueError):
            p.validate_capture(base+'TRACE_END\n', N, 3600, 120)

    def test_fixed_query_and_lifecycle_no_writes_to_register85(self):
        parts = shlex.split(p.reader_script(N, 3600, 120))
        self.assertEqual(parts[:8], ['timeout','-k','3','30','unshare','-m','/system/bin/sh','-c'])
        body = parts[8]
        self.assertEqual(body.count("'3 0x06 1 0 1 0 0 1 0x85'"), 1)
        self.assertNotIn('0xC1', body)
        self.assertEqual(body.count('0x85'), 1)
        self.assertNotIn('pwm_c1_', body)
        self.assertIn('pwm_85_'+N, body)
        self.assertIn('mkdir -m 700 "$LOCK"', body)
        self.assertIn('trap cleanup EXIT', body)
        self.assertIn("trap 'exit 30' HUP INT TERM", body)
        for mode in ('reg_read','esd_sw_sim_success'):
            self.assertIn("printf '%s\\n' "+mode+' > "$E"', body)
        for forbidden in ('settings put','reboot','rm -rf'):
            self.assertNotIn(forbidden, body)
        self.assertIn(p.MODULE_SHA, body)
        self.assertEqual(subprocess.run(['sh','-n'], input=body,text=True,capture_output=True).returncode, 0)
        # Existing C1 output/interface must remain unaltered.
        self.assertIn("'3 0x06 1 0 1 0 0 1 0xC1'", c1.reader_script(N,3600,120))

    def test_inherited_lock_and_template_change_fail_closed(self):
        body = shlex.split(p.reader_script(N,3600,144,'parent_token'))[8]
        self.assertNotIn('mkdir -m 700 "$LOCK"', body)
        self.assertNotIn('owned=1', body)
        self.assertIn('cat "$LOCK/owner"', body)
        original = c1.reader_script(N,3600,120)
        with patch.object(c1,'reader_script',return_value=original.replace('0xC1','0xC2')):
            with self.assertRaises(ValueError): p.reader_script(N,3600,120)
        with patch.object(c1,'MODULE_SHA','changed'):
            with self.assertRaises(ValueError): p.reader_script(N,3600,120)
        group,specs = c1.probe_specs(N)
        specs['header_'+N] = ('p','changed offset')
        with patch.object(c1,'probe_specs',return_value=(group,specs)):
            with self.assertRaises(ValueError): p.reader_script(N,3600,120)

    def test_failed_validation_preserves_raw_and_never_retries(self):
        calls = []
        raw = fixture(dt=0x1c).encode()
        class FakeADB:
            def preflight(self): calls.append('preflight')
            def bind(self,t): calls.append(('bind',t))
            def shell(self,t,command,timeout):
                calls.append(('shell',t,timeout))
                self_command = shlex.split(command)
                if self_command[:2] != ['su','-c']: raise AssertionError(command)
                return 0,raw,b'evidence'
        with tempfile.TemporaryDirectory() as d:
            with patch.dict(sys.modules,{'guarded_adb_socket':SimpleNamespace(GuardedADB=FakeADB)}):
                with self.assertRaises(ValueError): p.capture(7,N,3600,120,evidence_dir=d)
            self.assertEqual((Path(d)/'capture.txt').read_bytes(),raw)
            self.assertEqual((Path(d)/'stderr.txt').read_bytes(),b'evidence')
            self.assertEqual((Path(d)/'capture.txt').stat().st_mode & 0o777,0o600)
        self.assertEqual(calls,['preflight',('bind',7),('shell',7,40)])

    def test_offline_and_no_overwrite_under_optimized_python(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)/'new.json'
            cmd = ['python3','-O',str(Path(p.__file__)),'1','--dbv','3600',
                   '--refresh','120','--output',str(out),'--offline-check']
            result = subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertFalse(out.exists())
            out.write_text('preserve')
            self.assertNotEqual(subprocess.run(cmd,capture_output=True,text=True).returncode,0)
            self.assertEqual(out.read_text(),'preserve')
        for nonce,dbv,refresh,token in [('bad',3600,120,None), (N,0,120,None),
                                      (N,3600,60,None), (N,3600,120,'bad;token')]:
            with self.assertRaises(ValueError): p.reader_script(nonce,dbv,refresh,token)

    def test_exact_module_conditional_bounds_model(self):
        # Request3: short1 has a four-byte header at scratch+12; payload+13.
        allocation, requested, count = 16, 3, 4
        header = 16-count
        self.assertEqual((header,header+1), (12,13))
        self.assertLessEqual(header+4,allocation)
        self.assertLess(header+1,allocation)
        # Valid long1/2/3 do not overflow scratch16, but are NOT accepted as85.
        # Malformed long0 still leaves only2bytes for the stock copy3: panic.
        for wc in range(4):
            remaining = allocation-(16-(wc+6))-4
            self.assertEqual(remaining < requested, wc == 0)
        # Request1 scratch4 would leave0 after a long header: worse boundary.
        self.assertLess(4-4,1)


if __name__ == '__main__': unittest.main()
