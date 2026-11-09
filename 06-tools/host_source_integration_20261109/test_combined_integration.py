"""Combined actual caller/adapter/real sink tests, entirely fake proc/OS/socket/time."""
import ast
import dataclasses
import json
import inspect
import stat
import unittest
from combined_fixture import *

class CombinedTests(unittest.TestCase):
    def setUp(self):
        self.context=combined_context();self.c=self.context.__enter__()
    def tearDown(self):self.context.__exit__(None,None,None)
    def scenario(self,**kwargs):return scenario(self.c,**kwargs)
    def assert_failed(self,s):
        with self.assertRaises(RuntimeError):s.execute()
        self.assertNotEqual(s.run.report.get('status'),'awaiting_offline_video_validation')
        self.assertIsNot(s.run.report.get('video_lifecycle_complete'),True)
    def test_real_six_argument_constructor_is_inert(self):
        m=self.c.modules;clock=self.c.f.Clock();calls=[]
        class NoIO:
            def __getattr__(self,name):
                calls.append(name);raise AssertionError('Unexpected constructor I/O')
        g=NoIO();stock=m['stock_c1_sweep']
        stock.uuid=NS(uuid4=lambda:NS(hex='a'*32));stock.now=lambda:'fixture-time'
        r=m['run_p85_timed_stock_trial'].TimedStockTrial(g,7,8,'fixture_capture',
            Path('/fixture/output'),Path('/fixture/private'),sleep=clock.sleep,monotonic=clock)
        self.assertIs(r.g.transport,g)
        self.assertIs(r.g.trial,r)
        self.assertFalse(r.candidate or r.report['candidate_enabled'])
        self.assertEqual([r.report[k] for k in ('active_limit_seconds','host_limit_seconds',
                            'recovery_reserve_seconds','timed_watchdog_seconds')],[37,45,8,60])
        self.assertEqual(r.report['envelope_timings'],[])
        self.assertFalse(calls)
        with self.assertRaises(ValueError):
            m['run_p85_timed_stock_trial'].TimedStockTrial(g,7,8,'fixture_capture',
                Path('/fixture/output'),Path('/fixture/private'),candidate=True)
    def test_actual_stop_pull_restore_success_and_retention(self):
        s=self.scenario();s.os.write_sizes=[1,2];s.execute();s.assert_restored(self)
        r=s.run.report;ret=s.bundle.retained
        self.assertEqual(r['status'],'awaiting_offline_video_validation')
        self.assertTrue(r['video_lifecycle_complete'])
        self.assertEqual(r['video_acquisition_origin'],'timed_stock_caller')
        self.assertEqual(bytes(s.os.data),b'abc')
        self.assertEqual(ret.created_identity,(3,4,17,stat.S_IFREG|0o600))
        self.assertEqual(ret.facts().confirmed_written,3)
        self.assertEqual(ret.facts().close_outcome,'closed')
        self.assertFalse(ret.facts().write_outcome_uncertain)
        self.assertFalse(s.os.fds)
        self.assertTrue(r['camera_stopped_verified'] and r['camera_ui_temp_removed'])
        self.assertFalse(s.probe.calls)
        self.assertEqual(s.h.events.count(('service','reboot:')),0)
    def test_original_source_gate_before_new_dependencies(self):
        s=self.scenario(dirty=True)
        with self.assertRaises(ValueError):s.construct()
        self.assertFalse(s.proc.calls);self.assertFalse(s.os.calls);self.assertFalse(s.h.used)
        self.assertEqual(s.gate.calls[-1],('diff','--quiet','a'*40,'--',*construction.HARDWARE_PATHS))
    def test_original_guard_not_replaced_by_virtual_boolean(self):
        self.assertIn('source_provenance',construction.construct.__code__.co_names)
        self.assertEqual(len(construction.HARDWARE_PATHS),20)
        self.assertTrue(set(loader.BASELINE).issubset(construction.HARDWARE_PATHS))
    def test_acquisition_bridge_sticky_trust_invalidates_no_socket(self):
        s=self.scenario();s.proc.exe=dataclasses.replace(s.proc.exe,inode=99)
        count=len(s.h.used)
        with self.assertRaises(self.c.modules['offline_baseline_adb'].TransportError):
            s.bundle.adapter.preflight()
        self.assertTrue(s.bundle.adapter.trust_invalidated)
        self.assertTrue(s.bundle.adapter.last_facts.trust_invalidated)
        self.assertEqual(len(s.h.used),count)
    def test_second_sink_attempt_never_recreates_or_loses_identity(self):
        s=self.scenario();s.execute();ret=s.bundle.retained;first=ret.sink;identity=ret.created_identity
        calls=len(s.os.calls)
        with self.assertRaises(self.c.modules['offline_baseline_adb'].TransportError):s.h.pull()
        self.assertIs(ret.sink,first);self.assertEqual(ret.created_identity,identity)
        self.assertEqual(len(s.os.calls),calls)
    def test_capacity_failure_no_created_identity_cleanup_still_runs(self):
        s=self.scenario();s.os.available=0;self.assert_failed(s);s.assert_restored(self)
        self.assertTrue(s.bundle.retained.attempted)
        self.assertIsNone(s.bundle.retained.created_identity)
        self.assertIsNone(s.bundle.retained.sink)
        self.assertFalse(s.bundle.retained.facts().created)
        self.assertNotIn(self.c.f.DEST,s.os.nodes)
    def test_observed_size_metadata_mismatch_fails_before_completion(self):
        for size in ('0','2','4','101'):
            with self.subTest(size=size):
                s=self.scenario();s.bad_stat=size;self.assert_failed(s);s.assert_restored(self)
                self.assertFalse(s.run.panel_uncertain)
    def test_partial_transfer_retains_closed_bytes_without_admission(self):
        s=self.scenario();s.h.pull_fail=True;self.assert_failed(s);s.assert_restored(self)
        self.assertEqual(bytes(s.os.data),b'abc')
        self.assertEqual(s.bundle.retained.facts().close_outcome,'closed')
        self.assertNotIn('video_bytes',s.run.report)
    def test_sink_write_error_and_late_write_retain_uncertainty(self):
        for late in (False,True):
            with self.subTest(late=late):
                s=self.scenario()
                if late:s.os.hooks['after_write']=lambda n:setattr(s.h.clock,'now',s.h.clock.now+100)
                else:
                    def fail(*args):raise OSError('fixture write failure')
                    s.os.hooks['write']=fail
                self.assert_failed(s);s.assert_restored(self)
                self.assertEqual(s.bundle.retained.facts().write_outcome_uncertain,not late)
                if late:self.assertEqual(s.bundle.retained.facts().confirmed_written,3)
                self.assertEqual(s.bundle.retained.facts().close_outcome,'closed')
                self.assertFalse(s.run.panel_uncertain)
    def test_sink_close_failure_retains_identity_and_not_admissible(self):
        s=self.scenario()
        def fail(*args):raise OSError('fixture close uncertain')
        s.os.hooks['close']=fail
        self.assert_failed(s);s.assert_restored(self)
        self.assertEqual(s.bundle.retained.created_identity,(3,4,17,stat.S_IFREG|0o600))
        self.assertNotEqual(s.bundle.retained.facts().close_outcome,'closed')
    def test_acquire_failure_facts_survive_no_returned_sink(self):
        s=self.scenario()
        def late(path):
            if path==self.c.f.DEST:s.h.clock.now+=100
        s.os.hooks['after_open']=late
        self.assert_failed(s);s.assert_restored(self)
        self.assertIsNone(s.bundle.retained.sink)
        self.assertIsNone(s.bundle.retained.created_identity)
        self.assertTrue(s.bundle.retained.facts().created)
        self.assertIn(self.c.f.DEST,s.os.nodes)
    def test_missing_stop_ui_no_sink_and_camera_cleanup_pending(self):
        s=self.scenario();s.bad_ui=True;self.assert_failed(s);s.assert_restored(self)
        self.assertFalse(s.bundle.retained.attempted)
        self.assertTrue(s.run.report['camera_ui_cleanup_pending'])
        self.assertTrue(s.run.recording)
    def test_restore_failure_never_promotes_closed_sink(self):
        for label in ('restore-setting','final-esd','disarm-watchdog','release-owner'):
            with self.subTest(label=label):
                s=self.scenario();s.fail_label=label;self.assert_failed(s)
                self.assertEqual(s.bundle.retained.facts().close_outcome,'closed')
                self.assertNotIn('mutex_released',s.run.report)
    def test_active_fault_one_recovery_no_next_stage(self):
        for fault in ('timeout','late','alarm'):
            with self.subTest(fault=fault):
                s=self.scenario();s.fail_label='camera-active-fixture';s.fail_kind=fault;stages=[]
                def stage(label):
                    stages.append(label);s.run.cam('fixture active camera query','active-fixture')
                s.run.write_stage=stage;self.assert_failed(s);s.assert_restored(self)
                self.assertEqual(stages,['sham15'])
                self.assertEqual(s.h.events.count(('service','reboot:')),1)
                self.assertTrue(s.run.report['recovery_reboot_verified'])
    def test_malformed_recovery_boot_blocks_restore(self):
        s=self.scenario();s.fail_label='camera-active-fixture';s.boot_after='not-a-uuid'
        s.run.write_stage=lambda _:s.run.cam('fixture query','active-fixture')
        self.assert_failed(s)
        self.assertTrue(s.run.recovery_failed)
        self.assertNotIn('restore-setting',s.labels);self.assertNotIn('release-owner',s.labels)
        self.assertEqual(s.h.events.count(('service','reboot:')),1)
    def legacy_scenario(self):
        s=self.scenario()
        cls=self.c.modules['guarded_adb_socket'].GuardedADB
        self.assertEqual(str(inspect.signature(cls.run)),
            '(self, argv, *, capture_output=True, text=False, timeout=25, check=False)')
        legacy=object.__new__(cls);legacy.identities={};s.legacy_sync=[]
        def shell(transport,command,timeout):
            result=s.bundle.adapter.run(['adb','-t',str(transport),'shell',command],timeout=timeout)
            return result.returncode,result.stdout,result.stderr
        def sync(transport,local,remote,*,pull,timeout):
            s.legacy_sync.append((transport,str(local),remote,pull,timeout))
            s.os.data.extend(s.h.pull_data)
        legacy.shell=shell;legacy.sync=sync
        s.run.g=s.ns['DeadlineTransport'](s.run,legacy)
        return s
    def test_legacy_stop_default_still_validates(self):
        s=self.legacy_scenario()
        self.c.modules['run_p85_guarded_trial'].subprocess=s.probe
        s.run.stop_camera()
        self.assertEqual(s.run.report['video_profile']['codec'],'h264')
        self.assertEqual(s.probe.calls[0][1]['timeout'],20)
        self.assertNotIn('video_validation_status',s.run.report)
        self.assertEqual(s.legacy_sync,[('8',self.c.f.DEST,self.c.f.REMOTE,True,90)])
    def test_deferred_validation_alone_preserves_legacy_transport(self):
        s=self.legacy_scenario()
        s.run.stop_camera(defer_video_validation=True)
        self.assertEqual(len(s.legacy_sync),1)
        self.assertFalse(s.probe.calls)
        self.assertEqual(s.run.report['video_validation_status'],'pending_offline')
    def test_new_adapter_missing_bound_metadata_fails_without_fallback(self):
        s=self.scenario();before=len(s.h.used)
        with self.assertRaises(ValueError):s.run.stop_camera(defer_video_validation=True)
        self.assertIsNone(s.bundle.retained.sink)
        self.assertNotIn('video_transfer_verified',s.run.report)
        self.assertFalse(s.probe.calls)
        self.assertFalse(any(event==('service','sync:') for event in s.h.events))
    def test_host_timed_route_explicitly_binds_exact_size_once(self):
        s=self.scenario();calls=[];original=s.bundle.adapter.run
        def record(argv,**kw):
            if argv[3]=='pull':calls.append(dict(kw))
            return original(argv,**kw)
        s.bundle.adapter.run=record
        s.execute()
        self.assertEqual(len(calls),1)
        self.assertEqual((calls[0]['expected_size'],calls[0]['byte_cap']),(3,3))
        self.assertEqual(s.bundle.retained.facts().confirmed_written,3)
    def test_bound_transport_typeerror_is_not_retried_as_legacy(self):
        s=self.scenario();calls=[];original=s.bundle.adapter.run
        def fail(argv,**kw):
            if argv[3]=='pull':
                calls.append(dict(kw));raise TypeError('fixture bounded transport failure')
            return original(argv,**kw)
        s.bundle.adapter.run=fail
        with self.assertRaises(TypeError):s.run.stop_camera(bounded_pull=True)
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0]['expected_size'],3)
        self.assertIsNone(s.bundle.retained.sink)
        self.assertFalse(s.probe.calls)
    def test_budget_constants_and_original_alarm_logic(self):
        m=self.c.modules
        self.assertEqual(m['run_p85_timed_stock_trial'].ACTIVE_SECONDS,37)
        self.assertEqual(m['p85_guarded_trial'].CANDIDATE_BUDGET_SECONDS,45)
        self.assertEqual(m['p85_guarded_trial'].CANDIDATE_WATCHDOG_SECONDS,60)
        self.assertIn('sleep 600',m['stock_c1_sweep'].watchdog_command('/fixture','fixture_token','11111111-1111-4111-8111-111111111111'))
        s=self.scenario();s.execute()
        self.assertIn(('timer',37.0),s.signal.events)
        self.assertEqual(s.signal.timer,(0.0,0.0))
        self.assertTrue(s.run.report['host_alarm_restored_before_cleanup'])


    def test_final_evidence_uses_retained_created_inode_after_restore(self):
        s=self.scenario();s.execute();e=evidence_modules(self.c,s)
        ret=s.bundle.retained;raw=json.dumps(s.run.report).encode()
        result=e.h.source_evidence(raw,123,ret.facts(),
            expected_source_identity=ret.created_identity,no_concurrent_writers=True)
        self.assertEqual(result['status'],'source_finalized')
        self.assertEqual(result['source_identity'],list(ret.created_identity))
        self.assertEqual(result['source_sha256'],hashlib.sha256(b'abc').hexdigest())
        self.assertEqual(set(e.proof['source_blob_ids']),set(construction.FINALIZER_PATHS))
        e.reader.replaced=True
        with self.assertRaises(RuntimeError):
            e.h.source_evidence(raw,123,ret.facts(),
                expected_source_identity=ret.created_identity,no_concurrent_writers=True)
    def test_before_cleanup_or_after_failure_evidence_refused(self):
        for fail in (None,'release-owner'):
            with self.subTest(fail=fail):
                s=self.scenario()
                if fail:
                    s.fail_label=fail;self.assert_failed(s)
                else:s.run.stop_camera(defer_video_validation=True,bounded_pull=True)
                e=evidence_modules(self.c,s);ret=s.bundle.retained
                with self.assertRaises(RuntimeError):
                    e.h.source_evidence(json.dumps(s.run.report).encode(),123,ret.facts(),
                        expected_source_identity=ret.created_identity,no_concurrent_writers=True)
                self.assertFalse(e.reader.calls)
    def test_validator_snapshot_survives_combined_caller_change(self):
        s=self.scenario();e=evidence_modules(self.c,s)
        self.assertNotEqual(self.c.snapshots['06-tools/run_p85_guarded_trial.py'],
                            self.c.files['06-tools/run_p85_guarded_trial.py'])
        validator=e.a.validator(e.snapshot)
        valid={'streams':[{'codec_type':'video','codec_name':'h264','width':1280,
            'height':720,'avg_frame_rate':'30/1'}],'format':{'duration':'15'}}
        self.assertEqual(validator(valid,13.5)['codec'],'h264')
        with self.assertRaises(ValueError):validator({},13.5)
        with self.assertRaises(RuntimeError):e.a.validator(e.snapshot+b'\n')

if __name__=='__main__':unittest.main()
