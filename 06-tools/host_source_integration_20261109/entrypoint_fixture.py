"""Fake OS/Path/main wiring for the inactive entrypoint. Never real --execute."""
import contextlib
import errno
import io
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace as NS
from combined_fixture import *

def entry_scenario(ctx):
    s=scenario(ctx)
    qpath='06-tools/host_private_sink_20261109/test_qualify_private_sink.py'
    q=nodes_module(ctx.files[qpath],'qualified_os_fixture',ROOT/qpath,{'QualificationOS'},
        dict(FakeOS=ctx.fs.FakeOS,meta=ctx.fs.meta,RESERVE_BYTES=1024*1024,
             errno=errno,os=os,stat=stat))
    class FileSystem(q.QualificationOS):
        O_ACCMODE=os.O_ACCMODE;SEEK_CUR=os.SEEK_CUR;SEEK_SET=os.SEEK_SET
        def __init__(self):
            super().__init__()
            self.nodes={'/':self.nodes['/'],'/fixture':self.nodes['/approved/private']}
            self.buffers={ctx.f.DEST:self.data};self.next_inode=10;self.path_events=[]
        def open(self,name,flags,mode=0o777,dir_fd=None):
            p=self.path(name,dir_fd);was=p in self.nodes
            fd=super().open(name,flags,mode,dir_fd)
            if not was:
                self.next_inode+=1;self.nodes[p].st_ino=self.next_inode
                self.buffers.setdefault(p,bytearray())
            return fd
        def write(self,fd,data):
            p=self.fds[fd];before=self.data;self.data=self.buffers.setdefault(p,bytearray())
            try:return super().write(fd,data)
            finally:self.data=before
        def read(self,fd,count):
            self.event('read');p=self.fds[fd];start=self.read_offsets[fd]
            data=self.buffers.get(p,bytearray())[start:start+count]
            self.read_offsets[fd]+=len(data);return bytes(data)
        def lseek(self,fd,offset,whence):
            self.read_offsets[fd]=(self.read_offsets[fd]+offset if whence==os.SEEK_CUR else offset)
            return self.read_offsets[fd]
        def fstat(self,fd):
            value=super().fstat(fd);value.st_mtime_ns=1;value.st_ctime_ns=1;return value
    s.entry_os=fs=FileSystem()
    class MemoryPath:
        def __init__(self,path):self.path=str(path)
        def __str__(self):return self.path
        def __fspath__(self):return self.path
        def __truediv__(self,name):return MemoryPath(self.path.rstrip('/')+'/'+name)
        def joinpath(self,name):return self/name
        @property
        def parent(self):return MemoryPath(self.path.rsplit('/',1)[0] or '/')
        def exists(self):return self.path in fs.nodes
        def mkdir(self,mode=0o777,parents=False,exist_ok=False):
            fs.path_events.append(('mkdir',self.path))
            if self.exists():
                if exist_ok:return
                raise FileExistsError('fixture collision')
            fs.next_inode+=1;fs.nodes[self.path]=ctx.fs.meta(fs.next_inode,stat.S_IFDIR|mode)
        def write_text(self,text):
            fs.path_events.append(('write_text',self.path))
            fs.buffers[self.path]=bytearray(text.encode())
            if self.path not in fs.nodes:
                fs.next_inode+=1;fs.nodes[self.path]=ctx.fs.meta(fs.next_inode,stat.S_IFREG|0o600)
            fs.nodes[self.path].st_size=len(text.encode());return len(text)
        def read_bytes(self):return bytes(fs.buffers[self.path])
        def chmod(self,mode):fs.nodes[self.path].st_mode=(fs.nodes[self.path].st_mode&~0o777)|mode
        def stat(self):return fs.nodes[self.path]
        def open(self,mode):
            if mode!='xb' or self.exists():raise FileExistsError('fixture exclusive file')
            self.write_text('');path=self.path
            class Writer:
                def __enter__(self):return self
                def write(self,data):
                    fs.buffers[path].extend(data);fs.nodes[path].st_size+=len(data);return len(data)
                def __exit__(self,*args):pass
            return Writer()
    s.memory_path=MemoryPath
    ep=ctx.modules['host_entrypoint'];fresh=ctx.modules['fresh_private_directory']
    all_bytes={**ctx.files,**ctx.snapshots}
    s.loaded=dict(modules=ctx.modules,source_commit='a'*40,
        source_blob_ids={p:loader.blob_id(all_bytes[p],'sha1') for p in loader.PATHS},
        verified_source_bytes={p:all_bytes[p] for p in loader.PATHS},live_admitted=False)
    s.inputs=ep.HostInputs(base_path='/fixture',base_pin=fresh.BasePin(3,3,17,stat.S_IFDIR|0o700),
        directory_name='private',process_pin=ctx.proc.PIN,expected_serials=ctx.f.SERIALS,
        proc_limits=ctx.proc.LIMITS,capacity=ctx.modules['private_video_sink'].CapacityPolicy(100,10),
        no_concurrent_writers=True,no_concurrent_namespace_mutation=True)
    def factory(family,kind):
        raw=s.h.make_socket();raw.set_inheritable=lambda value:check(value is False,'Inheritable socket')
        return raw
    s.dependencies=ep.HostDependencies(os_api=fs,socket_factory=factory,proc=s.proc,
        monotonic=s.h.clock,sleep=s.h.clock.sleep,fcntl_api=NS(F_GETFL=3,fcntl=lambda *args:0))
    s.gate=GateGit(ctx,paths=construction.FINALIZER_PATHS)
    # Git fixture honours every actual requested subset; no sourceguard replacement.
    original_run=s.gate.run
    def git_run(argv,**kwargs):
        args=argv[3:]
        if args[0] in ('ls-tree','hash-object','diff'):
            s.gate.paths=tuple(args[args.index('--')+1:])
        return original_run(argv,**kwargs)
    ctx.modules['run_p85_guarded_trial'].subprocess=NS(run=git_run)
    s.h.used.clear();s.h.events.clear();s.proc.calls.clear()
    original_prepare=ep.prepare
    def record_prepare(*args):
        s.prepared=original_prepare(*args)
        return s.prepared
    ep.prepare=record_prepare
    timed=ctx.modules['run_p85_timed_stock_trial'];timed.Path=MemoryPath
    stock=ctx.modules['stock_c1_sweep']
    s.factory_calls=[]
    def caller(g,target,camera,experiment_id,out,private,**kw):
        s.factory_calls.append((g,target,camera,experiment_id,str(out),str(private),kw))
        s.h.adb=g;s.h.ready()
        r=s.run;r.g=ctx.modules['run_p85_timed_stock_trial'].DeadlineTransport(r,g)
        r.private=private;r.out=out
        r.save=lambda:stock.Sweep.save(r)
        return r
    timed.TimedStockTrial=caller
    original_signal=s.signal.signal
    s.signal.SIGINT=2;s.signal.SIGTERM=15;s.signal.SIGHUP=1;s.abort_handlers={}
    def signal(signum,handler):
        if signum==s.signal.SIGALRM:return original_signal(signum,handler)
        s.abort_handlers[signum]=handler
    s.signal.signal=signal
    def main(*,execute=True):
        old_argv=sys.argv[:]
        sys.argv=['fixture','7','8','--stock-only','--experiment-id','fixture_capture','--output','/fixture/output']
        if execute:sys.argv.append('--execute')
        output=io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                timed.main(host_inputs=s.inputs,verified_sources=s.loaded,host_dependencies=s.dependencies)
        finally:sys.argv=old_argv
        return output.getvalue()
    s.main=main
    return s
