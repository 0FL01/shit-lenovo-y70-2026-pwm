"""Narrow byte-bound construction for the separate stock observation.

No CLI, import-time I/O, subprocess, ADB fallback or Trial/main invocation.
External launcher authenticates THIS source before import and independently
pins the exact manifest. A self-generated hash map is not authorization.
"""
import ast
import builtins
from dataclasses import dataclass
import hashlib
import json
import re
import sys
from types import MappingProxyType, ModuleType

SOURCES = MappingProxyType({
    'offline_baseline_adb':'06-tools/host_adb_full_api_spike/offline_baseline_adb.py',
    'linux_adb_probe_dependencies':'06-tools/host_adb_full_api_spike/linux_adb_probe_dependencies.py',
    'private_video_sink':'06-tools/host_private_sink_20261109/private_video_sink.py',
    'fresh_private_directory':'06-tools/host_source_integration_20261109/fresh_private_directory.py',
    'camera_capture_metadata':'06-tools/camera_capture_metadata.py',
    'stock_readonly_probe':'06-tools/stock_observation_readonly_20261110/probe.py',
    'readonly_launch':'06-tools/stock_observation_readonly_20261110/launch.py',
    'prestart_inspection':'06-tools/stock_observation_readonly_20261110/prestart_inspection_v2.py',
    'dsi_trial_transaction':'06-tools/dsi_trial_transaction.py',
    'a9_reproduction':'06-tools/a9_reproduction.py',
    'video_selector':'06-tools/run_dsi_mode_trial.py',
    'protocol_v2':'06-tools/stock_observation_20261110/protocol_v2.py',
    'coordinator':'06-tools/stock_observation_20261110/coordinator.py',
})


def need(value, message='construction_rejected'):
    if not value:raise ValueError(message)


@dataclass(frozen=True)
class Sources:
    modules: object
    provenance: object
    hashes: object
    bootstrap_hashes: object


def load_sources(raw, expected_sha256, *, commit, bootstrap_sha256):
    """Verify entire fixed DAG BEFORE executing any module bytes."""
    need(type(raw) is dict and type(expected_sha256) is dict)
    need(set(raw)==set(expected_sha256)==set(SOURCES))
    need(type(bootstrap_sha256) is dict and set(bootstrap_sha256)=={
        '06-tools/stock_observation_20261110/construction.py',
        '06-tools/stock_observation_20261110/launch.py'})
    need(all(type(x) is str and re.fullmatch('[a-f0-9]{64}',x) for x in bootstrap_sha256.values()))
    need(type(commit) is str and re.fullmatch('[a-f0-9]{40}',commit))
    need(expected_sha256.get('prestart_inspection')=='6429d7f3d7d4e15b603c63ba55ee9437d7797214ca6dd3695e4990dda8832791',
         'unreviewed_inspection_producer')
    need(not set(SOURCES).intersection(sys.modules),'preloaded_project_modules')
    for name in SOURCES:
        need(type(raw[name]) is bytes and 0<len(raw[name])<=512*1024)
        need(type(expected_sha256[name]) is str and re.fullmatch('[a-f0-9]{64}',expected_sha256[name]))
        need(hashlib.sha256(raw[name]).hexdigest()==expected_sha256[name],'source_digest_mismatch')
    loaded={}; original=builtins.__import__
    def fixed_import(name,globals=None,locals=None,fromlist=(),level=0):
        need(level==0,'relative_import_refused')
        if name in SOURCES:
            need(name in loaded,'dependency_order_changed')
            return loaded[name]
        need(name.split('.')[0] in sys.stdlib_module_names,'unbound_import_refused')
        return original(name,globals,locals,fromlist,level)
    try:
        for name,path in SOURCES.items():
            m=ModuleType(name);m.__file__=path;m.__package__=''
            m.__builtins__={**vars(builtins),'__import__':fixed_import}
            loaded[name]=m;sys.modules[name]=m
            if name=='video_selector':
                tree=ast.parse(raw[name],filename=path)
                nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='new_camera_video']
                need(len(nodes)==1 and not nodes[0].decorator_list,'video_selector_definition_changed')
                # Exact function AST from independently verified full source;
                # legacy module top-level/main and unrelated writers never run.
                m.__dict__['re']=re
                code=compile(ast.Module(body=nodes,type_ignores=[]),path,'exec',dont_inherit=True)
            else:code=compile(raw[name],path,'exec',dont_inherit=True)
            exec(code,m.__dict__)
        canonical=json.dumps({**{SOURCES[n]:expected_sha256[n] for n in SOURCES},**bootstrap_sha256},sort_keys=True,separators=(',',':')).encode()
        provenance={'commit':commit,'closure_sha256':hashlib.sha256(canonical).hexdigest()}
        return Sources(MappingProxyType(loaded),MappingProxyType(provenance),MappingProxyType(dict(expected_sha256)),MappingProxyType(dict(bootstrap_sha256)))
    except BaseException:
        for name,m in loaded.items():
            if sys.modules.get(name) is m:del sys.modules[name]
        raise


@dataclass(frozen=True,repr=False)
class Inputs:
    process_pin: object
    proc_limits: object
    serials: tuple
    base_path: str
    base_pin: object
    directory_name: str
    capacity: object
    token: str
    no_concurrent_writers: bool
    no_concurrent_namespace_mutation: bool


class RetainedSink:
    def __init__(self):
        self.attempted=False;self.sink=None;self.created_identity=None;self.failure_facts=None
    def facts(self):
        return self.sink.facts if self.sink is not None else self.failure_facts


@dataclass
class Prepared:
    sources: Sources
    inputs: Inputs
    owned: object
    transport: object
    association: object
    retained: RetainedSink
    clock: object
    sleep: object
    coordinator: object = None
    spent: bool = False

    def select(self):
        """Fresh discovery only on the fixed pinned existing server."""
        need(not self.spent,'selection_attempt_spent');self.spent=True
        g=self.transport;g.preflight();rows={}
        for line in g.host('host:devices-l').splitlines():
            fields=line.split();need(len(fields)>=3,'inventory_shape')
            tids=[f[13:] for f in fields[2:] if f.startswith(b'transport_id:')]
            need(len(tids)==1 and re.fullmatch(rb'[1-9][0-9]{0,19}',tids[0]) and fields[0] not in rows,'inventory_identity')
            rows[fields[0]]=(tids[0].decode('ascii'),fields[1])
        need(all(s in rows and rows[s][1]==b'device' for s in self.inputs.serials),'roles_missing')
        tids=tuple(rows[s][0] for s in self.inputs.serials);need(len(set(tids))==2,'role_alias_collision')
        for tid,serial in zip(tids,self.inputs.serials):need(g.bind(tid)==serial,'role_bind_mismatch')
        m=self.sources.modules
        self.coordinator=m['coordinator'].Coordinator(transport=g,target=tids[0],camera=tids[1],
            serials=self.inputs.serials,parser=m['camera_capture_metadata'],readonly=m['stock_readonly_probe'],
            lock_commands=m['a9_reproduction'].lock_commands,new_camera_video=m['video_selector'].new_camera_video,
            native_state=m['dsi_trial_transaction'].native_state,inspection=m['prestart_inspection'],owned_directory=self.owned,
            retained_sink=self.retained,source=dict(self.sources.provenance),token=self.inputs.token,
            clock=self.clock,sleep=self.sleep,byte_cap=self.inputs.capacity.max_video_bytes)
        self.coordinator.persist('source-closure',{'source':dict(self.sources.provenance),
            'sha256':{**{SOURCES[n]:self.sources.hashes[n] for n in SOURCES},**self.sources.bootstrap_hashes}})
        return self.coordinator

    def close(self):
        self.owned.close()


def prepare(sources, inputs, *, os_api, socket_factory, proc, monotonic, sleep):
    """Create one fresh host directory; no device/server access until select()."""
    need(type(sources) is Sources and type(inputs) is Inputs)
    need(set(sources.modules)==set(SOURCES))
    m=sources.modules;dep=m['linux_adb_probe_dependencies'];adb=m['offline_baseline_adb']
    fm=m['fresh_private_directory'];sm=m['private_video_sink']
    need(type(inputs.process_pin) is dep.VerifiedPin and type(inputs.proc_limits) is dep.ProcLimits)
    need(type(inputs.base_pin) is fm.BasePin and type(inputs.capacity) is sm.CapacityPolicy)
    need(type(inputs.serials) is tuple and len(inputs.serials)==2 and len(set(inputs.serials))==2)
    need(all(type(x) is bytes and re.fullmatch(rb'[A-Za-z0-9_.-]{1,256}',x) and x!=b'unknown' for x in inputs.serials))
    need(inputs.no_concurrent_writers is True and inputs.no_concurrent_namespace_mutation is True)
    need(type(inputs.token) is str and re.fullmatch('[a-z][a-z0-9_]{7,63}',inputs.token))
    owned=fm.OwnedDirectory(base_path=inputs.base_path,base_pin=inputs.base_pin,
        directory_name=inputs.directory_name,os_api=os_api,monotonic=monotonic)
    try:
        owned.create(monotonic()+12)
        parent=sm.ParentPin(owned.identity[0],owned.identity[1],owned.identity[2])
        destination=str(owned.path/'capture.mp4');retained=RetainedSink()
        def create_sink(path,deadline,*,observed_size):
            need(not retained.attempted,'sink_attempt_spent');retained.attempted=True
            need(path==destination,'sink_destination_changed')
            factory=sm.PrivateSinkFactory(exact_path=destination,parent_pin=parent,observed_size=observed_size,
                capacity=inputs.capacity,os_api=os_api,monotonic=monotonic)
            try:sink=factory(path,deadline)
            except BaseException as error:
                retained.failure_facts=getattr(error,'facts',None);raise
            retained.sink=sink;retained.created_identity=tuple(sink.file_meta)
            return sink
        association=dep.LinuxAssociation(pin=inputs.process_pin,limits=inputs.proc_limits,proc=proc,monotonic=monotonic)
        transport=adb.OfflineBaselineADB(expected_process=inputs.process_pin.process,
            expected_serials=inputs.serials,acquire=association.acquire_process,
            make_socket=dep.make_socket_factory(socket_factory=socket_factory,monotonic=monotonic),
            create_sink=create_sink,expected_destination=destination,expected_uid=inputs.base_pin.uid,
            monotonic=monotonic,sleep=sleep)
        return Prepared(sources,inputs,owned,transport,association,retained,monotonic,sleep)
    except BaseException:
        owned.close(raise_error=False);raise
