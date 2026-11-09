"""Inactive same-buffer composition. No acquisition or socket construction on load.
Trusted Python/stdlib and exclusively owned injected I/O remain prerequisites.
"""
import builtins
import hashlib
from types import ModuleType, MappingProxyType

PINS=MappingProxyType({'offline_baseline_adb': '7f2d60bffcf4e74fc4060941a6a8444ee6bb052ae24a07d23407aaef0ce0585e', 'linux_adb_probe_dependencies': 'e341d0e2a844d03dd0f69ab7604d9defb86865ccd4649875b6670165b3bbcd06', 'identity_bound_reader_revision03': '658edfc705bb47485c4c60d481b11a931599dac99e0fe8c0e6f877045184559c', 'bound_reader_sticky_shim': '1e00fd3a0d109a0aac7c75c5f46d9a16f97c54640732f30335024c31f31c11a9', 'accepted_socket_helpers': '3aa5265d9bab2619f53f9c98f1c8309ce7acd9f9de0122ef5e60bec472047d8d', 'collector': '5ffc2160c7422e6c74d61fc501ce70a6e6379b39b21b55cff5da7178f4febd64'})
_STDLIB=frozenset(('contextlib','dataclasses','math','pathlib','re','stat','struct','subprocess','time','types','hashlib','functools','os','socket','ast','copy','json'))
_ORDER=('offline_baseline_adb','linux_adb_probe_dependencies','identity_bound_reader_revision03','bound_reader_sticky_shim','collector')
class CompositionError(ValueError):pass

class Composition:
 __slots__=('_modules','_sources')
 def __init__(self,*,sources):
  if hasattr(self,'_modules'):raise CompositionError('No reinitialization')
  if type(sources) is not dict or set(sources)!=set(PINS):raise CompositionError('Exact source closure required')
  checked={}
  # Check ALL buffers before executing ANY buffer. Immutable bytes copied by reference.
  for name,pin in PINS.items():
   value=sources[name]
   if type(value) is not bytes or hashlib.sha256(value).hexdigest()!=pin:raise CompositionError('Source mismatch')
   checked[name]=value
  modules={};original_import=builtins.__import__
  def resolve(name,globals=None,locals=None,fromlist=(),level=0):
   if level:raise CompositionError('Relative import forbidden')
   if name in PINS:
    if name not in modules:raise CompositionError('Dependency order violation')
    return modules[name]
   if name not in _STDLIB:raise CompositionError('Unexpected import')
   return original_import(name,globals,locals,fromlist,0)
  for name in _ORDER:
   module=ModuleType('_held_channel_frozen_'+name)
   module.__dict__['__builtins__']=dict(vars(builtins),__import__=resolve)
   # No sys.modules registration, lookup, importlib loader or .pyc path.
   exec(compile(checked[name],'<sha256:'+PINS[name]+'>','exec'),module.__dict__)
   modules[name]=module
  self._modules=MappingProxyType(modules);self._sources=MappingProxyType(checked)
 @property
 def source_hashes(self):return dict(PINS)
 @property
 def types(self):
  d=self._modules['linux_adb_probe_dependencies'];r=self._modules['identity_bound_reader_revision03'];c=self._modules['collector']
  return MappingProxyType(dict(RootPin=r.RootPin,FixedLoopbackSocket=d.FixedLoopbackSocket,ExpectedClient=c.ExpectedClient,VerifiedPin=d.VerifiedPin,ProcLimits=d.ProcLimits,ProcessIdentity=d.ProcessIdentity,ExecutableSnapshot=d.ExecutableSnapshot))
 def collector(self,*,pin,limits,expected_client,client,os_api,clock,root,poll_factory,proc,config_bytes,expected_config_sha256):
  d=self._modules['linux_adb_probe_dependencies'];r=self._modules['identity_bound_reader_revision03'];s=self._modules['bound_reader_sticky_shim'];c=self._modules['collector']
  if type(root) is not r.RootPin or type(pin) is not d.VerifiedPin or type(pin.process) is not d.ProcessIdentity or type(limits) is not d.ProcLimits:raise CompositionError('Composition-owned pin types required')
  sources={k:v for k,v in self._sources.items() if k!='collector'}
  return c.Collector(dependency=d,reader_module=r,shim_module=s,pin=pin,limits=limits,expected_client=expected_client,client=client,os_api=os_api,clock=clock,root=root,poll_factory=poll_factory,proc=proc,sources=sources,config_bytes=config_bytes,expected_config_sha256=expected_config_sha256)
