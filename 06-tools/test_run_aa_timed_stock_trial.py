"""Offline full lifecycle with real wire/framing/trace/C1 validators and fake I/O."""
from copy import deepcopy
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import signal
import tempfile
import unittest
from unittest.mock import patch

import run_aa_timed_stock_trial as t
from test_p85_batched_envelope import framed
from test_stock_c1_sweep import execute_reader_fixture,N
from test_p85_integration import REF,BOOT
from test_run_p85_batched_trial import ANCHOR
from test_run_p85_timed_stock_trial import Clock
from test_dsi_trial_transaction import TransactionTests

class Transport:
    def __init__(self,run):self.run=run
    def shell(self,target,command,timeout):
        r=self.run;r.clock.sleep(.03)
        if target==1:return 0,b'\x89PNG\r\n\x1a\nfixture',b''
        label=r.label;plan=r.plan_now
        if label==r.gap_inject:r.trace+=r.gap_event;r.gap_inject=None
        if label==r.failure:raise TimeoutError('injected unknown transport completion')
        payload={}
        for part in plan.parts:
            if part.label in ('BEGIN','END'):
                marker=part.command.split('<6>',1)[1].split('\\n',1)[0];r.log+=f'[{r.clock():.6f}] {marker}\n';value=''
            elif part.label=='WAIT':r.clock.sleep(2);value=''
            elif part.label=='PRE_GUARD':value='GUARD_TIMING 100.00 100.10\n'
            elif part.label=='TRACE_GUARD':
                t.validate_safe_gap(r.trace_snapshot,r.trace,r.entry_count);value='TRACE_GUARD_OK\n'
            elif part.label=='TRACE_BEFORE':value=r.trace
            elif part.label=='TRACE_AFTER':value=r.trace
            elif part.label=='CHILD':
                r.children.append(label)
                if label.endswith('-write'):
                    name='aa10' if label=='aa10-write' else 'stock'
                    value='BLOCK_TRACE_BEGIN -1\n'+r.trace+'BLOCK_TRACE_END -1\n'
                    for i in range(5):
                        r.trace+=TransactionTests().block(i)
                        value+=f'BLOCK_TRACE_BEGIN {i}\n'+r.trace+f'BLOCK_TRACE_END {i}\n'
                    r.log+=''.join(f'dsi-ctrl-1: dsi_ctrl_cmd_transfer len={len(p)}, type=0x{h[0]:02x} hs cmds= {p.hex(" ")}\n' for _,h,_,p in t.aa.packets(r.programs[name]))
                elif label.endswith('-c1'):
                    nonce=re.search(r'pwm-c1-([0-9a-f]{12})',part.command)[1]
                    value=r.reader.replace(N,nonce)
                    for index,rc in enumerate((0,3,0,0)):
                        if index!=1:r.trace+='mode_entry: pending=0 length=11 flags=0\n'
                        r.trace+=f'mode_ctrl_return: rc={rc}\n'
                        if index!=1:r.trace+='mode_return: rc=0\n'
                else:
                    value='ESD_ISOLATED esd_sw_sim_success\nR 23:A9 0x0e\nR 24:9D 0x0e\nR 00:52 0x0e 0x10\nESD_RESTORED reg_read\n'
                    for index,rc in enumerate(t.aa.SELECTOR_CONTROLS):
                        if index not in (1,4,7):r.trace+='mode_entry: pending=0 length=11 flags=0\n'
                        r.trace+=f'mode_ctrl_return: rc={rc}\n'
                        if index not in (1,4,7):r.trace+='mode_return: rc=0\n'
                if label==r.corrupt:value=value.replace('rc=0','rc=-5',1).replace('ESD_RESTORED','BAD_RESTORATION')
            elif part.label=='KERNEL':value=r.log
            elif part.label=='FIELDS':value='3600\n0\n0\nEnforcing\n'
            elif part.label=='DISPLAY':value='mActiveSfDisplayMode= peakRefreshRate=120.00001\n'
            elif part.label=='BOOT':value=BOOT+'\n'
            elif part.label in ('OWNER','TRACE_OWNER'):value=''
            else:raise AssertionError(part.label)
            payload[part.label]=value
        return 0,framed(plan,payload),b''

class Sim(t.AATimedTrial):
    reader=None
    def __init__(self,root,**kwargs):
        clock=Clock();super().__init__(None,6,1,'aa_timed_test',root,root,sleep=clock.sleep,monotonic=clock,**kwargs)
        self.clock=clock;self.g=t.timed.DeadlineTransport(self,Transport(self));self.calls=[];self.children=[]
        self.log=ANCHOR;self.trace='';self.failure=None;self.corrupt=None;self.frames=135;self.slow=False;self.gap_inject=None;self.gap_event='mode_ctrl_return: rc=0\n'
    def setup(self):
        self.before={'boot_id':BOOT,'native_dbv':6438,'screen_off_timeout':'1800000'};self.reference=REF
        self.report.update(source_worktree_clean_for_runner=True,source_commit='a'*40,source_blob_ids={'fixture.py':'b'*40},source_tracked_paths=['fixture.py'])
        self.report['recording_preflight']=[self.metadata('preflight1'),self.metadata('preflight2')]
    def identity(self):self.calls.append('identity')
    def camera_identity(self):self.calls.append('camera-identity')
    def envelope(self,plan,label):
        self.plan_now=plan;self.label=label;self.calls.append(label)
        return super().envelope(plan,label)
    def mark(self,suffix):
        marker=self._marker(suffix);self.log+=f'[{self.clock():.6f}] {marker}\n';self.clock.sleep(.01);return marker
    def metadata(self,label,**kwargs):
        start=self.clock();startutc=self.now();self.clock.sleep(.03);frame=self.frames;self.frames+=135
        self.calls.append(label)
        if label==self.failure:raise ValueError('camera metadata')
        from aa_acquisition_validation import PROFILE
        stamp=frame*1000000000//30
        data={**PROFILE,'request_id':1,'frame_duration_ns':33333333,'frame_count':frame,'timestamp_ns':stamp,'rolling_shutter_skew_ns':15047630}
        return {'frame_count':frame,'timestamp_ns':stamp,'session_token':'session','host_capture_bounds':{'begin_monotonic':start,'end_monotonic':self.clock()},'host_call_start_utc':startutc,'host_call_end_utc':self.now(),'host_call_elapsed_seconds':.03,'recording_verified':True,'request':deepcopy(data),'result':deepcopy(data),'rolling_shutter_skew_ns':15047630,'encoder_stream_id':1,'streams':[{'id':1,'width':1280,'height':720,'consumer_kind':'GraphicBufferSource','requested':True,'state':4,'frames_produced':frame,'last_timestamp_ns':stamp}]}
    def now(self):return datetime.fromtimestamp(1700000000+self.clock(),timezone.utc).isoformat()
    def shell(self,command,**kwargs):
        label=kwargs.get('label','shell');self.calls.append(label);self.clock.sleep(.01)
        if label==self.failure:raise TimeoutError(label)
        if '-replay-trace-' in label or label in ('main-trace-initial','main-trace-final') or label.endswith('-hold-trace') or label.endswith('-redraw-trace'):return self.trace
        if label.endswith('-esd'):return 'reg_read'
        if label.endswith('-replay'):
            self.log+='dsi-ctrl-1: dsi_ctrl_cmd_transfer len=3, type=0x39 hs cmds= 51 0e 10\n'
            self.trace+='mode_ctrl_return: rc=0\n'
        if label.endswith('-wire'):return self.log
        if label.endswith('-redraw-before') or label.endswith('-redraw-returned'):
            if self.slow:self.clock.sleep(8)
            return '<hierarchy><node text="Screen timeout" package="com.android.settings" clickable="true" bounds="[0,0][20,20]"/></hierarchy>'
        if label.endswith('-redraw-opened'):return '<hierarchy><node text="10 minutes"/></hierarchy>'
        if label.endswith('-redraw-setting'):return '1800000'
        return ''
    def wait_value(self,*args,**kwargs):pass
    def recover(self):
        self.calls.append('reboot');assert not self.guard_context and self.active_start is None
        self.panel_uncertain=self.pending_read=self.inflight=self.active_failed=False
        self.report['recovery_reboot_verified']=True;self.trace=''
    def stop_camera(self,**kwargs):
        self.calls.append('stop-camera');self.report.update(camera_stopped_verified=True,video_transfer_verified=True,video_bytes=5,video_validation_status='pending_offline')
    def cleanup_camera_xml(self):self.report['camera_ui_temp_removed']=True
    def restore(self):
        if self.panel_uncertain or self.pending_read:raise AssertionError('restore into uncertainty')
        self.calls.append('settings-restore');self.report.update(original_settings_dbv_logger_restored=True,watchdog_disarmed=True,mutex_released=True,main_trace_removed_verified=True,chunks_removed_verified=True,target_ui_temp_removed=True)

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result,_,_=execute_reader_fixture();assert result.returncode==0,result.stderr;Sim.reader=result.stdout
    def execute(self,run):
        with patch.object(t.s,'now',run.now):return run.execute()
    def test_complete_real_validators(self):
        from aa_acquisition_validation import validate_acquisition
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);report=self.execute(run)
            validate_acquisition(report)
            self.assertEqual(report['full_table_writes_attempted'],['baseline','sham_stock','return_stock'])
            self.assertEqual(len(run.children),12)
            self.assertLess(run.calls.index('disarm-candidate'),run.calls.index('return_stock-hold-start'))
            self.assertLess(run.calls.index('chunks-verify'),run.calls.index('timed-watchdog-arm'))
            self.assertLess(run.calls.index('return_stock-after-hold'),run.calls.index('settings-restore'))
            self.assertEqual(report['candidate_attempts'],0);self.assertLess(report['active_G_seconds'],37)
            self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0,0))
    def test_all_child_transport_failures_no_followup_writer(self):
        labels=[stage+suffix for stage in ('baseline','sham_stock','return_stock') for suffix in ('-write','-before-hold','-c1','-after-hold')]
        for label in labels:
            with self.subTest(label=label),tempfile.TemporaryDirectory() as root:
                run=Sim(root);run.failure=label
                with self.assertRaises(RuntimeError):self.execute(run)
                self.assertIn('reboot',run.calls);self.assertNotIn(label,run.children)
                self.assertEqual(run.calls.count('reboot'),1)
                after=run.calls[run.calls.index('reboot')+1:]
                self.assertFalse(any(x.endswith('-write') for x in after));self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0,0))
    def test_callback_failure_stops_before_next_child(self):
        for label in ('baseline-write','sham_stock-before-hold','return_stock-c1'):
            with tempfile.TemporaryDirectory() as root:
                run=Sim(root);run.corrupt=label
                with self.assertRaises(RuntimeError):self.execute(run)
                self.assertEqual(run.children[-1],label);self.assertIn('reboot',run.calls)
    def test_postreturn_failure_uses_recovery_after_short_disarm(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);run.failure='return_stock-after-hold'
            with self.assertRaises(RuntimeError):self.execute(run)
            self.assertLess(run.calls.index('disarm-candidate'),run.calls.index('reboot'))
            self.assertNotIn('return_hold_and_postselectors_verified',run.report)
    def test_slow_baseline_stops_before_arm_without_reboot(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);run.slow=True
            with self.assertRaises(RuntimeError):self.execute(run)
            self.assertNotIn('timed-watchdog-arm',run.calls);self.assertNotIn('reboot',run.calls)
            self.assertEqual(run.report['full_table_writes_attempted'],['baseline'])
    def test_replay_rejects_hidden_table(self):
        good=ANCHOR+'BEGIN\ndsi-ctrl-1: dsi_ctrl_cmd_transfer len=3, type=0x39 hs cmds= 51 0e 10\nEND\n'
        self.assertTrue(t.validate_replay(good,'BEGIN','END',REF)['exact_wire_verified'])
        with self.assertRaises(ValueError):t.validate_replay(good.replace('END','dsi-ctrl-1: dsi_ctrl_cmd_transfer len=2, type=0x39 hs cmds= aa 11\nEND'),'BEGIN','END',REF)
    def test_unqualified_candidate_refused_before_io(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):Sim(root,aa_candidate=True)
    def test_candidate_latched_before_dispatch(self):
        with tempfile.TemporaryDirectory() as root:
            stock=Sim(root);proof=self.execute(stock)
        with tempfile.TemporaryDirectory() as root:
            from aa_acquisition_validation import QUALIFICATION_SCHEMA,ALGORITHM,canonical_sha
            optical={'schema':QUALIFICATION_SCHEMA,'status':'limited_stock_diagnostic_pass','acquisition_canonical_sha256':canonical_sha(proof),'source_commit':'a'*40,'source_blob_ids':{'fixture.py':'b'*40},'optical_analysis_sha256':'c'*64,'algorithm':ALGORITHM,'fine_relative_tolerance':.05,'mean_y_relative_tolerance':.05,'rois_xywh':{'main':[250,0,100,400],'left':[100,0,100,400],'right':[400,0,100,400]},'baseline_fine_search_cycles_per_row':[.01,.03],'stock_ratios':[{'roi':roi,'stage':stage,'normalized_fine_over_baseline':1.,'mean_y_over_baseline':1.} for roi in ('main','left','right') for stage in ('sham_stock','return_stock')],'observed_active_G_seconds':proof['active_G_seconds'],'prearm_planning_estimate':proof['prearm_planning_estimate'],'physical_pwm_hz':None,'full_waveform_equivalence':None,'future_latency_bound':False,'optical_return_approval':False,'candidate_geometry_rule':'Use frozen ROI/band; baseline-only geometry review; mismatch is inconclusive, no B-driven reselection'}
            run=Sim(root,aa_candidate=True,stock_qualification=proof,optical_qualification=optical,source_record={'source_commit':'a'*40,'source_blob_ids':{'fixture.py':'b'*40}})
            run.failure='aa10-write'
            with self.assertRaises(RuntimeError):self.execute(run)
            self.assertEqual(run.report['candidate_attempts'],1);self.assertTrue(run.report['unknown_value_write_attempted'])
            self.assertEqual(run.report['full_table_writes_attempted'],['baseline','aa10']);self.assertNotIn('return_stock-write',run.calls)

if __name__=='__main__':unittest.main()

class SafeGapTests(unittest.TestCase):
    POLL=' kworker/1:2-88 [001] ... 123.450000: mode_ctrl_return: (dsi_display_validate_status+0x154/0x308 [msm_drm] <- dsi_ctrl_cmd_transfer) rc=1\n'
    def test_only_exact_native_gap_poll(self):
        self.assertEqual(len(t.validate_safe_gap('',self.POLL,0)),1)
        for bad in (self.POLL.replace('kworker/1:2','app'),self.POLL.replace('rc=1','rc=0'),self.POLL.replace('+0x154','+0x155'),self.POLL+'LOST',self.POLL+'mode_entry: pending=0 length=11 flags=0\n',self.POLL+'mode_return: rc=0\n'):
            with self.subTest(bad=bad),self.assertRaises(ValueError):t.validate_safe_gap('',bad,0)
    def test_poll_inside_operation_rejected(self):
        raw='BLOCK_TRACE_BEGIN -1\nBLOCK_TRACE_END -1\n';trace=''
        for index in range(5):
            trace+=TransactionTests().block(index)
            if index==0:trace+=self.POLL
            raw+=f'BLOCK_TRACE_BEGIN {index}\n'+trace+f'BLOCK_TRACE_END {index}\n'
        with self.assertRaises(ValueError):t.aa.tx.validate_batch_capture(raw,0)
        with self.assertRaises(ValueError):t.aa.trace_delta('',self.POLL,0,[],[])
    def test_probe_absence_does_not_mask_grep_error(self):
        import subprocess
        for code in (0,1,2):
            result=subprocess.run(['sh','-c',f'grep() {{ return {code}; }}; '+t.absent_probes()],capture_output=True)
            self.assertEqual(result.returncode==0,code==1)

class EntrypointTests(unittest.TestCase):
    def test_real_main_to_finished_source_evidence_with_fake_device_io(self):
        import sys
        from types import SimpleNamespace as NS
        sys.path.insert(0,str(Path(t.__file__).parent/'host_source_integration_20261109'))
        import host_entrypoint as host
        import aa_video_validation as media
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);out=root/'public';private=root/'private';calls=[];holder={}
            source={'source_commit':'a'*40,'source_blob_ids':{'fixture.py':'b'*40},'source_tracked_paths':['fixture.py'],'source_worktree_clean_for_runner':True}
            def prepare(*args):
                private.mkdir(mode=0o700)
                return NS(adapter=None,owned=NS(verify=lambda:calls.append('verify')),finalize=finalize,close=lambda:calls.append('close'))
            def finalize(run,raw):
                path=private/'capture.mp4';path.write_bytes(b'video');path.chmod(0o600)
                with path.open('rb') as file:
                    info=path.stat();result=media.source_evidence(raw,file.fileno(),{'created':True,'confirmed_written':5,'write_outcome_uncertain':False,'close_outcome':'closed','removed_by_sink':False},expected_source_identity=(info.st_dev,info.st_ino,info.st_uid,info.st_mode),no_concurrent_writers=True)
                calls.append('finalized');holder['evidence']=result
            def factory(adapter,target,camera,experiment,outdir,privatedir,**kwargs):
                run=Sim(privatedir);run.out=outdir;holder['run']=run
                Sim.reader=execute_reader_fixture()[0].stdout
                return run
            def now():return holder['run'].now() if 'run' in holder else datetime.fromtimestamp(1700000100,timezone.utc).isoformat()
            args=['aa','6','1','--stock-only','--experiment-id','aa_main_fixture','--output',str(out),'--execute']
            old={sig:signal.getsignal(sig) for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)}
            try:
                with patch.object(sys,'argv',args),patch.object(t.base,'source_provenance',return_value=source),patch.object(host,'source_gate',return_value=(root,source)),patch.object(host,'private_path',return_value=private),patch.object(host,'prepare',side_effect=prepare),patch.object(t,'AATimedTrial',side_effect=factory),patch.object(t.s,'now',side_effect=now):
                    t.main(host_inputs=object(),verified_sources={'profile':'aa'},host_dependencies=NS(sleep=None,monotonic=None))
            finally:
                for sig,handler in old.items():signal.signal(sig,handler)
            self.assertEqual(holder['evidence']['status'],'source_finalized');self.assertIn('finalized',calls);self.assertEqual(calls[-1],'close')

class TargetUIScratchTests(unittest.TestCase):
    def test_shell_uid_and_owner_are_not_root_fallback(self):
        import subprocess
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);run.target_ui_path=root+'/ui';path=Path(run.target_ui_path);path.mkdir(mode=0o700)
            (path/'owner').write_text(run.token);(path/'owner').chmod(0o600)
            for uid in (2000,0,1000):
                prefix=f'id() {{ echo {uid}; }}; stat() {{ if [ "$2" = %u ]; then echo {uid}; else command stat "$@"; fi; }}; '
                result=subprocess.run(['sh','-c','set -eu; '+prefix+run.target_ui_guard()],capture_output=True)
                self.assertEqual(result.returncode==0,uid==2000)
            (path/'owner').write_text('foreign')
            result=subprocess.run(['sh','-c','set -eu; '+prefix.replace('1000','2000')+run.target_ui_guard()],capture_output=True)
            self.assertNotEqual(result.returncode,0)
    def test_ui_path_separate_and_shell_commands_only(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);calls=[];original=run.shell
            def shell(command,**kwargs):calls.append((command,kwargs));return original(command,**kwargs)
            run.shell=shell
            with patch.object(t.s,'now',run.now):run.setup();run.setup_aa();run.redraw('baseline')
            for command,kwargs in calls:
                if 'uiautomator dump' in command:
                    self.assertIn(run.target_ui_path+'/redraw.xml',command);self.assertNotIn(run.tmp+'/redraw',command)
                    self.assertFalse(kwargs.get('root',False));self.assertIn('= 2000',command)


class PreChildGapTests(unittest.TestCase):
    def test_unexpected_gap_is_rejected_before_any_child_dispatch(self):
        Sim.reader=execute_reader_fixture()[0].stdout
        for label in ('baseline-write','baseline-before-hold','baseline-c1'):
            with self.subTest(label=label),tempfile.TemporaryDirectory() as root:
                run=Sim(root);run.gap_inject=label
                with patch.object(t.s,'now',run.now),self.assertRaises(RuntimeError):run.execute()
                self.assertNotIn(label,run.children);self.assertIn('reboot',run.calls)
    def test_exact_esd_in_prechild_gap_is_accepted(self):
        Sim.reader=execute_reader_fixture()[0].stdout
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);run.gap_inject='baseline-before-hold';run.gap_event=SafeGapTests.POLL
            with patch.object(t.s,'now',run.now):run.execute()
            self.assertEqual(len(run.report['background_esd_safe_gaps']),1)
    def test_generated_remote_guard_not_just_host_validation(self):
        import subprocess
        before='mode_entry: pending=0 length=11 flags=0\nmode_ctrl_return: rc=0\nmode_return: rc=0\n'
        cases=[('',True),(SafeGapTests.POLL,True),('mode_ctrl_return: rc=0\n',False),
               (SafeGapTests.POLL.replace('kworker/1:2','app'),False),
               (SafeGapTests.POLL.replace('rc=1','rc=2'),False),('LOST\n',False)]
        for suffix,accepted in cases:
            with self.subTest(suffix=suffix),tempfile.TemporaryDirectory() as root:
                root=Path(root);trace=root/'trace';trace.write_text(before+suffix)
                command=t.trace_guard('/data/local/tmp/aa_guard_fixture',':',before)
                command=command.replace('/data/local/tmp/aa_guard_fixture',str(root)).replace(t.aa.TRACE+'/trace',str(trace))
                result=subprocess.run(['sh','-c',command+f'; echo dispatched > {root}/dispatched'],capture_output=True,text=True)
                self.assertEqual(result.returncode==0,accepted,result.stdout+result.stderr)
                self.assertEqual((root/'dispatched').exists(),accepted)
    def test_guard_prefix_and_local_io_errors_are_terminal(self):
        import subprocess
        for failure in ('prefix','grep','head','tail'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as root:
                root=Path(root);trace=root/'trace';trace.write_text('mode_ctrl_return: rc=1\n' if failure=='prefix' else '')
                command=t.trace_guard('/data/local/tmp/aa_guard_fixture',':','mode_ctrl_return: rc=0\n' if failure=='prefix' else '')
                command=command.replace('/data/local/tmp/aa_guard_fixture',str(root)).replace(t.aa.TRACE+'/trace',str(trace))
                prefix=f'{failure}() {{ return 2; }}; ' if failure!='prefix' else ''
                result=subprocess.run(['sh','-c',prefix+command+f'; echo dispatched > {root}/dispatched'],capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0);self.assertFalse((root/'dispatched').exists())
