"""Inactive host entrypoint glue. No CLI, auto-start, patching, or default I/O.

Bootstrap must externally pin the loader before project execution. Sources must
already contain the separately reviewed patches in clean tracked HEAD.
"""
from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import sys
from types import ModuleType
from fresh_private_directory import OwnedDirectory, checked_path
import inert_host_construction as construction

HARDWARE_PATHS=construction.HARDWARE_PATHS
FINALIZER_PATHS=construction.FINALIZER_PATHS
FINALIZER_MODULES=(('offline_acceptance','06-tools/video_validation_split_20261109/offline_acceptance.py'),
                   ('host_evidence','06-tools/video_validation_split_20261109/host_evidence.py'))
REQUIRED_RUNTIME_SHA256 = {'06-tools/run_p85_guarded_trial.py': 'fba1ec5dbb0f7592a4d0a3167589dadac2130370cbf886cecc1d588772fa97a5', '06-tools/run_p85_timed_stock_trial.py': 'a50f04c23b306812dfd0b74d3cbe8f81d28ba0bbc74bb5f9a7c9d0bbfa10ff1a', '06-tools/stock_c1_sweep.py': '1c105480c1ec7abded156f16cf96a98719f0528620b176698dc4226bf933a0d4', '06-tools/host_adb_full_api_spike/offline_baseline_adb.py': '17b2cc726497e95e16414192c808fb3eed64cbe64ed87fba39710685a818cf51'}

# Explicit AA profile. P85 path/module set remains unchanged.
AA_HARDWARE_PATHS=HARDWARE_PATHS+('06-tools/aa_threshold_trial.py','06-tools/run_aa_timed_stock_trial.py','06-tools/aa_acquisition_validation.py')
AA_FINALIZER_MODULES=(('aa_video_validation','06-tools/aa_video_validation.py'),)
AA_FINALIZER_PATHS=AA_HARDWARE_PATHS+tuple(p for _,p in AA_FINALIZER_MODULES)+(    '06-tools/video_validation_split_20261109/video_validator_snapshot.py',)
AA_RUNTIME_SHA256 = {'06-tools/aa_threshold_trial.py': 'a6a495c5d3d363717c44546e93eb035eaa5c91ab93a3c200a1e7a8a09837e1d7', '06-tools/run_aa_timed_stock_trial.py': '4b1893dde6520bc17ba1f5e27c48d328839b5c2790ab9d9c85637fe5bd9d291b', '06-tools/aa_acquisition_validation.py': 'ae9d34aca8833ca6dd1d04341196d710c40d08ed7932072a12c5657f5b9172a4'}

@dataclass(frozen=True)
class HostInputs:
    base_path:str
    base_pin:object
    directory_name:str
    process_pin:object
    expected_serials:tuple
    proc_limits:object
    capacity:object
    no_concurrent_writers:bool
    no_concurrent_namespace_mutation:bool

@dataclass(frozen=True)
class HostDependencies:
    os_api:object
    socket_factory:object
    proc:object
    monotonic:object
    sleep:object
    fcntl_api:object

def require(ok,message):
    if not ok:raise RuntimeError(message)

def private_path(inputs):
    require(isinstance(inputs,HostInputs),'Explicit private host inputs required')
    return Path(str(checked_path(inputs.base_path,inputs.directory_name)))

def source_gate(loaded,*,finalizer=False):
    modules=loaded['modules'];is_aa=loaded.get('profile')=='aa'
    paths=(AA_FINALIZER_PATHS if finalizer else AA_HARDWARE_PATHS) if is_aa else (FINALIZER_PATHS if finalizer else HARDWARE_PATHS)
    root=Path(modules['run_p85_timed_stock_trial'].__file__).resolve().parents[1]
    # This is the ORIGINAL source guard, not a fixture flag or replacement checker.
    proof=modules['run_p85_guarded_trial'].source_provenance(root=root,paths=paths,require_clean=True)
    require(proof['source_commit']==loaded['source_commit'] and
            all(proof['source_blob_ids'].get(p)==loaded['source_blob_ids'].get(p) for p in paths),
            'Loaded bytes and post-load source gate differ')
    for path in paths:
        raw=loaded['verified_source_bytes'].get(path);identity=proof['source_blob_ids'][path]
        require(type(raw) is bytes and len(identity) in (40,64),'Exact source bytes required')
        algorithm='sha1' if len(identity)==40 else 'sha256'
        require(hashlib.new(algorithm,b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==identity,
                'Deferred/loaded source bytes changed after verification')
    require(len(REQUIRED_RUNTIME_SHA256)==4,'Reviewed intended runtime identity missing')
    for path,expected in REQUIRED_RUNTIME_SHA256.items():
        raw=loaded['verified_source_bytes'].get(path)
        require(type(raw) is bytes and hashlib.sha256(raw).hexdigest()==expected,
                'Required reviewed runtime patches are not present')
    if is_aa:
        require(set(AA_RUNTIME_SHA256)==set(AA_HARDWARE_PATHS)-set(HARDWARE_PATHS),'AA reviewed identity closure missing')
        for path,expected in AA_RUNTIME_SHA256.items():
            require(hashlib.sha256(loaded['verified_source_bytes'][path]).hexdigest()==expected,'AA reviewed runtime bytes changed')
    return root,proof

class PreparedHost:
    def __init__(self,owned,bundle,loaded,inputs,deps):
        self.owned,self.bundle,self.loaded,self.inputs,self.deps=owned,bundle,loaded,inputs,deps
        self.private=Path(str(owned.path));self.adapter=bundle.adapter
        self.finalizer_attempted=False;self.evidence=None
    def close(self):self.owned.close()
    def _finalizer_modules(self):
        source_gate(self.loaded,finalizer=True)
        finalizers=AA_FINALIZER_MODULES if self.loaded.get('profile')=='aa' else FINALIZER_MODULES
        names={name for name,_ in finalizers}
        require(not names.intersection(sys.modules),'Preloaded finalizer modules refused')
        # Exactly two fixed deferred modules. No working-tree import fallback.
        import builtins
        original_import=builtins.__import__;made={}
        def fixed_import(name,globals=None,locals=None,fromlist=(),level=0):
            if name=='aa_acquisition_validation' and self.loaded.get('profile')=='aa':
                require(level==0,'No relative acquisition imports')
                return self.loaded['modules'][name]
            if name in names:
                require(level==0 and name in made,'Finalizer dependency order changed')
                return made[name]
            require(level==0 and name.split('.')[0] in sys.stdlib_module_names,'Unexpected finalizer dependency')
            return original_import(name,globals,locals,fromlist,level)
        root=Path(self.loaded['modules']['run_p85_timed_stock_trial'].__file__).resolve().parents[1]
        for name,path in finalizers:
            raw=self.loaded['verified_source_bytes'][path]
            module=ModuleType(name);origin=str(root/path)
            module.__file__=origin;module.__spec__=importlib.util.spec_from_loader(name,loader=None,origin=origin)
            module.__package__='';module.__builtins__={**vars(builtins),'__import__':fixed_import}
            sys.modules[name]=module;made[name]=module
            exec(compile(raw,origin,'exec',dont_inherit=True),module.__dict__)
            require(sys.modules[name] is module and module.__file__==origin and module.__spec__.origin==origin,
                    'Finalizer module origin changed')
            module.os=self.deps.os_api
        made['aa_video_validation' if self.loaded.get('profile')=='aa' else 'host_evidence'].fcntl=self.deps.fcntl_api
        return made
    def _write_evidence(self,data):
        api=self.deps.os_api;fd=None;error=None
        try:
            fd=api.open('source-evidence.json',api.O_WRONLY|api.O_CREAT|api.O_EXCL|
                        api.O_NOFOLLOW|api.O_CLOEXEC,0o600,dir_fd=self.owned.fd)
            info=api.fstat(fd)
            require(info.st_uid==self.inputs.base_pin.uid and
                    info.st_mode==stat.S_IFREG|0o600 and info.st_nlink==1 and info.st_size==0,
                    'Private evidence file identity rejected')
            view=memoryview(data)
            while view:
                count=api.write(fd,view)
                require(type(count) is int and 0<count<=len(view),'Evidence write failed')
                view=view[count:]
        except BaseException as caught:error=caught
        finally:
            if fd is not None:
                try:api.close(fd)
                except BaseException as caught:error=error or caught
        if error:raise error
    def finalize(self,run,acquisition_raw):
        require(not self.finalizer_attempted,'Finalizer attempt already spent')
        self.finalizer_attempted=True
        require(self.inputs.no_concurrent_writers is True,'Explicit trusted no-writer assertion required')
        require(json.loads(acquisition_raw)==run.report,'Saved acquisition differs from caller report')
        made=self._finalizer_modules();h=made['aa_video_validation' if self.loaded.get('profile')=='aa' else 'host_evidence'];ret=self.bundle.retained
        require(ret.sink is not None and ret.created_identity is not None,'No owned sink identity for evidence')
        # New host-only inspection deadline, not renewal of any device/alarm guard.
        self.owned.deadline=self.deps.monotonic()+12.0;self.owned.verify()
        api=self.deps.os_api;fd=None;result=None;error=None
        try:
            fd=api.open('capture.mp4',api.O_RDONLY|api.O_NOFOLLOW|api.O_CLOEXEC,dir_fd=self.owned.fd)
            result=h.source_evidence(acquisition_raw,fd,ret.facts(),
                expected_source_identity=ret.created_identity,no_concurrent_writers=True)
            self.owned.verify()
        except BaseException as caught:error=caught
        finally:
            if fd is not None:
                try:api.close(fd)
                except BaseException as caught:error=error or caught
        if error:raise error
        self._write_evidence((json.dumps(result,sort_keys=True,separators=(',',':'))+'\n').encode())
        self.evidence=result
        return result

def prepare(loaded,inputs,deps):
    root,proof=source_gate(loaded)
    require(isinstance(inputs,HostInputs) and isinstance(deps,HostDependencies),'Explicit host configuration required')
    require(inputs.no_concurrent_writers is True,'Explicit trusted no-writer assertion required')
    private_path(inputs)
    require(inputs.no_concurrent_namespace_mutation is True,'Explicit trusted namespace stability required')
    owned=OwnedDirectory(base_path=inputs.base_path,base_pin=inputs.base_pin,
        directory_name=inputs.directory_name,os_api=deps.os_api,monotonic=deps.monotonic)
    try:
        owned.create(deps.monotonic()+12.0)
        sink=loaded['modules']['private_video_sink']
        parent=sink.ParentPin(owned.identity[0],owned.identity[1],owned.identity[2])
        hardware={name:loaded['modules'][name] for name in construction.HARDWARE_NAMES}
        bundle=construction.construct(modules=hardware,root=str(root),
            pin=inputs.process_pin,serials=inputs.expected_serials,limits=inputs.proc_limits,
            proc=deps.proc,parent_pin=parent,capacity=inputs.capacity,
            exact_capture_path=str(owned.path/'capture.mp4'),host_uid=inputs.base_pin.uid,
            os_api=deps.os_api,socket_factory=deps.socket_factory,monotonic=deps.monotonic,sleep=deps.sleep)
        return PreparedHost(owned,bundle,loaded,inputs,deps)
    except BaseException:
        owned.close(raise_error=False)
        raise
