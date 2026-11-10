"""Actual ordinary files/sinks + synthetic byte streams; no host/network/device."""
import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import test_capsule
from test_analyze import a,probe,profiles

spec=importlib.util.spec_from_file_location('observation_transfer',Path(__file__).with_name('transfer.py'))
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.f=test_capsule.CapsuleTests();self.f.setUp();self.addCleanup(self.f.tearDown)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.base.chmod(0o700)
        self.pin=t.identity(self.base.stat())
        # Fixture pins are computed for tests only, not a production approval.
        self.pins={p:t.sha((t.ROOT/p).read_bytes()) for p in [t.SELF,*t.SOURCES.values()]}
    def wire(self):
        stream=io.BytesIO()
        t.send_bundle(self.f.cp,stream,expected_source=self.f.source,expected_helpers=self.pins,
                      deadline=time.monotonic()+20,no_concurrent_writers=True)
        return stream.getvalue()
    def receive(self,wire=None,code=0,name='received'):
        return t.receive_bundle(io.BytesIO(self.wire() if wire is None else wire),base_path=self.base,
            base_pin=self.pin,directory_name=name,expected_source=self.f.source,expected_helpers=self.pins,
            authenticated_peer='synthetic-local-peer',finish_sender=lambda:code,
            deadline=time.monotonic()+20,no_concurrent_writers=True)
    def analyze_destination(self,d,receiver_exit_code=0):
        review=d/'review.json';review.write_bytes(self.f.review.read_bytes());review.chmod(0o600)
        with patch.object(a,'probe_video',return_value=probe()),patch.object(a,'extract_profiles',return_value=profiles()):
            return a.analyze_actual(d/self.f.cp.name,expected_source=self.f.source,review_path=review,
                video=d/'capture.mp4',no_concurrent_writers=True,transfer_path=d/'transfer.json',
                expected_transfer_sources=self.pins,authenticated_peer='synthetic-local-peer',receiver_exit_code=receiver_exit_code)
    def test_real_sink_transfer_and_conditional_analysis(self):
        original=self.f.cp.read_bytes();source_identity=t.identity(self.f.video.stat())
        dest,receipt=self.receive()
        self.assertEqual((dest/self.f.cp.name).read_bytes(),original)
        self.assertEqual(self.f.cp.read_bytes(),original)
        self.assertEqual(receipt['source_identity'],source_identity)
        self.assertNotEqual(receipt['destination_identity'],source_identity)
        self.assertEqual((dest/'capture.mp4').read_bytes(),self.f.video.read_bytes())
        summary,private,arrays=self.analyze_destination(dest)
        self.assertFalse(summary['qualification_eligible']);self.assertFalse(summary['acquisition_admitted'])
        self.assertEqual(private['capsule']['media']['created_identity'],source_identity)
        self.assertEqual(private['transfer_receipt']['destination_identity'],t.identity((dest/'capture.mp4').stat()))
        self.assertNotIn('authenticated_peer',summary)
    def test_copied_movie_without_receipt_rejected(self):
        dest,_=self.receive();review=dest/'review.json';review.write_bytes(self.f.review.read_bytes());review.chmod(0o600)
        with self.assertRaises(ValueError):a.analyze_actual(dest/self.f.cp.name,expected_source=self.f.source,
            review_path=review,video=dest/'capture.mp4',no_concurrent_writers=True)
    def test_missing_receipt(self):
        dest,_=self.receive();(dest/'transfer.json').unlink()
        with self.assertRaises(FileNotFoundError):self.analyze_destination(dest)
    def test_destination_inode_replaced_same_bytes(self):
        dest,_=self.receive();p=dest/'capture.mp4';raw=p.read_bytes();p.rename(dest/'old.mp4');p.write_bytes(raw);p.chmod(0o600)
        with self.assertRaises(ValueError):self.analyze_destination(dest)
    def test_source_inode_replaced_same_bytes(self):
        p=self.f.video;raw=p.read_bytes();p.rename(p.with_name('old.mp4'));p.write_bytes(raw);p.chmod(0o600)
        with self.assertRaises(ValueError):self.wire()
    def test_capsule_mutation_rejected(self):
        self.f.cap['media']['sha256']='f'*64;self.f.rewrite()
        with self.assertRaises(ValueError):self.wire()
    def test_helper_pin_mismatch(self):
        self.pins[t.SELF]='0'*64
        with self.assertRaises(ValueError):self.wire()
    def test_truncated_stream_no_receipt(self):
        wire=self.wire()
        with self.assertRaises(ValueError):self.receive(wire[:-10])
        self.assertFalse((self.base/'received'/'transfer.json').exists())
    def test_corrupt_media_no_receipt(self):
        wire=bytearray(self.wire());header_len=int.from_bytes(wire[:8],'big');wire[8+header_len]^=1
        with self.assertRaises(ValueError):self.receive(bytes(wire))
        self.assertFalse((self.base/'received'/'transfer.json').exists())
    def test_sender_nonzero_no_receipt(self):
        with self.assertRaises(ValueError):self.receive(code=1)
        self.assertFalse((self.base/'received'/'transfer.json').exists())
    def test_trailing_stream_no_receipt(self):
        with self.assertRaises(ValueError):self.receive(self.wire()+b'extra')
        self.assertFalse((self.base/'received'/'transfer.json').exists())
    def test_existing_destination_rejected(self):
        self.receive()
        with self.assertRaises(Exception):self.receive()
    def test_receipt_source_and_header_tampering(self):
        dest,receipt=self.receive();receipt['stream_header_sha256']='0'*64
        receipt['source_completion']['header_sha256']='0'*64
        (dest/'transfer.json').write_text(json.dumps(receipt))
        with self.assertRaises(ValueError):self.analyze_destination(dest)
    def test_aged_atime_transfer(self):
        for p in self.f.d.iterdir():os.utime(p,ns=(1,p.stat().st_mtime_ns))
        dest,_=self.receive();summary,_,_=self.analyze_destination(dest)
        self.assertEqual(summary['status'],'conditional_diagnostic_only')
    def test_swap_after_sink_close_rejected(self):
        def swap():
            p=self.base/'received'/'capture.mp4';raw=p.read_bytes()
            p.rename(p.with_name('old.mp4'));p.write_bytes(raw);p.chmod(0o600)
            return 0
        with self.assertRaisesRegex(ValueError,'created sink inode'):
            t.receive_bundle(io.BytesIO(self.wire()),base_path=self.base,
                base_pin=self.pin,directory_name='received',expected_source=self.f.source,
                expected_helpers=self.pins,authenticated_peer='synthetic-local-peer',finish_sender=swap,
                deadline=time.monotonic()+20,no_concurrent_writers=True)
        self.assertFalse((self.base/'received'/'transfer.json').exists())
    def test_missing_receiver_exit_rejected(self):
        dest,_=self.receive()
        with self.assertRaisesRegex(ValueError,'receiver process exit'):self.analyze_destination(dest,None)
    def test_nonzero_receiver_exit_rejected(self):
        dest,_=self.receive()
        with self.assertRaisesRegex(ValueError,'receiver process exit'):self.analyze_destination(dest,1)
    def test_final_directory_close_failure_requires_external_failed_exit(self):
        from contextlib import contextmanager
        original=t.dependencies
        @contextmanager
        def broken_close(expected):
            with original(expected) as modules:
                cls=modules['fresh_private_directory'].OwnedDirectory
                close=cls.close
                def fail(self):
                    close(self)
                    raise OSError('injected final directory close uncertainty')
                cls.close=fail
                yield modules
        wire=self.wire()
        with patch.object(t,'dependencies',broken_close):
            with self.assertRaisesRegex(OSError,'close uncertainty'):self.receive(wire)
        dest=self.base/'received'
        # Candidate bytes can remain, but they explicitly cannot attest receiver success.
        pending=json.loads((dest/'transfer.json').read_bytes())
        self.assertEqual(pending['status'],'destination_bytes_verified_receiver_exit_pending')
        with self.assertRaisesRegex(ValueError,'receiver process exit'):self.analyze_destination(dest,1)
    def test_nonfinite_deadline_rejected(self):
        for deadline in (float('inf'),float('nan'),-float('inf')):
            with self.subTest(deadline=deadline),self.assertRaisesRegex(ValueError,'deadline'):
                t.send_bundle(self.f.cp,io.BytesIO(),expected_source=self.f.source,expected_helpers=self.pins,
                    deadline=deadline,no_concurrent_writers=True)
            with self.subTest(receiver=deadline),self.assertRaisesRegex(ValueError,'deadline'):
                t.receive_bundle(io.BytesIO(),base_path=self.base,base_pin=self.pin,directory_name='received',
                    expected_source=self.f.source,expected_helpers=self.pins,authenticated_peer='synthetic',
                    finish_sender=lambda:0,deadline=deadline,no_concurrent_writers=True)
    def test_oversized_media_rejected_before_hash(self):
        from contextlib import contextmanager
        with self.f.video.open('r+b') as f:f.truncate(t.CAP+1)
        original=t.dependencies
        @contextmanager
        def no_hash(expected):
            with original(expected) as modules:
                modules['host_evidence'].snapshot=lambda *a,**k: (_ for _ in ()).throw(AssertionError('hash must not run'))
                yield modules
        with patch.object(t,'dependencies',no_hash),self.assertRaisesRegex(ValueError,'prehash byte cap'):
            self.wire()
    def test_stdlib_sender_without_site_packages(self):
        script='''import importlib.util,json,sys,time
spec=importlib.util.spec_from_file_location('t',sys.argv[1]);t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
assert 'numpy' not in sys.modules
t.send_bundle(sys.argv[2],sys.stdout.buffer,expected_source=json.loads(sys.argv[3]),expected_helpers=json.loads(sys.argv[4]),deadline=time.monotonic()+20,no_concurrent_writers=True)
assert 'numpy' not in sys.modules
'''
        result=subprocess.run([sys.executable,'-S','-c',script,str(Path(t.__file__)),str(self.f.cp),
            json.dumps(self.f.source),json.dumps(self.pins)],capture_output=True,timeout=25,check=True)
        dest,_=self.receive(result.stdout,code=result.returncode)
        self.assertEqual((dest/'capture.mp4').read_bytes(),self.f.video.read_bytes())

if __name__=='__main__':unittest.main()
