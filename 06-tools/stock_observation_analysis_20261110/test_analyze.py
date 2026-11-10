import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np

spec=importlib.util.spec_from_file_location('observation_analysis',Path(__file__).with_name('analyze.py'))
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)


def probe(n=300):
    return {'streams':[dict(codec_type='video',codec_name='h264',width=1280,height=720,
             pix_fmt='yuv420p',color_range='tv',nb_frames=str(n),duration='10',avg_frame_rate='30/1')],
            'format':{'duration':'10'},
            'frames':[{'best_effort_timestamp_time':str(i/30)} for i in range(n)]}


def profiles(factors=(1,1,1,1)):
    y=np.arange(330)
    return {r:np.stack([np.tile(100+v*np.cos(2*np.pi*a.Q*y),(60,1)) for v in factors]) for r in a.ROI}


def records():
    source={'commit':'a'*40,'closure_sha256':'b'*64}
    before={'boot_id':'12345678-1234-1234-1234-123456789abc','camera_boot_id':'22345678-1234-1234-1234-123456789abc','source':source}
    snaps=[{'elapsed':t,'snapshot':{'progress_verified':True}} for t in (.3,.6,9.5)]
    outcome=dict(schema=a.protocol.SCHEMA,source=source,status='awaiting_offline_media_validation',
        windows=a.WINDOWS,candidate_attempts=0,custom_dsi_writes=0,pwm_hz=None,
        start_attempt_monotonic=100,stop_observed_elapsed=10.2,early_controls_bound=True,
        camera_stopped_verified=True,advancing_recording_observed=True,originals_restored=True,
        mutex_released=True,camera_limit_readback={'duration_seconds':10,'restart_count':0,'filesize_restart':False},
        media={'bytes':123,'sha256':'c'*64,'created_inode_verified':True})
    return {'before':before,'recording-snapshots':snaps,'outcome':outcome}


def raw(r):return {k:json.dumps(v).encode() for k,v in r.items()}


class Tests(unittest.TestCase):
    def test_exact_windows(self):
        self.assertEqual(a.WINDOWS,((30,90),(90,150),(150,210),(210,270)))
        self.assertEqual(a.fixed_windows()[-1]['review_frames'],[210,240,269])
    def test_native_probe(self):
        pts,stream,windows=a.validate_probe(probe())
        self.assertEqual(len(pts),300);self.assertEqual(len(windows),4)
    def test_bad_probe(self):
        for mutate in [lambda p:p['streams'][0].update(nb_frames='301'),
                       lambda p:p['streams'][0].update(duration='15.01'),
                       lambda p:p['format'].update(duration='nan'),
                       lambda p:p['streams'][0].update(avg_frame_rate='60/1'),
                       lambda p:p['streams'][0].update(color_range='pc'),
                       lambda p:p['frames'][50].update(best_effort_timestamp_time='1.5')]:
            p=probe();mutate(p)
            with self.subTest(p=p['streams'][0]),self.assertRaises(ValueError):a.validate_probe(p)
    def test_frozen_duration_not_native_cap_proof(self):
        p=probe(330)
        p['streams'][0]['duration']='11';p['format']['duration']='11'
        _,stream,_=a.validate_probe(p)
        self.assertEqual(stream['delta_from_native10s_seconds'],1)
        self.assertFalse(stream['native10s_cap_proven_by_duration'])
    def test_short_video(self):
        with self.assertRaises(ValueError):a.validate_probe(probe(269))
    def test_reuse_metric(self):
        p=profiles((1,1.02,.98,1.03));result,detail=a.measure_profiles(p)
        for r in a.ROI:
            self.assertEqual(detail[r][0],a.optical.fixed_metrics(p[r][0],[a.Q],degree=2))
        np.testing.assert_allclose(result['change_windows2_to4_vs_window1_pct']['main'],[2,-2,3],atol=.02)
        self.assertTrue(result['all_roi_nominal_5pct_met'])
        self.assertFalse(result['windows_independent']);self.assertIsNone(result['physical_pwm_hz'])
    def test_one_roi_failure_not_averaged(self):
        p=profiles();p['right']=profiles((1,1.06,1,1))['right']
        result,_=a.measure_profiles(p)
        self.assertFalse(result['all_roi_nominal_5pct_met'])
        self.assertFalse(result['candidate_admission']);self.assertFalse(result['qualification_eligible'])
    def test_bad_profiles(self):
        for p in ({},dict(profiles(),left=np.zeros((3,60,330))),profiles((0,0,0,0))):
            with self.assertRaises(ValueError):a.measure_profiles(p)
    def test_decode_reused(self):
        with patch.object(a.optical,'decode_y',return_value=np.full((240,330,80),100,dtype=np.uint8)) as decoder:
            p=a.extract_profiles(Path('/synthetic/never-opened'))
            self.assertEqual(p['main'].shape,(4,60,330))
            self.assertEqual(decoder.call_args.args[1],list(range(30,270)))
    def test_synthetic_records_never_qualify(self):
        result=a.inspect_records(raw(records()))
        self.assertEqual(result['status'],'inconclusive');self.assertIsNone(result['actual_measurements'])
        with self.assertRaises(ValueError):a.analyze_actual(records=records(),qualified=True)
    def test_missing_boot(self):
        r=records();del r['before']['boot_id']
        with self.assertRaises(ValueError):a.inspect_records(raw(r))
    def test_record_rejections(self):
        for field,value in [('schema','stock-observation-v1'),('stop_observed_elapsed',15.01),
                            ('candidate_attempts',1),('cleanup_pending',True),('early_controls_bound',False),
                            ('status','inconclusive'),('transfer_error_type','Failure')]:
            r=records();r['outcome'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):a.inspect_records(raw(r))
    def test_late_controls(self):
        r=records();r['recording-snapshots'][1]['elapsed']=1.1
        with self.assertRaises(ValueError):a.inspect_records(raw(r))
    def test_roi_review(self):
        review=dict(schema='stock-observation-v2-roi-review',media_sha256='a'*64,records_sha256={'outcome':'b'*64},
            reviewed_frames={w['stage']:w['review_frames'] for w in a.fixed_windows()},
            rois_xywh={k:list(v) for k,v in a.ROI.items()},whole_screen_flat=False,
            native_y_noautorotate_inspected=True,roi_background_content_verified=True,fixed_geometry_verified=True,reviewer='synthetic')
        self.assertEqual(a.validate_roi_review(review,media_sha256='a'*64,records_sha256={'outcome':'b'*64}),a.ROI)
        review['rois_xywh']['main'][0]+=1
        with self.assertRaises(ValueError):a.validate_roi_review(review,media_sha256='a'*64,records_sha256={'outcome':'b'*64})

if __name__=='__main__':unittest.main()
