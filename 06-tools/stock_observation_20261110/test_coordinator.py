"""Offline synthetic fault tests; no device/transport admission claims."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import xml.etree.ElementTree as ET
from coordinator import Coordinator, DURATION, RESTART
from protocol_v2 import admission, timeline, ROI, WINDOWS


class Clock:
    def __init__(self):self.now=100.0
    def __call__(self):return self.now
    def sleep(self,n):self.now+=n


class CaptureError(ValueError):pass


def fresh():
    clock=Clock()
    c=Coordinator(transport=SimpleNamespace(),target='1',camera='2',serials=(b't',b'c'),
        parser=SimpleNamespace(CaptureMetadataError=CaptureError),readonly=SimpleNamespace(),
        lock_commands=lambda token:dict(verify='verify',acquire='acquire',release='release'),
        new_camera_video=lambda a,b:'/sdcard/DCIM/OpenCamera/new.mp4',native_state=lambda log:{},
        owned_directory=SimpleNamespace(path=Path('/private')),retained_sink=SimpleNamespace(),
        source={'commit':'a'*40,'closure_sha256':'b'*64},token='obs_20261110',
        clock=clock,sleep=clock.sleep,byte_cap=1000000)
    c.persist=Mock();c.shell=Mock(return_value='');c.unchanged=Mock()
    c.boots={'target':'t','camera':'c'};c.read_boots=Mock(return_value=c.boots)
    c.before={'native_dbv':6438,'settings':{'screen_brightness':'98'}}
    c.report['camera_limit_readback']={'duration_seconds':10,'restart_count':0,'filesize_restart':False}
    return c,clock


def receipt(c,clock):
    return dict(schema='stock-observation-prestart-v2',boots=c.boots,source=c.source,
        observed_monotonic=clock(),native_mode=dict(hz=120,group=3,evidence_sha256='c'*64,
        parser_source_sha256='d'*64),scene=dict(component='com.android.settings/.Settings$DisplaySettingsActivity',
        evidence_sha256='e'*64),geometry=dict(roi=ROI,image_sha256='f'*64,review_source='fresh_visual_review'))


START=ET.fromstring('<hierarchy><node content-desc="Start recording video" enabled="true" bounds="[0,0][10,10]" /></hierarchy>')


class Tests(unittest.TestCase):
    def prepare_recording(self,c,clock,*,stop=10,early_delay=.05,network=False):
        c.ui=Mock(return_value=START);c.click=Mock()
        def metadata(*,recording,previous=None,timeout=1):
            clock.sleep(early_delay)
            if network and c.start is not None:raise TimeoutError('network')
            if not recording:return {'recording_verified':False}
            if clock()-c.start>=stop:raise CaptureError('ended')
            return {'frame_count':len(c.persist.call_args_list)+1,'progress_verified':previous is not None}
        c.metadata=Mock(side_effect=metadata)

    def test_native10s_single_start_no_stop_tap(self):
        c,t=fresh();self.prepare_recording(c,t)
        c.record()
        self.assertTrue(c.stopped);self.assertEqual(c.click.call_count,1)
        self.assertTrue(c.report['early_controls_bound'])
        self.assertLess(c.report['stop_observed_elapsed'],15)
        self.assertEqual(c.unchanged.call_count,2)

    def test_never_stops_retains_uncertainty(self):
        c,t=fresh();self.prepare_recording(c,t,stop=100)
        with self.assertRaises(ValueError):c.record()
        self.assertFalse(c.stopped);self.assertEqual(c.click.call_count,1)
        with self.assertRaises(ValueError):c.restore()

    def test_uncertain_start_never_retried(self):
        c,t=fresh();self.prepare_recording(c,t)
        c.click.side_effect=TimeoutError('uncertain')
        with self.assertRaises(TimeoutError):c.record()
        self.assertIsNotNone(c.start);self.assertEqual(c.click.call_count,1)
        self.assertFalse(c.stopped)

    def test_network_no_stop_fallback(self):
        c,t=fresh();self.prepare_recording(c,t,network=True)
        with self.assertRaises(TimeoutError):c.record()
        self.assertEqual(c.click.call_count,1);self.assertFalse(c.stopped)

    def test_slow_startup_does_not_shift_windows(self):
        c,t=fresh();self.prepare_recording(c,t,early_delay=.7)
        with self.assertRaisesRegex(ValueError,'frame30'):c.record()
        self.assertTrue(c.stopped);self.assertFalse(c.report['early_controls_bound'])
        self.assertEqual(WINDOWS,((30,90),(90,150),(150,210),(210,270)))

    def test_already_recording_rejected(self):
        c,t=fresh();self.prepare_recording(c,t)
        c.ui.return_value=ET.fromstring('<hierarchy><node content-desc="Stop recording video" /></hierarchy>')
        with self.assertRaises(ValueError):c.record()
        self.assertEqual(c.click.call_count,0);self.assertIsNone(c.start)

    def test_preview_before_first_recording_is_not_stop(self):
        c,t=fresh();self.prepare_recording(c,t)
        def metadata(*,recording,**kw):
            t.sleep(.05)
            if recording:raise CaptureError('still preview')
            return {}
        c.metadata.side_effect=metadata
        with self.assertRaisesRegex(ValueError,'stop unverified'):c.record()
        self.assertFalse(c.stopped);self.assertTrue(c.report['startup_preview_pending'])
        self.assertEqual(c.click.call_count,1)
        with self.assertRaisesRegex(ValueError,'pending start'):c.observe_late_stop()

    def test_delayed_record_start_never_restarts(self):
        c,t=fresh();self.prepare_recording(c,t)
        def metadata(*,recording,previous=None,**kw):
            t.sleep(.05)
            if not recording:return {}
            elapsed=t()-c.start
            if elapsed<2 or elapsed>=12:raise CaptureError('preview')
            return {'progress_verified':previous is not None}
        c.metadata.side_effect=metadata
        with self.assertRaisesRegex(ValueError,'frame30'):c.record()
        self.assertTrue(c.stopped);self.assertEqual(c.click.call_count,1)

    def test_second_record_attempt_rejected(self):
        c,t=fresh();self.prepare_recording(c,t);c.record()
        with self.assertRaisesRegex(ValueError,'already spent'):c.record()
        self.assertEqual(c.click.call_count,1)

    def test_uncertain_start_direct_retry_rejected(self):
        c,t=fresh();self.prepare_recording(c,t);c.click.side_effect=TimeoutError()
        with self.assertRaises(TimeoutError):c.record()
        with self.assertRaisesRegex(ValueError,'already spent'):c.record()
        self.assertEqual(c.click.call_count,1)

    def test_preference_restore_failure_retains_original(self):
        c,t=fresh();c.preferences=[(DURATION,'Unlimited')]
        c.open_preference=Mock(side_effect=TimeoutError())
        with self.assertRaises(TimeoutError):c.finish_preferences()
        self.assertEqual(c.preferences,[(DURATION,'Unlimited')])
        with self.assertRaises(ValueError):c.release()

    def test_uncertain_switch_restore_retains_original(self):
        c,t=fresh();c.switch_original=True;c.filesize_switch=Mock(side_effect=TimeoutError())
        with self.assertRaises(TimeoutError):c.finish_preferences()
        self.assertIs(c.switch_original,True)

    def test_stop_read_finishes_after_deadline_rejected(self):
        c,t=fresh();self.prepare_recording(c,t,stop=14.5,early_delay=.1)
        original=c.metadata.side_effect
        def slow(**kwargs):
            result=original(**kwargs)
            if c.start is not None and not kwargs['recording']:t.sleep(2)
            return result
        c.metadata.side_effect=slow
        with self.assertRaisesRegex(ValueError,'late stop'):c.record()
        self.assertTrue(c.stopped)
        self.assertGreater(c.report['stop_observed_elapsed'],15)

    def test_no_target_mutation_before_stop(self):
        c,t=fresh();c.start=t()
        with self.assertRaises(ValueError):c.native_dbv(6438)
        c.shell.assert_not_called()

    def test_restore_fresh_original_only(self):
        c,t=fresh();c.changed=True;c.stopped=True;c.start=t()
        c.target_state=Mock(return_value=copy.deepcopy(c.before));c.native_dbv=Mock()
        c.restore();c.native_dbv.assert_called_once_with(6438)
        c.unchanged.assert_called_with(6438)

    def test_no_write_when_unchanged(self):
        c,t=fresh();c.native_dbv=Mock();c.restore();c.native_dbv.assert_not_called()

    def test_changed_framework_blocks_restore(self):
        c,t=fresh();c.changed=True;c.target_state=Mock(return_value={'settings':{}})
        c.native_dbv=Mock()
        with self.assertRaises(ValueError):c.restore()
        c.native_dbv.assert_not_called()

    def test_late_stop_keeps_failed_cap(self):
        c,t=fresh();c.start=t()-18;c.metadata=Mock()
        c.report['advancing_recording_observed']=True
        c.report['status']='inconclusive';c.observe_late_stop()
        self.assertEqual(c.report['status'],'inconclusive_late_stop')
        self.assertTrue(c.stopped);c.shell.assert_not_called()
        with self.assertRaises(ValueError):c.observe_late_stop()

    def test_preference_intent_saved_before_uncertain_click(self):
        c,t=fresh()
        tree=ET.fromstring('<hierarchy><node text="10 seconds" /></hierarchy>')
        c.open_preference=Mock(return_value=(tree,'Unlimited'));c.click=Mock(side_effect=TimeoutError())
        with self.assertRaises(TimeoutError):c.preference(DURATION,'10 seconds')
        self.assertEqual(c.preferences,[(DURATION,'Unlimited')])
        c.persist.assert_called_once()

    def test_boot_change_blocks_preferences(self):
        c,t=fresh();c.read_boots.return_value={};c.metadata=Mock()
        with self.assertRaises(ValueError):c.enter_video_settings()
        c.metadata.assert_not_called()

    def test_admission_missing_stale_wrong_boot(self):
        c,t=fresh();r=receipt(c,t)
        admission(r,boots=c.boots,source=c.source,now=t())
        for change in ({'boots':{}},{'observed_monotonic':0},{'native_mode':{}},{'geometry':True}):
            x=copy.deepcopy(r);x.update(change)
            with self.assertRaises(ValueError):admission(x,boots=c.boots,source=c.source,now=t())
        with self.assertRaises(ValueError):admission({},boots=c.boots,source=c.source,now=t())

    def test_v2_fixed_timeline(self):
        pts=[i/30 for i in range(300)]
        self.assertEqual(timeline(pts,10,early_controls_bound=True),WINDOWS)
        for p,d,e in ((pts,15.01,True),(pts[:269],10,True),(pts,10,False),([0]*300,10,True)):
            with self.assertRaises(ValueError):timeline(p,d,early_controls_bound=e)


if __name__=='__main__':unittest.main()
