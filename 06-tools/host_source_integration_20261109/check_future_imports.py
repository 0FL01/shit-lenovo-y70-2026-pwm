"""Isolated intended-source IMPORT-ONLY fixture; virtual Git is NOT admission."""
import ast
import builtins
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('fixture_inert_loader',HERE/'inert_source_loader.py')
loader_module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader_module)
# Explicit test-only source reader; --current has no baseline fallback.
sys.path.insert(0,str(HERE))
from replay_source_fixture import intended_sources, BINDING
sys.path.pop(0)
snapshot=intended_sources(current='--current' in sys.argv[1:])
binding={'files':BINDING['hardware_source_sha256']}
if set(snapshot)!=set(loader_module.PATHS):raise RuntimeError('Wrong fixed source closure')
# Inspect/preload only normal stdlib imports before the no-I/O interval.
for name,relative in loader_module.DAG:
    tree=ast.parse(snapshot[relative])
    for node in tree.body:
        names=([n.name for n in node.names] if isinstance(node,ast.Import)
               else [node.module] if isinstance(node,ast.ImportFrom) else [])
        for imported in names:
            if imported in loader_module.NAMES:continue
            if imported.split('.')[0] not in sys.stdlib_module_names:
                raise RuntimeError('Unexpected import closure')
            importlib.import_module(imported)
if loader_module.NAMES.intersection(sys.modules):
    raise RuntimeError('Project module preloaded in isolated fixture')
ids={p:loader_module.blob_id(raw,'sha1') for p,raw in snapshot.items()}
calls=[];resolutions=[]
def git(*args):
    calls.append(args);cmd=args[0]
    if cmd=='rev-parse':out='sha1' if args[1]=='--show-object-format' else 'a'*40
    elif cmd=='ls-tree':out='\n'.join('100644 blob '+ids[p]+'\t'+p for p in loader_module.PATHS)
    elif cmd=='hash-object':out='\n'.join(ids[p] for p in loader_module.PATHS)
    elif cmd=='diff':out=''
    else:raise RuntimeError('Unexpected virtual Git command')
    return SimpleNamespace(stdout=out,returncode=0)
def read(path):
    prefix=str(ROOT)+'/'
    if not path.startswith(prefix):raise RuntimeError('Unexpected source read')
    return snapshot[path[len(prefix):]]
def deny(*args,**kwargs):raise RuntimeError('I/O forbidden during import-only fixture')
def resolve(path,*args,**kwargs):
    text=str(path)
    if text!=str(ROOT/'06-tools/run_dsi_mode_trial.py'):
        raise RuntimeError('Unexpected path resolution')
    resolutions.append('run_dsi_mode_trial.__file__')
    return path
audit_active=False
def audit(event,args):
    if audit_active and (event=='open' or event.startswith('socket.') or event in
                        ('subprocess.Popen','os.system','os.fork','os.posix_spawn','os.exec','os.spawn')):
        raise RuntimeError('Forbidden audited I/O during import fixture')
sys.addaudithook(audit)
# Real sys.modules is needed by dataclass. No caller/adapter/sink instances are created.
with patch.object(socket,'socket',deny),patch.object(subprocess,'Popen',deny), \
     patch.object(subprocess,'run',deny),patch.object(os,'system',deny), \
     patch.object(os,'open',deny),patch.object(builtins,'open',deny), \
     patch.object(Path,'resolve',resolve):
    audit_active=True
    result=loader_module.FixedSourceLoader(root=str(ROOT),git=git,read_bytes=read,
                                         registry=sys.modules).load()
    modules=result['modules']
    if not issubclass(modules['run_p85_timed_stock_trial'].TimedStockTrial,
                      modules['run_p85_guarded_trial'].Trial):
        raise RuntimeError('Actual caller inheritance broken')
    if modules['private_video_sink'].SinkIdentity is not modules['offline_baseline_adb'].SinkIdentity:
        raise RuntimeError('Dataclass transport/sink identity split')
    if modules['run_p85_timed_stock_trial'].SOURCE_FILES!=loader_module.BASELINE:
        raise RuntimeError('Original thirteen source contract changed')
    if modules['run_p85_timed_stock_trial'].ACTIVE_SECONDS!=37.0:
        raise RuntimeError('Timing constant changed')
    if modules['p85_guarded_trial'].LIVE_ENABLED is not False:
        raise RuntimeError('Offline guard changed')
    for name,relative in loader_module.DAG:
        if modules[name].__file__!=str(ROOT/relative):
            raise RuntimeError('Wrong actual module origin')
    audit_active=False
# Original post-load source_provenance NOT called, real expanded Git gate still fails.
print(json.dumps(dict(status='import_only_pass',modules=len(loader_module.DAG),
    real_project_bytes=True,virtual_git=True,tracked_source_admission=False,
    caller_or_adapter_instances=0,device_services=0,
    private_sink_created=False,faked_path_resolutions=resolutions,
    source_sha256=binding['files']),sort_keys=True))
