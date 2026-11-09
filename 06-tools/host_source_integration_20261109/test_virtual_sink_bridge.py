"""Virtual adapter callback delta; fake protocol/caller suite only, no live I/O."""
import dataclasses
import difflib
import importlib
import json
import sys
from types import ModuleType
import unittest
from source_binding_fixture import ROOT, HERE, sha, require

SPIKE=ROOT/'06-tools/host_adb_full_api_spike'
sys.path.insert(0,str(SPIKE))
fixtures=importlib.import_module('test_offline_baseline_adb')
sys.path.pop(0)
binding=json.loads((HERE/'sink_bridge_binding.json').read_text())

def virtual_adapter():
    raw=(ROOT/binding['path']).read_bytes()
    require(sha(raw)==binding['original_sha256'],'Adapter source changed')
    before=raw.decode()
    require(before.count(binding['old'])==1,'Adapter anchor changed')
    after=before.replace(binding['old'],binding['new'])
    patch=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),
        fromfile='a/'+binding['path'],tofile='b/'+binding['path']))
    require(patch==(HERE/'sink_observed_size.proposed.patch').read_text(),'Patch changed')
    require(sha(after.encode())==binding['virtual_sha256'],'Virtual adapter changed')
    require(sha((SPIKE/'test_offline_baseline_adb.py').read_bytes())==
            binding['fixture_sha256'],'Reviewed fixtures changed')
    module=ModuleType('virtual_size_bound_adapter')
    sys.modules[module.__name__]=module
    exec(compile(after,'<virtual-size-bound-adapter>','exec'),module.__dict__)
    return module

class VirtualBridgeTests(unittest.TestCase):
    def setUp(self):
        self.old_m,self.old_pin,self.old_create=fixtures.m,fixtures.PIN,fixtures.Harness.create_sink
        fixtures.m=virtual_adapter()
        fixtures.PIN=fixtures.m.ProcessIdentity(*dataclasses.astuple(self.old_pin))
        original=self.old_create
        def bridge(h,path,deadline,*,observed_size):
            h.forwarded_size=observed_size
            return original(h,path,deadline)
        fixtures.Harness.create_sink=bridge
    def tearDown(self):
        fixtures.m,fixtures.PIN,fixtures.Harness.create_sink=self.old_m,self.old_pin,self.old_create
        sys.modules.pop('virtual_size_bound_adapter',None)
    def test_exact_size_forwarding(self):
        h=fixtures.Harness(auto=True);h.ready();h.pull()
        self.assertEqual(h.forwarded_size,3)
        self.assertTrue(h.adb.last_facts.completed)
    def test_wire_size_mismatch_refuses_completion(self):
        for data in (b'ab',b'abcd'):
            h=fixtures.Harness(auto=True);h.ready();h.pull_data=data
            with self.assertRaises(fixtures.m.TransportError):h.pull()
            self.assertEqual(h.forwarded_size,3)
            self.assertFalse(h.adb.last_facts.completed)
            self.assertTrue(h.sinks[0].closed)
    def test_invalid_size_cap_before_sink(self):
        for size,cap in ((4,3),(0,3),(True,3)):
            h=fixtures.Harness(auto=True);h.ready()
            with self.assertRaises(ValueError):h.pull(size=size,cap=cap)
            self.assertFalse(h.sinks)
    def test_capacity_refusal_no_accepted_completion(self):
        h=fixtures.Harness(auto=True);h.ready()
        def refuse(path,deadline,*,observed_size):
            self.assertEqual(observed_size,3)
            raise RuntimeError('Fixture capacity refuses')
        h.adb._create_sink=refuse
        with self.assertRaises(fixtures.m.TransportError):h.pull()
        self.assertFalse(h.adb.last_facts.completed)
        self.assertFalse(h.sinks)
    def test_original_protocol_and_concrete_cleanup_suite(self):
        # Run every unchanged reviewed test against virtual adapter and keyword bridge.
        suite=unittest.defaultTestLoader.loadTestsFromModule(fixtures)
        result=unittest.TestResult();suite.run(result)
        self.assertEqual(result.testsRun,32)
        self.assertFalse(result.errors,repr(result.errors))
        self.assertFalse(result.failures,repr(result.failures))


    def test_association_bridge_propagates_sticky_invalidation(self):
        import ast
        source=(SPIKE/'linux_adb_probe_dependencies.py').read_bytes()
        require(sha(source)=='e341d0e2a844d03dd0f69ab7604d9defb86865ccd4649875b6670165b3bbcd06',
                'Linux dependency drift')
        tree=ast.parse(source)
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='LinuxAssociation')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='acquire_process')
        error=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='ProbeError')
        namespace={}
        exec(compile(ast.Module(body=[error,method],type_ignores=[]),'<actual-acquisition-bridge>','exec'),namespace)
        class Association:
            trust_invalidated=True
            acquire_process=namespace['acquire_process']
            def __call__(self,deadline):raise namespace['ProbeError']('fixture',trust_invalidated=True)
        association=Association()
        h=fixtures.Harness()
        h.adb._acquire=association.acquire_process
        with self.assertRaises(fixtures.m.TransportError):h.adb.preflight()
        self.assertTrue(h.adb.trust_invalidated)
        self.assertTrue(h.adb.last_facts.trust_invalidated)
        self.assertFalse(h.used)

if __name__=='__main__':unittest.main()
