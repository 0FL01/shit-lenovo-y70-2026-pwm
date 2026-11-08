"""Concrete camera startup read-only settling; synthetic metadata, no devices."""
from pathlib import Path
import tempfile
import signal
import socket
import threading
import time
import unittest
from unittest.mock import patch

import camera_capture_metadata as c
import run_p85_guarded_trial as r
from test_camera_capture_metadata import sample


def dump(index=0, *, mismatch=False, session='synthetic-session', exposure=100000):
    raw=sample(frame=100+index,timestamp=10000000000+index*33350000,
               encoder_frames=90+index,session=session,exposure=exposure)
    if mismatch:
        before,after=raw.split('    Logical request settings:\n',1)
        after=after.replace('android.request.id (00001): int64[1]\n          [3 ]',
                            'android.request.id (00001): int64[1]\n          [4 ]',1)
        raw=before+'    Logical request settings:\n'+after
    return raw


class StartupTests(unittest.TestCase):
    def fixture(self,root,dumps,*,cost=.2,error=None):
        clock=[0.0]
        class ADB:
            def __init__(self):self.calls=[]
            def shell(self,target,command,timeout):
                if target!=1 or command!='dumpsys media.camera':raise AssertionError('Not a camera read')
                self.calls.append(timeout);clock[0]+=cost
                if error:raise error
                return 0,dumps[len(self.calls)-1].encode(),b''
        adb=ADB()
        run=r.Trial(adb,6,1,'p85_camera_settle_test',root,root,
                    monotonic=lambda:clock[0],sleep=lambda n:clock.__setitem__(0,clock[0]+n))
        run.recording=True
        return run,adb,clock

    def test_typed_mismatch_remains_rejected_and_other_faults_are_fatal(self):
        with self.assertRaises(c.RequestResultNotSettled) as caught:
            c.validate_capture(dump(mismatch=True),require_recording=True)
        self.assertIsInstance(caught.exception,c.CaptureMetadataError)
        self.assertNotEqual(caught.exception.continuity_snapshot['request']['request_id'],
                            caught.exception.continuity_snapshot['result']['request_id'])
        previous=c.validate_capture(dump(),require_recording=True)
        for raw in (dump(1,mismatch=True,exposure=200000),dump(1,mismatch=True,session='changed'),
                    dump(mismatch=True),dump(1,mismatch=True).replace('1280 x 720','1920 x 1080'),
                    dump(1,mismatch=True).replace('VIDEO_RECORD','PREVIEW',1)):
            with self.subTest(raw=raw[-25:]):
                try:c.validate_capture(raw,previous,require_recording=True)
                except c.RequestResultNotSettled:self.fail('Other invalid condition classified retryable')
                except c.CaptureMetadataError:pass
                else:self.fail('Invalid snapshot accepted')

    def test_real_metadata_mismatch_then_two_valid_and_private_raw(self):
        with tempfile.TemporaryDirectory() as root:
            run,adb,clock=self.fixture(root,[dump(mismatch=True),dump(1),dump(2)])
            with patch.object(run,'camera_tap') as tap,patch.object(run,'shell') as target:
                pair=run.settle_recording();tap.assert_not_called();target.assert_not_called()
            self.assertEqual(len(adb.calls),3)
            self.assertEqual([x['frame_count'] for x in pair],[101,102])
            self.assertTrue(all(x['request']['request_id']==x['result']['request_id'] for x in pair))
            self.assertTrue(all(x['progress_verified'] for x in pair))
            self.assertTrue(all(x['host_call_elapsed_seconds']>0 for x in pair))
            self.assertEqual(run.report['recording_preflight'],pair)
            self.assertEqual(run.report['recording_settle']['status'],'qualified')
            raw=list(Path(root).glob('*recording-settle-*.stdout'))
            self.assertEqual(len(raw),3)
            self.assertTrue(all(x.stat().st_mode&0o777==0o600 for x in raw))
            self.assertLess(clock[0],8)

    def test_consecutive_pair_restarts_after_known_transient(self):
        with tempfile.TemporaryDirectory() as root:
            run,adb,_=self.fixture(root,[dump(),dump(1,mismatch=True),dump(2),dump(3)])
            self.assertEqual([x['frame_count'] for x in run.settle_recording()],[102,103])
            self.assertEqual(len(adb.calls),4)

    def test_perpetual_mismatch_is_five_reads_no_preflight(self):
        with tempfile.TemporaryDirectory() as root:
            run,adb,_=self.fixture(root,[dump(i,mismatch=True) for i in range(5)])
            with self.assertRaisesRegex(ValueError,'attempt cap'):run.settle_recording()
            self.assertEqual(len(adb.calls),5)
            self.assertNotIn('recording_preflight',run.report)
            self.assertEqual(run.report['recording_settle']['status'],'failed')
            with self.assertRaises(ValueError):run.settle_recording()
            self.assertEqual(len(adb.calls),5)

    def test_deadline_capped_transport_and_no_acceptance_after_deadline(self):
        for mismatch in (False,True):
            with self.subTest(mismatch=mismatch),tempfile.TemporaryDirectory() as root:
                run,adb,_=self.fixture(root,[dump(mismatch=mismatch)],cost=9)
                with self.assertRaisesRegex(ValueError,'deadline'):run.settle_recording()
                self.assertEqual(adb.calls,[6.0]);self.assertNotIn('recording_preflight',run.report)

    def test_wrong_profile_session_geometry_and_transport_do_not_retry(self):
        variants=[dump(1,mismatch=True,session='changed'),dump(1,mismatch=True,exposure=200000),
                  dump(1,mismatch=True).replace('1280 x 720','1920 x 1080'),
                  dump(1,mismatch=True).replace('[15047630 ]','[15047631 ]')]
        for bad in variants:
            with self.subTest(bad=bad[-20:]),tempfile.TemporaryDirectory() as root:
                run,adb,_=self.fixture(root,[dump(),bad,dump(2),dump(3)])
                with self.assertRaises(ValueError):run.settle_recording()
                self.assertEqual(len(adb.calls),2);self.assertNotIn('recording_preflight',run.report)
        with tempfile.TemporaryDirectory() as root:
            run,adb,_=self.fixture(root,[],error=RuntimeError('transport failed'))
            with self.assertRaises(RuntimeError):run.settle_recording()
            self.assertEqual(len(adb.calls),1)

    def test_no_settling_after_baseline_or_second_invocation(self):
        with tempfile.TemporaryDirectory() as root:
            run,adb,_=self.fixture(root,[dump(),dump(1)])
            run.settle_recording()
            with self.assertRaises(ValueError):run.settle_recording()
            self.assertEqual(len(adb.calls),2)
        with tempfile.TemporaryDirectory() as root:
            run,adb,_=self.fixture(root,[]);run.report['stages']=[{'label':'baseline'}]
            with self.assertRaises(ValueError):run.settle_recording()
            self.assertEqual(adb.calls,[])


    def test_fixed_two_second_delay_inside_eight_second_budget(self):
        with tempfile.TemporaryDirectory() as root:
            run,adb,clock=self.fixture(root,[dump(),dump(1)])
            pair=run.settle_recording()
            self.assertEqual(adb.calls[0],6.0)
            self.assertEqual(pair[0]['host_capture_bounds']['begin_monotonic'],2.0)
            self.assertEqual(run.report['recording_settle']['initial_settle_seconds'],2.0)
            self.assertLessEqual(clock[0],8.0)

    def test_old_preview_skew_zero_encoder_is_fatal_not_polled(self):
        raw=dump(mismatch=True).replace('VIDEO_RECORD','PREVIEW',1)
        raw=raw.replace('[15047630 ]','[15596307 ]')
        raw=raw.replace('Frames produced: 90, last timestamp: 10000000000 ns',
                        'Frames produced: 0, last timestamp: 0 ns')
        with tempfile.TemporaryDirectory() as root:
            run,adb,_=self.fixture(root,[raw,dump(1),dump(2)])
            with self.assertRaises(c.CaptureMetadataError):run.settle_recording()
            self.assertEqual(len(adb.calls),1)
            self.assertNotIn('recording_preflight',run.report)


    def test_actual_blocked_read_alarm_and_restoration_before_final_save(self):
        with tempfile.TemporaryDirectory() as root:
            handler=signal.getsignal(signal.SIGALRM)
            class ADB:
                calls=0
                def shell(self,target,command,timeout):
                    self.calls+=1
                    left,right=socket.socketpair()
                    try:left.recv(1)  # Real blocking read; ignores passed transport timeout.
                    finally:left.close();right.close()
            adb=ADB();run=r.Trial(adb,6,1,'p85_blocked_read_test',root,root)
            run.recording=True
            saved=[];original_save=run.save
            def save():
                if run.report.get('recording_settle',{}).get('status')=='failed':
                    saved.append((signal.getitimer(signal.ITIMER_REAL),signal.getsignal(signal.SIGALRM)))
                original_save()
            run.save=save
            started=time.monotonic()
            with self.assertRaisesRegex(TimeoutError,'wall-clock'):run.settle_recording()
            elapsed=time.monotonic()-started
            self.assertGreaterEqual(elapsed,7.5);self.assertLess(elapsed,9.5)
            self.assertEqual(adb.calls,1);self.assertNotIn('recording_preflight',run.report)
            self.assertEqual(saved,[((0.0,0.0),handler)])
            self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))
            self.assertIs(signal.getsignal(signal.SIGALRM),handler)

    def test_timer_and_custom_handler_restored_on_success_and_errors(self):
        original=signal.getsignal(signal.SIGALRM)
        def custom(signum,frame):raise AssertionError('Must not fire')
        signal.signal(signal.SIGALRM,custom)
        try:
            for error in (None,RuntimeError('fatal transport'),KeyboardInterrupt()):
                with self.subTest(error=type(error).__name__),tempfile.TemporaryDirectory() as root:
                    run,adb,_=self.fixture(root,[dump(),dump(1)],error=error)
                    if error is None:run.settle_recording()
                    else:
                        with self.assertRaises(type(error)):run.settle_recording()
                    self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))
                    self.assertIs(signal.getsignal(signal.SIGALRM),custom)
        finally:
            signal.setitimer(signal.ITIMER_REAL,0.0);signal.signal(signal.SIGALRM,original)

    def test_preexisting_alarm_and_nonmain_thread_refused_without_reads(self):
        original=signal.getsignal(signal.SIGALRM)
        with tempfile.TemporaryDirectory() as root:
            run,adb,_=self.fixture(root,[])
            signal.setitimer(signal.ITIMER_REAL,30.0)
            try:
                with self.assertRaisesRegex(ValueError,'Existing real-time alarm'):run.settle_recording()
                self.assertGreater(signal.getitimer(signal.ITIMER_REAL)[0],25)
                self.assertIs(signal.getsignal(signal.SIGALRM),original)
                self.assertEqual(adb.calls,[]);self.assertNotIn('recording_settle',run.report)
            finally:signal.setitimer(signal.ITIMER_REAL,0.0)
        with tempfile.TemporaryDirectory() as root:
            run,adb,_=self.fixture(root,[]);errors=[]
            def worker():
                try:run.settle_recording()
                except BaseException as error:errors.append(error)
            thread=threading.Thread(target=worker);thread.start();thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(len(errors),1);self.assertIn('main thread',str(errors[0]))
            self.assertEqual(adb.calls,[]);self.assertNotIn('recording_settle',run.report)


if __name__=='__main__':unittest.main()
