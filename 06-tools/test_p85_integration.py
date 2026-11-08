"""Concrete setup/observation methods with simulated transport, never ADB."""
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import run_p85_guarded_trial as r

BOOT='00000000-0000-0000-0000-000000000001'
REF={'width':1440,'height':3168,'software_peak_hz':120,'native_actual_hz':120,
     'native_group':3,'clock_rate':1234000000,'timing_node':'timing@0',
     'evidence':'latest retained dsi_display_set_mode anchor, not physical PWM'}


class SetupTrial(r.Trial):
    def __init__(self,root,bad_dispatch=False):
        class ADB:
            def preflight(self):pass
            def bind(self,transport):return ('private-'+str(transport)).encode()
        super().__init__(ADB(),5,1,'p85_setup_test',root,root,sleep=lambda _:None)
        self.dbv=828;self.hz=120;self.log='';self.calls=[];self.bad_dispatch=bad_dispatch
    def identity(self):pass
    def camera_identity(self):pass
    def metadata(self,label):pass
    def settle_recording(self):pass
    def camera_tap(self,label):pass
    def camera_ui(self):return ET.fromstring('<root><node content-desc="Start recording video"/><node content-desc="Switch to front camera"/></root>')
    def cam(self,command,label,timeout=15):return ''
    def mark(self,suffix):
        marker=self.marker+'_'+suffix;self.log+=marker+'\n';return marker
    def shell(self,command,**kwargs):
        label=kwargs.get('label');self.calls.append((label,command))
        if label=='before-setting':
            key=command.split()[-1]
            return {'screen_brightness':'10','screen_brightness_mode':'0','min_refresh_rate':'120.0',
                    'peak_refresh_rate':'120.0','screen_off_timeout':'600000'}[key]
        if label in ('before-boot','boot'):return BOOT
        if label in ('before-logger','verify-logger'):return 'mipi_cmd_log_en: 0'
        if label=='state':return f'{self.dbv}\n0\n0\nEnforcing'
        if command=='cat '+r.s.BL+'brightness':return str(self.dbv)
        if command=='dumpsys display':return f'mActiveSfDisplayMode= DisplayMode peakRefreshRate={self.hz}.00001'
        if command=='dmesg':return self.log
        if label=='stock-anchor':
            self.hz=90 if 'min_refresh_rate 90.0' in command else 120
            group=5 if self.hz==90 else 3
            self.log+=f'dsi_display_set_mode hactive=1440, vactive=3168, fps={self.hz}(actual={self.hz}, group=0x{group}), clk_rate=1234000000\n'
        if label=='native-brightness':
            self.dbv=int(re.search(r' (\d+) > ',command)[1]);value=1 if self.bad_dispatch else self.dbv
            self.log+=f'dsi-ctrl-1: dsi_ctrl_cmd_transfer len=3, type=0x39 hs cmds= 51 {value>>8:02x} {value&255:02x}\n'
        if label=='initial-esd':return 'reg_read'
        if label=='awake':return 'screenState=SCREEN_STATE_ON interactiveState=INTERACTIVE_STATE_AWAKE mIsShowing=false'
        return ''


class ObservationTrial(r.Trial):
    def __init__(self,root,fail):
        super().__init__(None,5,1,'p85_observe_test',root,root,sleep=lambda _:None)
        self.reference=REF;self.fail=fail;self.steps=[];self.frames=0;self.state_count=0
    def setup(self):self.steps.append('setup')
    def quiet(self,*args,**kwargs):return {}
    def mark(self,suffix):return suffix
    def shell(self,command,**kwargs):
        label=kwargs.get('label')
        if label=='read-esd':return 'reg_read'
        if label=='hold-kernel' and self.fail=='lost-native':return 'LOST'
        if label=='hold-kernel' and self.fail=='extra-native':return 'EXTRA'
        return 'fixture'
    def state(self,dbv):
        self.state_count+=1
        if self.fail=='state' and self.state_count==3:raise ValueError('native DBV drift')
    def metadata(self,label):
        if self.fail=='metadata':raise ValueError('stale camera')
        frame=self.frames;self.frames+=5 if self.fail=='frames' else 135
        return {'frame_count':frame,'session_token':'session'}
    def recover(self):
        self.steps.append('reboot')
        self.panel_uncertain=self.pending_read=self.inflight=False
        self.report['recovery_reboot_verified']=True
    def stop_camera(self):self.steps.append('stop')
    def restore(self):
        if self.panel_uncertain or self.pending_read:raise ValueError('unsafe restore')
        self.steps.append('settings')
    def write_stage(self,label):self.steps.append('WRITE:'+label)


class IntegrationTests(unittest.TestCase):
    def test_actual_setup_anchor_dispatch_from828_to3600(self):
        with tempfile.TemporaryDirectory() as root:
            run=SetupTrial(root);run.setup()
            self.assertEqual(run.before['native_dbv'],828);self.assertEqual(run.dbv,3600)
            self.assertEqual(run.report['setup_brightness']['native_logged_values'],[3600])
            self.assertEqual([x[0] for x in run.calls].count('native-brightness'),1)
            self.assertEqual([x['native_actual_hz'] for x in run.report['fresh_native_anchor']],[90,120])
            self.assertFalse(run.pending_read);self.assertEqual(run.reference,REF)

    def test_actual_setup_bad_dispatch_latches_uncertainty(self):
        with tempfile.TemporaryDirectory() as root:
            run=SetupTrial(root,bad_dispatch=True)
            with self.assertRaises(ValueError):run.setup()
            self.assertTrue(run.pending_read)
            self.assertEqual([x[0] for x in run.calls].count('native-brightness'),1)
            self.assertEqual(run.before['native_dbv'],828)

    def test_concrete_observation_faults_reboot_before_settings(self):
        for stage in ('baseline','sham15','return15'):
            for fault in ('p85','c1','lost-native','extra-native','metadata','frames','state'):
                with self.subTest(stage=stage,fault=fault),tempfile.TemporaryDirectory() as root:
                    run=ObservationTrial(root,fault)
                    original=run.observe_stage
                    run.observe_stage=lambda _label: original(stage)
                    def quiet(log,*args):
                        if log in ('LOST','EXTRA'):raise ValueError('lost or extra native event')
                        return REF
                    with patch.object(r.p85,'validate_long3',return_value={'data':[20 if fault=='p85' else 21,0,0]}), \
                         patch.object(r.s,'validate_adapter_capture',return_value={'data':[0,0,95 if fault=='c1' else 96]}), \
                         patch.object(r.s,'verify_read_interval'),patch.object(r.s,'qualify_quiet',side_effect=quiet):
                        with self.assertRaises(RuntimeError):run.execute()
                    self.assertEqual(run.steps,['setup','reboot','stop','settings'])
                    self.assertTrue(run.report['status'].startswith('failed'))

    def test_actual_restore_refuses_whole_stage_uncertainty(self):
        with tempfile.TemporaryDirectory() as root:
            run=r.Trial(None,5,1,'p85_restore_test',root,root);run.panel_uncertain=True
            with patch.object(r.s.Sweep,'restore') as restore:
                with self.assertRaises(ValueError):run.restore()
                restore.assert_not_called()
            with patch.object(run,'shell') as shell:
                with self.assertRaises(ValueError):run.write_stage('sham15')
                shell.assert_not_called()
            run.panel_uncertain=False;run.observation_failed=True
            with patch.object(run,'_observe_stage') as observe:
                with self.assertRaises(ValueError):run.observe_stage('sham15')
                observe.assert_not_called()


if __name__=='__main__':unittest.main()
