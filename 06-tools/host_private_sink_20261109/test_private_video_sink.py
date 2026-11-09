"""Fake syscall-only tests: no sockets, devices or filesystem writes."""
import errno
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host_adb_full_api_spike'))
from private_video_sink import CapacityPolicy, ParentPin, PrivateSinkFactory, SinkError

PATH = '/approved/private/capture.mp4'


def meta(inode, mode, uid=17, size=0):
    return NS(st_dev=3, st_ino=inode, st_uid=uid, st_mode=mode,
              st_nlink=1, st_size=size)


class FakeOS:
    O_RDONLY=os.O_RDONLY; O_DIRECTORY=os.O_DIRECTORY; O_NOFOLLOW=os.O_NOFOLLOW
    O_CLOEXEC=os.O_CLOEXEC; O_CREAT=os.O_CREAT; O_EXCL=os.O_EXCL; O_WRONLY=os.O_WRONLY
    def __init__(self):
        self.nodes = {'/':meta(1,stat.S_IFDIR|0o755),
                      '/approved':meta(2,stat.S_IFDIR|0o755),
                      '/approved/private':meta(3,stat.S_IFDIR|0o700)}
        self.fds, self.next, self.closed, self.calls = {}, 20, [], []
        self.time, self.hooks, self.write_sizes = 0., {}, []
        self.available = 1000000
        self.data = bytearray()
    def event(self, op, *args):
        self.calls.append((op, args))
        if op in self.hooks:
            self.hooks[op](*args)
    def path(self, name, fd):
        return name if fd is None else self.fds[fd].rstrip('/') + '/' + name
    def open(self, name, flags, mode, dir_fd=None):
        self.event('open', name, flags, mode, dir_fd)
        p = self.path(name, dir_fd)
        if flags & os.O_CREAT:
            if p in self.nodes: raise FileExistsError('PRIVATE_SECRET')
            if flags & (os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC) != (os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC):
                raise AssertionError('missing creation flags')
            self.nodes[p] = meta(4,stat.S_IFREG|mode)
        else:
            if p not in self.nodes: raise FileNotFoundError('PRIVATE_SECRET')
            if not stat.S_ISDIR(self.nodes[p].st_mode): raise OSError('PRIVATE_SECRET')
        self.next += 1
        self.fds[self.next] = p
        self.event('after_open', p)
        return self.next
    def fstat(self, fd):
        self.event('fstat', fd)
        return self.nodes[self.fds[fd]]
    def stat(self, name, dir_fd, follow_symlinks):
        if follow_symlinks is not False: raise AssertionError()
        self.event('stat', name, dir_fd)
        return self.nodes[self.path(name, dir_fd)]
    def fstatvfs(self, fd):
        self.event('capacity', fd)
        return NS(f_bavail=self.available, f_frsize=1)
    def write(self, fd, data):
        self.event('write', fd, data)
        n = self.write_sizes.pop(0) if self.write_sizes else len(data)
        if type(n) is int and 0 < n <= len(data):
            self.data.extend(data[:n])
            self.nodes[self.fds[fd]].st_size += n
        self.event('after_write', n)
        return n
    def close(self, fd):
        self.closed.append(fd)
        self.event('close', fd)
        del self.fds[fd]


class SinkTests(unittest.TestCase):
    def setUp(self): self.o = FakeOS()
    def factory(self, **kw):
        params = dict(exact_path=PATH, parent_pin=ParentPin(3,3,17),
                      observed_size=6, capacity=CapacityPolicy(100,10),
                      os_api=self.o, monotonic=lambda:self.o.time)
        params.update(kw)
        return PrivateSinkFactory(**params)
    def sink(self): return self.factory()(PATH,10.)
    def rejected(self, op, code=None):
        with self.assertRaises(SinkError) as cm: op()
        self.assertNotIn('PRIVATE_SECRET', str(cm.exception))
        if code: self.assertEqual(cm.exception.code,code)
        self.assertEqual(len(self.o.closed), len(set(self.o.closed)))
        return cm.exception

    def test_inert(self):
        self.factory()
        self.assertFalse(self.o.calls)
    def test_success(self):
        s=self.sink()
        self.assertEqual(s.identity.path,PATH)
        self.assertTrue(s.identity.exclusive)
        self.assertEqual(s.write(b'abcdef'),6)
        s.close()
        self.assertEqual(s.facts.confirmed_written,6)
        self.assertEqual(s.facts.close_outcome,'closed')
        self.assertFalse(s.facts.removed_by_sink)
        self.assertFalse(self.o.fds)
    def test_short_writes(self):
        s=self.sink(); self.o.write_sizes=[2,1,3]; v=memoryview(b'abcdef')
        while v: v=v[s.write(v):]
        s.close(); self.assertEqual(self.o.data,b'abcdef')
    def test_grammar(self):
        for p in ['/approved/../private/capture.mp4','/approved//private/capture.mp4',
                  '/approved/./private/capture.mp4','/approved/private/other',
                  'approved/private/capture.mp4','/capture.mp4','//private/capture.mp4',
                  '/approved/pri\x00vate/capture.mp4']:
            with self.subTest(path=p),self.assertRaises(ValueError): self.factory(exact_path=p)
    def test_parent_owner(self):
        self.o.nodes['/approved/private'].st_uid=18
        self.rejected(self.sink,'private_parent_rejected')
        self.assertNotIn(PATH,self.o.nodes); self.assertFalse(self.o.fds)
    def test_parent_mode(self):
        self.o.nodes['/approved/private'].st_mode=stat.S_IFDIR|0o755
        self.rejected(self.sink,'private_parent_rejected')
    def test_parent_inode(self):
        self.o.nodes['/approved/private'].st_ino=7
        self.rejected(self.sink,'private_parent_rejected')
    def test_parent_device(self):
        self.o.nodes['/approved/private'].st_dev=9
        self.rejected(self.sink,'private_parent_rejected')
    def test_ancestor_symlink(self):
        self.o.nodes['/approved'].st_mode=stat.S_IFLNK|0o777
        self.rejected(self.sink); self.assertFalse(self.o.fds)
    def test_parent_symlink(self):
        self.o.nodes['/approved/private'].st_mode=stat.S_IFLNK|0o777
        self.rejected(self.sink); self.assertFalse(self.o.fds)
    def test_collision(self):
        self.o.nodes[PATH]=meta(9,stat.S_IFREG|0o600,size=77)
        self.rejected(self.sink)
        self.assertEqual(self.o.nodes[PATH].st_size,77)
    def test_final_symlink(self):
        self.o.nodes[PATH]=meta(9,stat.S_IFLNK|0o777)
        self.rejected(self.sink); self.assertEqual(self.o.nodes[PATH].st_ino,9)
    def test_capacity(self):
        self.o.available=15
        self.rejected(self.sink,'insufficient_capacity')
        self.assertNotIn(PATH,self.o.nodes)
    def test_capacity_boundary(self):
        self.o.available=16; self.sink().close()
    def test_explicit_resource_limits(self):
        for args in [dict(observed_size=101),dict(observed_size=True),
                     dict(capacity=CapacityPolicy(100,-1)),dict(observed_size=0)]:
            with self.assertRaises(ValueError): self.factory(**args)
    def test_one_attempt(self):
        f=self.factory(); s=f(PATH,10); s.close()
        self.rejected(lambda:f(PATH,10),'sink_attempt_spent')
    def test_no_retry_after_failure(self):
        f=self.factory(); self.o.available=0
        self.rejected(lambda:f(PATH,10)); self.o.available=100
        self.rejected(lambda:f(PATH,10),'sink_attempt_spent')
    def test_wrong_destination(self):
        f=self.factory(); self.rejected(lambda:f('/other/capture.mp4',10),'destination_mismatch')
        self.assertFalse(self.o.calls)
    def test_expired(self):
        self.o.time=11; self.rejected(self.sink,'deadline_exceeded')
        self.assertFalse(self.o.calls)
    def test_invalid_deadlines(self):
        for d in [True,float('nan'),float('inf'),'x']:
            self.rejected(lambda:self.factory()(PATH,d),'invalid_deadline')
    def test_late_open_owns_fd(self):
        self.o.hooks['after_open']=lambda p:setattr(self.o,'time',11.)
        self.rejected(self.sink,'deadline_exceeded'); self.assertFalse(self.o.fds)
    def test_late_file_create_retains(self):
        def late(p):
            if p == PATH: self.o.time=11
        self.o.hooks['after_open']=late
        e=self.rejected(self.sink,'deadline_exceeded')
        self.assertTrue(e.facts.created); self.assertIn(PATH,self.o.nodes)
        self.assertFalse(self.o.fds)
    def test_file_wrong_owner(self):
        def wrong(p):
            if p==PATH: self.o.nodes[p].st_uid=18
        self.o.hooks['after_open']=wrong
        e=self.rejected(self.sink,'private_file_rejected')
        self.assertTrue(e.facts.created); self.assertFalse(self.o.fds)
    def test_file_umask_mode(self):
        def wrong(p):
            if p==PATH: self.o.nodes[p].st_mode=stat.S_IFREG|0o400
        self.o.hooks['after_open']=wrong
        self.rejected(self.sink,'private_file_rejected')
    def test_file_hardlink(self):
        def wrong(p):
            if p==PATH: self.o.nodes[p].st_nlink=2
        self.o.hooks['after_open']=wrong
        self.rejected(self.sink,'private_file_rejected')
    def test_changed_directory_edge(self):
        orig=self.o.stat
        def replaced(name,**kw):
            s=orig(name,**kw)
            if name=='approved': return meta(99,s.st_mode)
            return s
        self.o.stat=replaced
        self.rejected(self.sink,'directory_identity_changed')
    def test_race_after_file_create(self):
        def wrong(p):
            if p==PATH: self.o.nodes['/approved/private'].st_ino=9
        self.o.hooks['after_open']=wrong
        self.rejected(self.sink,'directory_identity_changed')
    def test_partial_enospc(self):
        s=self.sink(); s.write(b'abc')
        def fail(*args): raise OSError(errno.ENOSPC,'PRIVATE_SECRET')
        self.o.hooks['write']=fail
        e=self.rejected(lambda:s.write(b'def'),'sink_write_failed')
        self.assertEqual(e.facts.confirmed_written,3)
        self.assertTrue(e.facts.write_outcome_uncertain)
        self.assertEqual(self.o.data,b'abc'); self.assertFalse(self.o.fds)
        s.close()
    def test_bad_counts(self):
        for count in [0,-1,7,True,None]:
            self.o=FakeOS(); s=self.sink(); self.o.write_sizes=[count]
            e=self.rejected(lambda:s.write(b'abcdef'),'write_count_rejected')
            self.assertTrue(e.facts.write_outcome_uncertain)
    def test_size_exceeded(self):
        s=self.sink()
        self.rejected(lambda:s.write(b'abcdefg'),'write_bound_rejected')
        self.assertEqual(self.o.data,b'')
    def test_chunk_exceeded(self):
        s=self.factory(observed_size=70000,capacity=CapacityPolicy(70000,10))(PATH,10)
        self.rejected(lambda:s.write(b'x'*65537),'write_bound_rejected')
    def test_late_write_keeps_confirmed_count(self):
        s=self.sink(); self.o.hooks['after_write']=lambda n:setattr(self.o,'time',11)
        e=self.rejected(lambda:s.write(b'abcdef'),'deadline_exceeded')
        self.assertEqual(e.facts.confirmed_written,6)
        self.assertFalse(e.facts.write_outcome_uncertain)
        self.assertFalse(self.o.fds)
    def test_changed_file_after_write(self):
        s=self.sink()
        self.o.hooks['after_write']=lambda n:setattr(self.o.nodes[PATH],'st_ino',99)
        self.rejected(lambda:s.write(b'abcdef'),'private_file_rejected')
    def test_close_error_all_fds_attempted_once(self):
        s=self.sink(); original_fds=set(self.o.fds)
        def fail(fd): raise OSError(errno.EINTR,'PRIVATE_SECRET')
        self.o.hooks['close']=fail
        e=self.rejected(s.close,'close_outcome_uncertain')
        self.assertEqual(set(self.o.closed),original_fds)
        self.assertEqual(e.facts.close_outcome,'uncertain')
        self.rejected(s.close,'close_outcome_uncertain')
    def test_late_close(self):
        s=self.sink()
        self.o.hooks['close']=lambda fd:setattr(self.o,'time',11)
        e=self.rejected(s.close,'deadline_exceeded')
        self.assertEqual(e.facts.close_outcome,'closed')
        self.assertFalse(self.o.fds)
    def test_postclose_write(self):
        s=self.sink(); s.close()
        self.rejected(lambda:s.write(b'a'),'sink_closed')
    def test_interrupt_cleans_owned(self):
        s=self.sink()
        def stop(*args): raise KeyboardInterrupt()
        self.o.hooks['write']=stop
        with self.assertRaises(KeyboardInterrupt): s.write(b'a')
        self.assertFalse(self.o.fds)
    def test_close_after_partial_is_not_completion(self):
        s=self.sink(); s.write(b'abc'); s.close()
        self.assertEqual(s.facts.confirmed_written,3)
    def test_create_cleanup_close_error_visible(self):
        def wrong(p):
            if p==PATH: self.o.nodes[p].st_uid=18
        def fail(fd): raise OSError('PRIVATE_SECRET')
        self.o.hooks.update(after_open=wrong,close=fail)
        e=self.rejected(self.sink,'private_file_rejected')
        self.assertEqual(e.facts.close_outcome,'uncertain')

if __name__=='__main__': unittest.main()
