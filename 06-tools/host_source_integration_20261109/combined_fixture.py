"""Pinned combined-source fixture helpers. Fake Git is never live admission."""
import ast
from contextlib import contextmanager
import dataclasses
import hashlib
import json
from pathlib import Path
import re
import shlex
import stat
import struct
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest
import inert_source_loader as loader
import inert_host_construction as construction

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
MANIFEST=json.loads((HERE/'combined_binding.json').read_text())
def check(ok,message):
    if not ok:raise RuntimeError(message)
def inputs():
    files={}
    for path,pin in MANIFEST['input_sha256'].items():
        raw=(ROOT/path).read_bytes()
        check(hashlib.sha256(raw).hexdigest()==pin,'Combined input source drift: '+path)
        files[path]=raw
    return files
def compose(files):
    snapshots={p:files[p] for p in loader.PATHS}
    # Execute only pinned offline transformation function, not its write_artifacts/CLI.
    p='06-tools/video_validation_split_20261109/proposal.py'
    tree=ast.parse(files[p])
    ns=dict(HERE=(ROOT/p).parent,hashlib=hashlib,PINS=MANIFEST['lifecycle_original_pins'])
    fun=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='sources')
    exec(compile(ast.Module(body=[fun],type_ignores=[]),'<pinned-lifecycle-transform>','exec'),ns)
    old,new=ns['sources']()
    for name,text in new.items():snapshots['06-tools/'+name]=text.encode()
    for replacement in MANIFEST['exact_replacements']:
        path=replacement['path'];text=snapshots[path].decode()
        check(text.count(replacement['old'])==1,'Combined anchor changed')
        snapshots[path]=text.replace(replacement['old'],replacement['new']).encode()
    for p,pin in MANIFEST['combined_sha256'].items():
        check(hashlib.sha256(snapshots[p]).hexdigest()==pin,'Combined virtual source drift')
    return snapshots

def nodes_module(raw,name,filename,names,namespace):
    tree=ast.parse(raw)
    nodes=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef))
           and n.name in names or isinstance(n,ast.Assign) and any(
               isinstance(t,ast.Name) and t.id in names for t in n.targets)]
    result=ModuleType(name);result.__file__=str(filename);result.__dict__.update(namespace)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<pinned-fixture-'+name+'>','exec'),result.__dict__)
    return result

@contextmanager
def combined_context():
    files=inputs();snapshots=compose(files)
    names=set(loader.NAMES)|{Path(p).stem for p in loader.DEFERRED_PATHS}
    previous={name:sys.modules.pop(name) for name in names if name in sys.modules}
    ids={p:loader.blob_id(raw,'sha1') for p,raw in snapshots.items()}
    def git(*args):
        if args[0]=='rev-parse':out='sha1' if args[1]=='--show-object-format' else 'a'*40
        elif args[0]=='ls-tree':out='\n'.join('100644 blob '+ids[p]+'\t'+p for p in loader.PATHS)
        elif args[0]=='hash-object':out='\n'.join(ids[p] for p in loader.PATHS)
        elif args[0]=='diff':out=''
        else:raise RuntimeError('Unexpected virtual Git command')
        return NS(stdout=out,returncode=0)
    try:
        modules=loader.FixedSourceLoader(root=str(ROOT),git=git,
            read_bytes=lambda p:snapshots[str(Path(p).relative_to(ROOT))],
            registry=sys.modules).load()['modules']
        guard_path='06-tools/host_adb_full_api_spike/test_canonical_boot_guard.py'
        guard=nodes_module(files[guard_path],'guard_fixture',ROOT/guard_path,
            {'check','BEFORE','AFTER','IDENTITY'},
            dict(re=re,hashlib=hashlib))
        fpath='06-tools/host_adb_full_api_spike/test_offline_baseline_adb.py'
        f=nodes_module(files[fpath],'transport_fixture',ROOT/fpath,
            {'PIN','SERIALS','LIST','MOVED','DEST','REMOTE','frame','sf','shell_reply','sync_frame',
             'Clock','Socket','Sink','Harness','AutoSocket'},
            dict(m=modules['offline_baseline_adb'],guard=guard,stat=stat,struct=struct,
                 dataclasses=dataclasses,SimpleNamespace=NS))
        lpath='06-tools/host_adb_full_api_spike/test_linux_adb_probe_dependencies.py'
        proc=nodes_module(files[lpath],'proc_fixture',ROOT/lpath,
            {'HEADER','tcp','statline','PIN','LIMITS','FakeProc'},
            dict(d=modules['linux_adb_probe_dependencies'],f=f,hashlib=hashlib,stat=stat))
        spath='06-tools/host_private_sink_20261109/test_private_video_sink.py'
        import os
        fs=nodes_module(files[spath],'os_fixture',ROOT/spath,{'meta','FakeOS'},
                        dict(os=os,NS=NS,stat=stat))
        cpath='06-tools/host_adb_full_api_spike/test_concrete_caller_cleanup.py'
        def classes(signal,probe):
            modules['run_p85_timed_stock_trial'].signal=signal
            modules['run_p85_guarded_trial'].signal=signal
            class FixtureAllocatedTrial(modules['run_p85_timed_stock_trial'].TimedStockTrial):
                def __init__(self):pass  # Existing Scenario explicitly supplies all fixture state.
                state=modules['stock_c1_sweep'].Sweep.state  # Existing cleanup fixture's real baseline state guard; no envelope choreography.
            return dict(TimedStockTrial=FixtureAllocatedTrial,
                DeadlineTransport=modules['run_p85_timed_stock_trial'].DeadlineTransport,
                KEYS=modules['stock_c1_sweep'].KEYS,MODULE_SHA=modules['stock_c1_sweep'].MODULE_SHA,
                c1=modules['capture_ddic_c1'])
        caller=nodes_module(files[cpath],'caller_fixture',ROOT/cpath,
            {'FakeSignal','MemoryPath','FakeProbe','Scenario'},
            dict(f=f,guard=guard,classes=classes,shlex=shlex,json=json,SimpleNamespace=NS))
        yield NS(files=files,snapshots=snapshots,modules=modules,f=f,proc=proc,fs=fs,caller=caller)
    finally:
        for name in names:sys.modules.pop(name,None)
        sys.modules.update(previous)

class GateGit:
    def __init__(self,ctx,dirty=False,paths=construction.HARDWARE_PATHS):
        self.calls=[];self.dirty=dirty;self.paths=paths
        self.bytes={**ctx.files,**ctx.snapshots,
          construction.HARDWARE_PATHS[-1]:ctx.files[construction.HARDWARE_PATHS[-1]]}
    def run(self,argv,**kw):
        args=argv[3:];self.calls.append(tuple(args));cmd=args[0]
        paths=self.paths
        ids={p:loader.blob_id(self.bytes[p],'sha1') for p in paths}
        if cmd=='rev-parse':out='a'*40
        elif cmd=='ls-tree':out='\n'.join('100644 blob '+ids[p]+'\t'+p for p in paths)
        elif cmd=='hash-object':out='\n'.join(ids[p] for p in paths)
        elif cmd=='diff':return NS(stdout='',returncode=int(self.dirty))
        else:raise RuntimeError('Unexpected original source guard operation')
        return NS(stdout=out,returncode=0)

def scenario(ctx,*,dirty=False):
    # Original Scenario supplies only stage choreography; complete real combined
    # execute/stop_camera/recover/restore/active_window are inherited actual methods.
    s=ctx.caller.Scenario()
    s.os=ctx.fs.FakeOS()
    s.os.nodes={'/':s.os.nodes['/'],'/fixture':s.os.nodes['/approved'],
                '/fixture/private':s.os.nodes['/approved/private']}
    s.proc=ctx.proc.FakeProc(s.h.clock)
    s.gate=GateGit(ctx,dirty)
    ctx.modules['run_p85_guarded_trial'].subprocess=s.gate
    def socket_factory(family,kind):
        raw=s.h.make_socket()
        raw.set_inheritable=lambda value:check(value is False,'Socket must be private')
        return raw
    sink=ctx.modules['private_video_sink']
    params=dict(modules={n:ctx.modules[n] for n in construction.HARDWARE_NAMES},root=str(ROOT),pin=ctx.proc.PIN,
        serials=ctx.f.SERIALS,limits=ctx.proc.LIMITS,proc=s.proc,
        parent_pin=sink.ParentPin(3,3,17),capacity=sink.CapacityPolicy(100,10),
        exact_capture_path=ctx.f.DEST,host_uid=17,os_api=s.os,
        socket_factory=socket_factory,monotonic=s.h.clock,sleep=s.h.clock.sleep)
    s.construct=lambda:ctx.modules['inert_host_construction'].construct(**params)
    # Clear initial reviewed Harness fake setup traffic, then instantiate our actual glue.
    s.h.used.clear();s.h.events.clear()
    if dirty:return s
    s.bundle=s.construct();s.h.adb=s.bundle.adapter;s.h.ready()
    s.run.g=s.ns['DeadlineTransport'](s.run,s.bundle.adapter)
    s.fs[ctx.f.DEST]=s.os.data
    s.run.report.update(s.bundle.source,experiment_id='fixture_capture')
    return s

def evidence_modules(ctx,scenario):
    # Execute original post-load source guard for this separate phase BEFORE
    # importing evidence helpers. This fake Git remains fixture-only authority.
    gate=GateGit(ctx,paths=construction.FINALIZER_PATHS)
    ctx.modules['run_p85_guarded_trial'].subprocess=gate
    proof=ctx.modules['run_p85_guarded_trial'].source_provenance(
        root=str(ROOT),paths=construction.FINALIZER_PATHS,require_clean=True)
    prefix='06-tools/video_validation_split_20261109/'
    a=ModuleType('combined_acceptance');a.__file__=str(ROOT/(prefix+'offline_acceptance.py'))
    exec(compile(ctx.files[prefix+'offline_acceptance.py'],'<pinned-acceptance>','exec'),a.__dict__)
    h=ModuleType('combined_evidence');h.__file__=str(ROOT/(prefix+'host_evidence.py'));h.a=a
    tree=ast.parse(ctx.files[prefix+'host_evidence.py'])
    tree.body=[n for n in tree.body if not(isinstance(n,ast.Import) and
               any(x.name=='offline_acceptance' for x in n.names))]
    exec(compile(tree,'<pinned-host-evidence>','exec'),h.__dict__)
    s=scenario
    class Reader:
        O_RDONLY=0;O_ACCMODE=3;SEEK_CUR=1;SEEK_SET=0
        def __init__(self):self.offset=0;self.calls=[];self.replaced=False
        def getuid(self):return 17
        def fstat(self,fd):
            self.calls.append('fstat')
            node=s.os.nodes[ctx.f.DEST]
            return NS(**{**vars(node),'st_ino':99 if self.replaced else node.st_ino,
                         'st_mtime_ns':1,'st_ctime_ns':1})
        def lseek(self,fd,offset,whence):
            self.offset=(self.offset+offset if whence==1 else offset);return self.offset
        def read(self,fd,count):
            self.calls.append('read');out=bytes(s.os.data[self.offset:self.offset+count])
            self.offset+=len(out);return out
    reader=Reader();a.os=reader;h.os=reader;h.fcntl=NS(F_GETFL=3,fcntl=lambda *args:0)
    return NS(a=a,h=h,reader=reader,proof=proof,
              snapshot=ctx.files[prefix+'video_validator_snapshot.py'])
