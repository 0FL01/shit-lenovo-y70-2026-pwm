"""Offline timed stock scheduling/guards using real DSI evidence validators."""
import json
from pathlib import Path
import re
import shlex
import signal
import socket
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import run_p85_timed_stock_trial as t
from test_p85_batched_envelope import framed,local_script
from test_p85_guarded_trial import writer_fixture,N
from test_stock_c1_sweep import execute_reader_fixture
from test_p85_integration import REF,BOOT
from test_run_p85_batched_trial import ANCHOR,BatchedSetup


class Clock:
    def __init__(self):self.value=100.0
    def __call__(self):return self.value
    def sleep(self,n):self.value+=n


class Transport:
    def __init__(self,run):self.run=run
    def shell(self,target,command,timeout):
        run=self.run;run.timeouts.append(timeout);run.clock.sleep(.15)
        if run.late:run.clock.sleep(38)
        if target==1:return 0,b'\x89PNG\r\n\x1a\nfixture',b''
        plan=run.active_plan;label=run.active_label
        if label==run.failure and run.mode=='transport_before':raise TimeoutError('before')
        if label==run.failure and run.mode=='deadline':run.clock.sleep(38)
        payload={}
        for part in plan.parts:
            if part.label in ('BEGIN','END'):
                marker=part.command.split('<6>',1)[1].split('\\n',1)[0];run.log+=f'[{run.clock():.6f}] '+marker+'\n';value=''
            elif part.label=='WAIT':run.clock.sleep(2);value=''
            elif part.label=='PRE_GUARD':
                if label==run.failure and run.mode=='guard':return 17,b'',b''
                value='GUARD_TIMING 100.00 100.10\n'
            elif part.label=='CHILD':
                run.children.append(label)
                if label.endswith('-write'):
                    value=run.writer
                    run.log+=''.join('dsi-ctrl-1: dsi_ctrl_cmd_transfer len='+str(len(packet)-7)+', type=0x39 hs cmds= '+packet[7:].hex(' ')+'\n' for packet in t.p85.proposal('restore15'))
                else:
                    value=run.reader
                    if label.endswith('-p85'):value=value.replace('C1 0x00 0x00 0x60','P85_LONG3 0x15 0x00 0x00')
                value=value.replace(N,plan.nonce)
            elif part.label=='KERNEL':value=run.log
            elif part.label=='FIELDS':value='3600\n0\n0\nEnforcing\n'
            elif part.label=='DISPLAY':value='mActiveSfDisplayMode= peakRefreshRate=120.00001\n'
            elif part.label=='BOOT':value=BOOT+'\n'
            elif part.label=='OWNER':value=''
            elif part.label=='ESD':value='reg_read\n'
            else:raise AssertionError(part.label)
            payload[part.label]=value
        if label==run.failure:
            if run.mode=='transport_after':raise TimeoutError('after')
            if run.mode=='native':payload['KERNEL']+=ANCHOR
            if run.mode=='state':payload['FIELDS']='3601\n0\n0\nEnforcing\n'
            if run.mode=='esd':payload['ESD']='wrong'
            if run.mode=='owner':payload['OWNER']='wrong'
            if run.mode=='boot':payload['BOOT']='wrong'
            if run.mode=='callback':payload['CHILD']=payload['CHILD'].replace('rc=0','rc=-5',1)
        raw=framed(plan,payload)
        if label==run.failure and run.mode=='framing':raw=raw[:-4]
        return 0,raw,b''


class Sim(t.TimedStockTrial):
    reader=None;writer=None
    def __init__(self,root,failure=None,mode=None):
        clock=Clock();super().__init__(None,6,1,'p85_timed_test',root,root,sleep=clock.sleep,monotonic=clock)
        self.clock=clock;self.g=t.DeadlineTransport(self,Transport(self));self.calls=[];self.children=[]
        self.log=ANCHOR;self.failure=failure;self.mode=mode;self.frames=0;self.timeouts=[];self.late=False
    def setup(self):self.before={'boot_id':BOOT,'native_dbv':6438};self.reference=REF
    def identity(self):self.calls.append('identity')
    def camera_identity(self):self.calls.append('camera-identity')
    def envelope(self,plan,label):
        self.active_plan=plan;self.active_label=label;self.calls.append(label)
        return super().envelope(plan,label)
    def mark(self,suffix):
        marker=self._marker(suffix);self.log+=marker+'\n';self.clock.sleep(.1);return marker
    def metadata(self,label,**kwargs):
        start=self.clock();self.clock.sleep(.15);frame=self.frames;self.frames+=135
        self.calls.append(label)
        if label==self.failure:raise ValueError('camera metadata')
        return {'frame_count':frame,'session_token':'session','host_capture_bounds':{'begin_monotonic':start,'end_monotonic':self.clock()}}
    def shell(self,command,**kwargs):
        label=kwargs.get('label');self.calls.append(label);self.clock.sleep(.1)
        if label==self.failure:raise TimeoutError(label)
        return ''
    def recover(self):
        self.calls.append('reboot');self.assert_alarm_off=not self.guard_context and self.active_start is None
        self.panel_uncertain=self.pending_read=self.inflight=False;self.active_failed=False
        self.report['recovery_reboot_verified']=True
    def stop_camera(self):self.calls.append('stop-camera');self.report['camera_stopped_verified']=True
    def restore(self):
        if self.panel_uncertain or self.pending_read:raise AssertionError('restore into uncertainty')
        self.calls.append('settings-restore');self.report['original_settings_dbv_logger_restored']=True
    def cleanup_camera_xml(self):pass


class TimedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result,_,_=execute_reader_fixture();assert result.returncode==0,result.stderr;Sim.reader=result.stdout
        result,_,_=writer_fixture('sham15');assert result.returncode==0,result.stderr;Sim.writer=result.stdout

    def test_full_protocol_and_overlap_real_host_validators(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);report=run.execute()
            self.assertEqual(run.children,['baseline-p85','baseline-c1','sham15-write','sham15-p85','return15-write','return15-p85','return15-c1'])
            self.assertEqual(report['scope'],t.SCOPE);self.assertEqual(report['candidate_attempts'],0)
            sham=report['stages'][1];self.assertEqual(sham['c1'],t.OMITTED_C1);self.assertNotIn('c1',sham['phase_seconds'])
            self.assertGreaterEqual(sham['camera_end']['host_capture_bounds']['begin_monotonic']-sham['camera_start']['host_capture_bounds']['end_monotonic'],4.5)
            self.assertGreaterEqual(report['writes'][1]['started_monotonic'],sham['hold_verified_monotonic'])
            self.assertLess(report['active_G_seconds'],37)
            self.assertLess(run.calls.index('quiet-sham15_PRE'),run.calls.index('timed-watchdog-arm'))
            self.assertLess(run.calls.index('disarm-candidate'),run.calls.index('return15-hold-start'))
            self.assertTrue(report['host_alarm_restored_before_cleanup']);self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0,0))
            self.assertTrue(report['active_actions']);self.assertFalse(report['candidate_enabled'])
            public=json.dumps(report)
            for secret in (run.token,BOOT,run.ops['verify'],str(run.private)):
                self.assertNotIn(secret,public)

    def test_faults_never_append_next_child_and_recover_before_settings(self):
        labels=['sham15-dispatch-gap','sham15-write','sham15-p85','sham15-hold-end','return15-dispatch-gap','return15-write','return15-p85','return15-c1']
        for label in labels:
            for mode in ('framing','transport_before','transport_after','state','native','owner','boot','deadline'):
                with self.subTest(label=label,mode=mode),tempfile.TemporaryDirectory() as root:
                    run=Sim(root,label,mode)
                    with self.assertRaises(RuntimeError):run.execute()
                    self.assertEqual(run.calls.count('reboot'),1);self.assertTrue(run.assert_alarm_off)
                    self.assertLess(run.calls.index('reboot'),run.calls.index('settings-restore'))
                    self.assertNotIn('return15-write',run.children if not label.startswith('return15') else [])
                    self.assertFalse(any(x.endswith('-write') for x in run.children[run.children.index(label)+1:]) if label in run.children else False)
                    self.assertFalse(run.report['candidate_enabled'])

    def test_guard_arm_disarm_and_camera_failures(self):
        for label,mode in [('sham15-write','guard'),('return15-write','guard'),('timed-watchdog-arm',None),('timed-watchdog-verify',None),('disarm-candidate',None),('sham15-hold-end',None)]:
            with self.subTest(label=label),tempfile.TemporaryDirectory() as root:
                run=Sim(root,label,mode)
                with self.assertRaises(RuntimeError):run.execute()
                self.assertIn('reboot',run.calls);self.assertTrue(run.assert_alarm_off)
                if label=='sham15-write':self.assertNotIn('sham15-write',run.children)

    def test_overlap_overshoot_keeps_whole_hold_and_truthful_timing(self):
        class SlowQuiet(Sim):
            def quiet(self,label,dbv,initial=False):
                result=super().quiet(label,dbv,initial=initial)
                if label=='return15_PRE':self.clock.sleep(4)
                return result
        with tempfile.TemporaryDirectory() as root:
            run=SlowQuiet(root);report=run.execute();sham=report['stages'][1];overlap=sham['return_prequiet']
            self.assertGreater(overlap['overshoot_seconds'],0);self.assertEqual(overlap['wait_seconds'],0)
            start=sham['camera_start']['host_capture_bounds']['end_monotonic']
            end=sham['camera_end']['host_capture_bounds']['begin_monotonic']
            self.assertGreater(end-start,4.5);self.assertGreaterEqual(sham['observed_sensor_frames'],120)
            self.assertEqual(report['disarmed_monotonic'],report['active_start_monotonic']+report['active_G_seconds'])

    def test_concrete_setup_preserves_actual_original_brightness(self):
        class TimedSetup(BatchedSetup,t.TimedStockTrial):
            def envelope(self,plan,label):
                result=super().envelope(plan,label)
                stamp=getattr(self,'kernel_stamp',100.0)
                for part in plan.parts:
                    if part.label=='WAIT':stamp+=2.0
                    if part.label in ('BEGIN','END'):
                        marker=part.command.split('<6>',1)[1].split('\\n',1)[0]
                        self.log=self.log.replace(marker+'\n',f'[{stamp:.6f}] '+marker+'\n')
                self.kernel_stamp=stamp+.1
                if 'KERNEL' in result:result['KERNEL']=self.log
                return result
        for original in (828,6438):
            with self.subTest(original=original),tempfile.TemporaryDirectory() as root:
                run=TimedSetup(root);run.dbv=original;run.setup()
                self.assertEqual(run.before['native_dbv'],original);self.assertEqual(run.dbv,3600)
                self.assertEqual([x[0] for x in run.calls].count('native-brightness'),1)
                self.assertEqual([x['native_actual_hz'] for x in run.report['fresh_native_anchor']],[90,120])
        with tempfile.TemporaryDirectory() as root:
            run=TimedSetup(root,bad_dispatch=True);run.dbv=6438
            with self.assertRaises(ValueError):run.setup()
            self.assertTrue(run.pending_read);self.assertEqual(run.before['native_dbv'],6438)

    def test_prepare_and_writer_are_one_shot(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);run.setup();run.prepare_writer('sham15')
            with self.assertRaises(ValueError):run.prepare_writer('sham15')
            run.panel_uncertain=True
            with self.assertRaises(ValueError):run.write_stage('sham15')
            self.assertFalse(run.children)
            run.panel_uncertain=False
            with self.assertRaises(ValueError):run.write_stage('sham15')
            with run.active_window():
                run.arm_timed();run.short_armed=False
                with self.assertRaises(ValueError):run.arm_timed()

    def test_caught_observation_failure_cannot_read_or_reapply(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root,'sham15-p85','framing');run.setup();run.observe_stage('baseline')
            run.prepare_writer('sham15')
            with run.active_window():
                run.arm_timed();run.write_stage('sham15')
                with self.assertRaises(ValueError):run.timed_observe('sham15')
                count=len(run.children);self.assertTrue(run.observation_failed)
                with self.assertRaises(ValueError):run.timed_observe('sham15')
                with self.assertRaises(ValueError):run.timed_observe('return15')
                with self.assertRaises(ValueError):run.write_stage('return15')
                self.assertEqual(len(run.children),count)
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);run.execute();count=len(run.children)
            with self.assertRaises(ValueError):run.timed_observe('return15')
            self.assertEqual(len(run.children),count)

    def test_caught_arm_failure_never_authorizes_writer(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root,'timed-watchdog-verify');run.setup();run.prepare_writer('sham15')
            with self.assertRaises(ValueError):
                with run.active_window():
                    with self.assertRaises(TimeoutError):run.arm_timed()
                    self.assertFalse(run.timed_watchdog_verified)
                    with self.assertRaises(ValueError):run.write_stage('sham15')
                    self.assertFalse(run.children)
            self.assertTrue(run.panel_uncertain)

    def test_transport_clipping_late_results_and_no_future_call(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);run.active_start=run.clock()-36.5;run.active_plan=t.env.state_envelope('f'*12,run.ops['verify']);run.active_label='state'
            run.before={'boot_id':BOOT};run.late=True
            with self.assertRaises(ValueError):run.g.shell(6,'irrelevant',50)
            self.assertLessEqual(run.timeouts[-1],.5);count=len(run.timeouts)
            with self.assertRaises(ValueError):run.g.shell(6,'irrelevant',50)
            self.assertEqual(len(run.timeouts),count)

    def test_deadline_interrupts_actual_blocked_read_restores_handler(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);old=signal.getsignal(signal.SIGALRM)
            with patch.object(t,'ACTIVE_SECONDS',.08):
                a,b=socket.socketpair()
                try:
                    with self.assertRaises(TimeoutError):
                        with run.active_window():a.recv(1)
                finally:a.close();b.close()
            self.assertIs(signal.getsignal(signal.SIGALRM),old);self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0,0))
            self.assertIsNone(run.active_start);self.assertTrue(run.active_failed)

    def test_existing_alarm_refused_without_replacing(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);handler=signal.getsignal(signal.SIGALRM);signal.setitimer(signal.ITIMER_REAL,20)
            try:
                with self.assertRaises(ValueError):
                    with run.active_window():pass
                self.assertIs(signal.getsignal(signal.SIGALRM),handler);self.assertGreater(signal.getitimer(signal.ITIMER_REAL)[0],0)
            finally:signal.setitimer(signal.ITIMER_REAL,0)

    def test_no_candidate_and_max_service_offline(self):
        sizes=t.size_preflight();self.assertLess(sizes['timed_sham15']['service_bytes'],65535)
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):t.TimedStockTrial(None,6,1,'p85_timed_test',root,root,candidate=True)
            run=Sim(root)
            for method in (lambda:run.write_stage('candidate14'),run.arm_candidate):
                with self.assertRaises(ValueError):method()


class DeviceGuardTests(unittest.TestCase):
    def exercise(self,log,*,read_rc=0,state='3600',owner='true'):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);work=root/'work';work.mkdir();kernel=root/'kernel';kernel.write_text(log)
            for name,value in {'brightness':state,'bl_power':'0','panelDC':'0','panelName':t.s.c1.PANEL,'boot':BOOT}.items():
                (root/name).write_text(value+'\n')
            plan=t.env.state_envelope('f'*12,owner)
            command='set -eu; '+t.guard_command(plan,owner,BOOT,'PROTECTED_BEGIN','f'*12)
            command=command.replace(plan.work,str(work)).replace(t.s.BL,str(root)+'/').replace(t.s.CON,str(root)+'/').replace('/proc/sys/kernel/random/boot_id',str(root/'boot'))
            command=command.replace('$(id -u)','0').replace('$(getenforce)','Enforcing')
            command=command.replace('dmesg >',f'(cat {kernel}; exit {read_rc}) >')
            result=subprocess.run(['sh','-c',command],capture_output=True,timeout=5)
            return result, (work/'guard-kernel').exists()

    def test_exact_guard_and_every_native_gap_failure(self):
        good=ANCHOR+'PROTECTED_BEGIN\nquiet\n'
        result,left=self.exercise(good);self.assertEqual(result.returncode,0,result.stderr)
        self.assertRegex(result.stdout,rb'^GUARD_TIMING [0-9.]+ [0-9.]+\n$');self.assertFalse(left)
        bad=[good+ANCHOR,good+ANCHOR.replace('actual=120','actual=1')+ANCHOR,
             good+'dsi_ctrl_cmd_transfer len=2\n',good+'Command transfer failed\n',good+'LOST 2 events\n',
             good+'PROTECTED_BEGIN\n',good.replace('PROTECTED_BEGIN','MISSING'),
             good.replace('1234000000','12340000000'),good.replace('fps=120','fps=90'),
             'malformed anchor\nPROTECTED_BEGIN\n',good+'PWM_P85_WRITE_'+'f'*12+'\n',
             good+('x'*(16*1024*1024))]
        for log in bad:
            with self.subTest(length=len(log)):
                result,_=self.exercise(log);self.assertNotEqual(result.returncode,0)
        for kw in ({'read_rc':7},{'state':'828'},{'owner':'false'}):
            result,_=self.exercise(good,**kw);self.assertNotEqual(result.returncode,0)

    def test_real_guard_envelope_failure_cannot_start_child_and_cleans_scratch(self):
        for bad in (False,True):
            with self.subTest(bad=bad),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);kernel=root/'kernel';child_ran=root/'child-ran'
                kernel.write_text(ANCHOR+'PROTECTED_BEGIN\n'+('LOST\n' if bad else ''))
                for name,value in {'brightness':'3600','bl_power':'0','panelDC':'0','panelName':t.s.c1.PANEL,'boot':BOOT}.items():
                    (root/name).write_text(value+'\n')
                seed=t.env.state_envelope('f'*12,'true')
                guard=t.guard_command(seed,'true',BOOT,'PROTECTED_BEGIN','f'*12)
                guard=guard.replace(t.s.BL,str(root)+'/').replace(t.s.CON,str(root)+'/').replace('/proc/sys/kernel/random/boot_id',str(root/'boot'))
                guard=guard.replace('$(id -u)','0').replace('$(getenforce)','Enforcing').replace('dmesg >',f'cat {kernel} >')
                child=f'echo ran > {child_ran}'
                plan=t.env.Envelope(seed.nonce,(t.env.Part('PRE_GUARD',guard,True,128),t.env.Part('CHILD',child,True,128)),10,child,seed.owner_digest)
                _,environ,work=local_script(plan,root)
                command=t.envelope_script(plan).replace('/system/bin/sh','/bin/sh').replace(plan.work,str(work))
                result=subprocess.run(['sh','-c',command],capture_output=True,env=environ,timeout=12)
                self.assertEqual(child_ran.exists(),not bad);self.assertFalse(work.exists())
                if bad:self.assertNotEqual(result.returncode,0)
                else:self.assertEqual(result.returncode,0,result.stderr);t.env.parse(result.stdout,plan)

    def test_unchanged_child_and_owned_scratch_cleanup(self):
        plan=t.guarded_writer_plan('f'*12,'true','x'*128,'sham15','BEGIN_MARKER','END_MARKER','/data/local/tmp/abcdefgh',BOOT,'PROTECTED_BEGIN')
        self.assertEqual(plan.child_command,t.p85.write_script('f'*12,'x'*128,'sham15'))
        labels=[x.label for x in plan.parts];self.assertEqual(labels[labels.index('CHILD')-1],'PRE_GUARD')
        command=t.envelope_script(plan);self.assertEqual(command.count('$W/guard-kernel'),2)
        cleanup=t.cleanup_command({'work':plan.work,'owner_digest':plan.owner_digest})
        self.assertIn('rm -f '+plan.work+'/guard-kernel '+plan.work+'/stdout',cleanup)
        self.assertLess(cleanup.index('owner)'),cleanup.index('rm -f'))
        result=subprocess.run(['sh','-n'],input=command.encode(),capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
