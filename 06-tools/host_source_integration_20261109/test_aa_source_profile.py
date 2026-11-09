"""Source-only AA closure tests. Fake Git answers; no transport/device I/O."""
import hashlib
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=r'''
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import inert_source_loader as loader
root=Path(sys.argv[1]);dirty=sys.argv[2]=='dirty'
files={p:(root/p).read_bytes() for p in loader.AA_PATHS}
def git(*args):
    if args[0]=='rev-parse':out='sha1' if args[1]=='--show-object-format' else 'a'*40
    elif args[0]=='ls-tree':out='\n'.join('100644 blob '+loader.blob_id(files[p],'sha1')+'\t'+p for p in args[3:])
    elif args[0]=='hash-object':out='\n'.join(loader.blob_id(files[p],'sha1') for p in args[2:])
    elif args[0]=='diff':return NS(returncode=int(dirty),stdout='')
    return NS(returncode=0,stdout=out)
obj=loader.FixedSourceLoader(root=str(root),git=git,read_bytes=lambda p:files[str(Path(p).relative_to(root))],registry=sys.modules,profile='aa')
try:loaded=obj.load()
except RuntimeError:
    assert dirty and 'run_aa_timed_stock_trial' not in sys.modules
    print('dirty rejected before module execution');sys.exit(0)
assert not dirty
mods=loaded['modules'];host=mods['host_entrypoint']
assert loaded['profile']=='aa'
assert issubclass(mods['run_aa_timed_stock_trial'].AATimedTrial,mods['run_p85_timed_stock_trial'].TimedStockTrial)
assert set(host.AA_HARDWARE_PATHS).issubset(loader.AA_PATHS)
assert set(host.AA_FINALIZER_PATHS).issubset(loader.AA_PATHS)
assert len(loader.PATHS)==22 and len(loader.BASELINE)==13
assert len(loader.AA_PATHS)==len(set(loader.AA_PATHS))
assert set(host.AA_RUNTIME_SHA256)==set(host.AA_HARDWARE_PATHS)-set(host.HARDWARE_PATHS)
import hashlib
for p,digest in host.AA_RUNTIME_SHA256.items():assert hashlib.sha256(files[p]).hexdigest()==digest
# Execute real AA deferred-module routing with an explicit offline provenance fixture.
import os,fcntl
mods['run_p85_guarded_trial'].source_provenance=lambda **kwargs: {'source_commit':loaded['source_commit'],'source_blob_ids':loaded['source_blob_ids']}
prepared=host.PreparedHost(NS(path=root,fd=-1),NS(adapter=None),loaded,NS(),NS(os_api=os,fcntl_api=fcntl))
made=prepared._finalizer_modules()
assert set(made)=={'aa_video_validation'} and callable(made['aa_video_validation'].source_evidence)
path='06-tools/aa_video_validation.py';loaded['verified_source_bytes'][path]+=b'\n'
try:host.source_gate(loaded,finalizer=True)
except RuntimeError:pass
else:raise AssertionError('Deferred bytes tamper accepted')
print('AA fixed bytes loaded; original P85 closure unchanged')
'''
class Tests(unittest.TestCase):
    def test_actual_fixed_module_imports_and_pins(self):
        for dirty in ('clean','dirty'):
            result=subprocess.run([sys.executable,'-c',SCRIPT,str(ROOT),dirty],cwd=Path(__file__).parent,capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    def test_profile_requires_explicit_selection(self):
        import inert_source_loader as loader
        with self.assertRaises(RuntimeError):loader.FixedSourceLoader(root=str(ROOT),git=None,read_bytes=None,registry={},profile='other')
