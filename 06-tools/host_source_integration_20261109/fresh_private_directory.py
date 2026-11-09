"""Inactive ordinary-host fresh directory setup; no CLI/default I/O.

Adapted only held-dirfd/base-pin/mkdir/verify/close logic from the reviewed
qualification wrapper. Never writes its synthetic capture or adopts existing dirs.
"""
from dataclasses import dataclass
import math
from pathlib import PurePosixPath
import re
import stat

@dataclass(frozen=True)
class BasePin:
    device:int
    inode:int
    uid:int
    mode:int

def metadata(info):return info.st_dev,info.st_ino,info.st_uid,info.st_mode

def checked_path(base_path,directory_name):
    p=PurePosixPath(base_path) if isinstance(base_path,str) else None
    if (p is None or not p.is_absolute() or str(p)!=base_path or base_path.startswith('//')
        or '..' in p.parts or '\0' in base_path or len(p.parts)>60 or len(base_path.encode())>3800
        or not isinstance(directory_name,str)
        or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',directory_name) is None):
        raise ValueError('Exact approved base and fresh basename required')
    return p/directory_name

class DirectoryError(RuntimeError):
    def __init__(self,stage,*,created=False,close_outcome='not_attempted'):
        self.stage,self.created,self.close_outcome=stage,created,close_outcome
        super().__init__('Private directory setup failed: '+stage)

class OwnedDirectory:
    def __init__(self,*,base_path,base_pin,directory_name,os_api,monotonic):
        self.path=checked_path(base_path,directory_name)
        if (not isinstance(base_pin,BasePin) or type(base_pin.device) is not int or base_pin.device<0
            or type(base_pin.inode) is not int or base_pin.inode<=0
            or type(base_pin.uid) is not int or base_pin.uid<0
            or type(base_pin.mode) is not int or not stat.S_ISDIR(base_pin.mode)
            or base_pin.mode & 0o022):
            raise ValueError('Independent existing base identity required')
        self.base,self.pin,self.name=PurePosixPath(base_path),base_pin,directory_name
        self.os,self.clock=os_api,monotonic
        self.fds=[];self.edges=[];self.fd=None;self.created=False;self.identity=None
        self.spent=False;self.closed=False;self.close_outcome='not_attempted';self.deadline=None
    def remaining(self):
        now=self.clock()
        if not math.isfinite(now) or now>=self.deadline:raise DirectoryError('deadline')
    def call(self,fn,*args,**kwargs):
        self.remaining();value=fn(*args,**kwargs);self.remaining();return value
    def own_open(self,name,flags,**kwargs):
        self.remaining();fd=self.os.open(name,flags,**kwargs);self.fds.append(fd)
        self.remaining();return fd
    def verify(self):
        if self.closed or self.fd is None:raise DirectoryError('closed_or_uncreated')
        for parent,name,child,expected in self.edges:
            actual=self.call(self.os.fstat,child)
            linked=self.call(self.os.stat,name,dir_fd=parent,follow_symlinks=False)
            if metadata(actual)!=expected or metadata(linked)!=expected:raise DirectoryError('changed_edge')
        if metadata(self.call(self.os.fstat,self.fd))!=self.identity:raise DirectoryError('changed_private_directory')
    def create(self,deadline):
        if self.spent:raise DirectoryError('attempt_spent',created=self.created,close_outcome=self.close_outcome)
        self.spent=True
        if isinstance(deadline,bool) or not isinstance(deadline,(int,float)) or not math.isfinite(deadline):
            raise DirectoryError('invalid_deadline')
        self.deadline=deadline;stage='base_identity'
        try:
            if self.call(self.os.getuid)!=self.pin.uid:raise DirectoryError(stage)
            flags=self.os.O_RDONLY|self.os.O_DIRECTORY|self.os.O_NOFOLLOW|self.os.O_CLOEXEC
            parent=self.own_open('/',flags)
            for name in self.base.parts[1:]:
                child=self.own_open(name,flags,dir_fd=parent)
                m=metadata(self.call(self.os.fstat,child))
                if not stat.S_ISDIR(m[3]):raise DirectoryError(stage)
                self.edges.append((parent,name,child,m));parent=child
            if metadata(self.call(self.os.fstat,parent))!=(self.pin.device,self.pin.inode,self.pin.uid,self.pin.mode):
                raise DirectoryError(stage)
            for p,n,c,m in self.edges:
                if metadata(self.call(self.os.fstat,c))!=m or metadata(self.call(self.os.stat,n,dir_fd=p,follow_symlinks=False))!=m:
                    raise DirectoryError('changed_base_edge')
            stage='fresh_directory'
            self.remaining();self.os.mkdir(self.name,0o700,dir_fd=parent);self.created=True;self.remaining()
            named=self.call(self.os.stat,self.name,dir_fd=parent,follow_symlinks=False)
            self.fd=self.own_open(self.name,flags,dir_fd=parent)
            created=self.call(self.os.fstat,self.fd);m=metadata(created)
            if metadata(named)!=m or created.st_uid!=self.pin.uid or created.st_mode!=stat.S_IFDIR|0o700:
                raise DirectoryError('fresh_identity')
            self.identity=m;self.edges.append((parent,self.name,self.fd,m));self.verify()
            return self
        except BaseException as error:
            self.close(raise_error=False)
            if isinstance(error,(KeyboardInterrupt,SystemExit)):raise
            code=error.stage if isinstance(error,DirectoryError) else stage
            raise DirectoryError(code,created=self.created,close_outcome=self.close_outcome) from None
    def close(self,*,raise_error=True):
        if not self.closed:
            self.closed=True;failed=False;interrupt=None
            for fd in reversed(self.fds):
                try:self.os.close(fd)
                except BaseException as error:
                    failed=True
                    if isinstance(error,(KeyboardInterrupt,SystemExit)):interrupt=error
            self.fds=[];self.fd=None;self.close_outcome='uncertain' if failed else 'closed'
            if interrupt is not None:raise interrupt
        if raise_error and self.close_outcome=='uncertain':
            raise DirectoryError('close_uncertain',created=self.created,close_outcome='uncertain')
