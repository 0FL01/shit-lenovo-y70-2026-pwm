"""Real loader/directory/sink wiring tests. Never reads proc, sockets or devices."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import construction as c

ROOT=Path(__file__).resolve().parents[2]

class Tests(unittest.TestCase):
    def restore_module_namespace(self):
        # Test-only isolation: keep production preload rejection unchanged.
        for name in c.SOURCES:
            sys.modules.pop(name,None)
        sys.modules.update(self.saved_modules)

    def setUp(self):
        self.saved_modules={n:sys.modules[n] for n in c.SOURCES if n in sys.modules}
        self.addCleanup(self.restore_module_namespace)
        for name in c.SOURCES:
            sys.modules.pop(name,None)
        self.raw={n:(ROOT/p).read_bytes() for n,p in c.SOURCES.items()}
        self.hashes={n:hashlib.sha256(raw).hexdigest() for n,raw in self.raw.items()}
        self.bootstrap={f'06-tools/stock_observation_20261110/{n}.py':hashlib.sha256((ROOT/f'06-tools/stock_observation_20261110/{n}.py').read_bytes()).hexdigest() for n in ('construction','launch')}
        self.loaded=None
    def tearDown(self):
        if self.loaded:
            for name,m in self.loaded.modules.items():
                if sys.modules.get(name) is m:del sys.modules[name]
    def load(self):
        self.loaded=c.load_sources(self.raw,self.hashes,commit='a'*40,bootstrap_sha256=self.bootstrap)
        return self.loaded
    def test_all_sources_validated_before_execution(self):
        self.raw['coordinator']+=b'\nraise RuntimeError("must_not_execute")\n'
        with self.assertRaisesRegex(ValueError,'source_digest'):self.load()
        self.assertFalse(set(c.SOURCES).intersection(sys.modules))
    def test_missing_source_rejected(self):
        self.raw.pop('camera_capture_metadata')
        with self.assertRaises(ValueError):self.load()
    def test_preloaded_project_rejected(self):
        sys.modules['coordinator']=SimpleNamespace()
        try:
            with self.assertRaisesRegex(ValueError,'preloaded'):self.load()
        finally:del sys.modules['coordinator']
    def test_real_dag_and_legacy_selector_extraction(self):
        source=self.load();m=source.modules
        self.assertFalse(hasattr(m['video_selector'],'main'))
        self.assertEqual(m['video_selector'].new_camera_video('','/sdcard/DCIM/OpenCamera/x.mp4'),'/sdcard/DCIM/OpenCamera/x.mp4')
        self.assertIs(m['linux_adb_probe_dependencies'].OfflineBaselineADB,m['offline_baseline_adb'].OfflineBaselineADB)
        manifest={**{c.SOURCES[n]:self.hashes[n] for n in c.SOURCES},**self.bootstrap}
        expected=hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.assertEqual(source.provenance['closure_sha256'],expected)
    def inputs(self,base):
        m=self.loaded.modules;adb=m['offline_baseline_adb'];dep=m['linux_adb_probe_dependencies'];fm=m['fresh_private_directory'];sm=m['private_video_sink']
        st=os.stat(base)
        process=adb.ProcessIdentity(adb.ENDPOINT,123,456,(0,0,0,0),'/usr/bin/adb',1,2,stat.S_IFREG|0o755,0,b'Android Debug Bridge version 1.0.41\nfixture')
        return c.Inputs(dep.VerifiedPin(process,3,'net:[4]','a'*64,123),dep.ProcLimits(4096,4096,4096,100,100,100,4096),
            (b'target',b'camera'),str(base),fm.BasePin(st.st_dev,st.st_ino,st.st_uid,st.st_mode),'new-observation',sm.CapacityPolicy(4096,0),'obs_20261110',True,True)
    def test_actual_private_directory_and_sink_no_device_io(self):
        self.load()
        with tempfile.TemporaryDirectory(prefix='stock-observation-test-') as base:
            os.chmod(base,0o700);inputs=self.inputs(base)
            proc=Mock();socket=Mock(side_effect=AssertionError('socket must not be touched'))
            p=c.prepare(self.loaded,inputs,os_api=os,socket_factory=socket,proc=proc,monotonic=time.monotonic,sleep=time.sleep)
            try:
                self.assertEqual(stat.S_IMODE(os.stat(p.owned.path).st_mode),0o700)
                dest=str(p.owned.path/'capture.mp4')
                sink=p.transport._create_sink(dest,time.monotonic()+5,observed_size=3)
                self.assertEqual(sink.write(b'abc'),3);sink.close()
                self.assertEqual(Path(p.owned.path/'capture.mp4').read_bytes(),b'abc')
                facts=p.retained.facts();self.assertEqual(facts.confirmed_written,3);self.assertEqual(facts.close_outcome,'closed')
                self.assertEqual(tuple(p.retained.created_identity)[:2],(os.stat(dest).st_dev,os.stat(dest).st_ino))
                with self.assertRaisesRegex(ValueError,'sink_attempt_spent'):
                    p.transport._create_sink(dest,time.monotonic()+5,observed_size=3)
                socket.assert_not_called();self.assertEqual(proc.mock_calls,[])
            finally:p.close()
    def test_actual_capsule_writer_and_private_pull_custody(self):
        self.load()
        with tempfile.TemporaryDirectory(prefix='stock-observation-test-') as base:
            os.chmod(base,0o700);inputs=self.inputs(base)
            p=c.prepare(self.loaded,inputs,os_api=os,socket_factory=Mock(side_effect=AssertionError()),
                proc=Mock(),monotonic=time.monotonic,sleep=time.sleep)
            real_transport=p.transport
            fake=SimpleNamespace(preflight=Mock(),host=Mock(return_value=b'target device transport_id:1\ncamera device transport_id:2'),
                bind=lambda tid: b'target' if tid=='1' else b'camera')
            p.transport=fake
            try:
                co=p.select()
                content=b'abc';digest=hashlib.sha256(content).hexdigest();remote='/sdcard/DCIM/OpenCamera/new.mp4'
                def sync(transport,dest,path,**kwargs):
                    self.assertEqual(transport,'2');self.assertEqual(path,remote)
                    sink=real_transport._create_sink(dest,time.monotonic()+5,observed_size=3)
                    sink.write(content);sink.close()
                fake.sync=sync
                co.shell=lambda role,cmd,**kwargs: remote if cmd.startswith('find ') else '3\n'+digest+'  '+remote
                co.stopped=True;co.files_before='';co.pull()
                co.boots={'target':'t','camera':'c'};co.read_boots=lambda:co.boots
                co.report.update(originals_restored=True,mutex_released=True)
                co.original_preview_verified=True;co.ui_restore_pending=False
                co.persist('before',{'boot_id':'t','camera_boot_id':'c'})
                co.persist('recording-snapshots',[])
                co.persist('outcome',co.report)
                capsule=co.capsule()
                self.assertEqual(capsule['media']['sink_facts']['confirmed_written'],3)
                self.assertEqual(capsule['media']['created_identity'],list(p.retained.created_identity))
                self.assertFalse(capsule['control_binding']['per_frame_controls_proven'])
                for label,record in capsule['records'].items():
                    raw=Path(p.owned.path/record['file']).read_bytes()
                    self.assertEqual(hashlib.sha256(raw).hexdigest(),capsule['records_sha256'][label])
                self.assertEqual(capsule['geometry_review_status'],'actual_media_review_required')
            finally:p.close()

    def test_real_parser_rejects_preview_with_encoder(self):
        import ast
        source=self.load();m=source.modules
        tree=ast.parse((ROOT/'06-tools/test_camera_capture_metadata.py').read_text())
        sample=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='sample')
        parser=m['camera_capture_metadata'];scope={'FIELDS':parser.FIELDS,'RESULT_ONLY':parser.RESULT_ONLY}
        exec(compile(ast.Module(body=[sample],type_ignores=[]),'<public-fixture>','exec'),scope)
        co=object.__new__(m['coordinator'].Coordinator);co.parser=parser;co.clock=lambda:0
        co.shell=lambda *args,**kwargs:scope['sample'](recording=True).replace('VIDEO_RECORD','PREVIEW')
        with self.assertRaises(m['coordinator'].PreviewEncoderPending):co.metadata(recording=False)
        co.shell=lambda *args,**kwargs:scope['sample'](recording=False)
        self.assertFalse(co.metadata(recording=False)['recording_verified'])

    def test_old_inspection_hash_rejected_even_if_caller_requests_it(self):
        self.hashes['prestart_inspection']='69af'+'0'*60
        with self.assertRaisesRegex(ValueError,'unreviewed_inspection'):self.load()

    def test_existing_private_directory_not_adopted(self):
        self.load()
        with tempfile.TemporaryDirectory(prefix='stock-observation-test-') as base:
            os.chmod(base,0o700);inputs=self.inputs(base);Path(base,'new-observation').mkdir(mode=0o700)
            with self.assertRaises(Exception):c.prepare(self.loaded,inputs,os_api=os,socket_factory=Mock(),proc=Mock(),monotonic=time.monotonic,sleep=time.sleep)
    def test_namespace_assumption_required(self):
        self.load()
        with tempfile.TemporaryDirectory(prefix='stock-observation-test-') as base:
            from dataclasses import replace
            inputs=replace(self.inputs(base),no_concurrent_namespace_mutation=False)
            with self.assertRaises(ValueError):c.prepare(self.loaded,inputs,os_api=os,socket_factory=Mock(),proc=Mock(),monotonic=time.monotonic,sleep=time.sleep)
            self.assertFalse(Path(base,'new-observation').exists())

if __name__=='__main__':unittest.main()
