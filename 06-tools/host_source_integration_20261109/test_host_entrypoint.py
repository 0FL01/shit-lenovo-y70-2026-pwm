"""Inactive entrypoint tests. --execute uses fake transport/OS only.

One explicit test invokes only the original read-only Git gate against current
nc-lab checkout; all filesystem creation and device capabilities remain fakes.
"""
import dataclasses
import json
import os
import stat
import subprocess
import unittest
from entrypoint_fixture import *

class EntryTests(unittest.TestCase):
    def setUp(self):
        self.context=combined_context();self.c=self.context.__enter__()
        self.s=entry_scenario(self.c)
    def tearDown(self):self.context.__exit__(None,None,None)
    def assert_no_setup_or_transport(self):
        self.assertFalse(self.s.h.used)
        self.assertFalse(self.s.entry_os.path_events)
        self.assertFalse(self.s.entry_os.calls)
    def test_main_success_preserves_owner_signals_report_and_evidence(self):
        s=self.s;answer=json.loads(s.main())
        self.assertEqual(answer['status'],'awaiting_offline_video_validation')
        self.assertFalse(answer['candidate_enabled'])
        self.assertEqual(set(s.abort_handlers),{2,15,1})
        self.assertEqual(bytes(s.entry_os.buffers['/fixture/private/owner.txt']),(s.run.token+'\n').encode())
        self.assertEqual(s.entry_os.nodes['/fixture/private/owner.txt'].st_mode,stat.S_IFREG|0o600)
        self.assertEqual(len(s.factory_calls),1)
        self.assertIs(s.factory_calls[0][0],s.prepared.bundle.adapter)
        self.assertEqual(s.factory_calls[0][1:6],(7,8,'fixture_capture','/fixture/output','/fixture/private'))
        evidence=json.loads(s.entry_os.buffers['/fixture/private/source-evidence.json'])
        self.assertEqual(evidence['status'],'source_finalized')
        self.assertEqual(evidence['source_identity'],list(s.prepared.bundle.retained.created_identity))
        self.assertTrue(s.run.report['mutex_released'])
        self.assertTrue(s.run.report['host_alarm_restored_before_cleanup'])
        self.assertFalse(s.entry_os.fds)
    def test_original_dirty_guard_blocks_before_any_mkdir_transport(self):
        self.s.gate.dirty=True
        with self.assertRaises(ValueError):self.s.main()
        self.assert_no_setup_or_transport()
    def test_actual_current_untracked_tree_blocks_before_mkdir_transport(self):
        self.c.modules['run_p85_guarded_trial'].subprocess=subprocess
        with self.assertRaisesRegex(ValueError,'Relevant runner/helpers differ'):
            self.s.main()
        self.assert_no_setup_or_transport()
    def test_clean_but_uncomposed_source_refused_before_mkdir(self):
        s=self.s;p='06-tools/run_p85_guarded_trial.py';raw=self.c.files[p]
        s.loaded['verified_source_bytes'][p]=raw
        s.loaded['source_blob_ids'][p]=loader.blob_id(raw,'sha1')
        s.gate.bytes[p]=raw
        with self.assertRaisesRegex(RuntimeError,'Required reviewed runtime patches'):s.main()
        self.assert_no_setup_or_transport()
    def test_deferred_source_bytes_tamper_refused_before_finalizer_exec(self):
        s=self.s;p='06-tools/video_validation_split_20261109/host_evidence.py'
        s.loaded['verified_source_bytes'][p]+=b'\n'
        with self.assertRaisesRegex(RuntimeError,'source bytes changed'):s.main()
        self.assertNotIn('host_evidence',sys.modules)
        self.assertNotIn('/fixture/private/source-evidence.json',s.entry_os.nodes)
        self.assertTrue(s.run.report['mutex_released'])
    def test_postload_blob_change_rejected_before_mkdir(self):
        self.s.loaded['source_blob_ids']['06-tools/stock_c1_sweep.py']='0'*40
        with self.assertRaisesRegex(RuntimeError,'Loaded bytes'):self.s.main()
        self.assert_no_setup_or_transport()
    def test_default_offline_branch_never_constructs_dependencies(self):
        report=json.loads(self.s.main(execute=False))
        self.assertTrue(report['offline_only']);self.assert_no_setup_or_transport()
    def test_explicit_private_configuration_required(self):
        self.s.inputs=None
        with self.assertRaises(ValueError):self.s.main()
        self.assert_no_setup_or_transport()
    def test_wrong_base_pin_or_uid_no_transport(self):
        s=self.s;s.inputs=dataclasses.replace(s.inputs,base_pin=dataclasses.replace(s.inputs.base_pin,inode=999))
        with self.assertRaises(RuntimeError):s.main()
        self.assertFalse(s.h.used);self.assertNotIn('/fixture/private',s.entry_os.nodes)
        self.assertFalse(s.entry_os.fds)
    def test_symlink_base_refused_without_device(self):
        s=self.s;s.entry_os.nodes['/fixture'].st_mode=stat.S_IFLNK|0o777
        with self.assertRaises(RuntimeError):s.main()
        self.assertFalse(s.h.used);self.assertNotIn('/fixture/private',s.entry_os.nodes)
    def test_existing_private_directory_no_adoption(self):
        s=self.s;s.entry_os.nodes['/fixture/private']=self.c.fs.meta(22,stat.S_IFDIR|0o700)
        with self.assertRaises(ValueError):s.main()
        self.assertFalse(s.h.used);self.assertFalse(s.entry_os.calls)
        self.assertEqual(s.entry_os.nodes['/fixture/private'].st_ino,22)
    def test_denied_mkdir_closes_owned_fds_and_never_uses_transport(self):
        s=self.s
        def denied():raise PermissionError('fixture denied')
        s.entry_os.hooks['mkdir']=denied
        with self.assertRaises(RuntimeError):s.main()
        self.assertFalse(s.h.used);self.assertFalse(s.entry_os.fds)
    def test_wrong_new_mode_no_repair_or_transport(self):
        s=self.s
        s.entry_os.hooks['after_mkdir']=lambda:setattr(s.entry_os.nodes['/fixture/private'],'st_mode',stat.S_IFDIR|0o755)
        with self.assertRaises(RuntimeError):s.main()
        self.assertFalse(s.h.used);self.assertEqual(s.entry_os.nodes['/fixture/private'].st_mode,stat.S_IFDIR|0o755)
        self.assertFalse(s.entry_os.fds)
    def test_base_swap_after_create_refused(self):
        s=self.s;s.entry_os.hooks['after_mkdir']=lambda:setattr(s.entry_os.nodes['/fixture'],'st_ino',999)
        with self.assertRaises(RuntimeError):s.main()
        self.assertFalse(s.h.used);self.assertFalse(s.entry_os.fds)
    def test_late_mkdir_retains_directory_and_no_transport(self):
        s=self.s;s.entry_os.hooks['after_mkdir']=lambda:setattr(s.h.clock,'now',s.h.clock.now+13)
        with self.assertRaises(RuntimeError):s.main()
        self.assertIn('/fixture/private',s.entry_os.nodes)
        self.assertFalse(s.h.used);self.assertFalse(s.entry_os.fds)
    def test_restore_failure_never_runs_finalizer(self):
        s=self.s;s.fail_label='release-owner'
        with self.assertRaises(RuntimeError):s.main()
        self.assertFalse(s.prepared.finalizer_attempted)
        self.assertNotIn('/fixture/private/source-evidence.json',s.entry_os.nodes)
        self.assertFalse(s.entry_os.fds)
    def test_failed_pull_never_finalizes_retained_partial_file(self):
        s=self.s;s.h.pull_fail=True
        with self.assertRaises(RuntimeError):s.main()
        self.assertFalse(s.prepared.finalizer_attempted)
        self.assertIn('/fixture/private/capture.mp4',s.entry_os.nodes)
        self.assertNotIn('/fixture/private/source-evidence.json',s.entry_os.nodes)
    def test_finalizer_dirty_phase_gate_refuses_before_helper_execution(self):
        s=self.s;original=s.run.execute
        def execute():
            value=original();s.gate.dirty=True;return value
        s.run.execute=execute
        with self.assertRaises(ValueError):s.main()
        self.assertNotIn('host_evidence',sys.modules)
        self.assertNotIn('/fixture/private/source-evidence.json',s.entry_os.nodes)
    def test_capture_replacement_after_cleanup_cannot_supply_new_identity(self):
        s=self.s;original=s.run.execute
        def execute():
            value=original();s.entry_os.nodes['/fixture/private/capture.mp4'].st_ino=999;return value
        s.run.execute=execute
        with self.assertRaisesRegex(RuntimeError,'differs from owned sink inode'):s.main()
        self.assertNotEqual(s.prepared.bundle.retained.created_identity[1],999)
        self.assertNotIn('/fixture/private/source-evidence.json',s.entry_os.nodes)
    def test_preloaded_finalizer_cannot_shadow_reviewed_bytes(self):
        s=self.s;sys.modules['host_evidence']=object()
        with self.assertRaisesRegex(RuntimeError,'Preloaded finalizer'):s.main()
        self.assertNotIn('/fixture/private/source-evidence.json',s.entry_os.nodes)
    def test_finalize_read_close_uncertainty_prevents_artifact(self):
        s=self.s;readfds=set();original=s.entry_os.open
        def open_file(name,flags,mode=0o777,dir_fd=None):
            fd=original(name,flags,mode,dir_fd)
            if name=='capture.mp4' and flags&os.O_ACCMODE==os.O_RDONLY:readfds.add(fd)
            return fd
        s.entry_os.open=open_file
        def fail(fd):
            if fd in readfds:raise OSError('read close uncertain')
        s.entry_os.hooks['close']=fail
        with self.assertRaises(OSError):s.main()
        self.assertIsNone(s.prepared.evidence)
        self.assertNotIn('/fixture/private/source-evidence.json',s.entry_os.nodes)
    def test_postcleanup_evidence_failure_preserves_hardware_and_saved_acquisition(self):
        s=self.s;original=s.run.execute;s.after_execute={}
        def execute():
            result=original()
            s.after_execute['events']=list(s.h.events)
            s.after_execute['raw']=bytes(s.entry_os.buffers['/fixture/output/run.json'])
            return result
        s.run.execute=execute
        def fail(fd,data):
            if s.entry_os.fds[fd].endswith('source-evidence.json'):raise OSError('evidence write failed')
        s.entry_os.hooks['write']=fail
        with self.assertRaises(OSError):s.main()
        self.assertEqual(s.h.events,s.after_execute['events'])
        self.assertEqual(bytes(s.entry_os.buffers['/fixture/output/run.json']),s.after_execute['raw'])
        self.assertTrue(s.run.report['mutex_released'] and s.run.report['watchdog_disarmed'])
        self.assertTrue(s.run.report['original_settings_dbv_logger_restored'])
        self.assertEqual(s.h.events.count(('service','reboot:')),0)
        self.assertEqual(s.run.report['status'],'awaiting_offline_video_validation')
    def test_namespace_stability_assumption_is_explicit(self):
        s=self.s;s.inputs=dataclasses.replace(s.inputs,no_concurrent_namespace_mutation=False)
        with self.assertRaisesRegex(RuntimeError,'namespace stability'):s.main()
        self.assertFalse(s.h.used);self.assertFalse(s.entry_os.calls)
    def test_finalizer_no_retry_after_artifact_write_failure(self):
        s=self.s
        def fail(fd,data):
            if s.entry_os.fds[fd].endswith('source-evidence.json'):raise OSError('evidence write uncertain')
        s.entry_os.hooks['write']=fail
        with self.assertRaises(OSError):s.main()
        self.assertTrue(s.prepared.finalizer_attempted);self.assertIsNone(s.prepared.evidence)
        with self.assertRaisesRegex(RuntimeError,'already spent'):
            s.prepared.finalize(s.run,json.dumps(s.run.report).encode())
    def test_construction_and_entrypoint_origins_are_byte_loaded(self):
        for name in ('inert_host_construction','fresh_private_directory','host_entrypoint'):
            module=self.c.modules[name];path='06-tools/host_source_integration_20261109/'+name+'.py'
            self.assertEqual(module.__file__,str(ROOT/path));self.assertEqual(module.__spec__.origin,str(ROOT/path))
            self.assertEqual(hashlib.sha256(self.c.snapshots[path]).hexdigest(),
                             MANIFEST['input_sha256'][path])
    def test_private_path_grammar_refuses_before_setup(self):
        self.s.inputs=dataclasses.replace(self.s.inputs,directory_name='../escape')
        with self.assertRaises(ValueError):self.s.main()
        self.assert_no_setup_or_transport()
    def test_owned_directory_is_single_attempt(self):
        fresh=self.c.modules['fresh_private_directory'];s=self.s
        owner=fresh.OwnedDirectory(base_path=s.inputs.base_path,base_pin=s.inputs.base_pin,
            directory_name=s.inputs.directory_name,os_api=s.entry_os,monotonic=s.h.clock)
        owner.create(12);owner.close();calls=len(s.entry_os.calls)
        with self.assertRaisesRegex(RuntimeError,'attempt_spent'):owner.create(12)
        self.assertEqual(len(s.entry_os.calls),calls)
    def test_direct_setup_collision_does_not_adopt(self):
        s=self.s;s.entry_os.nodes['/fixture/private']=self.c.fs.meta(22,stat.S_IFDIR|0o700)
        with self.assertRaises(RuntimeError):self.c.modules['host_entrypoint'].prepare(s.loaded,s.inputs,s.dependencies)
        self.assertFalse(s.h.used)
        self.assertEqual(s.entry_os.nodes['/fixture/private'].st_ino,22)
        self.assertFalse(s.entry_os.fds)

if __name__=='__main__':unittest.main()
