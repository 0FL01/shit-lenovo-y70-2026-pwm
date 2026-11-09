import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import hashlib
ROOT=Path(__file__).resolve().parents[2]
R=ROOT/'artifacts/identity_bound_reader_20261109_03'
raw=(R/'reader.py').read_bytes()
if hashlib.sha256(raw).hexdigest()!='658edfc705bb47485c4c60d481b11a931599dac99e0fe8c0e6f877045184559c':raise RuntimeError('Reader freeze mismatch')
spec=importlib.util.spec_from_file_location('identity_bound_reader_revision03',R/'reader.py');reader=importlib.util.module_from_spec(spec);sys.modules[spec.name]=reader;spec.loader.exec_module(reader)
sys.modules['reader']=reader
spec=importlib.util.spec_from_file_location('reader_fakes',R/'test_reader.py');fakes=importlib.util.module_from_spec(spec);spec.loader.exec_module(fakes)
import shim
sys.path.insert(0,str(ROOT/'06-tools/host_source_integration_20261109'))
import combined_fixture as fixture
from replay_source_fixture import baseline_inputs,intended_sources
from contextlib import contextmanager
@contextmanager
def actual():
    with patch.object(fixture,'inputs',lambda:dict(baseline_inputs())),patch.object(fixture,'compose',lambda _:dict(intended_sources(current=True))):
        with fixture.combined_context() as ctx:yield ctx

def exception_graph(error):
    found=[];pending=[error];seen=set()
    while pending:
        e=pending.pop()
        if e is None or id(e) in seen:continue
        seen.add(id(e));found.append(e);pending.extend([e.__cause__,e.__context__])
    return found
class Tests(unittest.TestCase):
    def test_original_os_error_context_and_sticky(self):
        with actual() as ctx:
            d=ctx.modules['linux_adb_probe_dependencies']
            for code in (1,2,3,5,13):
                f=fakes.Fake();a=f.acq();h=a.acquire(pid=42,deadline=12);s=shim.StatShim(held=h,dependency=d);f.fault='read_errno';f.read_error=OSError(code,'private')
                with self.assertRaises(d.ProbeError) as caught:s.read('/proc/42/stat',16384,12)
                self.assertTrue(caught.exception.trust_invalidated);self.assertIn(f.read_error,exception_graph(caught.exception));self.assertTrue(s.terminal);n=len(f.calls)
                with self.assertRaises(d.ProbeError):s.read('/proc/42/stat',16384,12)
                self.assertEqual(len(f.calls),n)
    def test_logical_unknown_and_interrupt_mapping(self):
        with actual() as ctx:
            d=ctx.modules['linux_adb_probe_dependencies']
            for fault in ('fd_reuse','namespace','deadline','cap'):
                f=fakes.Fake();h=f.acq().acquire(pid=42,deadline=12);s=shim.StatShim(held=h,dependency=d);f.fault=fault
                with self.assertRaises(d.ProbeError) as caught:s.read('/proc/42/stat',16384,12)
                self.assertTrue(caught.exception.trust_invalidated);self.assertTrue(h.terminal)
            for error in (RuntimeError('unknown'),KeyboardInterrupt(),SystemExit(7)):
                f=fakes.Fake();h=f.acq().acquire(pid=42,deadline=12);s=shim.StatShim(held=h,dependency=d);f.fault='read_errno';f.read_error=error
                try:s.read('/proc/42/stat',16384,12)
                except BaseException as raised:
                    if isinstance(error,(KeyboardInterrupt,SystemExit)):self.assertIs(raised,error)
                    else:self.assertTrue(raised.trust_invalidated);self.assertIn(error,exception_graph(raised))
                else:self.fail('Failure swallowed')
                self.assertTrue(s.terminal);self.assertTrue(h.terminal)
    def test_success_and_wrong_request(self):
        with actual() as ctx:
            d=ctx.modules['linux_adb_probe_dependencies'];f=fakes.Fake();h=f.acq().acquire(pid=42,deadline=12);s=shim.StatShim(held=h,dependency=d)
            self.assertEqual(s.read('/proc/42/stat',16384,12),fakes.raw());n=f.statcount
            with self.assertRaises(d.ProbeError) as caught:s.read('/proc/43/stat',16384,12)
            self.assertTrue(caught.exception.trust_invalidated);self.assertEqual(f.statcount,n)
            with self.assertRaises(AttributeError):s.terminal=False
            with self.assertRaises(ValueError):s.__init__(held=h,dependency=d)
    def test_actual_association_terminal_second_call_zero_io(self):
        with actual() as ctx:
            d=ctx.modules['linux_adb_probe_dependencies']
            for original in (PermissionError(13,'denied'),reader.BoundError('logical'),RuntimeError('unknown'),KeyboardInterrupt(),SystemExit(9)):
                f=fakes.Fake();h=f.acq().acquire(pid=42,deadline=12);s=shim.StatShim(held=h,dependency=d);f.fault='read_errno';f.read_error=original
                clock=type('Clock',(),{'now':0})()
                class Composite(ctx.proc.FakeProc):
                    def read(self,path,cap,deadline):
                        # Explicit fixture bridge substitutes one planned stat stage;
                        # its synthetic PID42 is NOT a real mapped PID101 claim.
                        if path=='/proc/101/stat':return s.read('/proc/42/stat',16384,deadline)
                        return super().read(path,cap,deadline)
                proc=Composite(clock);klass=shim.association_type(d);a=klass(pin=ctx.proc.PIN,limits=ctx.proc.LIMITS,proc=proc,monotonic=lambda:0)
                try:a(12)
                except BaseException as raised:
                    if isinstance(original,(KeyboardInterrupt,SystemExit)):self.assertIs(raised,original)
                    else:self.assertTrue(raised.trust_invalidated);self.assertIn(original,exception_graph(raised))
                else:self.fail('Association passed')
                self.assertTrue(a.trust_invalidated);n=len(f.calls)
                with self.assertRaises(d.ProbeError):a(12)
                self.assertEqual(len(f.calls),n)
if __name__=='__main__':unittest.main()
