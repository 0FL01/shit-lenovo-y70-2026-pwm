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
from test_aa_threshold_trial import SELECTOR_RAW

# Sanitized observed return-event shape; no live timestamps or process IDs.
REPLAY_POLL=' kworker/1:2-88 [001] d..1. 100.000000: mode_ctrl_return: (dsi_display_validate_status+0x154/0x308 [msm_drm] <- dsi_ctrl_cmd_transfer) rc=1\n'
REPLAY_RETURN=' printf-99 [001] d..1. 100.020000: mode_ctrl_return: (dsi_host_transfer_sub+0x2f4/0x558 [msm_drm] <- dsi_ctrl_cmd_transfer) rc=0\n'

def scene_fixture(opened=False,*,generated_id='5',pending=False):
    """Synthetic observed-format fixture; not target/latency qualification."""
    fragment='ScreenTimeoutSettings' if opened else 'DisplaySettings'
    component='.SubSettings' if opened else '.Settings$DisplaySettingsActivity'
    widget='android.widget.RadioButton' if opened else 'android.widget.TextView'
    text=f'''  ACTIVITY com.android.settings/{component} abc pid=123 userId=0 uid=1000 displayId=0(type=INTERNAL)
    Local Activity def State:
      mResumed=true mStopped=false mFinished=false
      mIsInMultiWindowMode=false mIsInPictureInPictureMode=false
      mChangingConfigurations=false
      mCurrentConfig={{mDisplayRotation=ROTATION_0 mWindowingMode=fullscreen}}
    ViewRoot:
      mAdded=true
      mRemoved=false
      mStopped=false
      mPausedForTransition=false
      mPendingInputEventCount=0
      mProcessInputEventsScheduled=false
      mTraversalScheduled=false
        mHasWindowFocus=true
        mWindowVisibility=0
    Choreographer:
      mFrameScheduled=false
    View Hierarchy:
      com.android.internal.policy.DecorView{{abc V.E...... R....... 0,0-1440,3168}}[Settings]
        android.widget.FrameLayout{{def V.E...... ........ 0,0-1440,3168 #1020002 android:id/content}}
          androidx.recyclerview.widget.RecyclerView{{fed VFED.V... .F...... 0,0-1440,3000 #7f0602 app:id/recycler_view aid=1234}}
            android.widget.LinearLayout{{aaa VFE..VC.. ........ 0,0-20,20 #0}}
              {widget}{{bbb V.ED.V... ........ 0,0-20,20 #1020016 android:id/title}}
          android.widget.LinearLayout{{123 G.E..V... ........ 0,0-0,0 #7f0a076c app:id/tab_container}}
            androidx.viewpager2.widget.ViewPager2{{456 V.E..V... ........ 0,0-0,0 #7f0a0810 app:id/view_pager}}
              androidx.viewpager2.widget.ViewPager2$RecyclerViewImpl{{789 VFED.V... ........ 0,0-0,0 #{generated_id}}}
    Looper (main, tid 2) {{ccc}}
    Local FragmentActivity def State:
      mCreated=true mResumed=true mStopped=false    Active Fragments:
    {fragment}{{ddd}} (11111111-1111-1111-1111-111111111111 id=0x7f048b)
        mState=7 mWho=11111111-1111-1111-1111-111111111111 mBackStackNesting=0
        mAdded=true mRemoving=false mFromLayout=false mInLayout=false
        mHidden=false mDetached=false mMenuVisible=true mHasMenu=true
    Added Fragments:
      #0: {fragment}{{ddd}} (11111111-1111-1111-1111-111111111111 id=0x7f048b)
    FragmentManager misc state:
      mCurState=7 mStateSaved=false mStopped=false mDestroyed=false
'''
    if pending:
        text=text.replace('mTraversalScheduled=false','mTraversalScheduled=true').replace('mHasWindowFocus=true','mHasWindowFocus=false').replace('mFrameScheduled=false','mFrameScheduled=true')
    return text


def retiring_scene_fixture(*,opened=True,state=5,finished=True):
    """Synthetic lifecycle only; no claim of a physical transition result."""
    return (scene_fixture(opened).replace('mResumed=true mStopped=false mFinished=false',
                'mResumed=false mStopped=false mFinished='+str(finished).lower())
            .replace('mCreated=true mResumed=true','mCreated=true mResumed=false')
            .replace('mState=7','mState='+str(state)).replace('mCurState=7','mCurState='+str(state))
            .replace('mHasWindowFocus=true','mHasWindowFocus=false')
            .replace('mFrameScheduled=false','mFrameScheduled=true'))

READY_XML='<hierarchy rotation="0"><node text="Screen timeout" package="com.android.settings" clickable="true" checkable="false" enabled="true" bounds="[0,0][20,20]"/></hierarchy>'
OPENED_XML=('<hierarchy rotation="0"><node resource-id="com.android.settings:id/collapsing_toolbar" package="com.android.settings" content-desc="Screen timeout"/>'+
    ''.join('<node text="'+text+'" package="com.android.settings" resource-id="android:id/title"/>' for text in
            ('15 seconds','30 seconds','1 minute','2 minutes','5 minutes','10 minutes','30 minutes'))+'</hierarchy>')

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
                    value='WRITER_ESD_ISOLATED esd_sw_sim_success\nBLOCK_TRACE_BEGIN -1\n'+r.trace+'BLOCK_TRACE_END -1\n'
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
                    if r.esd_mode != 'reg_read': raise AssertionError('Selector needs reg_read')
                    r.esd_mode='esd_sw_sim_success'
                    value=getattr(r,'selector_raw',SELECTOR_RAW)
                    for index,rc in enumerate(t.aa.SELECTOR_CONTROLS):
                        if index not in (1,4,7):r.trace+='mode_entry: pending=0 length=11 flags=0\n'
                        r.trace+=f'mode_ctrl_return: rc={rc}\n'
                        if index not in (1,4,7):r.trace+='mode_return: rc=0\n'
                if label==r.corrupt:value=value.replace('rc=0','rc=-5',1).replace('ESD_HELD','BAD_ISOLATION')
            elif part.label=='KERNEL':value=r.log
            elif part.label=='FIELDS':value='3600\n0\n0\nEnforcing\n'
            elif part.label=='DISPLAY':value='mActiveSfDisplayMode= peakRefreshRate=120.00001\n'
            elif part.label=='BOOT':value=BOOT+'\n'
            elif part.label in ('OWNER','TRACE_OWNER'):value=''
            else:raise AssertionError(part.label)
            if label.endswith('-write'):
                if r.esd_mode != 'esd_sw_sim_success':
                    raise AssertionError((label, part.label, r.esd_mode))
            fault = getattr(r, 'part_faults', {}).get((label, part.label))
            if fault is not None: value = fault(value)
            payload[part.label]=value
        return 0,framed(plan,payload),b''

class Sim(t.AATimedTrial):
    reader=None
    def __init__(self,root,**kwargs):
        clock=Clock();super().__init__(None,6,1,'aa_timed_test',root,root,sleep=clock.sleep,monotonic=clock,**kwargs)
        self.clock=clock;self.g=t.timed.DeadlineTransport(self,Transport(self));self.calls=[];self.children=[]
        self.log=ANCHOR;self.trace='';self.failure=None;self.corrupt=None;self.frames=135;self.slow=False;self.gap_inject=None;self.gap_event='mode_ctrl_return: rc=0\n'
        self.scene_state=False; self.esd_mode='reg_read'
    def setup(self):
        self.before={'boot_id':BOOT,'native_dbv':6438,'screen_off_timeout':'1800000'};self.reference=REF
        self.report['before']=deepcopy(self.before)
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
        if label.endswith('-writer-isolate'):
            if self.esd_mode != 'reg_read': raise AssertionError('Isolation did not start in reg_read')
            self.esd_mode = 'esd_sw_sim_success'
            return 'WRITER_ESD_ISOLATED esd_sw_sim_success'
        if label.endswith(('-writer-esd','-selector-esd')):
            if self.esd_mode != 'esd_sw_sim_success': raise AssertionError('Restore did not start in mode 5')
            self.esd_mode = 'reg_read'
            return 'WRITER_ESD_RESTORED reg_read'
        if label.endswith('-esd'):return 'reg_read'
        if label.endswith('-replay'):
            self.log+='dsi-ctrl-1: dsi_ctrl_cmd_transfer len=3, type=0x39 hs cmds= 51 0e 10\n'
            self.trace+=getattr(self,'replay_suffix',REPLAY_RETURN)
        if label.endswith('-wire'):return self.log
        if label.endswith('-redraw-before') or label.endswith('-redraw-returned'):
            return READY_XML
        if label.endswith('-redraw-opened'):return OPENED_XML
        if label.endswith('-redraw-open'):self.scene_state=True
        if label.endswith('-redraw-cancel'):self.scene_state=False
        if '-scene-' in label:
            if self.slow and label=='baseline-scene-ready':self.clock.sleep(20)
            return scene_fixture(self.scene_state)
        if label.endswith('-redraw-setting'):return '1800000'
        return ''
    def wait_value(self,*args,**kwargs):pass
    def recover(self):
        self.calls.append('reboot');assert not self.guard_context and self.active_start is None
        self.panel_uncertain=self.pending_read=self.inflight=self.active_failed=False
        self.report['recovery_reboot_verified']=True;self.trace='';self.esd_mode='reg_read'
    def stop_camera(self,**kwargs):
        self.calls.append('stop-camera');self.report.update(camera_stopped_verified=True,video_transfer_verified=True,video_bytes=5,video_validation_status='pending_offline')
    def cleanup_camera_xml(self):self.report['camera_ui_temp_removed']=True
    def restore(self):
        if self.panel_uncertain or self.pending_read:raise AssertionError('restore into uncertainty')
        self.calls.append('settings-restore');self.report.update(original_settings_dbv_logger_restored=True,watchdog_disarmed=True,mutex_released=True,main_trace_removed_verified=True,chunks_removed_verified=True,target_ui_temp_removed=True)

def optical_qualification_fixture(proof):
    from aa_acquisition_validation import QUALIFICATION_SCHEMA,ALGORITHM,canonical_sha
    return {'schema':QUALIFICATION_SCHEMA,'protocol':t.acquisition.DIAGNOSTIC_CONTRACT,'status':'limited_stock_diagnostic_pass','acquisition_canonical_sha256':canonical_sha(proof),'source_commit':'a'*40,'source_blob_ids':{'fixture.py':'b'*40},'optical_analysis_sha256':'c'*64,'algorithm':ALGORITHM,'fine_relative_tolerance':.05,'mean_y_relative_tolerance':.05,'rois_xywh':{'main':[250,0,100,400],'left':[100,0,100,400],'right':[400,0,100,400]},'baseline_fine_search_cycles_per_row':[.01,.03],'stock_ratios':[{'roi':roi,'stage':stage,'normalized_fine_over_baseline':1.,'mean_y_over_baseline':1.} for roi in ('main','left','right') for stage in ('sham_stock','return_stock')],'observed_active_G_seconds':proof['active_G_seconds'],'prearm_planning_estimate':proof['prearm_planning_estimate'],'physical_pwm_hz':None,'full_waveform_equivalence':None,'future_latency_bound':False,'optical_return_approval':False,'candidate_geometry_rule':'Use frozen ROI/band; baseline-only geometry review; mismatch is inconclusive, no B-driven reselection'}

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
            self.assertEqual(len(run.children),10)
            self.assertLess(run.calls.index('disarm-candidate'),run.calls.index('return_stock-hold-start'))
            self.assertLess(run.calls.index('chunks-verify'),run.calls.index('timed-watchdog-arm'))
            self.assertLess(run.calls.index('return_stock-after-hold'),run.calls.index('settings-restore'))
            self.assertEqual(report['candidate_attempts'],0);self.assertLess(report['active_G_seconds'],37)
            self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0,0))
    def test_all_child_transport_failures_no_followup_writer(self):
        labels=[stage+suffix for stage in ('baseline','sham_stock','return_stock')
                for suffix in (('-write','-before-hold') if stage=='sham_stock' else ('-write','-before-hold','-c1','-after-hold'))]
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
    def test_malformed_selector_read_recovers_before_c1_or_hold(self):
        for raw in (SELECTOR_RAW.replace('0x10','0x11'),SELECTOR_RAW.replace('0x0e \n','0x0e  \n',1),
                    SELECTOR_RAW.replace('R 24:9D','R 23:A9'),SELECTOR_RAW.replace('0x0e 0x10 ','0x0e ')):
            with self.subTest(raw=raw),tempfile.TemporaryDirectory() as root:
                run=Sim(root);run.selector_raw=raw
                with self.assertRaises(RuntimeError):self.execute(run)
                self.assertEqual(run.children,['baseline-write','baseline-before-hold'])
                self.assertEqual(run.calls.count('reboot'),1)
                self.assertNotIn('baseline-hold-start',run.calls)
                self.assertEqual(run.report['candidate_attempts'],0)
                self.assertEqual(run.report['full_table_writes_attempted'],['baseline'])
                self.assertTrue(run.report['original_settings_dbv_logger_restored'])
                self.assertTrue(run.report['mutex_released'])

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
            optical=optical_qualification_fixture(proof)
            run=Sim(root,aa_candidate=True,stock_qualification=proof,optical_qualification=optical,source_record={'source_commit':'a'*40,'source_blob_ids':{'fixture.py':'b'*40}})
            run.failure='aa10-write'
            with self.assertRaises(RuntimeError):self.execute(run)
            self.assertEqual(run.report['candidate_attempts'],1);self.assertTrue(run.report['unknown_value_write_attempted'])
            self.assertEqual(run.report['full_table_writes_attempted'],['baseline','aa10']);self.assertNotIn('return_stock-write',run.calls)

class ReplayTraceTests(unittest.TestCase):
    def before(self):
        return ''.join(TransactionTests().block(i) for i in range(5))
    def test_sanitized_observed_suffix_and_no_poll(self):
        before=self.before()
        for suffix,controls in ((REPLAY_RETURN,[0]),(REPLAY_POLL+REPLAY_RETURN,[1,0])):
            result=t.validate_replay_trace(before,before+suffix,5)
            self.assertEqual(result['controller_returns'],controls)
            self.assertEqual(result['entry_count_after'],5)
            self.assertEqual(len(result.get('background_esd_in_replay_observation',[])),len(controls)-1)
    def test_unqualified_shapes_rejected(self):
        before=self.before();good=REPLAY_POLL+REPLAY_RETURN
        bad=['',REPLAY_POLL,REPLAY_RETURN+REPLAY_POLL,REPLAY_POLL+good,good+REPLAY_RETURN,
             good.replace('printf-','sh-'),good.replace('kworker/1:2-','app-'),
             good.replace('+0x154','+0x155'),good.replace('+0x2f4','+0x2f5'),
             good.replace('rc=1','rc=0'),good.replace('rc=0','rc=1'),good.replace('rc=0','rc=-5'),
             good.replace('rc=0','rc=garbled'),good.replace('mode_ctrl_return:','mode_unknown:',1),
             good+'LOST\n',good+'unknown_event: rc=0\n',good+'mode_return: rc=0\n',
             good+'mode_entry: pending=0 length=11 flags=0\n',
             good+'mode_entry: pending=0 length=11 flags=0\nmode_return: rc=0\n']
        for suffix in bad:
            with self.subTest(suffix=suffix),self.assertRaises(ValueError):
                t.validate_replay_trace(before,before+suffix,5)
        with self.assertRaises(ValueError):t.validate_replay_trace(before,before.replace('pending=0','pending=1',1)+good,5)
    def test_return_timestamps_must_be_nondecreasing(self):
        before=self.before()
        for stamp in ('101.000000','100.020000000000000001'):
            suffix=REPLAY_POLL.replace('100.000000',stamp)+REPLAY_RETURN
            with self.subTest(stamp=stamp),self.assertRaises(ValueError):
                t.validate_replay_trace(before,before+suffix,5)
        equal=REPLAY_POLL.replace('100.000000','100.020000')+REPLAY_RETURN
        self.assertEqual(t.validate_replay_trace(before,before+equal,5)['controller_returns'],[1,0])
    def test_real_replay_method_with_fake_io(self):
        for suffix in (REPLAY_RETURN,REPLAY_POLL+REPLAY_RETURN,REPLAY_RETURN+REPLAY_POLL):
            with tempfile.TemporaryDirectory() as root:
                run=Sim(root);run.setup();run.entry_count=5
                run.trace=run.trace_snapshot=self.before();run.replay_suffix=suffix
                if suffix==REPLAY_RETURN+REPLAY_POLL:
                    with self.assertRaises(ValueError):run.replay('baseline')
                    self.assertTrue(run.pending_read)
                    self.assertEqual(run.trace_snapshot,self.before())
                else:
                    result=run.replay('baseline')
                    self.assertTrue(result['exact_wire_verified']);self.assertFalse(run.pending_read)
                    self.assertEqual(run.trace_snapshot,self.before()+suffix)
    def test_real_replay_keeps_wire_and_native_guards(self):
        for mutation in ('extra','native','failure'):
            with tempfile.TemporaryDirectory() as root:
                run=Sim(root);run.setup();run.entry_count=5
                run.trace=run.trace_snapshot=self.before();run.replay_suffix=REPLAY_POLL+REPLAY_RETURN
                shell=run.shell
                def corrupt(command,**kwargs):
                    value=shell(command,**kwargs)
                    if kwargs.get('label','').endswith('-replay-wire'):
                        if mutation=='extra':value=value.replace('cmds= 51 0e 10','cmds= 51 0e 10\ndsi-ctrl-1: dsi_ctrl_cmd_transfer len=2, type=0x39 hs cmds= aa 11')
                        elif mutation=='native':value=value.replace('actual=120, group=0x3','actual=1, group=0x8')
                        else:value=value.replace('cmds= 51 0e 10','cmds= 51 0e 10\nCommand transfer failed')
                    return value
                run.shell=corrupt
                with self.assertRaises(ValueError):run.replay('baseline')
                self.assertTrue(run.pending_read)


    def test_acquisition_exact_poll_schema_and_faults(self):
        from aa_acquisition_validation import validate_acquisition
        Sim.reader=execute_reader_fixture()[0].stdout
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);run.replay_suffix=REPLAY_POLL+REPLAY_RETURN
            with patch.object(t.s,'now',run.now):report=run.execute()
        validate_acquisition(report)
        original=report['stages'][0]['same_dbv_replay']['main_trace']
        mutations=[lambda x:x.update(controller_returns=[0]),lambda x:x.update(controller_returns=[0,1]),
            lambda x:x.update(controller_returns=[1,1,0]),lambda x:x.update(page_callbacks_verified=1),
            lambda x:x.update(entry_count_after=6),lambda x:x.pop('limitation'),
            lambda x:x.update(limitation='No overlap'),lambda x:x.update(extra=True),
            lambda x:x.pop('background_esd_in_replay_observation'),
            lambda x:x['background_esd_in_replay_observation'].append(deepcopy(x['background_esd_in_replay_observation'][0])),
            lambda x:x['background_esd_in_replay_observation'][0].update(caller='unknown'),
            lambda x:x['background_esd_in_replay_observation'][0].update(return_code=0),
            lambda x:x['background_esd_in_replay_observation'][0].update(extra=True)]
        for mutate in mutations:
            broken=deepcopy(report);trace=broken['stages'][0]['same_dbv_replay']['main_trace'];mutate(trace)
            with self.subTest(trace=trace),self.assertRaises(ValueError):validate_acquisition(broken)
        self.assertEqual(original['controller_returns'],[1,0])


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
    def test_generated_shell_requires_fresh_xml_after_zero_exit_dump(self):
        import subprocess
        for mode in ('no_write','fresh','remove_failure'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as root:
                run=Sim(root);run.target_ui_path=root+'/ui';path=Path(run.target_ui_path)
                path.mkdir(mode=0o700);(path/'owner').write_text(run.token);(path/'owner').chmod(0o600)
                stale=path/'redraw.xml';stale.write_text(READY_XML);stale.chmod(0o600)
                calls=[]
                prefix='id() { echo 2000; }; stat() { if [ "$2" = %u ]; then echo 2000; else command stat "$@"; fi; }; '
                dump=('return 0;' if mode=='no_write' else 'printf %s '+t.q(OPENED_XML)+' > "$2";')
                prefix+='uiautomator() { '+dump+' }; '
                if mode=='remove_failure':prefix+='rm() { return 2; }; '
                def shell(command,**kwargs):
                    result=subprocess.run(['sh','-c',prefix+command],capture_output=True,text=True)
                    calls.append(result)
                    if result.returncode:raise ValueError('Generated XML command failed')
                    return result.stdout
                run.shell=shell
                if mode=='fresh':self.assertEqual(t.ET.tostring(run.target_ui('fresh')),t.ET.tostring(t.ET.fromstring(OPENED_XML)))
                else:
                    with self.assertRaises(ValueError):run.target_ui('fresh')
                self.assertEqual(len(calls),1)
                if mode=='no_write':self.assertFalse(stale.exists());self.assertEqual(calls[0].stdout,'')
                if mode=='remove_failure':self.assertEqual(stale.read_text(),READY_XML)
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
            with patch.object(t.s,'now',run.now):run.setup();run.setup_aa();run.calibrate_redraw();run.redraw('baseline')
            for command,kwargs in calls:
                if 'uiautomator dump' in command:
                    self.assertIn(run.target_ui_path+'/redraw.xml',command);self.assertNotIn(run.tmp+'/redraw',command)
                    self.assertFalse(kwargs.get('root',False));self.assertIn('= 2000',command)


class SceneParserTests(unittest.TestCase):
    def test_own_resumed_settings_section_not_stopped_launcher(self):
        ready=scene_fixture()
        launcher=ready.replace('com.android.settings/.Settings$DisplaySettingsActivity','com.motorola.launcher3/.Launcher').replace('mResumed=true mStopped=false mFinished=false','mResumed=false mStopped=true mFinished=false').replace('DisplaySettings{','MisleadingSettings{')
        self.assertEqual(t.settings_scene(launcher+'TASK settings\n'+ready),t.settings_scene(ready))
        self.assertEqual(t.settings_scene(ready+'TASK launcher\n'+launcher),t.settings_scene(ready))
        with self.assertRaises(ValueError):t.settings_scene(ready+ready)
    def test_partial_foreign_and_unsettled_dumps_rejected(self):
        good=scene_fixture()
        bad=[good[:good.index('    Looper')],good.replace('    View Hierarchy:','    Other:'),
             good.replace('uid=1000','uid=2000'),good.replace('displayId=0','displayId=1'),
             good.replace('mHasWindowFocus=true','mHasWindowFocus=false'),good.replace('mWindowVisibility=0','mWindowVisibility=4'),
             good.replace('mTraversalScheduled=false','mTraversalScheduled=true'),
             good.replace('mPendingInputEventCount=0','mPendingInputEventCount=1'),
             good.replace('mState=7','mState=5'),good.replace('mHidden=false','mHidden=true'),
             good.replace('#0: DisplaySettings{ddd}','#0: OtherSettings{ddd}'),
             good.replace('mCurState=7 mStateSaved=false mStopped=false mDestroyed=false',''),
             good.replace('0,0-20,20','garbled',1),good+'\ufffd',good.replace('ROTATION_0','ROTATION_1')]
        for text in bad:
            with self.subTest(text=text[-80:]),self.assertRaises(ValueError):t.settings_scene(text)
    def test_only_transient_ids_and_dirty_bits_normalized(self):
        good=scene_fixture();expected=t.settings_scene(good)
        transient=good.replace('{aaa ', '{123abc ').replace('aid=1234','aid=8888').replace('VFE..VC.. ........','VFE..VC.. ......ID')
        self.assertEqual(expected,t.settings_scene(transient))
        for before,after in [('VFE..VC..','GFE..VC..'),('VFE..VC..','VF...VC..'),('VFE..VC..','VFE..V...'),
                             ('0,0-20,20','0,1-20,20'),('android:id/title','android:id/summary'),
                             ('pid=123','pid=456'),('DisplaySettings','OtherSettings')]:
            with self.subTest(change=after):self.assertNotEqual(expected,t.settings_scene(good.replace(before,after)))


class OpeningPendingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):Sim.reader=execute_reader_fixture()[0].stdout
    def execute(self,run):
        with patch.object(t.s,'now',run.now):return run.execute()
    def test_only_observed_hidden_generated_id_is_normalized(self):
        five=scene_fixture(True);six=scene_fixture(True,generated_id='6')
        expected=t.settings_scene(five)
        self.assertEqual(expected,t.settings_scene(six))
        child='androidx.viewpager2.widget.ViewPager2$RecyclerViewImpl{789 VFED.V... ........ 0,0-0,0 #6}'
        changes=[six.replace('#6}', '#0}'),six.replace('#6}', '#1020005}'),
            six.replace('#6}', '#6 app:id/other}'),
            six.replace(child,child.replace('0,0-0,0','0,0-1,1')),
            six.replace(child,child.replace('VFED.V...','VFED.VC..')),
            six.replace(child,child.replace('RecyclerViewImpl','OtherRecycler')),
            six.replace('123 G.E..V...', '123 V.E..V...'),
            six.replace('app:id/tab_container','app:id/other_container'),
            six.replace('app:id/view_pager','app:id/other_pager'),
            six.replace('456 V.E..V... ........ 0,0-0,0','456 V.E..V... ........ 0,0-1,1'),
            six.replace('#7f0a0810','#7f0a0811')]
        for changed in changes:
            with self.subTest(changed=changed[-80:]):self.assertNotEqual(expected,t.settings_scene(changed))
    def test_pending_is_typed_unready_not_stable_success(self):
        raw=scene_fixture(True,generated_id='6',pending=True)
        with self.assertRaises(ValueError):t.settings_scene(raw)
        with self.assertRaises(t.SettingsTransitionPending) as caught:t.settings_scene(raw,transition=True)
        self.assertEqual(caught.exception.scene,t.settings_scene(scene_fixture(True)))
        for old,new in [('mWindowVisibility=0','mWindowVisibility=9'),
                        ('mPendingInputEventCount=0','mPendingInputEventCount=-1'),
                        ('mFrameScheduled=true','mFrameScheduled=unknown'),
                        ('mState=7','mState=1'),('mHidden=false','mHidden=true')]:
            with self.subTest(change=new),self.assertRaises(ValueError) as bad:
                t.settings_scene(raw.replace(old,new),transition=True)
            self.assertNotIsInstance(bad.exception,t.SettingsTransitionPending)
        for line in ('      mTraversalScheduled=true\n','        mHasWindowFocus=false\n','      mFrameScheduled=true\n'):
            for changed in (raw.replace(line,''),raw.replace(line,line+line)):
                with self.subTest(line=line),self.assertRaises(ValueError) as bad:t.settings_scene(changed,transition=True)
                self.assertNotIsInstance(bad.exception,t.SettingsTransitionPending)
    def test_frame_readiness_is_bound_to_selected_choreographer(self):
        pending=scene_fixture(True,pending=True)
        launcher=scene_fixture().replace('com.android.settings/.Settings$DisplaySettingsActivity','com.motorola.launcher3/.Launcher').replace('mResumed=true mStopped=false mFinished=false','mResumed=false mStopped=true mFinished=false').replace('mFrameScheduled=false','mFrameScheduled=true')
        invalid=pending.replace('      mFrameScheduled=true\n','')
        with self.assertRaises(ValueError) as bad:t.settings_scene(launcher+'TASK current\n'+invalid,transition=True)
        self.assertNotIsInstance(bad.exception,t.SettingsTransitionPending)
        with self.assertRaises(t.SettingsTransitionPending):t.settings_scene(launcher+'TASK current\n'+pending,transition=True)
    def test_actual_caller_pending_then_stable_never_replays_input(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);original=run.shell;seen=0
            def shell(command,**kwargs):
                nonlocal seen
                value=original(command,**kwargs)
                if kwargs.get('label')=='baseline-scene-opened':
                    seen+=1;return scene_fixture(True,generated_id='6',pending=seen==1)
                return value
            run.shell=shell;report=self.execute(run)
            self.assertEqual(seen,2);self.assertEqual(run.calls.count('baseline-redraw-open'),1)
            self.assertEqual(run.calls.count('baseline-redraw-cancel'),1)
            indices=[i for i,label in enumerate(run.calls) if label=='baseline-scene-opened']
            self.assertLess(indices[-1],run.calls.index('baseline-redraw-cancel'))
            self.assertEqual(report['stages'][0]['redraw_audit']['scene_sha256'][1],report['redraw_ui_calibration']['scene_sha256']['opened'])
    def test_pending_timeout_unknown_late_and_transport_recover_before_back(self):
        for fault in ('timeout','tree','pid','config','late','transport','permission'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as root:
                run=Sim(root);original=run.shell;seen=0
                def shell(command,**kwargs):
                    nonlocal seen
                    value=original(command,**kwargs)
                    if kwargs.get('label')!='baseline-scene-opened':return value
                    seen+=1
                    if fault=='transport' and seen==2:raise TimeoutError('uncertain read')
                    if fault=='permission' and seen==2:raise ValueError('permission denied')
                    value=scene_fixture(True,generated_id='6',pending=True)
                    if fault=='tree':value=value.replace('android:id/title','android:id/other')
                    if fault=='pid':value=value.replace('pid=123','pid=999')
                    if fault=='config':value=value.replace('mDisplayRotation=ROTATION_0','density=changed mDisplayRotation=ROTATION_0')
                    if fault=='late':run.clock.sleep(1.1)
                    return value
                run.shell=shell
                with self.assertRaises(RuntimeError):self.execute(run)
                self.assertEqual(run.calls.count('baseline-redraw-open'),1)
                self.assertNotIn('baseline-redraw-cancel',run.calls);self.assertEqual(run.children,['baseline-write'])
                self.assertEqual(run.calls.count('reboot'),1)
                if fault in ('tree','pid','config','late'):self.assertEqual(seen,1)
                if fault in ('transport','permission'):self.assertEqual(seen,2)
    def test_pending_never_allowed_in_calibration_or_before_tap(self):
        for label in ('calibration-scene-opened','baseline-scene-ready'):
            with self.subTest(label=label),tempfile.TemporaryDirectory() as root:
                run=Sim(root);original=run.shell
                def shell(command,**kwargs):
                    value=original(command,**kwargs)
                    return scene_fixture(True,pending=True) if kwargs.get('label')==label else value
                run.shell=shell
                with self.assertRaises(RuntimeError):self.execute(run)
                self.assertEqual(run.calls.count(label),1);self.assertEqual(run.calls.count('reboot'),1)
                if label=='calibration-scene-opened':self.assertIsNone(run.redraw_scenes);self.assertEqual(run.children,[])
                if label=='baseline-scene-ready':self.assertNotIn('baseline-redraw-open',run.calls)
    def test_external_actual_same_run_pair_through_real_redraw(self):
        import hashlib,os
        stable_path=os.environ.get('AA_SCENE_STABLE_PATH');pending_path=os.environ.get('AA_SCENE_PENDING_PATH')
        if not stable_path or not pending_path:self.skipTest('Explicit external saved scene pair not supplied')
        stable=Path(stable_path).read_bytes();pending=Path(pending_path).read_bytes()
        self.assertEqual(hashlib.sha256(stable).hexdigest(),'84c73501853be4e8e843b7c217796f112e3d94eafa6a2614281526005a28cfab')
        self.assertEqual(hashlib.sha256(pending).hexdigest(),'cc51ddb6b8dac870bce3cd82288d108cd4b1df1cd933ea22ba1fb316c9af295d')
        expected=t.settings_scene(stable.decode())
        with self.assertRaises(t.SettingsTransitionPending) as caught:t.settings_scene(pending.decode(),transition=True)
        self.assertEqual(caught.exception.scene,expected)
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);run.setup();run.setup_aa();original=run.shell;reads=0
            ready_raw=scene_fixture().replace('pid=123','pid='+str(expected['pid']))
            run.redraw_scenes={'ready':t.settings_scene(ready_raw),'opened':expected};run.redraw_tap=[10,10]
            def shell(command,**kwargs):
                nonlocal reads
                value=original(command,**kwargs);label=kwargs.get('label','')
                if label in ('baseline-scene-ready','baseline-scene-returned'):return ready_raw
                if label=='baseline-scene-opened':reads+=1;return (pending if reads==1 else stable).decode()
                return value
            run.shell=shell
            result=run.redraw('baseline')
            self.assertEqual(reads,2);self.assertEqual(run.calls.count('baseline-redraw-open'),1)
            self.assertEqual(run.calls.count('baseline-redraw-cancel'),1);self.assertFalse(run.pending_read)
            self.assertEqual(result['scene_sha256'][1],t.scene_digest(expected))


class TransitionLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):Sim.reader=execute_reader_fixture()[0].stdout
    def execute(self,run):
        with patch.object(t.s,'now',run.now):return run.execute()
    def test_live_view_states_are_pending_not_success(self):
        expected=t.settings_scene(scene_fixture(True))
        for state in range(2,8):
            raw=retiring_scene_fixture(state=state)
            with self.subTest(state=state):
                with self.assertRaises(ValueError):t.settings_scene(raw)
                with self.assertRaises(t.SettingsTransitionPending) as caught:t.settings_scene(raw,transition=True)
                self.assertEqual(caught.exception.scene,expected);self.assertTrue(caught.exception.finished)
        for state in (-1,0,1,8):
            with self.subTest(state=state),self.assertRaises(ValueError) as caught:
                t.settings_scene(retiring_scene_fixture(state=state),transition=True)
            self.assertNotIsInstance(caught.exception,t.SettingsTransitionPending)
    def test_readiness_is_not_a_boolean_tuple_whitelist(self):
        good=scene_fixture(True);expected=t.settings_scene(good)
        # Each otherwise-complete readiness change is read-only pending.
        changes=[('mHasWindowFocus=true','mHasWindowFocus=false'),
            ('mTraversalScheduled=false','mTraversalScheduled=true'),
            ('mPausedForTransition=false','mPausedForTransition=true'),
            ('mPendingInputEventCount=0','mPendingInputEventCount=3'),
            ('mProcessInputEventsScheduled=false','mProcessInputEventsScheduled=true'),
            ('mWindowVisibility=0','mWindowVisibility=4'),('mWindowVisibility=0','mWindowVisibility=8'),
            ('      mStopped=false\n','      mStopped=true\n'),
            ('mCreated=true mResumed=true','mCreated=true mResumed=false'),
            ('mStateSaved=false','mStateSaved=true'),('mState=7','mState=6'),('mCurState=7','mCurState=3')]
        for before,after in changes:
            with self.subTest(after=after),self.assertRaises(t.SettingsTransitionPending) as caught:
                t.settings_scene(good.replace(before,after),transition=True)
            self.assertEqual(caught.exception.scene,expected)
        # Scheduled frames alone were never excluded by strict success.
        self.assertEqual(t.settings_scene(good.replace('mFrameScheduled=false','mFrameScheduled=true')),expected)
    def test_hard_guards_and_malformed_fields_are_never_pending(self):
        good=retiring_scene_fixture()
        changes=[('      mAdded=true\n','      mAdded=false\n'),('mRemoved=false','mRemoved=true'),
            ('mCreated=true','mCreated=false'),('mAdded=true mRemoving=false','mAdded=false mRemoving=false'),
            ('mRemoving=false','mRemoving=true'),('mHidden=false','mHidden=true'),
            ('mDetached=false','mDetached=true'),('mDestroyed=false','mDestroyed=true'),
            ('uid=1000','uid=2000'),('mChangingConfigurations=false','mChangingConfigurations=true'),
            ('mWindowVisibility=0','mWindowVisibility=9'),('mPendingInputEventCount=0','mPendingInputEventCount=-1'),
            ('mResumed=false mStopped=false mFinished=true','mResumed=true mStopped=true mFinished=false'),
            ('mCreated=true mResumed=false mStopped=false','mCreated=true mResumed=true mStopped=true')]
        invalid=[good.replace(a,b) for a,b in changes]+['',good[:good.index('    Looper')],scene_fixture()+scene_fixture(True)]
        fields=['      mResumed=false mStopped=false mFinished=true\n',
            '      mAdded=true\n','      mRemoved=false\n','      mStopped=false\n',
            '      mPausedForTransition=false\n','      mPendingInputEventCount=0\n',
            '      mProcessInputEventsScheduled=false\n','      mTraversalScheduled=false\n',
            '        mHasWindowFocus=false\n','        mWindowVisibility=0\n','      mFrameScheduled=true\n',
            '      mChangingConfigurations=false\n',
            '        mState=5 mWho=11111111-1111-1111-1111-111111111111 mBackStackNesting=0\n',
            '      mCurState=5 mStateSaved=false mStopped=false mDestroyed=false\n']
        for field in fields:invalid.extend((good.replace(field,''),good.replace(field,field+field)))
        for raw in invalid:
            with self.subTest(raw=raw[-100:]),self.assertRaises(ValueError) as caught:t.settings_scene(raw,transition=True)
            self.assertNotIsInstance(caught.exception,t.SettingsTransitionPending)
    def test_zero_resumed_requires_a_unique_complete_settings_context(self):
        raw=retiring_scene_fixture()
        launcher=scene_fixture().replace('com.android.settings/.Settings$DisplaySettingsActivity','com.motorola.launcher3/.Launcher').replace(
            'mResumed=true mStopped=false mFinished=false','mResumed=false mStopped=true mFinished=false')
        with self.assertRaises(t.SettingsTransitionPending):t.settings_scene(launcher+'TASK current\n'+raw,transition=True)
        for bad in (launcher,raw+raw,launcher.replace('mResumed=false mStopped=true','mResumed=false mStopped=false')+raw,
                    scene_fixture().replace('com.android.settings/.Settings$DisplaySettingsActivity','com.foreign/.Activity')+raw):
            with self.subTest(bad=bad[:100]),self.assertRaises(ValueError) as caught:t.settings_scene(bad,transition=True)
            self.assertNotIsInstance(caught.exception,t.SettingsTransitionPending)
    def test_malformed_duplicate_lifecycle_never_hides_behind_valid_line(self):
        for raw in (scene_fixture(),retiring_scene_fixture()):
            lines=[line for line in raw.splitlines(True) if line.startswith(
                ('      mResumed=','      mCurState=','      mFrameScheduled=',
                 '      mPendingInputEventCount=','        mState=','      mCreated='))]
            for line in lines:
                malformed=re.sub(r'=(?:true|false|\d+)', '=invalid extra',line,count=1)
                for replacement in (line+malformed,malformed+line):
                    for transition in (False,True):
                        with self.subTest(line=line,transition=transition),self.assertRaises(ValueError) as caught:
                            t.settings_scene(raw.replace(line,replacement),transition=transition)
                        self.assertNotIsInstance(caught.exception,t.SettingsTransitionPending)
    def test_return_pending_then_new_stable_read_has_one_back(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);original=run.shell;reads=0
            def shell(command,**kwargs):
                nonlocal reads
                value=original(command,**kwargs)
                if kwargs.get('label')=='baseline-scene-returned':
                    reads+=1
                    if reads==1:return retiring_scene_fixture()
                return value
            run.shell=shell;report=self.execute(run)
            self.assertEqual(reads,2);self.assertEqual(run.calls.count('baseline-redraw-open'),1)
            self.assertEqual(run.calls.count('baseline-redraw-cancel'),1)
            self.assertEqual(report['stages'][0]['redraw_audit']['scene_sha256'][2],report['redraw_ui_calibration']['scene_sha256']['ready'])
            self.assertLess(max(i for i,x in enumerate(run.calls) if x=='baseline-scene-returned'),run.calls.index('baseline-before-hold'))
    def test_return_pending_faults_are_terminal_and_recover_once(self):
        for fault in ('timeout','tree','pid','config','foreign','ambiguous','malformed','removed','destroyed',
                      'hidden','detached','finished_expected','transport','permission','late'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as root:
                run=Sim(root);original=run.shell;reads=0
                def shell(command,**kwargs):
                    nonlocal reads
                    value=original(command,**kwargs)
                    if kwargs.get('label')!='baseline-scene-returned':return value
                    reads+=1
                    if fault=='transport' and reads==2:raise TimeoutError('uncertain read')
                    if fault=='permission' and reads==2:raise PermissionError('guard/access denied')
                    value=retiring_scene_fixture()
                    edits={'tree':('android:id/title','android:id/other'),'pid':('pid=123','pid=999'),
                        'config':('mDisplayRotation=ROTATION_0','density=changed mDisplayRotation=ROTATION_0'),
                        'foreign':('com.android.settings/.SubSettings','com.foreign/.SubSettings'),
                        'removed':('mRemoved=false','mRemoved=true'),'destroyed':('mDestroyed=false','mDestroyed=true'),
                        'hidden':('mHidden=false','mHidden=true'),'detached':('mDetached=false','mDetached=true')}
                    if fault in edits:value=value.replace(*edits[fault])
                    if fault=='ambiguous':value=scene_fixture()+scene_fixture(True)
                    if fault=='malformed':value='Permission Denial: no activity data'
                    if fault=='finished_expected':value=retiring_scene_fixture(opened=False)
                    if fault=='late':run.clock.sleep(1.1)
                    return value
                run.shell=shell
                with self.assertRaises(RuntimeError):self.execute(run)
                self.assertEqual(run.calls.count('baseline-redraw-open'),1);self.assertEqual(run.calls.count('baseline-redraw-cancel'),1)
                self.assertEqual(run.calls.count('reboot'),1);self.assertEqual(run.children,['baseline-write'])
                self.assertNotIn('baseline-before-hold',run.calls)
                if fault in ('transport','permission'):self.assertEqual(reads,2)
                elif fault!='timeout':self.assertEqual(reads,1)
    def test_caught_return_failure_cannot_resume_inputs_or_dsi(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);run.setup();run.setup_aa();original=run.shell
            run.redraw_scenes={'ready':t.settings_scene(scene_fixture()),'opened':t.settings_scene(scene_fixture(True))}
            run.redraw_tap=[10,10]
            def shell(command,**kwargs):
                value=original(command,**kwargs)
                return 'malformed' if kwargs.get('label')=='baseline-scene-returned' else value
            run.shell=shell
            with self.assertRaises(ValueError):run.redraw('baseline')
            self.assertTrue(run.pending_read);before=list(run.calls)
            for operation in (lambda:run.redraw('again'),lambda:run.replay('again'),lambda:run.selectors('again'),
                              lambda:run.c1('again'),lambda:run.prehold({}),lambda:run.finish_hold({})):
                with self.assertRaises(ValueError):operation()
                self.assertEqual(run.calls,before)
    def test_transition_acceptance_is_clipped_to_remaining_active_budget(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);run.setup();run.setup_aa();original=run.shell
            run.redraw_scenes={'ready':t.settings_scene(scene_fixture()),'opened':t.settings_scene(scene_fixture(True))}
            run.redraw_tap=[10,10];start=run.clock();run.active_start=start-36.8
            def shell(command,**kwargs):
                value=original(command,**kwargs)
                return retiring_scene_fixture() if kwargs.get('label')=='baseline-scene-returned' else value
            run.shell=shell
            with self.assertRaises(ValueError):run.redraw('baseline')
            self.assertLess(run.clock()-start,.3);self.assertTrue(run.pending_read)
            self.assertEqual(run.calls.count('baseline-redraw-open'),1);self.assertEqual(run.calls.count('baseline-redraw-cancel'),1)
    def test_phase_binding_does_not_grant_pending_to_arbitrary_calls(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);ready=t.settings_scene(scene_fixture());opened=t.settings_scene(scene_fixture(True))
            for label,expected,previous,pending in [('wrong',ready,opened,True),('x-scene-opened',ready,opened,True),
                    ('x-scene-returned',opened,ready,True),('x-scene-returned',ready,opened,False)]:
                run.pending_read=pending
                with self.assertRaises(ValueError):run.settle_scene(label,expected,previous)
            self.assertEqual(run.calls,[])
    def test_external_9ee_retiring_context_and_simulated_fresh_return(self):
        import hashlib,os
        ready_path=os.environ.get('AA_RETURN_READY_PATH');retiring_path=os.environ.get('AA_RETURN_PENDING_PATH')
        if not ready_path or not retiring_path:self.skipTest('Explicit private 9ee scene references not supplied')
        ready_raw=Path(ready_path).read_bytes();retiring_raw=Path(retiring_path).read_bytes()
        self.assertEqual(hashlib.sha256(ready_raw).hexdigest(),'4417e4b70e10b85914cc8696c2a55906cf440678963860e2cf21d04eedea2c07')
        self.assertEqual(hashlib.sha256(retiring_raw).hexdigest(),'3f226af0a21e614a5d4de34c7a68d927ce92bc34645c6c37e5554263e4bf0494')
        ready=t.settings_scene(ready_raw.decode())
        self.assertEqual(t.scene_digest(ready),'6f85cdeed29e9e3d672438d3bcf733e1188551a4a6ccc5f1520249fd7a2bfb32')
        with self.assertRaises(ValueError):t.settings_scene(retiring_raw.decode())
        with self.assertRaises(t.SettingsTransitionPending) as caught:t.settings_scene(retiring_raw.decode(),transition=True)
        opened=caught.exception.scene;self.assertTrue(caught.exception.finished)
        self.assertEqual(t.scene_digest(opened),'a6103e941432f4822c97b15c12e58c743620bb20796c253f64fd520f35a3bf5e')
        # Test-only stable lifecycle projection supplies the earlier opened read.
        # Historical 0107 supplies a SIMULATED later stable return. Neither is
        # evidence that a physical post-Back return occurred in the failed run.
        stable_opened=retiring_raw.decode()
        for old,new in [('mResumed=false mStopped=false mFinished=true','mResumed=true mStopped=false mFinished=false'),
            ('mCreated=true mResumed=false mStopped=false','mCreated=true mResumed=true mStopped=false'),
            ('        mHasWindowFocus=false\n','        mHasWindowFocus=true\n'),
            ('        mState=5 mWho=','        mState=7 mWho='),
            ('mCurState=5 mStateSaved=false mStopped=false mDestroyed=false','mCurState=7 mStateSaved=false mStopped=false mDestroyed=false')]:
            stable_opened=stable_opened.replace(old,new)
        self.assertEqual(t.settings_scene(stable_opened),opened)
        for timeout in (False,True):
            with self.subTest(timeout=timeout),tempfile.TemporaryDirectory() as root:
                run=Sim(root);run.setup();run.setup_aa();original=run.shell;reads=0
                run.redraw_scenes={'ready':ready,'opened':opened};run.redraw_tap=[10,10]
                def shell(command,**kwargs):
                    nonlocal reads
                    value=original(command,**kwargs);label=kwargs.get('label')
                    if label=='baseline-scene-ready':return ready_raw.decode()
                    if label=='baseline-scene-opened':return stable_opened
                    if label=='baseline-scene-returned':
                        reads+=1;return retiring_raw.decode() if timeout or reads==1 else ready_raw.decode()
                    return value
                run.shell=shell
                if timeout:
                    with self.assertRaises(ValueError):run.redraw('baseline')
                    self.assertTrue(run.pending_read)
                else:
                    result=run.redraw('baseline');self.assertEqual(reads,2);self.assertFalse(run.pending_read)
                    self.assertEqual(result['scene_sha256'][2],t.scene_digest(ready))
                self.assertEqual(run.calls.count('baseline-redraw-open'),1);self.assertEqual(run.calls.count('baseline-redraw-cancel'),1)


class MissingObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):Sim.reader=execute_reader_fixture()[0].stdout
    def contexts(self):return t.settings_scene(scene_fixture()),t.settings_scene(scene_fixture(True))
    def observe(self,raw):return t.settings_scene(raw,transition=True,known_scenes=self.contexts())
    def partials(self):
        raw=scene_fixture(True)
        cuts=[raw.index('    Local Activity'),raw.index('      mResumed='),raw.index('    ViewRoot:'),
              raw.index('      mPausedForTransition='),raw.index('    Looper'),raw.index('    Local FragmentActivity'),
              raw.index('      mCurState=')]
        values=[raw[:cut] for cut in cuts]
        values.extend((raw.replace('    Local Activity def State:\n',''),
            raw[:raw.index('    ViewRoot:')]+raw[raw.index('    View Hierarchy:'):],
            raw.replace('    Local FragmentActivity def State:\n',''),
            raw.replace('      mCurrentConfig={mDisplayRotation=ROTATION_0 mWindowingMode=fullscreen}\n','')))
        for marker in ('    Local Activity def State:','    ViewRoot:','    View Hierarchy:',
                       '    Local FragmentActivity def State:','    Added Fragments:'):
            values.append(raw[:raw.index(marker)+len(marker)])
        return values
    def test_partial_body_matrix_has_no_scene_or_success_authority(self):
        for raw in self.partials():
            with self.subTest(length=len(raw)):
                with self.assertRaises(ValueError) as strict:t.settings_scene(raw)
                self.assertNotIsInstance(strict.exception,t.IncompleteSettingsObservation)
                with self.assertRaises(t.IncompleteSettingsObservation) as pending:self.observe(raw)
                self.assertTrue(pending.exception.missing);self.assertFalse(hasattr(pending.exception,'scene'))
    def test_missing_early_data_does_not_hide_later_contradictions(self):
        raw=scene_fixture(True).replace('    Local Activity def State:\n','')
        changes=[('pid=123','pid=999'),('uid=1000','uid=2000'),('userId=0','userId=1'),('displayId=0','displayId=1'),
            ('mCurrentConfig={','mCurrentConfig={different '),('mHidden=false','mHidden=true'),
            ('mDetached=false','mDetached=true'),('mDestroyed=false','mDestroyed=true'),
            ('mAdded=true mRemoving=false','mAdded=false mRemoving=false'),('mRemoved=false','mRemoved=true'),
            ('mFrameScheduled=false','mFrameScheduled=invalid'),('mState=7','mState=1'),
            ('ScreenTimeoutSettings','ForeignSettings'),('android:id/title','android:id/foreign'),
            ('mPendingInputEventCount=0','mPendingInputEventCount=-1')]
        for before,after in changes:
            with self.subTest(after=after),self.assertRaises(ValueError) as caught:self.observe(raw.replace(before,after))
            self.assertNotIsInstance(caught.exception,t.IncompleteSettingsObservation)
        foreign=scene_fixture().replace('com.android.settings/.Settings$DisplaySettingsActivity','com.foreign/.Activity')
        with self.assertRaisesRegex(ValueError,'Foreign resumed'):self.observe(raw.splitlines(True)[0]+foreign)
        # A complete-line tree prefix already proving a mismatch is terminal.
        prefix=raw[:raw.index('    Looper')].replace('android:id/title','android:id/foreign')
        with self.assertRaisesRegex(ValueError,'hierarchy changed'):self.observe(prefix)
    def test_malformed_present_is_not_missing(self):
        raw=scene_fixture(True).replace('      mPendingInputEventCount=0\n','')
        changes=[('    Local Activity def State:','    Local Activity NOT_HEX State:'),
            ('    ViewRoot:','    ViewRoot: extra'),('mCurrentConfig={mDisplayRotation=ROTATION_0 mWindowingMode=fullscreen}','mCurrentConfig='),
            ('    Local FragmentActivity def State:','    Local FragmentActivity BAD State:'),
            ('    Added Fragments:','    Added Fragments: extra'),('mHasWindowFocus=true','mHasWindowFocus=wat'),
            ('mCurrentConfig={mDisplayRotation=ROTATION_0 mWindowingMode=fullscreen}','mCurrentConfig invalid'),
            ('mFrameScheduled=false','mFrameScheduled invalid'),('      #0: ScreenTimeoutSettings','      #0 ScreenTimeoutSettings')]
        values=[raw.replace(a,b) for a,b in changes]
        values.extend((raw+'  ACTIVITY \n',raw+'  ACTIVITY malformed\n',raw.splitlines(True)[0]*2,raw.replace('      mFrameScheduled=false\n','      mFrameScheduled=false\n      mFrameScheduled=invalid\n'),
            raw[:raw.index('    Looper')]+'        android.widget.TextView{half-row'))
        for value in values:
            with self.subTest(last=value[-90:]),self.assertRaises(ValueError) as caught:self.observe(value)
            self.assertNotIsInstance(caught.exception,t.IncompleteSettingsObservation)
        for value in ('','TASK nothing\n','Permission Denial: activity dump\n'):
            with self.assertRaises(ValueError) as caught:self.observe(value)
            self.assertNotIsInstance(caught.exception,t.IncompleteSettingsObservation)
    def test_complete_strict_results_and_diagnostics_remain_strict(self):
        ready,opened=self.contexts()
        self.assertEqual(self.observe(scene_fixture()),ready);self.assertEqual(self.observe(scene_fixture(True)),opened)
        full=scene_fixture()
        for valid,malformed in [('    Local Activity def State:','    Local Activity NOT_HEX State:'),
                ('    ViewRoot:','    ViewRoot: extra'),
                ('    Local FragmentActivity def State:','    Local FragmentActivity NOT_HEX State:'),
                ('      mFrameScheduled=false','      mFrameScheduled invalid'),
                ('      mChangingConfigurations=false','      mChangingConfigurations invalid')]:
            bad=full.replace(valid,malformed+'\n'+valid)
            for read in (t.settings_scene,self.observe):
                with self.subTest(malformed=malformed),self.assertRaises(ValueError) as caught:read(bad)
                self.assertNotIsInstance(caught.exception,t.IncompleteSettingsObservation)
        for prefix in (scene_fixture(),scene_fixture(True).splitlines(True)[0]):
            for diagnostic in ('Permission Denial: no access','dumpsys: Permission denied','java.lang.SecurityException: denied',
                               'Error dumping activity: remote died','Error: unavailable',
                               'Failure while dumping the activity: java.io.IOException: Pipe closed',
                               'Exception while dumping: java.lang.IllegalStateException','Unable to dump activity'):
                with self.subTest(diagnostic=diagnostic),self.assertRaisesRegex(ValueError,'access/error diagnostic'):
                    self.observe(prefix+diagnostic+'\n')
    def test_actual_caller_missing_then_stable_never_repeats_input(self):
        for suffix in ('opened','returned'):
            with self.subTest(suffix=suffix),tempfile.TemporaryDirectory() as root:
                run=Sim(root);original=run.shell;reads=0
                def shell(command,**kwargs):
                    nonlocal reads
                    value=original(command,**kwargs)
                    if kwargs.get('label')=='baseline-scene-'+suffix:
                        reads+=1
                        if reads==1:return scene_fixture(suffix=='returned').splitlines(True)[0]
                    return value
                run.shell=shell
                with patch.object(t.s,'now',run.now):report=run.execute()
                self.assertEqual(reads,2);self.assertEqual(run.calls.count('baseline-redraw-open'),1)
                self.assertEqual(run.calls.count('baseline-redraw-cancel'),1)
                self.assertEqual(report['stages'][0]['redraw_audit']['scene_sha256'][2],report['redraw_ui_calibration']['scene_sha256']['ready'])
    def test_missing_timeout_late_transport_access_and_caught_failures_stay_latched(self):
        for fault in ('timeout','late','transport','access','contradiction'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as root:
                run=Sim(root);original=run.shell;reads=0
                def shell(command,**kwargs):
                    nonlocal reads
                    value=original(command,**kwargs)
                    if kwargs.get('label')!='baseline-scene-returned':return value
                    reads+=1;value=scene_fixture(True).splitlines(True)[0]
                    if fault=='late':run.clock.sleep(1.1)
                    if fault=='transport' and reads==2:raise TimeoutError('read transport failed')
                    if fault=='access':value+='Permission Denial: no access\n'
                    if fault=='contradiction':value=value.replace('pid=123','pid=999')
                    return value
                run.shell=shell
                with patch.object(t.s,'now',run.now),self.assertRaises(RuntimeError):run.execute()
                self.assertEqual(run.calls.count('reboot'),1);self.assertEqual(run.children,['baseline-write'])
                self.assertEqual(run.calls.count('baseline-redraw-open'),1);self.assertEqual(run.calls.count('baseline-redraw-cancel'),1)
                self.assertNotIn('baseline-before-hold',run.calls)
                if fault in ('late','access','contradiction'):self.assertEqual(reads,1)
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);run.setup();run.setup_aa();run.redraw_scenes=dict(zip(('ready','opened'),self.contexts()));run.redraw_tap=[10,10]
            original=run.shell
            def shell(command,**kwargs):
                value=original(command,**kwargs)
                return scene_fixture(True).splitlines(True)[0] if kwargs.get('label')=='baseline-scene-returned' else value
            run.shell=shell
            with self.assertRaises(ValueError):run.redraw('baseline')
            self.assertTrue(run.pending_read);before=list(run.calls)
            for action in (lambda:run.redraw('again'),lambda:run.replay('again'),lambda:run.prehold({})):
                with self.assertRaises(ValueError):action()
                self.assertEqual(run.calls,before)
    def test_real_scene_command_merges_rc0_stderr_and_preserves_failure_rc(self):
        import subprocess,shlex
        ready,opened=self.contexts()
        for full in (False,True):
            for rc,diagnostic in ((0,'Permission Denial: no access'),(0,'Error dumping activity: failed'),(7,'')):
                with self.subTest(full=full,rc=rc,diagnostic=diagnostic),tempfile.TemporaryDirectory() as root:
                    clock=Clock();calls=[];stderr_results=[]
                    class FakeADB:
                        def shell(self,target,command,timeout):
                            calls.append(command)
                            raw='TASK fixture\n'+(scene_fixture() if full else scene_fixture(True).splitlines(True)[0])
                            stub='dumpsys() { printf %s '+shlex.quote(raw)+'; printf %s '+shlex.quote(diagnostic)+' >&2; return '+str(rc)+'; }; '
                            result=subprocess.run(['sh','-c',stub+command],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                            stderr_results.append(result.stderr)
                            return result.returncode,result.stdout,result.stderr
                    run=t.AATimedTrial(FakeADB(),6,1,'aa_stderr_scene',root,root,sleep=clock.sleep,monotonic=clock)
                    run.target_ui_guard=lambda:'true';run.pending_read=True
                    with self.assertRaises(ValueError):run.settle_scene('baseline-scene-returned',ready,opened)
                    self.assertEqual(len(calls),1);self.assertTrue(run.pending_read)
                    self.assertEqual(stderr_results,[b''])
                    self.assertTrue(calls[0].endswith('dumpsys activity top 2>&1'));self.assertNotIn('|',calls[0])
    def test_external_c2_header_only_through_inherited_read_settle(self):
        import hashlib,os
        path=os.environ.get('AA_MISSING_SCENE_PATH')
        if not path:self.skipTest('Explicit private C2 missing-body reference not supplied')
        raw=Path(path).read_bytes();self.assertEqual(len(raw),63056)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'06c101b59d8d6e8e01b111febf6c06a0c5bd29ed21e5aa92e44a035051ae2d99')
        text=raw.decode();header=re.search(r'^  ACTIVITY com.android.settings/.SubSettings [0-9a-f]+ pid=(\d+)[^\n]*\n\Z',text,re.M)
        self.assertIsNotNone(header)
        # The exact missing record has no canonical scene. Test contexts and
        # later ready response are synthetic, bound to the available header PID.
        ready_raw='TASK synthetic\n'+scene_fixture().replace('pid=123','pid='+header[1])
        opened_raw=scene_fixture(True).replace('pid=123','pid='+header[1])
        ready,opened=t.settings_scene(ready_raw),t.settings_scene(opened_raw)
        with self.assertRaises(ValueError):t.settings_scene(text)
        with self.assertRaises(t.IncompleteSettingsObservation) as caught:
            t.settings_scene(text,transition=True,known_scenes=(ready,opened))
        self.assertFalse(hasattr(caught.exception,'scene'))
        for timeout in (False,True):
            with self.subTest(timeout=timeout),tempfile.TemporaryDirectory() as root:
                clock=Clock();calls=[]
                class FakeADB:
                    def shell(self,target,command,budget):
                        calls.append((command,budget));clock.sleep(.01)
                        return 0,(raw if timeout or len(calls)==1 else ready_raw.encode()),b''
                run=t.AATimedTrial(FakeADB(),6,1,'aa_missing_scene',root,root,sleep=clock.sleep,monotonic=clock)
                run.target_ui_guard=lambda:'true';run.pending_read=True
                if timeout:
                    with self.assertRaises(ValueError):run.settle_scene('baseline-scene-returned',ready,opened)
                else:
                    self.assertEqual(run.settle_scene('baseline-scene-returned',ready,opened),t.scene_digest(ready));self.assertEqual(len(calls),2)
                self.assertTrue(run.pending_read)
                self.assertTrue(all('input ' not in command for command,_ in calls))
                self.assertTrue(all(a[1]>b[1] for a,b in zip(calls,calls[1:])))


class RedrawCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):Sim.reader=execute_reader_fixture()[0].stdout
    def execute(self,run):
        with patch.object(t.s,'now',run.now):return run.execute()
    def test_slow_calibration_outside_baseline_and_all_stages_same_fast_path(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);commands=[];original=run.shell
            def shell(command,**kwargs):
                commands.append((command,kwargs))
                if 'uiautomator dump' in command:run.clock.sleep(2.2)
                return original(command,**kwargs)
            run.shell=shell;report=self.execute(run)
            baseline=run.calls.index('baseline-write')
            self.assertFalse(any('redraw-before' in label or 'redraw-opened' in label or 'redraw-returned' in label for label in run.calls[baseline:]))
            for stage in ('baseline','sham_stock','return_stock'):
                for part in ('ready','opened','returned'):self.assertEqual(run.calls.count(stage+'-scene-'+part),1)
            self.assertLessEqual(report['redraw_ui_calibration']['completed_monotonic'],report['writes'][0]['started_monotonic'])
            self.assertEqual(report['prearm_planning_estimate']['observed_baseline_phase_seconds'],report['stages'][0]['phase_seconds'])
            self.assertLess(report['stages'][0]['phase_seconds']['redraw_audit'],1)
            for command,kwargs in commands:
                if 'dumpsys activity top' in command:
                    self.assertFalse(kwargs.get('root',False));self.assertIn('= 2000',command)
    def test_calibration_semantic_or_return_fault_stops_before_writer(self):
        for fault in ('checkable','rotation','duplicate','opened','returned','same_scene','pid','stale'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as root:
                run=Sim(root);original=run.shell
                def shell(command,**kwargs):
                    value=original(command,**kwargs);label=kwargs.get('label','')
                    if label=='calibration-redraw-before':
                        if fault=='checkable':value=value.replace('checkable="false"','checkable="true"')
                        if fault=='rotation':value=value.replace('rotation="0"','rotation="1"')
                        if fault=='duplicate':value=value.replace('</hierarchy>','<node text="Screen timeout" package="com.android.settings"/></hierarchy>')
                    if label=='calibration-redraw-opened' and fault=='opened':value=value.replace('10 minutes','5 minutes')
                    if label=='calibration-redraw-returned' and fault=='returned':value=value.replace('20,20','21,20')
                    if label=='calibration-scene-opened' and fault=='same_scene':value=scene_fixture()
                    if label=='calibration-scene-opened' and fault=='pid':value=value.replace('pid=123','pid=456')
                    if fault=='stale' and label in ('calibration-redraw-before','calibration-redraw-opened','calibration-redraw-returned'):
                        value=READY_XML.replace('</hierarchy>','<node text="10 minutes" package="com.android.settings"/></hierarchy>')
                    return value
                run.shell=shell
                with self.assertRaises(RuntimeError):self.execute(run)
                self.assertEqual(run.children,[]);self.assertNotIn('timed-watchdog-arm',run.calls)
                if fault in ('checkable','rotation','duplicate'):self.assertNotIn('calibration-redraw-open',run.calls)
    def test_real_dispatch_uncertainty_never_retries_input_or_next_dsi(self):
        labels=[stage+suffix for stage in ('calibration','baseline','sham_stock','return_stock')
                for suffix in ('-scene-ready','-redraw-open','-scene-opened','-redraw-cancel','-scene-returned','-redraw-setting')]
        for label in labels:
            with self.subTest(label=label),tempfile.TemporaryDirectory() as root:
                run=Sim(root);run.failure=label
                with self.assertRaises(RuntimeError):self.execute(run)
                self.assertEqual(run.calls.count(label),1);self.assertEqual(run.calls.count('reboot'),1)
                after=run.calls[run.calls.index(label)+1:run.calls.index('reboot')]
                self.assertFalse(any(x.endswith(('-write','-before-hold','-c1','-after-hold','-redraw-open','-redraw-cancel')) for x in after))
    def test_known_previous_scene_can_settle_without_input_replay(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);original=run.shell;pending=['baseline-scene-opened','baseline-scene-returned']
            def shell(command,**kwargs):
                value=original(command,**kwargs);label=kwargs.get('label','')
                if label in pending:pending.remove(label);return scene_fixture(label.endswith('returned'))
                return value
            run.shell=shell;self.execute(run)
            for part in ('opened','returned'):self.assertEqual(run.calls.count('baseline-scene-'+part),2)
            self.assertEqual(run.calls.count('baseline-redraw-open'),1);self.assertEqual(run.calls.count('baseline-redraw-cancel'),1)
    def test_wrong_stable_scene_and_malformed_result_not_pollable(self):
        for value in (scene_fixture(True).replace('pid=123','pid=999'),'truncated'):
            with tempfile.TemporaryDirectory() as root:
                run=Sim(root);original=run.shell
                def shell(command,**kwargs):
                    result=original(command,**kwargs)
                    return value if kwargs.get('label')=='baseline-scene-opened' else result
                run.shell=shell
                with self.assertRaises(RuntimeError):self.execute(run)
                self.assertEqual(run.calls.count('baseline-scene-opened'),1)
                self.assertNotIn('baseline-redraw-cancel',run.calls);self.assertEqual(run.children,['baseline-write'])
    def test_settle_deadline_is_total_and_keeps_pending_on_expiry(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);original=run.shell
            def shell(command,**kwargs):
                result=original(command,**kwargs)
                return scene_fixture() if kwargs.get('label')=='baseline-scene-opened' else result
            run.shell=shell
            with self.assertRaises(RuntimeError):self.execute(run)
            self.assertEqual(run.calls.count('baseline-redraw-open'),1)
            self.assertNotIn('baseline-redraw-cancel',run.calls);self.assertIn('reboot',run.calls)
    def test_real_inherited_version_handshake_can_exceed_acceptance_deadline(self):
        import struct
        import guarded_adb_socket as adb_module
        clock=Clock();start=clock();connect_timeouts=[];dispatch=[]
        raw=b'TASK settings\n'+scene_fixture().encode()
        class Socket:
            def __init__(self,data):self.data=data
            def __enter__(self):return self
            def __exit__(self,*args):self.close()
            def close(self):pass
            def settimeout(self,value):pass
            def recv(self,n):part,self.data=self.data[:n],self.data[n:];return part
            def sendall(self,data):
                if b'shell,v2,raw:' in data:dispatch.append(clock())
        adb=adb_module.GuardedADB.__new__(adb_module.GuardedADB);adb.protocol=b'0029';adb.identities={}
        def connect(timeout):
            connect_timeouts.append(timeout)
            if len(connect_timeouts)==1:
                clock.sleep(1.1);return Socket(b'OKAY00040029')
            return Socket(b'OKAYOKAY'+struct.pack('<BI',1,len(raw))+raw+struct.pack('<BI',3,1)+b'\x00')
        adb.connect=connect
        with tempfile.TemporaryDirectory() as root,patch.object(adb_module.time,'monotonic',clock):
            run=t.AATimedTrial(adb,6,1,'aa_scene_clock',root,root,sleep=clock.sleep,monotonic=clock)
            run.pending_read=True
            with self.assertRaisesRegex(ValueError,'Late Settings scene result'):
                run.settle_scene('late-scene-returned',t.settings_scene(raw.decode()),t.settings_scene(scene_fixture(True)))
            self.assertTrue(run.pending_read);self.assertEqual(connect_timeouts,[12,1.0])
            self.assertEqual(len(dispatch),1);self.assertAlmostEqual(dispatch[0]-start,1.1)
    def test_timeout_setting_and_wire_still_reject(self):
        for fault in ('setting','wire','trace'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as root:
                run=Sim(root);original=run.shell
                def shell(command,**kwargs):
                    value=original(command,**kwargs);label=kwargs.get('label')
                    if fault=='setting' and label=='baseline-redraw-setting':return '600000'
                    if fault=='wire' and label=='baseline-redraw-wire':return value.replace(run.marker+'_REDRAW_END_baseline','dsi_ctrl_cmd_transfer native unexpected\n'+run.marker+'_REDRAW_END_baseline')
                    if fault=='trace' and label=='baseline-redraw-trace':return value+'mode_ctrl_return: rc=0\n'
                    return value
                run.shell=shell
                with self.assertRaises(RuntimeError):self.execute(run)
                self.assertEqual(run.children,['baseline-write']);self.assertIn('reboot',run.calls)


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


class MiddleDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Sim.reader=execute_reader_fixture()[0].stdout

    execute=Tests.execute

    def make_run(self,root,candidate=False):
        if not candidate:return Sim(root)
        with tempfile.TemporaryDirectory() as stock_root:
            proof=self.execute(Sim(stock_root))
        return Sim(root,aa_candidate=True,stock_qualification=proof,
                   optical_qualification=optical_qualification_fixture(proof),source_record=proof)

    def test_exact_stock_and_candidate_policy_and_real_callback_chain(self):
        for candidate in (False,True):
            with self.subTest(candidate=candidate),tempfile.TemporaryDirectory() as root:
                run=self.make_run(root,candidate);report=self.execute(run)
                t.acquisition.validate_acquisition(report)
                middle='aa10' if candidate else 'sham_stock'
                self.assertEqual(run.entry_count,56)
                self.assertEqual([s['transaction']['entry_count_after'] for s in report['stages']],[5,27,39])
                self.assertEqual([s['selectors_before_hold']['entry_count_after'] for s in report['stages']],[12,34,46])
                self.assertNotIn(middle+'-c1',run.calls);self.assertNotIn(middle+'-after-hold',run.calls)
                self.assertEqual(report['stages'][1]['c1'],t.acquisition.OMITTED_C1)
                self.assertEqual(report['stages'][1]['selectors_after_hold'],t.acquisition.OMITTED_POSTSELECTORS)
                self.assertNotIn('postselectors_verified_monotonic',report['stages'][1])
                self.assertEqual(report['stages'][1]['hold_end_guard']['entry_count_after'],34)
                self.assertLess(run.calls.index(middle+'-hold-end-esd'),run.calls.index(middle+'-hold-trace'))
                self.assertLess(run.calls.index(middle+'-hold-trace'),run.calls.index('return_stock-writer-isolate'))
                self.assertNotIn('return_stock-hold-end-esd',run.calls)
                for label in ('baseline',middle,'return_stock'):
                    self.assertEqual(run.calls.count(label+'-redraw-open'),1)
                    self.assertEqual(run.calls.count(label+'-redraw-cancel'),1)
                for index,label in ((0,'baseline'),(2,'return_stock')):
                    self.assertEqual(report['stages'][index]['c1']['data'],[0,0,96])
                    self.assertIn(label+'-after-hold',run.children)
                self.assertEqual(report['candidate_attempts'],int(candidate))

    def test_baseline_and_return_diagnostics_still_mandatory_for_candidate(self):
        for label in ('baseline-c1','baseline-after-hold','return_stock-c1','return_stock-after-hold'):
            with self.subTest(label=label),tempfile.TemporaryDirectory() as root:
                run=self.make_run(root,True);run.failure=label
                with self.assertRaises(RuntimeError):self.execute(run)
                self.assertEqual(run.calls.count('reboot'),1)
                self.assertNotIn('return_hold_and_postselectors_verified',run.report)

    def test_middle_hold_state_native_owner_esd_and_trace_failures_abort(self):
        faults={'FIELDS':lambda _: '3599\n0\n0\nEnforcing\n',
                'BOOT':lambda _: 'foreign-boot\n','OWNER':lambda _: 'unexpected\n',
                'KERNEL':lambda raw:raw+'dsi_ctrl_cmd_transfer len=1\n'}
        for fault in (*faults,'esd_transport','esd_value','trace_transport','trace_value'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as root:
                run=Sim(root);original=run.shell
                if fault in faults:run.part_faults={('sham_stock-hold-end',fault):faults[fault]}
                if fault.endswith('_transport'):
                    run.failure='sham_stock-'+('hold-end-esd' if fault.startswith('esd') else 'hold-trace')
                def shell(command,**kwargs):
                    value=original(command,**kwargs);label=kwargs.get('label')
                    if fault=='esd_value' and label=='sham_stock-hold-end-esd':return 'esd_sw_sim_success'
                    if fault=='trace_value' and label=='sham_stock-hold-trace':return value+'mode_ctrl_return: rc=-5\n'
                    return value
                run.shell=shell
                with self.assertRaises(RuntimeError):self.execute(run)
                self.assertEqual(run.calls.count('reboot'),1)
                self.assertNotIn('return_stock-writer-isolate',run.calls)
                self.assertEqual([s['label'] for s in run.report['stages']],['baseline'])

    def test_caught_hold_guard_error_stays_latched_without_later_input_or_dsi(self):
        for failure in ('baseline-hold-end-esd','baseline-hold-trace'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as root:
                run=Sim(root);run.setup();run.setup_aa();run.calibrate_redraw()
                record=run.writer('baseline');run.prehold(record);run.failure=failure
                with self.assertRaises(TimeoutError):run.finish_hold(record)
                self.assertTrue(run.panel_uncertain);self.assertTrue(run.pending_read)
                calls=list(run.calls)
                for operation in (lambda:run.writer('sham_stock'),lambda:run.redraw('later'),
                                  lambda:run.c1('later'),lambda:run.selectors('later'),
                                  lambda:run.replay('later'),lambda:run.finish_hold(record)):
                    with self.assertRaises(ValueError):operation()
                self.assertEqual(run.calls,calls)
                self.assertNotIn('hold_end_guard',record)
                self.assertNotIn('hold_guard_verified_monotonic',record)

    def test_new_guard_uses_real_inherited_shell_with_no_dsi_and_terminal_rc(self):
        for fault in (None,'rc','timeout','value','trace','late'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as root:
                run=Sim(root);run.setup();run.setup_aa();commands=[]
                class FakeADB:
                    def shell(self,target,command,timeout):
                        commands.append(command)
                        if fault=='late':run.clock.sleep(.02)
                        if fault=='timeout':raise TimeoutError('unknown completion')
                        if len(commands)==1:
                            return (1 if fault=='rc' else 0),('bad' if fault=='value' else 'reg_read\n').encode(),b''
                        return 0,(b'mode_ctrl_return: rc=-5\n' if fault=='trace' else b''),b''
                run.g=t.timed.DeadlineTransport(run,FakeADB());run.shell=t.s.Sweep.shell.__get__(run)
                if fault=='late':run.active_start=run.clock()-36.99
                if fault is None:
                    self.assertEqual(run.hold_end_guard('baseline'),{'esd_mode':'reg_read','main_trace_prefix_verified':True,'entry_count_after':0})
                    self.assertFalse(run.pending_read);self.assertEqual(len(commands),2)
                else:
                    with self.assertRaises((ValueError,TimeoutError)):run.hold_end_guard('baseline')
                    self.assertTrue(run.pending_read)
                    if fault=='late':
                        self.assertTrue(run.panel_uncertain);self.assertTrue(run.active_failed)
                        self.assertEqual(len(commands),1)
                self.assertIn('set -eu',commands[0]);self.assertIn('esd_check_mode',commands[0])
                self.assertNotIn('tx_cmd',commands[0]);self.assertNotIn('rx_cmd',commands[0])
                self.assertNotIn('input ',commands[0])

    def test_stage_policy_never_omits_unknown_or_wrong_mode(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root)
            for label in ('aa10','unknown',''):
                with self.assertRaises(ValueError):run.middle_stage(label)
            run.aa_candidate=True
            with self.assertRaises(ValueError):run.middle_stage('sham_stock')

    def test_generated_hold_guard_owner_failure_prevents_esd_subprocess(self):
        import os
        import subprocess
        for valid in (False,True):
            with self.subTest(valid=valid),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);lock=root/'lock';lock.mkdir(mode=0o700)
                run=Sim(directory);run.setup();commands=[]
                (lock/'owner').write_text(run.token if valid else 'another-owner')
                (lock/'owner').chmod(0o600)
                def shell(command,**kwargs):
                    commands.append(command)
                    return 'reg_read' if kwargs.get('label').endswith('-esd') else ''
                run.shell=shell;run.hold_end_guard('baseline')
                command=commands[0].replace(t.a9.LOCK,str(lock))
                command=command.replace(')" = 0',')" = '+str(os.getuid()))
                child=t.s.esd_read_script(run.tmp)
                self.assertEqual(command.count(child),1)
                # Stub only the read-only child. Real generated ownership,
                # type/mode/token checks must run before its dispatch.
                command=command.replace(child,'printf called > '+str(root/'dispatched'))
                result=subprocess.run(['sh','-c',command],capture_output=True,timeout=5)
                self.assertEqual(result.returncode==0,valid)
                self.assertEqual((root/'dispatched').exists(),valid)

    def test_projection_counts_measured_guard_once_and_refuses_slow_guard_before_arm(self):
        phases={key:1. for key in t.acquisition.BASELINE_PHASES}
        self.assertEqual(t.acquisition.planning_estimate(phases),14.)
        phases['hold_end_guard']=2.
        self.assertEqual(t.acquisition.planning_estimate(phases),15.)
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);original=run.shell
            def shell(command,**kwargs):
                value=original(command,**kwargs)
                if kwargs.get('label')=='baseline-hold-end-esd':run.clock.sleep(30)
                return value
            run.shell=shell
            with self.assertRaises(RuntimeError):self.execute(run)
            self.assertNotIn('timed-watchdog-arm',run.calls);self.assertNotIn('reboot',run.calls)
            self.assertEqual(run.report['full_table_writes_attempted'],['baseline'])
            self.assertGreater(run.report['prearm_planning_estimate']['estimated_active_seconds'],37)


if __name__=='__main__':unittest.main()
