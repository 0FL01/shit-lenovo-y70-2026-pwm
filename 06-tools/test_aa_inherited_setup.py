"""Regression: execute inherited setup+settle+metadata; fake only external I/O.
No setup/settle/anchor/state/metadata overrides. No Android or network access.
"""
from pathlib import Path
import signal
import tempfile
import unittest
import run_aa_timed_stock_trial as aa
from test_p85_integration import SetupTrial,BOOT,REF
from test_p85_camera_startup import dump
from test_run_p85_timed_stock_trial import Clock

class SetupIO:
    def __init__(self,root,dumps=None):
        self.clock=Clock();self.calls=[];self.camera_calls=[];self.preflight_count=0;self.binds=[]
        owner=self
        class Transport:
            def preflight(self):owner.preflight_count+=1
            def bind(self,target):owner.binds.append(target);return ('fake-identity-'+str(target)).encode()
        super().__init__(Transport(),6,1,'aa_setup_regression',root,root,sleep=self.clock.sleep,monotonic=self.clock)
        self.dbv=828;self.hz=120;self.log='';self.bad_dispatch=False
        self.dumps=iter(dumps or [dump(),dump(1),dump(2)]);self.dump_count=0
    def shell(self,command,**kwargs):
        self.clock.sleep(.01)
        if kwargs.get('label')=='identity':
            self.calls.append(('identity',command))
            return 'XT2611-1\nW3WWS36.65-64-4-1\n_b\n6.12.58-android16-6-g09eda8c8505a-dirty-ab15950084-4k\nEnforcing\navr'
        if kwargs.get('label')=='root':return '0'
        if kwargs.get('label')=='panel':return aa.s.c1.PANEL
        if kwargs.get('label')=='module':return aa.s.MODULE_SHA+'  /vendor/lib/modules/msm_drm.ko'
        return SetupTrial.shell(self,command,**kwargs)
    def cam(self,command,label,timeout=15):
        self.camera_calls.append(label);self.clock.sleep(.05)
        if label=='identity':return 'Galaga\nROW\nA001'
        if label=='package':return 'versionName=1.56.2'
        if command=='dumpsys media.camera':self.dump_count+=1;return next(self.dumps)
        if label=='ui':return '<root><node content-desc="Start recording video" bounds="[0,0][100,100]"/><node content-desc="Switch to front camera" bounds="[100,0][200,100]"/></root>'
        return ''
    def mark(self,suffix):
        marker=self.marker+'_'+suffix;self.log+=f'[{self.clock():.6f}] {marker}\n';return marker
    def envelope(self,plan,label):
        self.calls.append(('envelope',label));result={}
        for part in plan.parts:
            if part.label in ('BEGIN','END'):
                marker=part.command.split('<6>',1)[1].split('\\n',1)[0]
                self.log+=f'[{self.clock():.6f}] {marker}\n';result[part.label]=''
            elif part.label=='WAIT':self.clock.sleep(2);result[part.label]=''
            elif part.label=='KERNEL':result[part.label]=self.log
            elif part.label=='FIELDS':result[part.label]=f'{self.dbv}\n0\n0\nEnforcing\n'
            elif part.label=='DISPLAY':result[part.label]=f'mActiveSfDisplayMode= peakRefreshRate={self.hz}.00001'
            elif part.label=='BOOT':result[part.label]=BOOT
            elif part.label=='OWNER':result[part.label]=''
            else:raise AssertionError(part.label)
        return result

class RealAASetup(SetupIO,aa.AATimedTrial):pass
class RealP85Setup(SetupIO,aa.base.Trial):pass

class Tests(unittest.TestCase):
    def test_actual_inherited_setup_reaches_real_settle_in_aa_schema(self):
        self.assertIs(RealAASetup.setup,aa.base.Trial.setup)
        self.assertIs(RealAASetup.settle_recording,aa.base.Trial.settle_recording)
        self.assertIs(RealAASetup.metadata,aa.base.Trial.metadata)
        with tempfile.TemporaryDirectory() as root:
            run=RealAASetup(root);run.setup()
            self.assertEqual(run.preflight_count,1);self.assertEqual(run.binds,[6,1])
            self.assertEqual(run.before['native_dbv'],828);self.assertEqual(run.dbv,3600)
            self.assertEqual([x['native_actual_hz'] for x in run.report['fresh_native_anchor']],[90,120])
            self.assertEqual(run.report['setup_brightness']['native_logged_values'],[3600])
            self.assertEqual(run.camera_calls.count('tap'),1)
            self.assertEqual(run.dump_count,3)
            self.assertEqual([x['frame_count'] for x in run.report['recording_preflight']],[101,102])
            self.assertEqual(run.report['recording_settle']['status'],'qualified')
            self.assertEqual(run.report['full_table_writes_attempted'],[])
            self.assertNotIn('register85_writes_attempted',run.report)
            self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0,0))
    def test_aa_prior_attempt_refuses_before_metadata(self):
        for attempt in ('baseline','sham_stock','aa10','return_stock'):
            with self.subTest(attempt=attempt),tempfile.TemporaryDirectory() as root:
                run=RealAASetup(root);run.recording=True;run.report['full_table_writes_attempted']=[attempt]
                with self.assertRaises(ValueError):run.settle_recording()
                self.assertEqual(run.dump_count,0);self.assertNotIn('recording_settle',run.report)
    def test_original_p85_setup_and_attempt_guard_unchanged(self):
        with tempfile.TemporaryDirectory() as root:
            run=RealP85Setup(root);run.setup()
            self.assertEqual(run.report['recording_settle']['status'],'qualified')
            self.assertEqual(run.report['register85_writes_attempted'],[])
            self.assertNotIn('full_table_writes_attempted',run.report)
        with tempfile.TemporaryDirectory() as root:
            run=RealP85Setup(root);run.recording=True;run.report['register85_writes_attempted']=['sham15']
            with self.assertRaises(ValueError):run.settle_recording()
            self.assertEqual(run.dump_count,0)
    def test_actual_setup_preserves_settle_retry_limit_and_second_call_guard(self):
        with tempfile.TemporaryDirectory() as root:
            run=RealAASetup(root,[dump(),dump(1,mismatch=True),dump(2),dump(3)])
            run.setup();self.assertEqual(run.dump_count,4)
            self.assertEqual([x['frame_count'] for x in run.report['recording_preflight']],[102,103])
            with self.assertRaises(ValueError):run.settle_recording()
            self.assertEqual(run.dump_count,4)
    def test_missing_aa_attempts_is_not_defaulted_to_empty(self):
        with tempfile.TemporaryDirectory() as root:
            run=RealAASetup(root);run.recording=True;del run.report['full_table_writes_attempted']
            with self.assertRaises(KeyError):run.settle_recording()
            self.assertEqual(run.dump_count,0)

if __name__=='__main__':unittest.main()
