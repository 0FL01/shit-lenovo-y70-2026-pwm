import errno
import inspect
import os
import stat
import unittest
from types import SimpleNamespace as NS
from reader import Acquisition,RootPin,BoundError

def raw(pid=42,start=123,state=b'S'):return str(pid).encode()+b' (name with ) bracket) '+state+b' '+b'0 '*18+str(start).encode()+b'\n'
class Fake:
    O_RDONLY=0;O_DIRECTORY=1;O_CLOEXEC=2;O_NOFOLLOW=4
    def __init__(self):self.t=0.;self.n=10;self.files={};self.reads={};self.calls=[];self.statcount=0;self.fault=None;self.fdmeta={9:(1,9,stat.S_IFDIR|0o555)};self.closed=[];self.polls=0
    def clock(self):return self.t
    def open(self,path,flags,*,dir_fd):
        self.calls.append(('open',path,flags,dir_fd))
        if path=='stat':
            self.statcount+=1
            if self.fault=='hidepid':raise FileNotFoundError(2,'private')
            if self.fault=='deny':raise PermissionError(13,'private')
        self.n+=1;fd=self.n;self.files[fd]=path;self.fdmeta[fd]=(1,fd,(stat.S_IFDIR if path=='42' else stat.S_IFREG)|0o444);return fd
    def fstat(self,fd):
        self.calls.append(('fstat',fd));d,i,m=self.fdmeta[fd]
        if self.fault=='fd_reuse' and self.files.get(fd)=='42':i+=1
        return NS(st_dev=d,st_ino=i,st_mode=m)
    def readlink(self,path,*,dir_fd):
        self.calls.append(('readlink',path,dir_fd))
        return 'pid:[999]' if self.fault=='namespace' else 'pid:[100]'
    def pidfd_open(self,pid,flags):
        self.calls.append(('pidfd_open',pid,flags));self.n+=1;self.fdmeta[self.n]=(1,self.n,0o700);return self.n
    def read(self,fd,n):
        self.calls.append(('read',fd,n))
        if self.fault in ('read_errno','mask'):raise self.read_error
        if self.fault=='deadline':self.t=20
        if self.fault=='cap':return b'x'*n
        if self.reads.get(fd):return b''
        self.reads[fd]=True
        return raw(start=124 if self.fault=='pid_reuse' and self.statcount>=2 else 123,state=b'Z' if self.fault=='zombie' else b'S')
    def close(self,fd):
        self.calls.append(('close',fd));self.closed.append(fd)
        if self.fault=='mask' and self.files.get(fd)=='stat':raise self.close_error
    def poll_factory(self):return self
    def register(self,fd,flags):self.pfd=fd;self.calls.append(('register',fd,flags))
    def poll(self,timeout):
        self.calls.append(('poll',timeout));self.polls+=1
        if self.fault=='exit' or (self.fault=='exit_after_read' and self.polls>=4):return [(self.pfd,1)]
        if self.fault=='bad_poll':return [(True,'unknown')]
        return []
    def acq(self):return Acquisition(os_api=self,poll_factory=self.poll_factory,clock=self.clock,root=RootPin(9,1,9,stat.S_IFDIR|0o555,'pid:[100]','a'*64))
class Tests(unittest.TestCase):
    def test_actual_api_shapes_no_invocation(self):
        for fn,args,kwargs in [(os.open,('stat',0),{'dir_fd':9}),(os.readlink,('ns/pid',),{'dir_fd':9}),(os.pidfd_open,(42,0),{}),(os.fstat,(9,),{}),(os.read,(9,10),{}),(os.close,(9,),{})]:inspect.signature(fn).bind(*args,**kwargs)
    def test_success_relative_only(self):
        f=Fake();a=f.acq();h=a.acquire(pid=42,deadline=12);self.assertEqual(h.read_stat(deadline=12),raw());h.close()
        opens=[x for x in f.calls if x[0]=='open'];self.assertEqual(opens[0][1],'42');self.assertTrue(all(x[1]=='stat' and x[3]==h.dfd for x in opens[1:]));self.assertNotIn(9,f.closed);self.assertEqual(len(f.closed),len(set(f.closed)))
    def test_acquisition_reuse_exit_ambiguity_stop(self):
        for fault in ('pid_reuse','exit','zombie','namespace','hidepid','deny','bad_poll'):
            f=Fake();f.fault=fault;a=f.acq()
            with self.assertRaises(Exception):a.acquire(pid=42,deadline=12)
            self.assertTrue(a.terminal);n=len(f.calls)
            with self.assertRaises(BoundError):a.acquire(pid=42,deadline=12)
            self.assertEqual(len(f.calls),n)
    def test_acquired_fd_reuse_terminal(self):
        f=Fake();a=f.acq();h=a.acquire(pid=42,deadline=12);f.fault='fd_reuse'
        with self.assertRaises(BoundError):h.read_stat(deadline=12)
        self.assertTrue(h.closed);n=len(f.calls)
        with self.assertRaises(BoundError):h.read_stat(deadline=12)
        self.assertEqual(len(f.calls),n)
    def test_read_errno_same_object_no_retry(self):
        for number in (errno.ENOENT,errno.ESRCH,errno.EACCES,errno.EPERM,errno.EIO):
            f=Fake();a=f.acq();h=a.acquire(pid=42,deadline=12);f.fault='read_errno';f.read_error=OSError(number,'secret')
            with self.assertRaises(OSError) as caught:h.read_stat(deadline=12)
            self.assertIs(caught.exception,f.read_error);self.assertTrue(a.terminal);self.assertTrue(h.closed)
            self.assertTrue(any(x.get('stage')=='stat_read' and x.get('errno')==number for x in a.events));self.assertNotIn('secret',str(a.events))
    def test_read_close_masking_chain(self):
        f=Fake();a=f.acq();h=a.acquire(pid=42,deadline=12);f.fault='mask';f.read_error=OSError(2,'read');f.close_error=OSError(5,'close')
        with self.assertRaises(OSError) as caught:h.read_stat(deadline=12)
        self.assertIs(caught.exception,f.close_error);self.assertIs(caught.exception.__context__,f.read_error);self.assertTrue(any(x['stage']=='stat_read' and x.get('errno')==2 for x in a.events));self.assertTrue(any(x['stage']=='stat_close' and x.get('errno')==5 for x in a.events))
    def test_exit_during_read_not_success(self):
        f=Fake();a=f.acq();h=a.acquire(pid=42,deadline=12);f.fault='exit_after_read'
        with self.assertRaises(BoundError):h.read_stat(deadline=12)
        self.assertTrue(h.terminal)
    def test_cap_and_deadline_terminal(self):
        for fault in ('cap','deadline'):
            f=Fake();a=f.acq();h=a.acquire(pid=42,deadline=12);f.fault=fault
            with self.assertRaises(BoundError):h.read_stat(deadline=12)
            self.assertTrue(h.closed)
    def test_strict_inputs(self):
        for value in (None,True,0,'42',[],{}):
            f=Fake();a=f.acq()
            with self.assertRaises(BoundError):a.acquire(pid=value,deadline=12)
            self.assertEqual(f.calls,[])
        for value in (None,True,'9',[],{}):
            with self.assertRaises(BoundError):RootPin(value,1,9,stat.S_IFDIR|0o555,'pid:[100]','a'*64)
    def test_closed_no_new_io(self):
        f=Fake();a=f.acq();h=a.acquire(pid=42,deadline=12);h.close();n=len(f.calls);h.close()
        with self.assertRaises(BoundError):h.read_stat(deadline=12)
        self.assertEqual(len(f.calls),n)
    def test_public_identity_lifecycle_readonly(self):
        f=Fake();a=f.acq();h=a.acquire(pid=42,deadline=12)
        for obj,names in [(a,('root','os','clock','spent','terminal','events','last_error')),(h,('a','pid','dfd','pfd','dir_meta','pid_meta','start','ready','terminal','closed','owned'))]:
            for name in names:
                with self.assertRaises(AttributeError):setattr(obj,name,False)
                with self.assertRaises(AttributeError):delattr(obj,name)
        rows=a.events
        if rows:rows[0]['stage']='corrupt snapshot'
        self.assertNotEqual(a.events[0]['stage'],'corrupt snapshot')
        with self.assertRaises(BoundError):h.__init__(a,42)
        with self.assertRaises(BoundError):a.__init__(os_api=f,poll_factory=f.poll_factory,clock=f.clock,root=a.root)
        h.close()
    def test_uncertain_close_cannot_reopen(self):
        f=Fake();a=f.acq();h=a.acquire(pid=42,deadline=12)
        def bad_close(fd):f.calls.append(('close_uncertain',fd));raise OSError(5,'uncertain')
        f.close=bad_close
        with self.assertRaises(OSError):h.close()
        n=len(f.calls)
        for obj,name,value in [(a,'terminal',False),(h,'terminal',False),(h,'closed',False),(h,'ready',True)]:
            with self.assertRaises(AttributeError):setattr(obj,name,value)
        self.assertEqual(h.owned,())
        with self.assertRaises(BoundError):h.read_stat(deadline=12)
        h.close();self.assertEqual(len(f.calls),n)
    def test_only_documented_public_io_boundary(self):
        f=Fake();a=f.acq();h=a.acquire(pid=42,deadline=12);h.close();n=len(f.calls)
        for obj,names in [(h,('acquire_fd','metadata','root_check','namespace_check','alive','close_fd','stat_read')),(a,('call','check','record'))]:
            for name in names:self.assertFalse(hasattr(obj,name))
        self.assertEqual(len(f.calls),n);self.assertEqual(h.owned,())
if __name__=='__main__':unittest.main()
