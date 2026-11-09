"""Inactive single expected-server / prebound-owned-channel observation.
No socket factory, connect, endpoint requests, default OS or live entry point.
"""
import ast
import copy
import dataclasses
import hashlib
import json
import math
import stat
from dataclasses import dataclass
from types import MappingProxyType

SOURCE_PINS=MappingProxyType({
 'offline_baseline_adb':'7f2d60bffcf4e74fc4060941a6a8444ee6bb052ae24a07d23407aaef0ce0585e',
 'linux_adb_probe_dependencies':'e341d0e2a844d03dd0f69ab7604d9defb86865ccd4649875b6670165b3bbcd06',
 'identity_bound_reader_revision03':'658edfc705bb47485c4c60d481b11a931599dac99e0fe8c0e6f877045184559c',
 'bound_reader_sticky_shim':'1e00fd3a0d109a0aac7c75c5f46d9a16f97c54640732f30335024c31f31c11a9',
 'accepted_socket_helpers':'3aa5265d9bab2619f53f9c98f1c8309ce7acd9f9de0122ef5e60bec472047d8d'})
class Stop(ValueError):pass
@dataclass(frozen=True)
class ExpectedClient:
 fd:int;device:int;inode:int;uid:int;mode:int;local:tuple;peer:tuple
 def __post_init__(self):
  if any(type(v) is not int or v<0 for v in (self.fd,self.device,self.inode,self.uid,self.mode)) or not stat.S_ISSOCK(self.mode):raise Stop('Strict socket metadata required')
  for pair in (self.local,self.peer):
   if type(pair) is not tuple or len(pair)!=2 or pair[0]!='127.0.0.1' or type(pair[1]) is not int or not 0<pair[1]<65536:raise Stop('Fixed loopback tuple required')
 def tuple(self):return (self.fd,self.device,self.inode,self.uid,self.mode,self.local,self.peer)

def config_value(pin,limits,client):
 value=dataclasses.asdict(pin);value['process']['version']=pin.process.version.hex()
 return dict(server_pin=value,limits=dataclasses.asdict(limits),client=dataclasses.asdict(client))

def _helpers(raw,namespace):
 # Reuse exact reviewed helper function bodies, not a rewritten predicate.
 tree=ast.parse(raw);run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
 nodes=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in ('ProbeFailure','require')]
 nodes += [n for n in run.body if isinstance(n,ast.FunctionDef) and n.name in ('address','held','custody')]
 if len(nodes)!=5:raise Stop('Frozen helper shape mismatch')
 exec(compile(ast.Module(body=nodes,type_ignores=[]),'<exact-reviewed-accepted-helpers>','exec'),namespace)
 return namespace['held'],namespace['custody']

class _BoundProc:
 def __init__(self,base,bridge,pid):self._base=base;self._bridge=bridge;self._path='/proc/'+str(pid)+'/stat'
 def read(self,path,cap,deadline):
  if path==self._path:return self._bridge.read(path,cap,deadline)
  return self._base.read(path,cap,deadline)
 def __getattr__(self,name):return getattr(self._base,name)

class Collector:
 __slots__=('_dep','_reader','_shim','_pin','_limits','_expected','_client','_raw_client','_os','_clock','_root','_poll','_proc','_sources','_state','_deadline','_last_time','_server','_bridge','_association','_held','_custody','_accepted','_report','_closed','_config_sha','_acquisition')
 @property
 def state(self):return self._state
 @property
 def report(self):return copy.deepcopy(self._report)
 def __init__(self,*,dependency,reader_module,shim_module,pin,limits,expected_client,client,os_api,clock,root,poll_factory,proc,sources,config_bytes,expected_config_sha256):
  if hasattr(self,'_state'):raise Stop('No reinitialization')
  # All checks before accepting ownership. Invalid constructor leaves it with caller.
  if type(expected_client) is not ExpectedClient:raise Stop('Exact expected client pin required')
  if type(config_bytes) is not bytes or type(expected_config_sha256) is not str or len(expected_config_sha256)!=64 or hashlib.sha256(config_bytes).hexdigest()!=expected_config_sha256:raise Stop('External config pin mismatch')
  expected=json.loads(json.dumps(config_value(pin,limits,expected_client)))
  if json.dumps(json.loads(config_bytes),sort_keys=True,separators=(',',':'))!=json.dumps(expected,sort_keys=True,separators=(',',':')):raise Stop('Supplied pins differ from frozen configuration')
  if type(sources) is not dict or set(sources)!=set(SOURCE_PINS):raise Stop('Exact source closure required')
  for name,pin_hash in SOURCE_PINS.items():
   if type(sources[name]) is not bytes or hashlib.sha256(sources[name]).hexdigest()!=pin_hash:raise Stop('Frozen source mismatch')
  if type(client) is not dependency.FixedLoopbackSocket:raise Stop('Exact original socket wrapper required')
  if type(client.connected) is not bool or not client.connected or type(client.closed) is not bool or client.closed:raise Stop('Caller must supply prebound owned socket')
  if limits.stat_bytes!=16384:raise Stop('Bound stat shim requires exact qualified cap')
  if expected_client.peer!=pin.process.endpoint:raise Stop('Expected endpoint mismatch')
  self._dep=dependency;self._reader=reader_module;self._shim=shim_module;self._pin=pin;self._limits=limits;self._expected=expected_client
  self._client=client;self._raw_client=client.sock;self._os=os_api;self._clock=clock;self._root=root;self._poll=poll_factory;self._proc=proc;self._sources=dict(sources)
  self._state='new';self._deadline=None;self._last_time=None;self._server=None;self._acquisition=None;self._bridge=None;self._association=None;self._accepted=None;self._closed=False;self._config_sha=expected_config_sha256
  self._report=dict(state='new',events=[],snapshots=[],config_sha256=expected_config_sha256,source_hashes=dict(SOURCE_PINS),root_authenticated=False,recovery_admitted=False,executable_continuity=False,holder_continuity=False,unique_holder_qualified=False)
 def _now(self):
  value=self._clock()
  if type(value) not in (int,float) or not math.isfinite(value) or (self._last_time is not None and value<self._last_time):raise Stop('Invalid monotonic clock')
  self._last_time=value;return value
 def _remaining(self):
  value=self._deadline-self._now()
  if value<=0:raise Stop('Absolute observation deadline')
  return value
 def _event(self,stage,error=None):
  event=dict(stage=stage)
  if error is not None:
   name=type(error).__name__;event.update(type=name if len(name)<=64 and name.isidentifier() and name.isascii() else 'ExceptionType',errno=error.errno if isinstance(error,OSError) and type(error.errno) is int else None)
   chain=[];seen=set();current=error;relation='raised'
   while current is not None and id(current) not in seen and len(chain)<8:
    seen.add(id(current));name=type(current).__name__
    chain.append(dict(relation=relation,type=name if len(name)<=64 and name.isascii() and name.isidentifier() else 'ExceptionType',errno=current.errno if isinstance(current,OSError) and type(current.errno) is int else None))
    if current.__cause__ is not None:current=current.__cause__;relation='cause'
    else:current=current.__context__;relation='context'
   event['exception_chain']=chain;event['chain_truncated_or_cycle']=current is not None
  self._report['events'].append(event)
 def _abort(self,error):
  self._state='terminal';self._report['state']='terminal';self._event('terminal',error)
  try:self.close()
  except BaseException:pass
 def _socket_identity(self):
  self._remaining()
  if self._client.sock is not self._raw_client or self._client.closed or not self._client.connected:raise Stop('Owned channel object changed')
  value=self._held(self._client)
  if value!=self._expected.tuple():raise Stop('Held client pin mismatch')
  self._remaining();return value
 def _snapshot(self,label):
  begin=self._now();self._remaining()
  if self._association(self._deadline)!=(self._pin.process,):raise Stop('Original association rejected')
  identity=self._socket_identity();accepted=self._custody(identity)
  if self._accepted is not None and accepted!=self._accepted:raise Stop('Accepted FD inode changed')
  self._accepted=accepted
  # Successful bound stat includes pidfd nonready checks both sides; no exec claim.
  data=self._bridge.read('/proc/'+str(self._pin.process.pid)+'/stat',16384,self._deadline)
  self._socket_identity();self._remaining();end=self._now()
  self._report['snapshots'].append(dict(label=label,monotonic_begin=begin,monotonic_end=end,server_pid_object_nonready_bracket=True,client_identity_sample_match=True,accepted_inode=accepted,original_executable_snapshot_match=True,original_visible_leader_holder_snapshot_match=True,stat_digest=hashlib.sha256(data).hexdigest()))
 def acquire(self,*,deadline):
  if self._state!='new':raise Stop('Acquisition unavailable; no retry')
  self._state='acquiring';self._deadline=deadline
  try:
   now=self._now()
   if type(deadline) not in (int,float) or not math.isfinite(deadline) or not 0<deadline-now<=12:raise Stop('One checked budget at most12s required')
   self._acquisition=self._reader.Acquisition(os_api=self._os,poll_factory=self._poll,clock=self._clock,root=self._root)
   self._server=self._acquisition.acquire(pid=self._pin.process.pid,deadline=deadline)
   if self._server.start!=self._pin.process.starttime:raise Stop('Expected server process mismatch')
   self._bridge=self._shim.StatShim(held=self._server,dependency=self._dep)
   bound=_BoundProc(self._proc,self._bridge,self._pin.process.pid)
   self._association=self._shim.association_type(self._dep)(pin=self._pin,limits=self._limits,proc=bound,monotonic=self._clock)
   def call(method,*args):
    self._remaining();value=getattr(bound,method)(*args,self._deadline);self._remaining();return value
   self._held,self._custody=_helpers(self._sources['accepted_socket_helpers'],dict(stat=stat,os_api=self._os,pin=self._pin,limits=self._limits,call=call,remaining=self._remaining,parse_starttime=self._dep.parse_starttime))
   self._snapshot('acquire');self._state='acquired';self._report['state']='acquired';return self.report
  except BaseException as error:self._abort(error);raise
 def observe(self):
  if self._state!='acquired':raise Stop('Observation unavailable; no retry')
  self._state='observing'
  try:
   self._snapshot('observe');self._state='consumed';self._report['state']='consumed';return self.report
  except BaseException as error:self._abort(error);raise
 def close(self):
  if self._closed:return self.report
  self._closed=True;previous=self._state;self._state='terminal';self._report['state']='terminal';primary=None
  try:
   if self._client.sock is not self._raw_client:
    self._report['wrapper_object_changed']=True;self._report['original_raw_close_attempted']=True
    self._raw_client.close();self._report['original_raw_close_returned']=True
    raise Stop('Wrapper mutated; only original owned raw object closed')
   if self._client.closed:
    self._report['client_close_latch_seen']=True;raise Stop('Raw client close outcome unknown')
   self._report['client_close_attempted']=True
   self._client.close();self._report['client_close_returned']=True
  except BaseException as error:self._event('client_close',error);primary=error
  if self._server is not None:
   try:self._server.close();self._report['server_handle_close_call_returned']=True
   except BaseException as error:self._event('server_handle_close',error);primary=primary or error
  if self._acquisition is not None:
   self._report['server_reader_events']=self._acquisition.events;self._report['server_reader_events_dropped']=self._acquisition.dropped;self._report['server_reader_logging_failed']=self._acquisition.logging_failed;self._report['server_reader_last_error']=self._acquisition.last_error;self._report['server_reader_trace_complete']=not(self._acquisition.dropped or self._acquisition.logging_failed)
   incomplete_error = not self._report['server_reader_trace_complete'] and (self._acquisition.last_error is not None or any(e['stage']=='terminal' for e in self._report['events']))
   if incomplete_error:self._report['server_cleanup_uncertainty_reason']='incomplete_trace_with_error_cannot_exclude_lost_close_failure'
   if incomplete_error or self._acquisition.logging_failed or (self._acquisition.last_error is not None and self._acquisition.last_error['stage'] in ('stat_close','handle_close')) or any(e['stage'] in ('stat_close','handle_close') and 'type' in e for e in self._acquisition.events):
    self._report['server_cleanup_or_evidence_unknown']=True;primary=primary or Stop('Server handle cleanup/evidence incomplete')
  try:
   end=self._now();self._report['terminal_monotonic']=end
   if self._deadline is not None and end>self._deadline:raise Stop('Cleanup late')
  except BaseException as error:self._event('cleanup_time',error);primary=primary or error
  if primary is not None:raise primary
  return self.report
