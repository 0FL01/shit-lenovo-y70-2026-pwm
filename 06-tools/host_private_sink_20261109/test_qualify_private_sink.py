"""Fake-only execution of the inert synthetic qualification wrapper."""
import errno
import os
from pathlib import Path
import stat
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'host_adb_full_api_spike'))
from test_private_video_sink import FakeOS, meta
from qualify_private_sink import BasePin, HostSinkQualification, PAYLOAD, RESERVE_BYTES

BASE='/approved/private'
NAME='sink_probe'
FILE=BASE+'/'+NAME+'/capture.mp4'


class QualificationOS(FakeOS):
    def __init__(self):
        super().__init__()
        self.available=2*RESERVE_BYTES
        self.read_offsets={}
        self.mkdir_count=0
        self.exclusive_collisions=0
    def getuid(self):
        self.event('getuid')
        return 17
    def open(self,name,flags,mode=0o777,dir_fd=None):
        if flags & os.O_CREAT and self.path(name,dir_fd) in self.nodes:
            self.exclusive_collisions += 1
            self.event('collision')
            raise FileExistsError(errno.EEXIST,'PRIVATE_SECRET')
        if not flags & os.O_CREAT and not flags & os.O_DIRECTORY:
            self.event('open',name,flags,mode,dir_fd)
            p=self.path(name,dir_fd)
            if p not in self.nodes or not stat.S_ISREG(self.nodes[p].st_mode):
                raise OSError('PRIVATE_SECRET')
            self.next += 1
            fd=self.next
            self.fds[fd]=p
        else:
            fd=super().open(name,flags,mode,dir_fd)
        self.read_offsets[fd]=0
        return fd
    def mkdir(self,name,mode,dir_fd):
        self.event('mkdir')
        self.mkdir_count += 1
        p=self.path(name,dir_fd)
        if p in self.nodes:
            raise FileExistsError(errno.EEXIST,'PRIVATE_SECRET')
        self.nodes[p]=meta(8,stat.S_IFDIR|mode)
        self.event('after_mkdir')
    def read(self,fd,count):
        self.event('read')
        start=self.read_offsets[fd]
        part=bytes(self.data[start:start+count])
        self.read_offsets[fd]+=len(part)
        return part


class QualificationTests(unittest.TestCase):
    def setUp(self): self.os=QualificationOS()
    def probe(self,**kwargs):
        params=dict(base_path=BASE,base_pin=BasePin(3,3,17,stat.S_IFDIR|0o700),
                    directory_name=NAME,os_api=self.os,monotonic=lambda:self.os.time)
        params.update(kwargs)
        return HostSinkQualification(**params)
    def assert_failed(self,probe=None,stage=None):
        out=(probe or self.probe()).run()
        self.assertEqual(out['status'],'failed')
        if stage: self.assertEqual(out['stage'],stage)
        self.assertNotIn('PRIVATE_SECRET',str(out))
        self.assertFalse(out['artifacts_removed'])
        self.assertEqual(len(self.os.closed),len(set(self.os.closed)))
        return out
    def test_import_construct_inert(self):
        self.probe()
        self.assertFalse(self.os.calls)
    def test_success_one_file_collision_retained(self):
        out=self.probe().run()
        self.assertEqual(out['status'],'passed')
        self.assertTrue(out['one_shot_refused'])
        self.assertTrue(out['collision_refused'])
        self.assertTrue(out['exact_readback'])
        self.assertEqual(out['confirmed_written'],4096)
        self.assertEqual(bytes(self.os.data),PAYLOAD)
        self.assertEqual(self.os.nodes[FILE].st_size,4096)
        self.assertEqual(self.os.mkdir_count,1)
        self.assertEqual(self.os.exclusive_collisions,1)
        self.assertFalse(self.os.fds)
    def test_wrapper_spent(self):
        p=self.probe(); p.run(); calls=len(self.os.calls)
        self.assertEqual(p.run(),dict(status='refused',stage='qualification_spent'))
        self.assertEqual(len(self.os.calls),calls)
    def test_wrong_uid_no_mkdir(self):
        self.os.getuid=lambda:18
        self.assert_failed(stage='base_identity')
        self.assertEqual(self.os.mkdir_count,0)
    def test_wrong_base_inode_no_mkdir(self):
        self.assert_failed(self.probe(base_pin=BasePin(3,99,17,stat.S_IFDIR|0o700)),
                  'base_identity')
        self.assertEqual(self.os.mkdir_count,0)
    def test_existing_directory_no_adoption(self):
        self.os.nodes[BASE+'/'+NAME]=meta(8,stat.S_IFDIR|0o700)
        self.assert_failed(stage='fresh_directory')
        self.assertNotIn(FILE,self.os.nodes)
    def test_new_directory_wrong_mode_no_repair(self):
        self.os.hooks['after_mkdir']=lambda:setattr(self.os.nodes[BASE+'/'+NAME],
                                                   'st_mode',stat.S_IFDIR|0o500)
        self.assert_failed(stage='fresh_directory')
        self.assertEqual(self.os.nodes[BASE+'/'+NAME].st_mode,stat.S_IFDIR|0o500)
    def test_capacity_no_capture(self):
        self.os.available=0
        out=self.assert_failed(stage='sink_create')
        self.assertTrue(out['directory_created'])
        self.assertFalse(out['file_created'])
        self.assertNotIn(FILE,self.os.nodes)
    def test_write_enospc_retains(self):
        def fail(*args): raise OSError(errno.ENOSPC,'PRIVATE_SECRET')
        self.os.hooks['write']=fail
        out=self.assert_failed(stage='sink_write')
        self.assertTrue(out['file_created'])
        self.assertIn(FILE,self.os.nodes)
        self.assertFalse(self.os.fds)
    def test_unknown_write_count_is_explicit(self):
        def fail(*args): raise OSError('PRIVATE_SECRET')
        self.os.hooks['after_write']=fail
        out=self.assert_failed(stage='sink_write')
        self.assertEqual(len(self.os.data),4096)
        self.assertEqual(out['confirmed_written'],0)
        self.assertTrue(out['write_outcome_uncertain'])
        self.assertEqual(out['sink_close'],'closed')
    def test_collision_cleanup_uncertainty_separate(self):
        def fail_once(fd):
            if self.os.exclusive_collisions and not getattr(self.os,'close_failed',False):
                self.os.close_failed=True
                raise OSError('PRIVATE_SECRET')
        self.os.hooks['close']=fail_once
        out=self.assert_failed(stage='collision_refusal')
        self.assertFalse(out['collision_file_created'])
        self.assertEqual(out['collision_close'],'uncertain')
        self.assertEqual(out['sink_close'],'closed')
        self.assertEqual(out['wrapper_close'],'closed')
        self.assertEqual(len(self.os.fds),1)
    def test_acquisition_failure_uncertainty_is_explicit(self):
        self.os.available=0
        out=self.assert_failed(stage='sink_create')
        self.assertFalse(out['write_outcome_uncertain'])
        self.assertFalse(out['file_created'])
    def test_short_write_loop(self):
        self.os.write_sizes=[1,7,4088]
        self.assertEqual(self.probe().run()['status'],'passed')
    def test_readback_corrupt(self):
        self.os.hooks['read']=lambda:self.os.data.__setitem__(0,255)
        self.assert_failed(stage='first_readback')
    def test_collision_recheck_detects_change(self):
        self.os.hooks['collision']=lambda:self.os.data.__setitem__(0,255)
        self.assert_failed(stage='second_readback')
    def test_postclose_replacement_rejected(self):
        def replace(fd):
            if self.os.fds[fd]==FILE and self.os.nodes[FILE].st_size==4096:
                self.os.nodes[FILE].st_ino=77
        self.os.hooks['close']=replace
        self.assert_failed(stage='sink_close')
    def test_late_mkdir_retained(self):
        self.os.hooks['after_mkdir']=lambda:setattr(self.os,'time',20)
        out=self.assert_failed(stage='deadline_exceeded')
        self.assertTrue(out['directory_created'])
        self.assertFalse(self.os.fds)
    def test_close_error_uncertain_no_retry(self):
        def fail(fd): raise OSError(errno.EINTR,'PRIVATE_SECRET')
        self.os.hooks['close']=fail
        out=self.assert_failed(stage='wrapper_close')
        self.assertEqual(out['sink_close'],'uncertain')
        self.assertEqual(out['wrapper_close'],'uncertain')
    def test_names_rejected_without_io(self):
        for name in ['../other','a/b','.','', 'a b']:
            with self.assertRaises(ValueError):self.probe(directory_name=name)
        self.assertFalse(self.os.calls)
    def test_interrupt_cleanup(self):
        def stop(*args): raise KeyboardInterrupt()
        self.os.hooks['write']=stop
        with self.assertRaises(KeyboardInterrupt):self.probe().run()
        self.assertFalse(self.os.fds)
    def test_denied_mkdir_no_retry(self):
        def fail(*args): raise PermissionError('PRIVATE_SECRET')
        self.os.hooks['mkdir']=fail
        p=self.probe()
        self.assert_failed(p,'fresh_directory')
        self.assertEqual(p.run()['stage'],'qualification_spent')
        self.assertFalse(self.os.fds)


if __name__=='__main__':unittest.main()
