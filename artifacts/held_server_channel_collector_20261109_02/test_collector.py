import importlib.util
from pathlib import Path
import sys,json,hashlib,stat,dataclasses
from types import SimpleNamespace as NS
import unittest
import collector as c
ROOT=Path(__file__).resolve().parents[2];S=ROOT/'artifacts/identity_bound_sticky_shim_20261109_01';sys.path.insert(0,str(S))
spec=importlib.util.spec_from_file_location('collector_fixtures',S/'test_shim.py');prev=importlib.util.module_from_spec(spec);spec.loader.exec_module(prev)
PATHS={'offline_baseline_adb':'06-tools/host_adb_full_api_spike/offline_baseline_adb.py','linux_adb_probe_dependencies':'06-tools/host_adb_full_api_spike/linux_adb_probe_dependencies.py','identity_bound_reader_revision03':'artifacts/identity_bound_reader_20261109_03/reader.py','bound_reader_sticky_shim':'artifacts/identity_bound_sticky_shim_20261109_01/shim.py','accepted_socket_helpers':'artifacts/host_only_protocol_revision02_20261109/host_only_probe_proposal.py'}
class Fixture:
 def __init__(self,ctx):
  self.ctx=ctx;self.dep=ctx.modules['linux_adb_probe_dependencies'];outer=self
  class OS(prev.fakes.Fake):
   def open(self,path,flags,*,dir_fd):
    fd=super().open(path,flags,dir_fd=dir_fd)
    if path=='101':self.fdmeta[fd]=(1,fd,stat.S_IFDIR|0o444)
    return fd
   def read(self,fd,n):
    if self.fault:return super().read(fd,n)
    if self.reads.get(fd):return b''
    self.reads[fd]=True;return ctx.proc.statline()
   def fstat(self,fd):
    if fd==50:return NS(st_dev=1,st_ino=50+(1 if self.fault=='client_fd' else 0),st_uid=0,st_mode=stat.S_IFSOCK|0o600)
    return super().fstat(fd)
   def getuid(self):return 0
  self.os=OS();self.raw_closes=0;self.connects=0;self.requests=0
  class Raw:
   def set_inheritable(self,x):pass
   def get_inheritable(self):return False
   def settimeout(self,t):pass
   def connect(self,p):outer.connects+=1
   def fileno(self):return 50
   def getsockname(self):return ('127.0.0.1',40000)
   def getpeername(self):return ('127.0.0.1',5037)
   def send(self,*a):outer.requests+=1;raise AssertionError('No endpoint sends allowed')
   def recv(self,*a):outer.requests+=1;raise AssertionError('No endpoint reads allowed')
   def close(self):
    outer.raw_closes+=1
    if outer.os.fault=='client_close':raise OSError(5,'unknown close')
    if outer.os.fault=='late_close':outer.os.t=20
  self.raw=Raw();self.client=self.dep.FixedLoopbackSocket(socket_factory=lambda *a:self.raw,monotonic=self.os.clock);self.client.settimeout(12);self.client.connect(ctx.proc.PIN.process.endpoint)
  clock=NS(now=0);self.proc=ctx.proc.FakeProc(clock)
  self.proc.reads['/proc/net/tcp']+=b'1: 0100007F:13AD 0100007F:9C40 01 0 0 0 0 0 1000\n'
  self.proc.dirs['/proc/101/fd']=('0','1','2');self.proc.links['/proc/101/fd/2']='socket:[1000]'
  self.limits=dataclasses.replace(ctx.proc.LIMITS,stat_bytes=16384)
  self.expected=c.ExpectedClient(50,1,50,0,stat.S_IFSOCK|0o600,('127.0.0.1',40000),('127.0.0.1',5037))
  self.sources={k:(ROOT/p).read_bytes() for k,p in PATHS.items()}
  self.config=json.dumps(c.config_value(ctx.proc.PIN,self.limits,self.expected),sort_keys=True).encode()
 def make(self,**changes):
  kw=dict(dependency=self.dep,reader_module=prev.reader,shim_module=prev.shim,pin=self.ctx.proc.PIN,limits=self.limits,expected_client=self.expected,client=self.client,os_api=self.os,clock=self.os.clock,root=prev.reader.RootPin(9,1,9,stat.S_IFDIR|0o555,'pid:[100]','a'*64),poll_factory=self.os.poll_factory,proc=self.proc,sources=self.sources,config_bytes=self.config,expected_config_sha256=hashlib.sha256(self.config).hexdigest());kw.update(changes);return c.Collector(**kw)
class Tests(unittest.TestCase):
 def test_acquire_observe_close_original_predicates(self):
  with prev.actual() as ctx:
   f=Fixture(ctx);x=f.make();x.acquire(deadline=12);r=x.observe();self.assertEqual(len(r['snapshots']),2);self.assertFalse(r['holder_continuity']);self.assertFalse(r['recovery_admitted']);x.close();self.assertEqual(f.connects,1);self.assertEqual(f.requests,0);self.assertEqual(f.raw_closes,1);self.assertFalse(x.report['server_reader_trace_complete']);self.assertGreater(x.report['server_reader_events_dropped'],0)
 def test_drift_and_unknown_stop_zero_retry(self):
  with prev.actual() as ctx:
   for fault in ('exe','holder','deny','client_fd','exit','namespace','deadline'):
    f=Fixture(ctx);x=f.make();x.acquire(deadline=12)
    if fault=='exe':f.proc.exe=dataclasses.replace(f.proc.exe,inode=999)
    elif fault=='holder':f.proc.links['/proc/101/fd/2']='socket:[1001]'
    elif fault=='deny':f.proc.denied='/proc/101/status'
    elif fault=='deadline':f.os.t=20
    else:f.os.fault=fault
    with self.assertRaises(BaseException):x.observe()
    n=(len(f.os.calls),len(f.proc.calls),f.raw_closes)
    with self.assertRaises(c.Stop):x.observe()
    with self.assertRaises(c.Stop):x.acquire(deadline=30)
    x.close();self.assertEqual(n,(len(f.os.calls),len(f.proc.calls),f.raw_closes));self.assertEqual(f.requests,0);self.assertEqual(f.connects,1)
 def test_source_config_failure_before_ownership(self):
  with prev.actual() as ctx:
   f=Fixture(ctx);bad=dict(f.sources);bad['accepted_socket_helpers']+=b' '\

   with self.assertRaises(c.Stop):f.make(sources=bad)
   with self.assertRaises(c.Stop):f.make(config_bytes=b'{}')
   self.assertEqual(f.os.calls,[]);self.assertEqual(f.raw_closes,0)
 def test_public_state_and_detached_reports(self):
  with prev.actual() as ctx:
   f=Fixture(ctx);x=f.make();x.acquire(deadline=12);r=x.report;r['state']='new';r['snapshots'].clear();self.assertEqual(x.state,'acquired');self.assertEqual(len(x.report['snapshots']),1)
   with self.assertRaises(AttributeError):x.state='new'
   with self.assertRaises(AttributeError):x.report={}
   for name in ('snapshot','remaining','socket_identity','abort'):self.assertFalse(hasattr(x,name))
   x.close()
 def test_close_failure_and_late_close(self):
  with prev.actual() as ctx:
   for fault in ('client_close','late_close'):
    f=Fixture(ctx);x=f.make();x.acquire(deadline=12);f.os.fault=fault
    with self.assertRaises(Exception):x.close()
    n=f.raw_closes;x.close();self.assertEqual(f.raw_closes,n);self.assertEqual(x.state,'terminal')
 def test_wrapper_swap_closes_only_original_raw(self):
  with prev.actual() as ctx:
   f=Fixture(ctx);x=f.make();x.acquire(deadline=12);foreign=NS(close=lambda:(_ for _ in ()).throw(AssertionError('foreign close')));f.client.sock=foreign
   with self.assertRaises(Exception):x.observe()
   self.assertEqual(f.raw_closes,1);self.assertTrue(x.report['original_raw_close_returned'])
 def test_server_close_unknown_and_latch_unknown(self):
  with prev.actual() as ctx:
   f=Fixture(ctx);x=f.make();x.acquire(deadline=12)
   def failed_close(fd):f.os.calls.append(('uncertain_close',fd));raise OSError(5,'unknown')
   f.os.close=failed_close
   with self.assertRaises(Exception):x.close()
   self.assertTrue(x.report['server_cleanup_or_evidence_unknown']);n=len(f.os.calls);x.close();self.assertEqual(len(f.os.calls),n)
   f=Fixture(ctx);x=f.make();x.acquire(deadline=12);f.client.closed=True
   with self.assertRaises(Exception):x.observe()
   self.assertTrue(x.report['client_close_latch_seen']);self.assertEqual(f.raw_closes,0)
 def test_acquisition_failure_and_consumed_no_io(self):
  with prev.actual() as ctx:
   f=Fixture(ctx);x=f.make();f.os.fault='deny'
   with self.assertRaises(Exception):x.acquire(deadline=12)
   self.assertEqual(x.state,'terminal');self.assertEqual(f.raw_closes,1)
   f=Fixture(ctx);x=f.make();x.acquire(deadline=12);x.observe();n=(len(f.os.calls),len(f.proc.calls))
   with self.assertRaises(c.Stop):x.observe()
   self.assertEqual(n,(len(f.os.calls),len(f.proc.calls)));x.close()
 def test_saturated_trace_stat_close_failure_unknown(self):
  with prev.actual() as ctx:
   f=Fixture(ctx);x=f.make();x.acquire(deadline=12);original_close=f.os.close
   def fail_stat_close(fd):
    if f.os.files.get(fd)=='stat':raise OSError(5,'uncertain stat close')
    return original_close(fd)
   f.os.close=fail_stat_close
   with self.assertRaises(f.dep.ProbeError):x.observe()
   r=x.report
   self.assertEqual(x.state,'terminal');self.assertTrue(r['server_handle_close_call_returned'])
   self.assertGreater(r['server_reader_events_dropped'],0);self.assertFalse(r['server_reader_trace_complete'])
   self.assertEqual(r['server_reader_last_error']['stage'],'reader_terminal');self.assertEqual(r['server_reader_last_error']['errno'],5)
   self.assertFalse(any(e['stage']=='stat_close' and 'type' in e for e in r['server_reader_events']))
   self.assertTrue(r['server_cleanup_or_evidence_unknown'])
   self.assertEqual(r['server_cleanup_uncertainty_reason'],'incomplete_trace_with_error_cannot_exclude_lost_close_failure')
   n=(len(f.os.calls),len(f.proc.calls),f.raw_closes)
   with self.assertRaises(c.Stop):x.observe()
   with self.assertRaises(c.Stop):x.acquire(deadline=12)
   x.close();self.assertEqual(n,(len(f.os.calls),len(f.proc.calls),f.raw_closes));self.assertEqual(f.requests,0)
 def test_saturated_success_not_cleanup_failure_and_order_rejection(self):
  with prev.actual() as ctx:
   f=Fixture(ctx);x=f.make();n=len(f.os.calls)
   with self.assertRaises(c.Stop):x.observe()
   self.assertEqual(x.state,'new');self.assertEqual(len(f.os.calls),n)
   x.acquire(deadline=12);x.observe();r=x.close()
   self.assertFalse(r['server_reader_trace_complete']);self.assertIsNone(r['server_reader_last_error'])
   self.assertNotIn('server_cleanup_or_evidence_unknown',r)
if __name__=='__main__':unittest.main()
