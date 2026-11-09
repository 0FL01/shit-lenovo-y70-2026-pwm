"""Inactive raising relative-proc reader. No default OS/poll/clock or live CLI.
RootPin is an externally reviewed prerequisite, NOT self-authenticating evidence.
No executable/ADB/custody/recovery claims. No reset or acquisition retry.
"""
from dataclasses import dataclass
import math
import re
import stat

class BoundError(ValueError): pass

@dataclass(frozen=True)
class RootPin:
    fd: int
    device: int
    inode: int
    mode: int
    pid_namespace: str
    evidence_id: str
    def __post_init__(self):
        if any(type(x) is not int or x<0 for x in (self.fd,self.device,self.inode,self.mode)):raise BoundError('Strict root metadata required')
        if not stat.S_ISDIR(self.mode) or self.inode==0:raise BoundError('Pinned root directory required')
        if type(self.pid_namespace) is not str or re.fullmatch(r'pid:\[[1-9][0-9]*\]',self.pid_namespace) is None:raise BoundError('Pinned namespace required')
        if type(self.evidence_id) is not str or re.fullmatch(r'[0-9a-f]{64}',self.evidence_id) is None:raise BoundError('External evidence reference required')

class Acquisition:
    __slots__=('_os', '_poll_factory', '_clock', '_root', '_spent', '_terminal', '_events', '_dropped', '_last_error', '_logging_failed')
    @property
    def os(self):return self._os
    @property
    def poll_factory(self):return self._poll_factory
    @property
    def clock(self):return self._clock
    @property
    def root(self):return self._root
    @property
    def spent(self):return self._spent
    @property
    def terminal(self):return self._terminal
    @property
    def events(self):return tuple(dict(e) for e in self._events)
    @property
    def dropped(self):return self._dropped
    @property
    def last_error(self):return (dict(self._last_error) if self._last_error is not None else None)
    @property
    def logging_failed(self):return self._logging_failed
    def __init__(self,*,os_api,poll_factory,clock,root):
        if hasattr(self,'_root'):raise BoundError('Cannot reinitialize acquisition')
        if type(root) is not RootPin:raise BoundError('Exact RootPin required')
        self._os=os_api;self._poll_factory=poll_factory;self._clock=clock;self._root=root
        self._spent=False;self._terminal=False;self._events=[];self._dropped=0;self._last_error=None;self._logging_failed=False
    def _record(self,stage,error=None):
        try:
            e=dict(stage=stage)
            if error is not None:
                name=type(error).__name__;e.update(type=name if name.isascii() and name.isidentifier() and len(name)<=64 else 'ExceptionType',errno=error.errno if isinstance(error,OSError) and type(error.errno) is int else None);self._last_error=e
            if len(self._events)<128:self._events.append(e)
            else:self._dropped+=1
        except BaseException:self._logging_failed=True # Never infer complete evidence after failure.
    def _check(self,deadline):
        now=self._clock()
        if type(deadline) not in (int,float) or not math.isfinite(deadline) or type(now) not in (int,float) or not math.isfinite(now) or now>=deadline:raise BoundError('Absolute deadline exhausted')
    def _call(self,stage,fn,*args,deadline,**kwargs):
        self._check(deadline)
        try:result=fn(*args,**kwargs)
        except BaseException as e:self._record(stage,e);raise
        self._record(stage);self._check(deadline);return result
    def acquire(self,*,pid,deadline):
        if self._spent or self._terminal:raise BoundError('Acquisition spent or terminal')
        self._spent=True;h=None
        try:
            if type(pid) is not int or pid<=0:raise BoundError('Strict positive PID required')
            h=Held(self,pid)
            h._root_check(deadline)
            h._dfd=h._acquire_fd('task_dir_open',self._os.open,str(pid),self._os.O_RDONLY|self._os.O_DIRECTORY|self._os.O_CLOEXEC|self._os.O_NOFOLLOW,deadline=deadline,dir_fd=self._root.fd)
            h._dir_meta=h._metadata(h._dfd,'task_dir_fstat',deadline)
            if not stat.S_ISDIR(h._dir_meta[2]):raise BoundError('Task handle not directory')
            h._namespace_check(deadline)
            first=h._stat_read(deadline)
            h._start=h._parse_live(first)
            h._pfd=h._acquire_fd('pidfd_open',self._os.pidfd_open,pid,0,deadline=deadline)
            h._pid_meta=h._metadata(h._pfd,'pidfd_fstat',deadline)
            h._poller=self._call('poll_create',self._poll_factory,deadline=deadline)
            self._call('poll_register',h._poller.register,h._pfd,17,deadline=deadline)
            h._alive(deadline)
            if h._parse_live(h._stat_read(deadline))!=h._start:raise BoundError('Acquisition identity changed')
            h._namespace_check(deadline);h._alive(deadline);h._root_check(deadline)
            h._ready=True;return h
        except BaseException as e:
            self._terminal=True;self._record('acquisition_terminal',e)
            if h is not None:
                try:h.close()
                except BaseException:pass # Cleanup error separately recorded; original raised object preserved.
            raise

class Held:
    __slots__=('_a', '_pid', '_dfd', '_pfd', '_dir_meta', '_pid_meta', '_start', '_poller', '_ready', '_terminal', '_closed', '_owned')
    @property
    def a(self):return self._a
    @property
    def pid(self):return self._pid
    @property
    def dfd(self):return self._dfd
    @property
    def pfd(self):return self._pfd
    @property
    def dir_meta(self):return self._dir_meta
    @property
    def pid_meta(self):return self._pid_meta
    @property
    def start(self):return self._start
    @property
    def poller(self):return self._poller
    @property
    def ready(self):return self._ready
    @property
    def terminal(self):return self._terminal
    @property
    def closed(self):return self._closed
    @property
    def owned(self):return tuple(self._owned)
    def __init__(self,owner,pid):
        if hasattr(self,'_a'):raise BoundError('Cannot reinitialize held handle')
        self._a=owner;self._pid=pid;self._dfd=None;self._pfd=None;self._dir_meta=None;self._pid_meta=None;self._start=None;self._poller=None
        self._ready=False;self._terminal=False;self._closed=False;self._owned=[]
    def _acquire_fd(self,stage,fn,*args,deadline,**kwargs):
        self._a._check(deadline)
        try:fd=fn(*args,**kwargs)
        except BaseException as e:self._a._record(stage,e);raise
        if type(fd) is not int or fd<0 or fd==self._a._root.fd or fd in self._owned:raise BoundError('Invalid owned descriptor')
        self._owned.append(fd);self._a._record(stage);self._a._check(deadline);return fd
    def _metadata(self,fd,stage,deadline):
        st=self._a._call(stage,self._a._os.fstat,fd,deadline=deadline)
        values=(st.st_dev,st.st_ino,st.st_mode)
        if any(type(x) is not int or x<0 for x in values):raise BoundError('Malformed FD metadata')
        return values
    def _root_check(self,deadline):
        p=self._a._root
        if self._metadata(p.fd,'root_fstat',deadline)!=(p.device,p.inode,p.mode):raise BoundError('Borrowed root handle changed')
        observed=self._a._call('root_pid_namespace',self._a._os.readlink,'self/ns/pid',dir_fd=p.fd,deadline=deadline)
        if observed!=p.pid_namespace:raise BoundError('Root namespace ambiguity')
    def _namespace_check(self,deadline):
        if self._dir_meta is not None and self._metadata(self._dfd,'task_dir_continuity',deadline)!=self._dir_meta:raise BoundError('Task descriptor changed')
        observed=self._a._call('task_pid_namespace',self._a._os.readlink,'ns/pid',dir_fd=self._dfd,deadline=deadline)
        if observed!=self._a._root.pid_namespace:raise BoundError('Task namespace mismatch')
    def _alive(self,deadline):
        if self._metadata(self._pfd,'pidfd_continuity',deadline)!=self._pid_meta:raise BoundError('Pidfd descriptor changed')
        rows=self._a._call('pidfd_poll',self._poller.poll,0,deadline=deadline)
        if type(rows) is not list:raise BoundError('Malformed poll evidence')
        if rows:raise BoundError('Task exit or unqualified poll event')
    def _close_fd(self,fd,stage):
        self._owned.remove(fd) # Never retry a potentially completed close.
        try:self._a._os.close(fd)
        except BaseException as e:self._a._record(stage,e);raise
        self._a._record(stage+'_returned')
    def _stat_read(self,deadline):
        fd=self._acquire_fd('stat_open',self._a._os.open,'stat',self._a._os.O_RDONLY|self._a._os.O_CLOEXEC|self._a._os.O_NOFOLLOW,dir_fd=self._dfd,deadline=deadline)
        try:
            data=bytearray()
            for _ in range(65):
                cap=16385-len(data);chunk=self._a._call('stat_read',self._a._os.read,fd,cap,deadline=deadline)
                if type(chunk) is not bytes or len(chunk)>cap:raise BoundError('Malformed read bytes')
                if not chunk:return bytes(data)
                data.extend(chunk)
                if len(data)>16384:raise BoundError('Stat byte cap')
            raise BoundError('Stat call cap')
        finally:self._close_fd(fd,'stat_close') # Preserve ordinary read/close masking and exception chain.
    def _parse_live(self,data):
        end=data.rfind(b')');parts=data[end+1:].split()
        if (not data.startswith(str(self._pid).encode()+b' (') or end<0 or len(parts)<20
            or parts[0] not in (b'R',b'S',b'D',b'T',b't',b'W',b'I',b'P')
            or not parts[19].isdigit() or int(parts[19])<=0):raise BoundError('Unqualified live process stat')
        return int(parts[19])
    def read_stat(self,*,deadline):
        if not self._ready or self._terminal or self._a._terminal or self._closed:raise BoundError('Held task is terminal or unavailable')
        try:
            self._root_check(deadline);self._namespace_check(deadline);self._alive(deadline)
            data=self._stat_read(deadline)
            if self._parse_live(data)!=self._start:raise BoundError('Task identity changed')
            self._alive(deadline);self._namespace_check(deadline);self._root_check(deadline)
            return data
        except BaseException as e:
            self._terminal=True;self._a._terminal=True;self._a._record('reader_terminal',e)
            try:self.close()
            except BaseException:pass
            raise
    def close(self):
        if self._closed:return
        self._closed=True;self._ready=False;self._terminal=True;primary=None
        for fd in tuple(reversed(self._owned)):
            try:self._close_fd(fd,'handle_close')
            except BaseException as e:
                if primary is None:primary=e
        if primary is not None:self._a._terminal=True;raise primary
