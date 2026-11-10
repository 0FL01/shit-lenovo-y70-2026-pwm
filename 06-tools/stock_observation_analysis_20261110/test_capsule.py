"""Synthetic private capsule tests. No real video or actual camera evidence."""
import copy
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from test_analyze import a,records,probe,profiles


class CapsuleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.d=Path(self.tmp.name);self.d.chmod(0o700)
        self.r=records();self.r['outcome']['recording_observation_complete']=True
        source_map={'06-tools/synthetic.py':'a'*64}
        source={'commit':'b'*40,'closure_sha256':a.digest(json.dumps(source_map,sort_keys=True,separators=(',',':')).encode())}
        self.source=source
        self.r['before']['source']=source;self.r['outcome']['source']=source
        self.r['source-closure']={'source':source,'sha256':source_map}
        for i,item in enumerate(self.r['recording-snapshots']):
            count=10+i*10;t=1000000000+round(i*10*1e9/30)
            request=dict(a.optical.PROFILE,frame_duration_ns=33333333,request_id=1)
            result=dict(request,frame_count=count,timestamp_ns=t,rolling_shutter_skew_ns=15047630)
            item['snapshot']=dict(request=request,result=result,recording_verified=True,
                session_token='synthetic',frame_count=count,timestamp_ns=t,rolling_shutter_skew_ns=15047630,
                progress_verified=i>0,encoder_stream_id=1,
                streams=[dict(id=1,width=1280,height=720,consumer_kind='GraphicBufferSource',state=4,
                              requested=True,frames_produced=count,last_timestamp_ns=t)])
        self.r['outcome']['first_advancing_recording_elapsed']=.6
        self.video=self.d/'capture.mp4';self.video.write_bytes(b'SYNTHETIC NOT AN MP4');self.video.chmod(0o600)
        st=self.video.stat()
        media={'bytes':st.st_size,'sha256':a.digest(self.video.read_bytes()),
               'created_identity':[st.st_dev,st.st_ino,st.st_uid,st.st_mode],
               'sink_facts':dict(created=True,confirmed_written=st.st_size,write_outcome_uncertain=False,
                                 close_outcome='closed',removed_by_sink=False)}
        self.r['outcome']['media']={k:media[k] for k in ('bytes','sha256')}
        self.r['outcome']['media']['created_inode_verified']=True
        self.cap=dict(schema='stock-observation-analysis-evidence-v1',source=source,
            final_boots={'target':self.r['before']['boot_id'],'camera':self.r['before']['camera_boot_id']},
            media=media,geometry_review_status='actual_media_review_required')
        self.rewrite()

    def tearDown(self):self.tmp.cleanup()
    def save(self,name,value):
        p=self.d/name;p.write_text(json.dumps(value));p.chmod(0o600);return p
    def rewrite(self):
        receipts={}
        for i,(key,value) in enumerate(self.r.items()):
            p=self.save(f'{i:04d}-{key}.json',value)
            receipts[key]={'file':p.name,'sha256':a.digest(p.read_bytes()),'bytes':p.stat().st_size}
        self.cap['records']=receipts;self.cap['records_sha256']={k:v['sha256'] for k,v in receipts.items()}
        self.cap['control_binding']=dict(first_window_start_index=30,last_window_end_exclusive=270,
            method='camera_snapshots_progress_with_pts_validation_pending',
            evidence_sha256=receipts['recording-snapshots']['sha256'],per_frame_controls_proven=False,
            sensor_to_file_calibrated=False)
        self.cp=self.save('0009-analysis-evidence.json',self.cap)
        self.review=self.save('review.json',dict(schema='stock-observation-v2-roi-review',
            media_sha256=self.cap['media']['sha256'],records_sha256=self.cap['records_sha256'],
            reviewed_frames={w['stage']:w['review_frames'] for w in a.fixed_windows()},
            rois_xywh={k:list(v) for k,v in a.ROI.items()},whole_screen_flat=False,
            native_y_noautorotate_inspected=True,roi_background_content_verified=True,
            fixed_geometry_verified=True,reviewer='synthetic-only'))
    def run_diagnostic(self):
        with patch.object(a,'probe_video',return_value=probe()),patch.object(a,'extract_profiles',return_value=profiles()):
            return a.analyze_actual(self.cp,expected_source=self.source,review_path=self.review,
                video=self.video,no_concurrent_writers=True)
    def test_working_conditional_route_and_outputs(self):
        summary,details,arrays=self.run_diagnostic()
        self.assertEqual(summary['status'],'conditional_diagnostic_only')
        self.assertTrue(summary['all_roi_nominal_5pct_met']);self.assertFalse(summary['acquisition_admitted'])
        a.write_outputs(summary,details,arrays,private_json=self.d/'details.json',
                        private_npz=self.d/'profiles.npz',summary_json=self.d/'summary.json')
        self.assertEqual(stat.S_IMODE((self.d/'details.json').stat().st_mode),0o600)
        self.assertNotIn('session_token',(self.d/'summary.json').read_text())
        self.assertNotIn('source',(self.d/'summary.json').read_text())
    def test_aged_atime_read_and_actual_route(self):
        # A read on relatime mounts can advance atime without changing bytes.
        # Age every file, including capture and capsule, while preserving mtime.
        for path in self.d.iterdir():
            st=path.stat()
            os.utime(path,ns=(1,st.st_mtime_ns))
        before=self.video.stat()
        summary,_,_=self.run_diagnostic()
        after=self.video.stat()
        self.assertEqual(a.stable_identity(before),a.stable_identity(after))
        self.assertEqual(summary['status'],'conditional_diagnostic_only')
        # Explicitly prove the comparison ignores atime even on noatime mounts.
        from types import SimpleNamespace
        attrs={key:getattr(before,key) for key in ('st_dev','st_ino','st_mode','st_uid',
            'st_nlink','st_size','st_mtime_ns','st_ctime_ns')}
        self.assertEqual(a.stable_identity(SimpleNamespace(**attrs,st_atime_ns=1)),
                         a.stable_identity(SimpleNamespace(**attrs,st_atime_ns=999)))
    def test_identity_still_detects_mutations(self):
        from types import SimpleNamespace
        st=self.video.stat()
        attrs={key:getattr(st,key) for key in ('st_dev','st_ino','st_mode','st_uid',
            'st_nlink','st_size','st_mtime_ns','st_ctime_ns')}
        for key in attrs:
            changed=dict(attrs);changed[key]+=1
            self.assertNotEqual(a.stable_identity(SimpleNamespace(**attrs)),
                                a.stable_identity(SimpleNamespace(**changed)))
    def test_late_pair_remains_inconclusive(self):
        self.r['recording-snapshots'][0]['elapsed']=2
        self.r['recording-snapshots'][1]['elapsed']=2.4
        self.r['outcome'].update(first_advancing_recording_elapsed=2.4,early_controls_bound=False,
            capture_validity_failure='early_controls_unbound',control_coverage_status='unknown_first_window',
            status='inconclusive',error_type='ValueError',failure_reason='frame30 controls unbound')
        self.rewrite();summary,_,_=self.run_diagnostic()
        self.assertEqual(summary['control_limits']['first_window_control_coverage'],'unknown')
        self.assertFalse(summary['qualification_eligible'])
    def test_capsule_required(self):
        self.cp.unlink()
        with self.assertRaises(FileNotFoundError):self.run_diagnostic()
    def test_record_tampering_rejected(self):
        self.save(self.cap['records']['before']['file'],{})
        with self.assertRaises(ValueError):self.run_diagnostic()
    def test_source_and_boot_rejected(self):
        self.source=dict(self.source,commit='f'*40)
        with self.assertRaises(ValueError):self.run_diagnostic()
    def test_final_boot_drift(self):
        self.cap['final_boots']['target']='other'
        self.rewrite()
        with self.assertRaises(ValueError):self.run_diagnostic()
    def test_source_closure_tampering(self):
        self.r['source-closure']['sha256']['06-tools/synthetic.py']='f'*64
        self.rewrite()
        with self.assertRaises(ValueError):self.run_diagnostic()
    def test_bad_controls_rejected(self):
        self.r['recording-snapshots'][1]['snapshot']['result']['iso']=100
        self.rewrite()
        with self.assertRaises(ValueError):self.run_diagnostic()
    def test_unrelated_failure_rejected(self):
        self.r['outcome'].update(status='inconclusive',error_type='ValueError')
        self.rewrite()
        with self.assertRaises(ValueError):self.run_diagnostic()
    def test_inode_and_custody_rejected(self):
        self.cap['media']['created_identity'][1]+=1
        self.rewrite()
        with self.assertRaises(ValueError):self.run_diagnostic()
    def test_sink_incomplete(self):
        self.cap['media']['sink_facts']['close_outcome']='unknown'
        self.rewrite()
        with self.assertRaises(ValueError):self.run_diagnostic()
    def test_media_tampering(self):
        self.video.write_bytes(b'altered')
        with self.assertRaises(ValueError):self.run_diagnostic()
    def test_private_mode(self):
        self.video.chmod(0o644)
        with self.assertRaises(ValueError):self.run_diagnostic()
    def test_missing_roi_review(self):
        self.review.unlink()
        with self.assertRaises(FileNotFoundError):self.run_diagnostic()
    def test_no_overwrite(self):
        s,d,ar=self.run_diagnostic()
        with self.assertRaises(ValueError):a.write_outputs(s,d,ar,private_json=self.video,private_npz=self.d/'p.npz',summary_json=self.d/'s.json')

if __name__=='__main__':unittest.main()
