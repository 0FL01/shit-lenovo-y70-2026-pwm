"""Offline concrete batched orchestration with fake transport and real validators."""
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import p85_batched_envelope as e
import run_p85_batched_trial as b
from test_p85_batched_envelope import framed
from test_p85_guarded_trial import writer_fixture,N
from test_stock_c1_sweep import execute_reader_fixture
from test_p85_integration import SetupTrial,REF,BOOT

ANCHOR='dsi_display_set_mode hactive=1440, vactive=3168, fps=120(actual=120, group=0x3), clk_rate=1234000000\n'


class Simulated(b.BatchedTrial):
    reader=None;writer=None
    def __init__(self,root,fail_label=None,mode=None):
        super().__init__(None,6,1,'p85_batch_test',root,root,sleep=lambda _:None)
        self.g=self;self.failure=fail_label;self.mode=mode;self.calls=[];self.children=[];self.frames=0
    def setup(self):
        self.calls.append('setup');self.before={'boot_id':BOOT,'native_dbv':6438};self.reference=REF
    def envelope(self,plan,label):
        self.active_plan=plan;self.active_label=label;self.calls.append(label)
        return super().envelope(plan,label)
    def shell(self,*args,**kwargs):
        # As a fake ADB transport, shell(target, command, timeout); ordinary
        # coordinator cleanup shell(command,...) is handled without transport.
        if len(args)==3:
            target,command,timeout=args
            if target==1:
                if command!='screencap -p':raise AssertionError('Unexpected camera operation')
                return 0,b'\x89PNG\r\n\x1a\nfixture',b''
            plan=self.active_plan;label=self.active_label
            if label==self.failure and self.mode=='transport_before':raise TimeoutError('before child')
            if plan.child_command:self.children.append(label)
            if label==self.failure and self.mode=='transport_after':raise TimeoutError('after child')
            payload={}
            markers={p.label:p.command.split('<6>',1)[1].split('\\n',1)[0]
                     for p in plan.parts if p.label in ('BEGIN','END')}
            for part in plan.parts:
                if part.label in ('BEGIN','END','WAIT','OWNER'):value=''
                elif part.label=='FIELDS':value='3600\n0\n0\nEnforcing\n'
                elif part.label=='DISPLAY':value='mActiveSfDisplayMode= peakRefreshRate=120.00001\n'
                elif part.label=='BOOT':value=BOOT+'\n'
                elif part.label=='ESD':value='reg_read\n'
                elif part.label=='CHILD':
                    value=self.writer if label.endswith('-write') else self.reader
                    if label.endswith('-p85'):
                        value=value.replace('C1 0x00 0x00 0x60','P85_LONG3 0x15 0x00 0x00')
                    value=value.replace(N,plan.nonce)
                elif part.label=='KERNEL':
                    begin=markers.get('BEGIN',getattr(self,'hold_begin','MISSING'))
                    value=ANCHOR+begin+'\n'
                    if label.endswith('-write'):
                        value+=''.join('dsi-ctrl-1: dsi_ctrl_cmd_transfer len='+str(len(packet)-7)+
                            ', type=0x39 hs cmds= '+packet[7:].hex(' ')+'\n' for packet in b.p85.proposal('restore15'))
                    if label==self.failure and self.mode=='native':value+=ANCHOR
                    value+=markers.get('END','MISSING')+'\n'
                else:raise AssertionError(part.label)
                payload[part.label]=value
            if label==self.failure:
                if self.mode=='state':payload['FIELDS']='3601\n0\n0\nEnforcing\n'
                elif self.mode=='boot':payload['BOOT']='changed\n'
                elif self.mode=='owner':payload['OWNER']='unexpected'
                elif self.mode=='esd':payload['ESD']='esd_sw_sim_success\n'
                elif self.mode=='callback':payload['CHILD']=payload['CHILD'].replace('rc=0','rc=-5',1)
                elif self.mode=='payload':payload['CHILD']=payload['CHILD'].replace('0x15 0x00 0x00','0x14 0x00 0x00')
            raw=framed(plan,payload)
            if label==self.failure:
                if self.mode=='framing':raw=raw[:-4]
                elif self.mode=='invalid_utf8':raw=raw.replace(b'Enforcing',b'Enforcin\xff',1)
                elif self.mode=='stderr':return 0,raw,b'warning'
                elif self.mode=='nonzero':return 17,raw,b''
            return 0,raw,b''
        command=args[0]
        self.calls.append('cleanup-owned-envelope')
        return ''
    def mark(self,suffix):
        marker=self._marker(suffix);self.hold_begin=marker;self.calls.append('hold-begin');return marker
    def metadata(self,label):
        self.calls.append(label);frame=self.frames;self.frames+=135
        return {'frame_count':frame,'session_token':'session'}
    def recover(self):
        self.calls.append('reboot');self.panel_uncertain=self.pending_read=self.inflight=False
        self.observation_failed=False;self.report['recovery_reboot_verified']=True
    def stop_camera(self):self.calls.append('camera-stop');self.report['camera_stopped_verified']=True


class BatchedSetup(SetupTrial,b.BatchedTrial):
    def envelope(self,plan,label):
        result={}
        for part in plan.parts:
            if part.label in ('BEGIN','END'):
                marker=part.command.split('<6>',1)[1].split('\\n',1)[0]
                self.log+=marker+'\n';result[part.label]=''
            elif part.label=='WAIT':result[part.label]=''
            elif part.label=='KERNEL':result[part.label]=self.log
            elif part.label=='FIELDS':result[part.label]=f'{self.dbv}\n0\n0\nEnforcing\n'
            elif part.label=='DISPLAY':result[part.label]=f'mActiveSfDisplayMode= peakRefreshRate={self.hz}.00001'
            elif part.label=='BOOT':result[part.label]=BOOT
            elif part.label=='OWNER':result[part.label]=''
            else:raise AssertionError(part.label)
        return result


class BatchedRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result,_,_=execute_reader_fixture()
        if result.returncode!=0:raise AssertionError(result.stderr)
        Simulated.reader=result.stdout
        result,_,_=writer_fixture('sham15')
        if result.returncode!=0:raise AssertionError(result.stderr)
        Simulated.writer=result.stdout

    def test_complete_stock_order_real_validators_and_timing(self):
        with tempfile.TemporaryDirectory() as root:
            run=Simulated(root)
            with patch.object(b.base.Trial,'restore',side_effect=lambda:run.calls.append('settings-restore')):
                result=run.execute()
            self.assertEqual(run.children,['baseline-p85','baseline-c1','sham15-write','sham15-p85','sham15-c1','return15-write','return15-p85','return15-c1'])
            self.assertEqual(result['status'],'awaiting_optical_review')
            self.assertFalse(result['unknown_value_write_attempted']);self.assertEqual(result['candidate_attempts'],0)
            self.assertEqual([x['hold_seconds'] for x in result['stages']],[4.5]*3)
            self.assertEqual([x['observed_sensor_frames'] for x in result['stages']],[135]*3)
            self.assertIn('host_validation',{x['kind'] for x in result['phase_timings']})
            for event in result['envelope_timings']:
                self.assertGreaterEqual(event['end_monotonic'],event['start_monotonic'])
                self.assertEqual(event['transport_seconds'],event['transport_end_monotonic']-event['transport_start_monotonic'])
            self.assertTrue(all(x['cleaned'] for x in json.loads((Path(root)/'envelope-manifest.json').read_text())))
            for label in ('baseline','sham15','return15'):
                order=[run.calls.index(label+'-hold-start'),run.calls.index(label+'-hold-end'),run.calls.index(label+'-hold-end',run.calls.index(label+'-hold-end')+1)]
                self.assertEqual(order,sorted(order))  # camera_end precedes target end envelope.

    def test_each_child_failure_reboots_without_next_child_or_blind15(self):
        children=['baseline-p85','baseline-c1','sham15-write','sham15-p85','sham15-c1','return15-write','return15-p85','return15-c1']
        for label in children:
            for mode in ('framing','invalid_utf8','stderr','nonzero','transport_before','transport_after','callback','state','boot','owner','esd','native'):
                with self.subTest(label=label,mode=mode),tempfile.TemporaryDirectory() as root:
                    run=Simulated(root,label,mode)
                    with patch.object(b.base.Trial,'restore',side_effect=lambda:run.calls.append('settings-restore')):
                        with self.assertRaises(RuntimeError):run.execute()
                    expected=children[:children.index(label)+(0 if mode=='transport_before' else 1)]
                    self.assertEqual(run.children,expected)
                    self.assertEqual(run.calls.count('reboot'),1)
                    self.assertLess(run.calls.index('reboot'),run.calls.index('settings-restore'))
                    self.assertTrue(run.report['status'].startswith('failed'))

    def test_wrong_p85_readback_prevents_following_c1(self):
        for label in ('baseline-p85','sham15-p85','return15-p85'):
            with self.subTest(label=label),tempfile.TemporaryDirectory() as root:
                run=Simulated(root,label,'payload')
                with patch.object(b.base.Trial,'restore'):
                    with self.assertRaises(RuntimeError):run.execute()
                self.assertEqual(run.children[-1],label)
                self.assertEqual(run.calls.count('reboot'),1)

    def test_hold_end_state_native_framing_transport_failures_recover(self):
        for stage in ('baseline','sham15','return15'):
            for mode in ('state','boot','owner','native','framing','stderr','transport_after'):
                with self.subTest(stage=stage,mode=mode),tempfile.TemporaryDirectory() as root:
                    run=Simulated(root,stage+'-hold-end',mode)
                    with patch.object(b.base.Trial,'restore',side_effect=lambda:run.calls.append('settings-restore')):
                        with self.assertRaises(RuntimeError):run.execute()
                    self.assertEqual(run.calls.count('reboot'),1)
                    self.assertLess(run.calls.index('reboot'),run.calls.index('settings-restore'))

    def test_prestate_blocks_quiet_and_subsequent_child(self):
        with tempfile.TemporaryDirectory() as root:
            run=Simulated(root,'state','state')
            with patch.object(b.base.Trial,'restore'):
                with self.assertRaises(RuntimeError):run.execute()
            self.assertEqual(run.children,[])
            self.assertFalse(any(label.startswith('quiet-') for label in run.calls))

    def test_concrete_setup_preserves_actual_original6438(self):
        with tempfile.TemporaryDirectory() as root:
            run=BatchedSetup(root);run.dbv=6438;run.setup()
            self.assertEqual(run.before['native_dbv'],6438);self.assertEqual(run.dbv,3600)
            self.assertEqual(run.report['setup_brightness']['native_logged_values'],[3600])
            self.assertEqual([label for label,_ in run.calls].count('native-brightness'),1)
            self.assertEqual(run.reference,REF)

    def test_candidate_and_uncertain_cleanup_blocked(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):b.BatchedTrial(None,6,1,'p85_batch_test',root,root,candidate=True)
            run=Simulated(root)
            with self.assertRaises(ValueError):run.write_stage('candidate14')
            with self.assertRaises(ValueError):run.arm_candidate()
            run.panel_uncertain=True
            with patch.object(b.base.Trial,'restore') as restore:
                with self.assertRaises(ValueError):run.restore()
                restore.assert_not_called()

    def test_offline_cli_no_output_or_private_creation(self):
        with tempfile.TemporaryDirectory() as root:
            output=Path(root)/'absent'
            result=subprocess.run(['python3',str(Path(b.__file__)),'6','1','--stock-only',
                '--experiment-id','p85_batch_cli_test','--output',str(output)],capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr)
            data=json.loads(result.stdout);self.assertTrue(data['offline_only']);self.assertFalse(data['candidate_enabled'])
            self.assertEqual(len(data['source_tracked_paths']),len(b.base.SOURCE_FILES)+2)
            self.assertFalse(output.exists())


if __name__=='__main__':unittest.main()
