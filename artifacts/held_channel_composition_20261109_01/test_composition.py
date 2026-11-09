import unittest,sys,json,hashlib,dataclasses,stat,importlib.util
from pathlib import Path
from unittest.mock import patch
import composition as c
ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'artifacts/held_server_channel_collector_20261109_02'
sys.path.insert(0,str(OLD))
spec=importlib.util.spec_from_file_location('composition_fixtures',OLD/'test_collector.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
MAN=json.loads((Path(__file__).parent/'source_manifest.json').read_text())
def buffers():return {k:(ROOT/v['path']).read_bytes() for k,v in MAN.items()}
class Tests(unittest.TestCase):
 def test_all_hashes_before_exec(self):
  for key in c.PINS:
   b=buffers();b[key]+=b' '
   with patch('builtins.exec',side_effect=AssertionError('must not execute')):
    with self.assertRaises(c.CompositionError):c.Composition(sources=b)
 def test_registry_poison_is_ignored(self):
  poison={n:object() for n in c.PINS}
  with patch.dict(sys.modules,poison):
   x=c.Composition(sources=buffers());self.assertIs(x._modules['bound_reader_sticky_shim'].Held,x._modules['identity_bound_reader_revision03'].Held)
   self.assertIs(x._modules['linux_adb_probe_dependencies'].ProcessIdentity,x._modules['offline_baseline_adb'].ProcessIdentity)
   for n in poison:self.assertIs(sys.modules[n],poison[n])
  self.assertFalse(any(n.startswith('_held_channel_frozen_') for n in sys.modules))
 def test_separate_compositions_and_readonly_boundary(self):
  x=c.Composition(sources=buffers());y=c.Composition(sources=buffers())
  self.assertIsNot(x.types['RootPin'],y.types['RootPin'])
  with self.assertRaises(AttributeError):x.types={}
  with self.assertRaises(TypeError):x.types['RootPin']=object
  with self.assertRaises(c.CompositionError):x.__init__(sources=buffers())
  r=x.source_hashes;r.clear();self.assertEqual(len(x.source_hashes),6)
 def test_actual_composed_collector_fake_io(self):
  with f.prev.actual() as ctx:
   fixture=f.Fixture(ctx);x=c.Composition(sources=buffers());t=x.types
   process=t['ProcessIdentity'](**dataclasses.asdict(ctx.proc.PIN.process))
   pin=t['VerifiedPin'](**dict(dataclasses.asdict(ctx.proc.PIN),process=process));limits=t['ProcLimits'](**dataclasses.asdict(fixture.limits))
   expected=t['ExpectedClient'](**dataclasses.asdict(fixture.expected))
   client=t['FixedLoopbackSocket'](socket_factory=lambda *a:fixture.raw,monotonic=fixture.os.clock)
   # Fake prebinding belongs to caller fixture, not loader or collector.
   client.settimeout(12);client.connect(process.endpoint)
   fixture.proc.exe=t['ExecutableSnapshot'](**dataclasses.asdict(fixture.proc.exe))
   root=t['RootPin'](9,1,9,stat.S_IFDIR|0o555,'pid:[100]','a'*64)
   kw=dict(pin=pin,limits=limits,expected_client=expected,client=client,os_api=fixture.os,clock=fixture.os.clock,root=root,poll_factory=fixture.os.poll_factory,proc=fixture.proc,config_bytes=fixture.config,expected_config_sha256=hashlib.sha256(fixture.config).hexdigest())
   with self.assertRaises(c.CompositionError):x.collector(**dict(kw,pin=ctx.proc.PIN))
   self.assertEqual(fixture.os.calls,[])
   collector=x.collector(**kw);collector.acquire(deadline=12);collector.observe();r=collector.close()
   self.assertEqual(len(r['snapshots']),2);self.assertFalse(r['recovery_admitted']);self.assertEqual(fixture.requests,0)
   n=(len(fixture.os.calls),len(fixture.proc.calls),fixture.raw_closes)
   with self.assertRaises(Exception):collector.observe()
   collector.close();self.assertEqual(n,(len(fixture.os.calls),len(fixture.proc.calls),fixture.raw_closes))
if __name__=='__main__':unittest.main()
