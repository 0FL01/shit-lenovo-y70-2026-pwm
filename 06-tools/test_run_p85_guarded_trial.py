"""Offline orchestration tests. Fake all transport; no phones or ADB commands."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import run_p85_guarded_trial as r


class Model(r.Trial):
    def __init__(self,root,*,candidate=False,fail=None):
        super().__init__(None,5,1,'p85_mock_test',root,root,candidate=candidate)
        self.calls=[];self.fail=fail;self.saved=[]
    def save(self):self.saved.append(dict(self.report))
    def step(self,label):
        self.calls.append(label)
        if self.fail==label:raise ValueError('injected')
    def setup(self):self.step('setup')
    def observe_stage(self,label):self.step('observe:'+label)
    def write_stage(self,label):
        self.pending_read=True
        if label=='candidate14':self.report['candidate_may_be_active']=True
        self.step('write:'+label);self.pending_read=False
    def arm_candidate(self):self.short_armed=True;self.step('arm')
    def recover(self):
        self.step('recover');self.pending_read=False
        self.report['recovery_reboot_verified']=True
    def stop_camera(self):self.step('stop');self.report['camera_stopped_verified']=True
    def restore(self):self.step('restore');self.report['original_settings_dbv_logger_restored']=True
    def disarm_short(self):
        if not self.explicit_return_verified and not self.report.get('recovery_reboot_verified'):
            raise ValueError('unsafe disarm')
        self.step('disarm');self.short_armed=False


class RunnerTests(unittest.TestCase):
    def test_stock_only_sequence_never14(self):
        with tempfile.TemporaryDirectory() as root:
            run=Model(root);result=run.execute()
            self.assertEqual(run.calls,['setup','observe:baseline','write:sham15','observe:sham15',
                'write:return15','observe:return15','stop','restore'])
            self.assertEqual(result['status'],'awaiting_optical_review')
            self.assertTrue(result['explicit15_readback_and_stock_c1_return'])

    def test_candidate_sequence_disarm_only_after_return(self):
        with tempfile.TemporaryDirectory() as root:
            run=Model(root,candidate=True);run.execute()
            self.assertEqual(run.calls,['setup','observe:baseline','write:sham15','observe:sham15',
                'arm','write:candidate14','observe:candidate14','write:return15','observe:return15',
                'disarm','stop','restore'])

    def test_faults_recover_without_blind_return_or_retry(self):
        for point in ('arm','write:candidate14','observe:candidate14','write:return15','observe:return15'):
            with self.subTest(point=point),tempfile.TemporaryDirectory() as root:
                run=Model(root,candidate=True,fail=point)
                with self.assertRaises(RuntimeError):run.execute()
                after=run.calls[run.calls.index(point)+1:]
                self.assertEqual(after,['recover','stop','disarm','restore'])
                self.assertNotIn('write:return15',after)
        with tempfile.TemporaryDirectory() as root:
            run=Model(root,fail='write:sham15')
            with self.assertRaises(RuntimeError):run.execute()
            self.assertEqual(run.calls[-3:],['recover','stop','restore'])

    def test_recovery_failure_preserves_watchdog_and_owner(self):
        with tempfile.TemporaryDirectory() as root:
            run=Model(root,candidate=True,fail='write:candidate14')
            def fail():run.calls.append('recover');run.recovery_failed=True;raise ValueError('failed boot')
            run.recover=fail
            with self.assertRaises(RuntimeError):run.execute()
            self.assertEqual(run.calls[-2:],['recover','stop'])
            self.assertTrue(run.short_armed)

    def test_camera_failure_is_never_completion(self):
        with tempfile.TemporaryDirectory() as root:
            run=Model(root,fail='stop')
            with self.assertRaises(RuntimeError):run.execute()
            self.assertTrue(run.report['status'].startswith('failed'))

    def test_qualification_requires_hash_exact_scope_optics_and_budget(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);report=root/'run.json';review=root/'review.json'
            run={'scope':'p85-stock-only','status':'awaiting_optical_review','module_sha256':r.s.MODULE_SHA,
                 'video_profile':{'codec':'h264','audio_streams':0},
                 'source_worktree_clean_for_runner':True,'source_blob_ids':dict.fromkeys(r.SOURCE_FILES,'a'*40),
                 **dict.fromkeys(('camera_stopped_verified','original_settings_dbv_logger_restored','watchdog_disarmed','mutex_released'),True),
                 'stages':[{'label':label,'p85':{'data':[21,0,0]},'c1':{'data':[0,0,96]},
                            'observed_sensor_frames':135,'qualified':True,'elapsed_seconds':12} for label in ('baseline','sham15','return15')]}
            report.write_text(json.dumps(run))
            witness={'schema':'p85-stock-review-v1','stock_optics_restored':True,'sham_optics_unchanged':True,
                     'lead_approved':True,'central_stable_encoded_frames':60,'timestamp_margins_reviewed':True,
                     'run_report':str(report),'run_sha256':hashlib.sha256(report.read_bytes()).hexdigest()}
            review.write_text(json.dumps(witness));self.assertEqual(r.qualification(review)['max_stage_seconds'],12)
            for key,value in (('stock_optics_restored',False),('central_stable_encoded_frames',59),
                              ('run_sha256','changed'),('timestamp_margins_reviewed',False)):
                review.write_text(json.dumps({**witness,key:value}))
                with self.assertRaises(ValueError):r.qualification(review)
            review.write_text(json.dumps(witness));report.write_text(report.read_text()+' ')
            with self.assertRaises(ValueError):r.qualification(review)

    def test_short_watchdog_exact60_no_refresh_or_dsi(self):
        script=r.short_watchdog('/data/local/tmp/p85_mock_test','parent_token','00000000-0000-0000-0000-000000000001')
        self.assertIn('sleep 60;',script);self.assertNotIn('tx_cmd',script)
        self.assertIn('/proc/sys/kernel/random/boot_id',script);self.assertIn('/owner',script)
        self.assertEqual(subprocess.run(['sh','-n'],input=script,text=True,capture_output=True).returncode,0)
        with self.assertRaises(ValueError):r.short_watchdog('/tmp/x; reboot','parent_token','bad')

    def test_offline_cli_creates_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            output=Path(root)/'not-created'
            result=subprocess.run(['python3',str(Path(r.__file__)),'5','1','--stock-only',
                '--experiment-id','p85_offline_fixture','--output',str(output)],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue(json.loads(result.stdout)['offline_only']);self.assertFalse(output.exists())

    def test_candidate_deadline_before_command(self):
        with tempfile.TemporaryDirectory() as root:
            run=r.Trial(None,5,1,'p85_mock_test',root,root,monotonic=lambda:50)
            run.candidate_started=0
            with patch.object(r.s.Sweep,'shell') as shell:
                with self.assertRaises(ValueError):run.shell('must not execute')
                shell.assert_not_called()
            with self.assertRaises(ValueError):run.cam('must not execute','test')


    def test_child_registry_and_camera_xml_exact_cleanup(self):
        with tempfile.TemporaryDirectory() as root:
            run=r.Trial(None,5,1,'p85_mock_test',root,root)
            for kind in ('c1','p85','writer'):
                nonce=run.child_nonce(kind)
                self.assertEqual(run.child_records[-1]['work'],'/data/local/tmp/pwm-c1-'+nonce)
                self.assertEqual(run.child_records[-1]['group'],'pwm_c1_'+nonce)
            with patch.object(r.s.Sweep,'restore') as restore, patch.object(run,'shell') as shell:
                run.restore();restore.assert_called_once()
                self.assertEqual(shell.call_count,1)
                cleanup=shell.call_args.args[0]
                for name in r.p85.WRITER_GATE_FILES:
                    self.assertIn('test ! -e '+run.child_records[-1]['work']+'/'+name,cleanup)
                run.child_records[-1]['group']='foreign_group'
                with self.assertRaises(ValueError):run.restore()
                self.assertEqual(restore.call_count,1)
            run.cam_xml_owned=True
            with patch.object(run,'cam') as cam:
                run.cleanup_camera_xml()
                self.assertEqual(cam.call_args.args[0],'rm -f /data/local/tmp/p85_mock_test-camera.xml; test ! -e /data/local/tmp/p85_mock_test-camera.xml')
                self.assertFalse(run.cam_xml_owned)
                run.cam_xml_owned=True;run.recording=True
                with self.assertRaises(ValueError):run.cleanup_camera_xml()
                self.assertEqual(cam.call_count,1)

    def test_video_profile(self):
        video={'codec_type':'video','codec_name':'h264','width':1280,'height':720,'avg_frame_rate':'30/1'}
        probe={'streams':[video],'format':{'duration':'45.0'}}
        self.assertEqual(r.validate_video_probe(probe,13.5)['audio_streams'],0)
        for bad in ({**probe,'streams':[video,{'codec_type':'audio'}]},
                    {**probe,'streams':[{**video,'width':1920}]},
                    {**probe,'streams':[{**video,'codec_name':'hevc'}]},
                    {**probe,'format':{'duration':'2'}},
                    {**probe,'streams':[{**video,'avg_frame_rate':'0/0'}]}):
            with self.assertRaises(ValueError):r.validate_video_probe(bad,13.5)


    def test_reboot_remnant_removes_only_fixed_owned_gate_files(self):
        with tempfile.TemporaryDirectory() as root:
            run=r.Trial(None,5,1,'p85_remnant_test',root,root)
            run.child_nonce('writer');child=run.child_records[0]
            work=Path(root)/'fake-child';work.mkdir()
            for name in r.p85.WRITER_GATE_FILES:(work/name).write_text('retained evidence')
            (work/'unrelated').write_text('preserve')
            run.ops['verify']='true'
            def shell(command,**kwargs):
                command=command.replace(child['work'],str(work))
                subprocess.run(['sh','-c',command],capture_output=True,check=True,timeout=5)
                return ''
            with patch.object(run,'shell',side_effect=shell),patch.object(r.s.Sweep,'restore') as parent:
                run.restore();parent.assert_called_once()
            self.assertEqual([x.name for x in work.iterdir()],['unrelated'])


    def test_source_provenance_ignores_unrelated_files_but_blocks_changed_code(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);paths=('runner.py','helper.py')
            for name in paths:(root/name).write_text('pass\n')
            def git(*args):
                return subprocess.run(['git','-C',str(root),'-c','user.name=Offline Test',
                    '-c','user.email=offline@example.invalid',*args],capture_output=True,text=True,check=True,timeout=10)
            git('init','-q');git('add','--',*paths);git('commit','-qm','fixture')
            first=r.source_provenance(root,paths,require_clean=True)
            (root/'unrelated-charge-artifact.txt').write_text('ignore')
            self.assertEqual(r.source_provenance(root,paths,require_clean=True),first)
            (root/'README.md').write_text('docs only');git('add','README.md');git('commit','-qm','docs')
            second=r.source_provenance(root,paths,require_clean=True)
            self.assertNotEqual(first['source_commit'],second['source_commit'])
            self.assertEqual(first['source_blob_ids'],second['source_blob_ids'])
            (root/'runner.py').write_text('changed = True\n')
            self.assertFalse(r.source_provenance(root,paths)['source_worktree_clean_for_runner'])
            with self.assertRaises(ValueError):r.source_provenance(root,paths,require_clean=True)


if __name__=='__main__':unittest.main()
