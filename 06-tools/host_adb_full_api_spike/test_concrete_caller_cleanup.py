"""Concrete source stop_camera/restore/alarm logic with exclusively fake I/O.

Two inactive proposals are applied only to source text in memory. Stage methods
are fixture choreography, not DDIC qualification. Signal injection tests Python
alarm cleanup logic, not real POSIX signal delivery. No runtime module imports.
"""
import ast
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import shlex
from types import SimpleNamespace
import unittest
import xml.etree.ElementTree as ET

import test_offline_baseline_adb as f
import test_canonical_boot_guard as guard

HERE=Path(__file__).resolve().parent
PINS={
 'stock_c1_sweep.py':guard.PIN,
 'run_p85_guarded_trial.py':'b651f185c0691d72de050415ad76886439f700e0e8d0a34e404de012014662d0',
 'run_p85_batched_trial.py':'51a21e7aa38b69402afe94fe1f7db3cea3f1d6edb49dc56cf64af03a9f98d0f7',
 'run_p85_timed_stock_trial.py':'69d6a563ba313c2c2ba304f4d1abc77f2186326c4c27fd0f09ed85adc54eb4f1',
 'run_dsi_mode_trial.py':'e57c886791311f2cd7ab764efd0ec7ab89956f04273f26f1482dda002659ef4e',
 'dsi_trial_transaction.py':'9dc5c47b2bdc1932e30d2764b27c218d1b7f8465f99e9eb2b98c635a183fc142'}

def read_source(name):
    raw=(HERE.parent/name).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PINS[name]:raise RuntimeError('Pinned input changed: '+name)
    return raw.decode()

def proposed_trial_source():
    import difflib
    source=read_source('run_p85_guarded_trial.py')
    old="        self.g.run(['adb','-t',str(self.camera),'pull',source,str(self.private/'capture.mp4')],timeout=90,check=True)\n"
    new="        self.g.run(['adb','-t',str(self.camera),'pull',source,str(self.private/'capture.mp4')],\n                   timeout=90,check=True,expected_size=size,byte_cap=size)\n"
    if source.count(old)!=1:raise RuntimeError('Pull proposal anchor changed')
    proposed=source.replace(old,new)
    diff=''.join(difflib.unified_diff(source.splitlines(True),proposed.splitlines(True),
        fromfile='a/06-tools/run_p85_guarded_trial.py',tofile='b/06-tools/run_p85_guarded_trial.py'))
    binding=json.loads((HERE/'pull_metadata_source_binding.json').read_text())
    if (diff!=(HERE/'pull_metadata.proposed.patch').read_text()
        or hashlib.sha256(diff.encode()).hexdigest()!=binding['patch_sha256']
        or hashlib.sha256(proposed.encode()).hexdigest()!=binding['proposed_in_memory_sha256']
        or binding['original_sha256']!=PINS['run_p85_guarded_trial.py']
        or binding['applied_to_runtime'] is not False):raise RuntimeError('Pull proposal binding mismatch')
    return proposed

class FakeSignal:
    ITIMER_REAL=0;SIGALRM=14
    def __init__(self):self.timer=(0.0,0.0);self.original=object();self.handler=self.original;self.events=[]
    def getitimer(self,which):return self.timer
    def getsignal(self,which):return self.handler
    def signal(self,which,handler):self.handler=handler;self.events.append(('handler',handler))
    def setitimer(self,which,seconds):self.timer=(float(seconds),0.0);self.events.append(('timer',seconds))
    def fire(self):return self.handler(self.SIGALRM,None)

class MemoryPath:
    def __init__(self,fs,path):self.fs=fs;self.path=path
    def __str__(self):return self.path
    def __truediv__(self,name):return MemoryPath(self.fs,self.path+'/'+name)
    def open(self,mode):
        if mode!='xb':raise AssertionError('Only exclusive artifact create expected')
        if self.path in self.fs:raise FileExistsError('Fixture path already exists')
        self.fs[self.path]=bytearray()
        path=self
        class Writer:
            def __enter__(self):return self
            def write(self,data):path.fs[path.path].extend(data);return len(data)
            def __exit__(self,*args):pass
        return Writer()
    def chmod(self,mode):
        if mode!=0o600:raise AssertionError('Unexpected artifact permissions')
    def stat(self):return SimpleNamespace(st_size=len(self.fs[self.path]))

class FakeProbe:
    def __init__(self):
        self.calls=[];self.error=None;self.raw=None
        self.data={'streams':[{'codec_type':'video','codec_name':'h264','width':1280,'height':720,
            'avg_frame_rate':'30/1'}], 'format':{'duration':'15'}}
    def run(self,argv,**kwargs):
        self.calls.append((argv,kwargs))
        if self.error:raise self.error
        return SimpleNamespace(stdout=self.raw if self.raw is not None else json.dumps(self.data).encode())

def classes(signal,probe):
    thread=object()
    ns={'check':guard.check,'q':shlex.quote,'re':re,'json':json,'ET':ET,'contextmanager':contextmanager,
        'signal':signal,'threading':SimpleNamespace(current_thread=lambda:thread,main_thread=lambda:thread),
        'subprocess':probe,'c1':SimpleNamespace(PANEL='fixture-panel',LOCK='/fixture/existing-lock'),
        'HOLD':4.5,'ACTIVE_SECONDS':37.0,'now':lambda:'fixture-time'}
    def compile_nodes(nodes):exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),
                                          '<pinned-concrete-caller>','exec'),ns)
    stock=ast.parse(guard.source_pair()[1])
    constants=[n for n in stock.body if isinstance(n,ast.Assign) and len(n.targets)==1
        and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('BL','CON','KEYS','MODULE_SHA')]
    helpers=[n for n in stock.body if isinstance(n,ast.FunctionDef)
        and n.name in ('esd_read_script','logger_value','software_hz')]
    restore_order=next(n for n in ast.parse(read_source('dsi_trial_transaction.py')).body
        if isinstance(n,ast.FunctionDef) and n.name=='refresh_restore_order')
    video_select=next(n for n in ast.parse(read_source('run_dsi_mode_trial.py')).body
        if isinstance(n,ast.FunctionDef) and n.name=='new_camera_video')
    compile_nodes(constants+helpers+[restore_order,video_select])
    ns['s']=SimpleNamespace(**ns)
    def add_class(tree,name,new_name,base,methods):
        original=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==name)
        body=[n for n in original.body if isinstance(n,ast.FunctionDef) and n.name in methods]
        if {n.name for n in body}!=set(methods):raise RuntimeError('Missing class methods')
        node=ast.ClassDef(name=new_name,bases=[ast.Name(id=base,ctx=ast.Load())] if base else [],
            keywords=[],body=body,decorator_list=[])
        compile_nodes([node])
    add_class(stock,'Sweep','Sweep',None,('shell','identity','state','wait_value','recover','restore'))
    trial=ast.parse(proposed_trial_source())
    compile_nodes([next(n for n in trial.body if isinstance(n,ast.FunctionDef) and n.name=='validate_video_probe')])
    add_class(trial,'Trial','Trial','Sweep',('shell','cam','camera_ui','camera_tap','cleanup_camera_xml',
        'stop_camera','recover','restore','disarm_short'))
    batch=ast.parse(read_source('run_p85_batched_trial.py'))
    add_class(batch,'BatchedTrial','BatchedTrial','Trial',('restore',))
    timed=ast.parse(read_source('run_p85_timed_stock_trial.py'))
    add_class(timed,'DeadlineTransport','DeadlineTransport',None,('__init__','__getattr__','shell'))
    add_class(timed,'TimedStockTrial','TimedStockTrial','BatchedTrial',('shell','cam','remaining',
        'active_window','recover','restore','execute'))
    return ns

class Scenario:
    def __init__(self):
        self.signal=FakeSignal();self.probe=FakeProbe();self.ns=classes(self.signal,self.probe)
        self.h=f.Harness(auto=True);self.h.ready();self.fs={};self.labels=[]
        self.fail_label=None;self.fail_kind='timeout';self.fail_once=True;self.fail_count=0
        self.bad_stat=None;self.bad_listing=None;self.bad_ui=False;self.recording=True
        self.settings={key:'120.0' for key in self.ns['KEYS']}
        self.settings.update(screen_brightness='100',screen_off_timeout='600000',screen_brightness_mode='0')
        self.dbv=3600;self.logger=1;self.boot=guard.BEFORE;self.boot_after=guard.AFTER
        parent=self
        base=self.ns['TimedStockTrial']
        class Concrete(base):
            def shell(run,command,**kw):
                parent.current_label=kw.get('label','shell');parent.current_command=command
                parent.labels.append(parent.current_label)
                return super().shell(command,**kw)
            def cam(run,command,label,timeout=15):
                parent.current_label='camera-'+label;parent.current_command=command
                parent.labels.append(parent.current_label)
                return super().cam(command,label,timeout)
        self.run=r=Concrete()
        r.target=7;r.camera=8;r.serial=f.SERIALS[0];r.camera_serial=f.SERIALS[1]
        r.private=MemoryPath(self.fs,'/fixture/private');r.plan={'experiment_id':'fixture_capture'}
        r.monotonic=self.h.clock;r.sleep=self.h.clock.sleep;r.save=lambda:None;r._persist=lambda _:None
        r.event=0;r.report={'events':[],'stages':[],'active_actions':[]};r.current_action='none'
        r.before={'boot_id':self.boot,'native_dbv':6438,'logger':0,'screen_brightness':'80',
            'screen_brightness_mode':'0','screen_off_timeout':'null','min_refresh_rate':'null','peak_refresh_rate':'120.0'}
        r.ops={'verify':'fixture-owner-check','release':'fixture-release-owner'};r.tmp='/data/local/tmp/fixture_capture'
        r.token='fixture_owner_token';r.pending_read=r.inflight=r.recovery_failed=r.panel_uncertain=False
        r.active_start=None;r.active_failed=False;r.guard_context=False;r.candidate_started=None
        r.candidate_attempts=0;r.observation_failed=False;r.explicit_return_verified=True
        r.short_armed=False;r.changed=r.armed=r.temp=r.locked=True
        r.child_records=[];r.nonces=[];r.envelopes=[]
        r.recording=True;r.cam_xml_owned=False;r.files_before=''
        r.return_estimate=lambda:{}
        r.g=self.ns['DeadlineTransport'](r,self.h.adb)
        original_create=self.h.create_sink
        def create_sink(path,deadline):
            sink=original_create(path,deadline)
            if path in self.fs:raise FileExistsError('Fixture exclusive sink collision')
            self.fs[path]=sink.data;return sink
        self.h.adb._create_sink=create_sink
        self.h.shell_handler=self.respond
        # Stage fixture choreography only. Actual execute, alarm, recovery,
        # camera stop and complete restore functions below are not replaced.
        r.setup=lambda:None;r.observe_stage=lambda label:r.report['stages'].append({'label':label})
        r.camera_identity=lambda:None;r.metadata=lambda _:None;r.prepare_writer=lambda _:None
        r.arm_timed=lambda:None;r.write_stage=lambda label:None
        def timed_observe(label):
            record={'label':label}
            if label=='sham15':r.report['stages'].append(record)
            return record,self.h.clock()
        r.timed_observe=timed_observe
        r.optical_hold=lambda *args:None
    def respond(self,command):
        r=self.run;label=self.current_label;raw=self.current_command
        if label==self.fail_label and (not self.fail_once or self.fail_count==0):
            self.fail_count+=1
            if self.fail_kind=='late':self.h.clock.now+=100
            elif self.fail_kind=='alarm':self.signal.fire()
            else:return TimeoutError('fixture failure after request dispatch')
        if label=='camera-ui':
            if self.bad_ui:return b'<hierarchy><node content-desc="missing"/></hierarchy>'
            state='Stop recording video' if self.recording else 'Start recording video'
            return f'<hierarchy><node content-desc="{state}" bounds="[0,0][10,10]"/></hierarchy>'.encode()
        if label=='camera-tap':self.recording=False;return b''
        if label=='camera-files-after':return (f.REMOTE if self.bad_listing is None else self.bad_listing).encode()
        if label=='camera-video-size':return (str(len(self.h.pull_data)) if self.bad_stat is None else self.bad_stat).encode()
        if label in ('camera-fresh-ui-path','camera-remove-owned-ui'):return b''
        if label=='identity':return guard.IDENTITY.encode()
        if label=='root':return b'0'
        if label=='panel':return self.ns['c1'].PANEL.encode()
        if label=='module':return (self.ns['MODULE_SHA']+' fixture').encode()
        if label in ('boot','recovery-boot'):
            if self.h.listing==f.MOVED:self.boot=self.boot_after
            return self.boot.encode()
        if label=='recovery-complete':return b'1'
        if label in ('recovery-owner','owner'):return b''
        if label=='recovery-dc':return b'0'
        if label in ('recovery-esd','final-esd'):return b'reg_read'
        if label=='restore-power':return b'0'
        if label=='restore-peak':return self.settings['peak_refresh_rate'].encode()
        if label=='restore-setting':
            tokens=shlex.split(raw);key=tokens[3]
            self.settings[key]='null' if tokens[1]=='delete' else tokens[4];return b''
        if label=='restore-dbv':self.dbv=r.before['native_dbv'];return b''
        if label=='poll':return str(self.dbv).encode()
        if label=='verify-setting':return self.settings[shlex.split(raw)[3]].encode()
        if label=='state':return f'{self.dbv}\n0\n0\nEnforcing'.encode()
        if label=='display':return b'mActiveSfDisplayMode= peakRefreshRate=120.0'
        if label=='restore-logger':self.logger=r.before['logger'];return b''
        if label=='verify-logger':return f'logger: {self.logger}'.encode()
        if label in ('disarm-watchdog','remove-owned-temp','release-owner','disarm-candidate'):return b''
        raise AssertionError('Unmodeled actual caller command label: '+label)
    def execute(self):return self.run.execute()
    def assert_restored(self,test):
        r=self.run
        test.assertTrue(r.report['original_settings_dbv_logger_restored'])
        test.assertTrue(r.report['watchdog_disarmed']);test.assertTrue(r.report['mutex_released'])
        test.assertEqual(self.dbv,r.before['native_dbv']);test.assertEqual(self.logger,r.before['logger'])
        for key in self.ns['KEYS']:test.assertEqual(self.settings[key],r.before[key])
        test.assertEqual(self.signal.timer,(0.0,0.0));test.assertIs(self.signal.handler,self.signal.original)
        test.assertIsNone(r.active_start);test.assertFalse(r.guard_context)

class ConcreteCleanupTests(unittest.TestCase):
    def test_full_actual_camera_stop_probe_and_settings_restore(self):
        s=Scenario();s.execute();s.assert_restored(self)
        self.assertTrue(s.run.report['camera_stopped_verified']);self.assertTrue(s.run.report['camera_ui_temp_removed'])
        self.assertEqual(s.run.report['video_bytes'],3);self.assertEqual(s.run.report['video_profile']['codec'],'h264')
        self.assertEqual(s.probe.calls[0][1],{'capture_output':True,'timeout':20,'check':True})
        self.assertEqual(s.probe.calls[0][0],['ffprobe','-v','error','-show_streams','-show_format','-of','json',f.DEST])
        self.assertEqual(bytes(s.fs[f.DEST]),b'abc')
        self.assertEqual(s.h.events.count(('service','reboot:')),0)
    def test_postreturn_probe_timeout_and_wrong_or_missing_metadata_restore(self):
        cases=('timeout','process-error','malformed-json','missing-stream','wrong-codec','wrong-rate','wrong-duration')
        for case in cases:
            with self.subTest(case=case):
                s=Scenario()
                if case=='timeout':s.probe.error=TimeoutError('fixture ffprobe timeout')
                elif case=='process-error':s.probe.error=RuntimeError('fixture nonzero ffprobe')
                elif case=='malformed-json':s.probe.raw=b'{'
                elif case=='missing-stream':s.probe.data={}
                elif case=='wrong-codec':s.probe.data['streams'][0]['codec_name']='hevc'
                elif case=='wrong-rate':s.probe.data['streams'][0]['avg_frame_rate']='0/0'
                else:s.probe.data['format']['duration']='0'
                with self.assertRaises(RuntimeError):s.execute()
                s.assert_restored(self);self.assertFalse(s.run.panel_uncertain)
                self.assertEqual(s.h.events.count(('service','reboot:')),0)
                self.assertNotIn('video_profile',s.run.report);self.assertTrue(s.run.report['status'].startswith('failed'))
    def test_actual_selected_file_and_observed_size_rejections(self):
        for kind,value in (('listing',''),('listing',f.REMOTE+'\n'+f.REMOTE),
                           ('listing','/wrong/path.mp4'),('stat',''),('stat','not-int'),('stat','0'),('stat','2'),('stat','4')):
            with self.subTest(kind=kind,value=value):
                s=Scenario();setattr(s,'bad_'+('listing' if kind=='listing' else 'stat'),value)
                with self.assertRaises(RuntimeError):s.execute()
                s.assert_restored(self);self.assertFalse(s.run.panel_uncertain)
                self.assertFalse(s.probe.calls);self.assertEqual(s.h.events.count(('service','reboot:')),0)
    def test_actual_pull_after_dispatch_failure_preserves_cleanup(self):
        s=Scenario();s.h.pull_fail=True
        with self.assertRaises(RuntimeError):s.execute()
        s.assert_restored(self);self.assertFalse(s.run.panel_uncertain)
        self.assertEqual(s.h.events.count(('service','reboot:')),0);self.assertFalse(s.probe.calls)
        self.assertNotIn('video_bytes',s.run.report)
    def test_actual_pull_sink_deadline_after_dispatch_still_restores(self):
        s=Scenario();s.h.write_delay=100
        with self.assertRaises(RuntimeError):s.execute()
        s.assert_restored(self);self.assertFalse(s.run.panel_uncertain)
        self.assertEqual(s.h.events.count(('service','reboot:')),0);self.assertFalse(s.probe.calls)
        self.assertNotIn('video_bytes',s.run.report)
    def test_missing_stop_ui_retains_xml_but_panel_restore_remains_allowed(self):
        s=Scenario();s.bad_ui=True
        with self.assertRaises(RuntimeError):s.execute()
        s.assert_restored(self);self.assertTrue(s.run.recording and s.run.cam_xml_owned)
        self.assertNotIn('camera_stopped_verified',s.run.report)
        self.assertNotIn('camera-remove-owned-ui',s.labels);self.assertFalse(s.probe.calls)
        self.assertTrue(s.run.report['camera_ui_cleanup_pending'])
        self.assertEqual(s.h.events.count(('service','reboot:')),0)
    def test_restore_refresh_ceiling_order_and_null_delete(self):
        s=Scenario();s.settings['peak_refresh_rate']='90.0';s.run.before['min_refresh_rate']='120.0'
        s.execute();s.assert_restored(self)
        services=[e[1] for e in s.h.events if e[0]=='service']
        self.assertLess(services.index('shell,v2,raw:settings put system peak_refresh_rate 120.0'),
                        services.index('shell,v2,raw:settings put system min_refresh_rate 120.0'))
        self.assertIn('shell,v2,raw:settings delete system screen_off_timeout',services)
    def test_cleanup_tail_failures_do_not_claim_owner_release(self):
        for label in ('disarm-watchdog','remove-owned-temp','release-owner'):
            with self.subTest(label=label):
                s=Scenario();s.fail_label=label
                with self.assertRaises(RuntimeError):s.execute()
                self.assertNotIn('mutex_released',s.run.report)
                if label=='disarm-watchdog':
                    self.assertNotIn('watchdog_disarmed',s.run.report)
                    self.assertEqual(s.run.report['watchdog_state'],'disarm_outcome_uncertain')
                if label!='release-owner':self.assertNotIn('release-owner',s.labels)
                self.assertIs(s.signal.handler,s.signal.original)
    def test_late_postreturn_camera_result_is_failed_video_not_panel(self):
        s=Scenario();s.fail_label='camera-video-size';s.fail_kind='late'
        with self.assertRaises(RuntimeError):s.execute()
        s.assert_restored(self);self.assertFalse(s.run.panel_uncertain)
        self.assertEqual(s.h.events.count(('service','reboot:')),0);self.assertFalse(s.probe.calls)
    def test_cleanup_failure_retains_watchdog_owner(self):
        for label in ('restore-setting','restore-dbv','restore-logger','final-esd'):
            with self.subTest(label=label):
                s=Scenario();s.fail_label=label
                with self.assertRaises(RuntimeError):s.execute()
                self.assertNotIn('disarm-watchdog',s.labels);self.assertNotIn('release-owner',s.labels)
                self.assertNotIn('watchdog_disarmed',s.run.report);self.assertNotIn('mutex_released',s.run.report)
                self.assertEqual(s.signal.timer,(0.0,0.0));self.assertIs(s.signal.handler,s.signal.original)
    def test_active_camera_fault_actual_recovery_before_complete_restore(self):
        for fault in ('timeout','late','alarm'):
            with self.subTest(fault=fault):
                s=Scenario();s.fail_label='camera-active-fixture';s.fail_kind=fault
                stages=[]
                def write_stage(label):
                    stages.append(label)
                    s.run.cam('fixture active camera query','active-fixture')
                s.run.write_stage=write_stage
                with self.assertRaises(RuntimeError):s.execute()
                s.assert_restored(self)
                self.assertEqual(stages,['sham15']);self.assertEqual(s.h.events.count(('service','reboot:')),1)
                self.assertTrue(s.run.report['recovery_reboot_verified'])
                self.assertEqual(s.run.before['boot_id'],guard.AFTER)
                self.assertLess(s.labels.index('recovery-esd'),s.labels.index('restore-setting'))
                self.assertEqual(s.run.target,7);self.assertEqual(s.h.adb.identities['7'],f.SERIALS[0])
                index=s.h.events.index(('service','reboot:'))
                self.assertEqual(s.h.events[index-1],('service','host:transport:fixture-target'))
    def test_active_failure_wrong_new_boot_blocks_all_panel_cleanup(self):
        s=Scenario();s.fail_label='camera-active-fixture';s.boot_after='not-a-uuid'
        s.run.write_stage=lambda _:s.run.cam('fixture query','active-fixture')
        with self.assertRaises(RuntimeError):s.execute()
        self.assertTrue(s.run.recovery_failed);self.assertTrue(s.run.panel_uncertain)
        self.assertNotIn('restore-setting',s.labels);self.assertNotIn('disarm-watchdog',s.labels)
        self.assertNotIn('release-owner',s.labels);self.assertEqual(s.h.events.count(('service','reboot:')),1)
        self.assertIs(s.signal.handler,s.signal.original)
    def test_existing_alarm_refused_without_override(self):
        s=Scenario();s.signal.timer=(20.0,0.0)
        with self.assertRaises(ValueError):
            with s.run.active_window():pass
        self.assertEqual(s.signal.timer,(20.0,0.0));self.assertIs(s.signal.handler,s.signal.original)
        self.assertFalse(s.signal.events)
    def test_actual_short_watchdog_disarm_gate(self):
        s=Scenario();r=s.run;r.explicit_return_verified=False;r.short_armed=True
        with self.assertRaises(ValueError):r.disarm_short()
        self.assertNotIn('disarm-candidate',s.labels)
        r.report['recovery_reboot_verified']=True;r.disarm_short()
        self.assertFalse(r.short_armed);self.assertIn('disarm-candidate',s.labels)

if __name__=='__main__':unittest.main(verbosity=2)
