"""Inactive fixed-source loader prototype. No CLI, transport, or automatic I/O.

Callers inject Git, reads, and module registry. Tests use only fakes.
A future real launcher must be externally pinned BEFORE executing this module.
This does not grant live admission or replace the original post-load source guard.
"""
import builtins
import hashlib
import importlib.util
from pathlib import PurePosixPath
import re
import sys
from types import ModuleType

BASELINE = tuple('06-tools/'+n+'.py' for n in (
    'run_p85_guarded_trial','p85_guarded_trial','stock_c1_sweep','capture_ddic_c1',
    'p85_single_bit_plan','dsi_trial_transaction','a9_reproduction',
    'camera_capture_metadata','run_dsi_mode_trial','guarded_adb_socket',
    'p85_batched_envelope','run_p85_batched_trial','run_p85_timed_stock_trial'))
DAG = (
    ('a9_reproduction','06-tools/a9_reproduction.py'),
    ('capture_ddic_c1','06-tools/capture_ddic_c1.py'),
    ('dsi_trial_transaction','06-tools/dsi_trial_transaction.py'),
    ('p85_single_bit_plan','06-tools/p85_single_bit_plan.py'),
    ('camera_capture_metadata','06-tools/camera_capture_metadata.py'),
    ('run_dsi_mode_trial','06-tools/run_dsi_mode_trial.py'),
    ('guarded_adb_socket','06-tools/guarded_adb_socket.py'),
    ('stock_c1_sweep','06-tools/stock_c1_sweep.py'),
    ('p85_guarded_trial','06-tools/p85_guarded_trial.py'),
    ('run_p85_guarded_trial','06-tools/run_p85_guarded_trial.py'),
    ('p85_batched_envelope','06-tools/p85_batched_envelope.py'),
    ('run_p85_batched_trial','06-tools/run_p85_batched_trial.py'),
    ('run_p85_timed_stock_trial','06-tools/run_p85_timed_stock_trial.py'),
    ('offline_baseline_adb','06-tools/host_adb_full_api_spike/offline_baseline_adb.py'),
    ('linux_adb_probe_dependencies','06-tools/host_adb_full_api_spike/linux_adb_probe_dependencies.py'),
    ('private_video_sink','06-tools/host_private_sink_20261109/private_video_sink.py'),
    ('inert_host_construction','06-tools/host_source_integration_20261109/inert_host_construction.py'),
    ('fresh_private_directory','06-tools/host_source_integration_20261109/fresh_private_directory.py'),
    ('host_entrypoint','06-tools/host_source_integration_20261109/host_entrypoint.py'),
)
SELF_PATH='06-tools/host_source_integration_20261109/inert_source_loader.py'
DEFERRED_PATHS=('06-tools/video_validation_split_20261109/offline_acceptance.py',
                '06-tools/video_validation_split_20261109/host_evidence.py')
PATHS=BASELINE+tuple(p for _,p in DAG if p not in BASELINE)+(SELF_PATH,)+DEFERRED_PATHS
NAMES=frozenset(n for n,_ in DAG)

def require(ok, reason):
    if not ok:raise RuntimeError(reason)

def blob_id(raw, algorithm):
    return hashlib.new(algorithm,b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()

class FixedSourceLoader:
    def __init__(self, *, root, git, read_bytes, registry):
        path=PurePosixPath(root)
        require(path.is_absolute() and str(path)==root and '..' not in path.parts,
                'Exact absolute root required')
        self.root,self.git,self.read,self.registry=root,git,read_bytes,registry
        self.spent=False

    def prepare(self):
        """Original scoped HEAD/tree/hash/diff semantics plus raw-byte binding."""
        def git(*args):
            result=self.git(*args)
            require(result.returncode==0,'Git source query failed')
            return result.stdout.strip()
        commit=git('rev-parse','--verify','HEAD')
        require(re.fullmatch(r'[0-9a-f]{40,64}',commit) is not None,'Invalid source commit')
        rows=git('ls-tree',commit,'--',*PATHS).splitlines()
        blobs={}
        for row in rows:
            match=re.fullmatch(r'[0-7]+ blob ([0-9a-f]{40,64})\t(.+)',row)
            require(match is not None and match[2] in PATHS,'Unexpected source tree entry')
            require(match[2] not in blobs,'Duplicate source tree entry')
            blobs[match[2]]=match[1]
        actual=git('hash-object','--',*PATHS).splitlines()
        require(len(actual)==len(PATHS),'Incomplete source content identities')
        diff=self.git('diff','--quiet',commit,'--',*PATHS)
        require(diff.returncode in (0,1),'Source diff failed')
        require(set(blobs)==set(PATHS) and dict(zip(PATHS,actual))==blobs
                and diff.returncode==0,'Relevant sources not clean tracked HEAD blobs')
        algorithm=git('rev-parse','--show-object-format')
        require(algorithm in ('sha1','sha256'),'Unsupported Git object format')
        snapshot={}
        for path in PATHS:
            raw=self.read(self.root+'/'+path)
            require(type(raw) is bytes,'Source must be exact bytes')
            require(blob_id(raw,algorithm)==blobs[path],'Raw source bytes differ from HEAD blob')
            snapshot[path]=raw
        return commit,blobs,snapshot

    def load(self):
        """Explicit byte execution only; never imports main/starts runtime."""
        require(not self.spent,'Loader attempt already spent')
        self.spent=True
        require(not NAMES.intersection(self.registry),'Preloaded project module refused')
        commit,blobs,snapshot=self.prepare()
        # Reject late preloading before any project code executes.
        require(not NAMES.intersection(self.registry),'Late preloaded project module refused')
        loaded={}
        original_import=builtins.__import__
        def fixed_import(name,globals=None,locals=None,fromlist=(),level=0):
            if level==0 and name in NAMES:
                require(name in loaded,'Fixed dependency order violated')
                return loaded[name]
            require(level==0 and name.split('.')[0] in sys.stdlib_module_names,
                    'Unexpected non-stdlib dependency')
            return original_import(name,globals,locals,fromlist,level)
        for name,path in DAG:
            origin=self.root+'/'+path
            module=ModuleType(name)
            module.__file__=origin
            module.__spec__=importlib.util.spec_from_loader(name,loader=None,origin=origin)
            module.__package__=''
            module.__builtins__={**vars(builtins),'__import__':fixed_import}
            self.registry[name]=module
            loaded[name]=module
            exec(compile(snapshot[path],origin,'exec',dont_inherit=True),module.__dict__)
            require(self.registry.get(name) is module and module.__file__==origin
                    and module.__spec__.origin==origin,'Module origin/registry changed')
        return {'source_commit':commit,'source_blob_ids':blobs,'modules':loaded,
                'live_admitted':False,'verified_source_bytes':snapshot}
