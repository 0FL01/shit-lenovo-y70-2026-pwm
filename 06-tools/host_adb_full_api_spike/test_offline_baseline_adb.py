"""Fake-only protocol and concrete AST caller integration. No external I/O.

Source reads/test invocation are local. No sockets/processes/filesystem writes
are created by tests. Stage fixtures are explicitly not DDIC qualification.
"""
import ast
from contextlib import contextmanager
import dataclasses
import hashlib
import importlib.util
from pathlib import Path
import stat
import struct
import sys
from types import SimpleNamespace, MethodType
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('offline_baseline_adb',HERE/'offline_baseline_adb.py')
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
import test_canonical_boot_guard as guard
PIN=m.ProcessIdentity(m.ENDPOINT,101,123,(0,0,0,0),'/fixture/adb',1,2,
    stat.S_IFREG|0o755,0,b'Android Debug Bridge version 1.0.41\nfixture-build\n')
SERIALS=(b'fixture-target',b'fixture-camera')
LIST=b'fixture-target device device:avr transport_id:7\nfixture-camera device transport_id:8\n'
MOVED=b'fixture-target device device:avr transport_id:9\nfixture-camera device transport_id:8\nother device transport_id:7\n'
DEST='/fixture/private/capture.mp4'
REMOTE='/sdcard/DCIM/OpenCamera/fixture.mp4'

def frame(data):return b'OKAY'+f'{len(data):04x}'.encode()+data
def sf(ch,data):return struct.pack('<BI',ch,len(data))+data
def shell_reply(out=b'',err=b'',rc=0):return sf(1,out)+sf(2,err)+sf(3,bytes([rc]))
def sync_frame(kind,data=b'',size=None):return kind+struct.pack('<I',len(data) if size is None else size)+data

class Clock:
    def __init__(self):self.now=0
    def __call__(self):return self.now
    def sleep(self,n):self.now+=n

class Socket:
    def __init__(self,h,data=b'',*,chunk=65536,send_chunk=65536,step=0,send_delay=0,send_error_at=None):
        self.h=h;self.data=bytearray(data);self.sent=bytearray();self.chunk=chunk
        self.send_chunk=send_chunk;self.step=step;self.send_delay=send_delay
        self.send_error_at=send_error_at;self.closed=False;self.timeouts=[]
    def settimeout(self,n):self.timeouts.append(n)
    def connect(self,endpoint):
        if endpoint!=m.ENDPOINT:raise AssertionError('Fallback endpoint')
    def send(self,data):
        self.h.clock.now+=self.send_delay
        if self.send_error_at is not None and len(self.sent)>=self.send_error_at:raise TimeoutError('fixture partial send')
        n=min(len(data),self.send_chunk);self.sent.extend(data[:n]);return n
    def recv(self,n):
        self.h.clock.now+=self.step;n=min(n,self.chunk,len(self.data))
        data=bytes(self.data[:n]);del self.data[:n];return data
    def close(self):self.closed=True

class Sink:
    def __init__(self,h):
        self.h=h;self.data=bytearray();self.closed=False
        self.identity=m.SinkIdentity(DEST,1000,stat.S_IFREG|0o600,1000,stat.S_IFDIR|0o700,True,True)
    def write(self,data):
        self.h.clock.now+=self.h.write_delay
        if self.h.write_error:raise OSError('fixture sink failure')
        n=min(len(data),self.h.write_chunk);self.data.extend(data[:n]);return n
    def close(self):self.closed=True

class Harness:
    def __init__(self,auto=False):
        self.clock=Clock();self.queue=[];self.used=[];self.snapshots=[];self.acquisitions=0
        self.sinks=[];self.write_delay=0;self.write_error=False;self.write_chunk=65536
        self.sink_change={};self.auto=auto;self.listing=LIST;self.events=[]
        self.shell_handler=lambda command:b'';self.pull_data=b'abc';self.pull_fail=False
        self.reboot_fail=False;self.after_boot=guard.AFTER;self.complete='1'
        self.adb=m.OfflineBaselineADB(expected_process=PIN,expected_serials=SERIALS,
            acquire=self.acquire,make_socket=self.make_socket,create_sink=self.create_sink,
            expected_destination=DEST,expected_uid=1000,sleep=self.clock.sleep,monotonic=self.clock)
    def acquire(self,deadline):
        self.acquisitions+=1
        return self.snapshots.pop(0) if self.snapshots else (PIN,)
    def make_socket(self):
        if self.auto:sock=AutoSocket(self)
        elif self.queue:sock=self.queue.pop(0)
        else:raise AssertionError('Unexpected socket/retry')
        self.used.append(sock);return sock
    def create_sink(self,path,deadline):
        if self.sinks:raise FileExistsError('fixture exclusive destination')
        if path!=DEST:raise AssertionError('Unexpected local destination')
        sink=Sink(self);sink.identity=dataclasses.replace(sink.identity,**self.sink_change)
        self.sinks.append(sink);return sink
    def add(self,data,**kwargs):
        sock=Socket(self,data,**kwargs);self.queue.append(sock);return sock
    def ready(self):
        if not self.auto:self.add(frame(b'0029'))
        self.adb.preflight()
        for tid,serial in ((7,SERIALS[0]),(8,SERIALS[1])):
            if not self.auto:
                self.add(frame(b'0029'));self.add(frame(LIST));self.add(frame(serial))
            self.adb.bind(tid)
    def selected(self,payload=b'',listing=LIST,**kwargs):
        self.add(frame(b'0029'));self.add(frame(listing))
        return self.add(b'OKAYOKAY'+payload,**kwargs)
    def pull(self,**kwargs):
        return self.adb.run(['adb','-t','8','pull',REMOTE,DEST],expected_size=kwargs.pop('size',3),
                            byte_cap=kwargs.pop('cap',3),timeout=kwargs.pop('timeout',25),**kwargs)

class AutoSocket(Socket):
    """In-memory fake server; parses actual smart-socket service frames."""
    def __init__(self,h):super().__init__(h);self.buffer=bytearray();self.mode='service'
    def send(self,data):
        n=super().send(data);self.buffer.extend(data[:n])
        while self.buffer:
            if self.mode=='sync':
                if len(self.buffer)<8:break
                kind,size=struct.unpack('<4sI',self.buffer[:8])
                if len(self.buffer)<8+size:break
                payload=bytes(self.buffer[8:8+size]);del self.buffer[:8+size]
                self.h.events.append(('sync',kind,payload))
                if kind==b'RECV':
                    self.data.extend(sync_frame(b'DATA',self.h.pull_data))
                    if not self.h.pull_fail:self.data.extend(sync_frame(b'DONE'))
                elif kind!=b'QUIT':raise AssertionError('Unexpected sync mutation')
                continue
            if len(self.buffer)<4:break
            size=int(self.buffer[:4],16)
            if len(self.buffer)<4+size:break
            service=bytes(self.buffer[4:4+size]).decode('ascii');del self.buffer[:4+size]
            self.h.events.append(('service',service))
            if service=='host:version':self.data.extend(frame(b'0029'))
            elif service=='host:devices-l':self.data.extend(frame(self.h.listing))
            elif service.startswith('host-transport-id:'):
                tid=service.split(':')[1];self.data.extend(frame(SERIALS[0] if tid=='7' else SERIALS[1]))
            elif service.startswith('host:transport:'):self.data.extend(b'OKAY')
            elif service.startswith('shell,v2,raw:'):
                command=service[len('shell,v2,raw:'):]
                value=self.h.shell_handler(command)
                if isinstance(value,Exception):raise value
                self.data.extend(b'OKAY'+shell_reply(value))
            elif service=='reboot:':
                self.h.listing=MOVED
                if self.h.reboot_fail:raise TimeoutError('fixture reboot send uncertain')
                self.data.extend(b'OKAY')
            elif service=='sync:':self.mode='sync';self.data.extend(b'OKAY')
            else:raise AssertionError('Unexpected service')
        return n

class ProtocolTests(unittest.TestCase):
    def test_inert_constructor_and_no_push(self):
        with self.assertRaises(TypeError):m.OfflineBaselineADB()
        h=Harness();self.assertEqual(h.acquisitions,0);self.assertFalse(h.used)
        with self.assertRaises(ValueError):h.adb.run(['adb','-t','7','push','x','y'])
        self.assertFalse(h.used)
    def test_pin_invalid_values(self):
        for change in ({'endpoint':('localhost',5037)},{'uids':(1,1,1,1)},
                       {'pid':0},{'executable_mode':stat.S_IFREG|0o777},{'version':b'bad'}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                m.OfflineBaselineADB._validate_process(dataclasses.replace(PIN,**change))
    def test_partial_shell_and_output(self):
        h=Harness();h.ready();sock=h.selected(shell_reply(b'abc',b'err',4),chunk=1,send_chunk=1)
        self.assertEqual(h.adb.shell(7,'fixture',25),(4,b'abc',b'err'))
        self.assertIn(b'host:transport:fixture-target',sock.sent)
        self.assertTrue(h.adb.last_facts.completed);self.assertEqual(h.adb.last_facts.bytes_received,6)
        self.assertTrue(all(s.closed for s in h.used))
    def test_alias_survives_move_and_rebind_no_reassignment(self):
        h=Harness();h.ready();sock=h.selected(shell_reply(),listing=MOVED)
        h.adb.shell(7,'fixture',25);self.assertIn(b'host:transport:fixture-target',sock.sent)
        h.add(frame(b'0029'));h.add(frame(MOVED));s=h.add(b'OKAY')
        self.assertEqual(h.adb.bind(7),SERIALS[0]);self.assertIn(b'host:transport:fixture-target',s.sent)
        self.assertEqual(h.adb.identities['7'],SERIALS[0])
    def test_nonselected_missing_does_not_block_cleanup(self):
        h=Harness();h.ready();h.selected(shell_reply(),listing=LIST.splitlines(True)[0])
        h.adb.shell(7,'cleanup-fixture',25)
    def test_wrong_or_duplicate_selected_identity(self):
        for listing in (LIST.replace(b'fixture-target',b'other'),LIST+LIST.splitlines(True)[0],LIST.replace(b'transport_id:8',b'transport_id:7')):
            h=Harness();h.ready();h.add(frame(b'0029'));h.add(frame(listing))
            with self.assertRaises(m.TransportError):h.adb.shell(7,'fixture',25)
            self.assertFalse(h.adb.last_facts.dispatched)
    def test_ordinary_failure_does_not_disable_explicit_recovery(self):
        h=Harness();h.ready();h.selected(b'')
        with self.assertRaises(m.TransportError) as caught:h.adb.shell(7,'uncertain-child',25)
        self.assertTrue(caught.exception.uncertain);self.assertFalse(h.adb.trust_invalidated)
        h.selected();h.adb.reboot(7)
        self.assertEqual(h.adb.last_facts.operation,'reboot')
        self.assertTrue(h.adb.last_facts.accepted)
    def test_fully_framed_refusal_is_not_uncertain(self):
        h=Harness();h.ready();h.add(frame(b'0029'));h.add(frame(LIST));h.add(b'OKAYFAIL0003bad')
        with self.assertRaises(m.Refused) as caught:h.adb.shell(7,'fixture',25)
        self.assertFalse(caught.exception.uncertain);self.assertFalse(caught.exception.facts.accepted)
    def test_partial_send_is_uncertain_no_retry(self):
        h=Harness();h.ready();s=h.selected(shell_reply(),send_chunk=1,send_error_at=40)
        with self.assertRaises(m.TransportError) as caught:h.adb.shell(7,'fixture-command-long',25)
        self.assertTrue(caught.exception.uncertain);self.assertTrue(s.closed);self.assertFalse(h.queue)
    def test_frame_bounds_and_truncation(self):
        for payload in (b'x',struct.pack('<BI',4,0),struct.pack('<BI',1,m.MAX_OUTPUT+1),sf(3,b'')):
            h=Harness();h.ready();h.selected(payload)
            with self.assertRaises(m.TransportError):h.adb.shell(7,'fixture',25)
            self.assertFalse(h.adb.last_facts.completed)
    def test_late_completion_is_failure(self):
        h=Harness();h.ready();h.selected(shell_reply(),step=2)
        with self.assertRaises(m.TransportError):h.adb.shell(7,'fixture',3)
        self.assertTrue(h.adb.last_facts.uncertain)
    def test_process_and_protocol_invalidation_sticky(self):
        for cause in ('process','protocol','postprocess'):
            h=Harness();h.ready()
            if cause=='process':h.snapshots=[(dataclasses.replace(PIN,pid=102),)]
            elif cause=='protocol':h.add(frame(b'0028'))
            else:
                h.snapshots=[(PIN,),(dataclasses.replace(PIN,starttime=124),)]
                h.selected(shell_reply())
            with self.assertRaises(m.TransportError):h.adb.shell(7,'fixture',25)
            count=len(h.used);self.assertTrue(h.adb.trust_invalidated)
            with self.assertRaises(m.TransportError):h.adb.reboot(7)
            self.assertEqual(len(h.used),count)
    def test_late_observed_process_mismatch_is_sticky(self):
        h=Harness();h.ready()
        def late_acquire(deadline):
            h.clock.now=deadline
            return (dataclasses.replace(PIN,pid=102),)
        h.adb._acquire=late_acquire
        with self.assertRaises(m.TransportError):h.adb.shell(7,'fixture',25)
        self.assertTrue(h.adb.trust_invalidated)
        h.adb._acquire=h.acquire;count=len(h.used)
        with self.assertRaises(m.TransportError):h.adb.reboot(7)
        self.assertEqual(len(h.used),count)
    def test_host_version_has_one_validated_query(self):
        h=Harness();h.ready();h.add(frame(b'0029'));count=len(h.used)
        self.assertEqual(h.adb.host('host:version'),b'0029')
        self.assertEqual(len(h.used),count+1);self.assertFalse(h.queue)
        h.add(frame(b'0028'))
        with self.assertRaises(m.TransportError):h.adb.host('host:version')
        self.assertTrue(h.adb.trust_invalidated)
        with self.assertRaises(m.TransportError):h.adb.reboot(7)
    def test_reboot_uncertain_payload_and_wrong_role(self):
        h=Harness();h.ready()
        with self.assertRaises(ValueError):h.adb.reboot(8)
        h.selected(b'extra')
        with self.assertRaises(m.TransportError):h.adb.reboot(7)
        self.assertTrue(h.adb.last_facts.accepted);self.assertTrue(h.adb.last_facts.uncertain)
    def test_wait_target_absent_then_moved(self):
        h=Harness();h.ready()
        h.add(frame(b'0029'));h.add(frame(b''));h.add(frame(b'0029'));h.add(frame(MOVED))
        self.assertEqual(h.adb.wait_target('fixture-target'),9)
        self.assertEqual(h.adb.identities['7'],SERIALS[0])
    def test_wait_target_timeout_wrong_metadata_no_mutation(self):
        h=Harness();h.ready();h.add(frame(b'0029'));h.add(frame(b''))
        with self.assertRaises(m.TransportError):h.adb.wait_target('fixture-target',timeout=.5)
        self.assertFalse(h.adb.last_facts.dispatched)
        h.add(frame(b'0029'));h.add(frame(LIST.replace(b'device:avr',b'device:wrong')))
        with self.assertRaises(m.TransportError):h.adb.wait_target('fixture-target')
    def test_pull_exact_partial_io_and_sink(self):
        h=Harness();h.ready();h.write_chunk=1
        s=h.selected(sync_frame(b'DATA',b'abc')+sync_frame(b'DONE'),chunk=1,send_chunk=1)
        h.pull();self.assertEqual(h.sinks[0].data,b'abc');self.assertTrue(h.sinks[0].closed)
        self.assertTrue(h.adb.last_facts.completed);self.assertIn(b'host:transport:fixture-camera',s.sent)
        self.assertIn(b'RECV',s.sent);self.assertIn(b'QUIT',s.sent)
    def test_pull_requires_metadata_role_destination_before_io(self):
        h=Harness();h.ready();count=len(h.used)
        for args,kw in ((['8',REMOTE,DEST],{}),(['8',REMOTE,'/other/capture.mp4'],{'expected_size':3,'byte_cap':3}),
                        (['7',REMOTE,DEST],{'expected_size':3,'byte_cap':3}),
                        (['8','/data/local/forbidden',DEST],{'expected_size':3,'byte_cap':3})):
            with self.subTest(args=args),self.assertRaises(ValueError):
                h.adb.run(['adb','-t',args[0],'pull',args[1],args[2]],**kw)
        self.assertEqual(len(h.used),count)
    def test_pull_errors_size_frames_truncation(self):
        for payload in (sync_frame(b'DATA',b'ab')+sync_frame(b'DONE'),sync_frame(b'DATA',b'abcd'),
            sync_frame(b'DONE',size=1),sync_frame(b'FAIL',b'private'),sync_frame(b'FAIL',size=4097),
            sync_frame(b'DATA',size=65537),sync_frame(b'DATA',size=0),b'xx',sync_frame(b'DATA',b'ab',size=3)):
            h=Harness();h.ready();h.selected(payload)
            with self.subTest(payload=payload),self.assertRaises(m.TransportError):h.pull()
            self.assertFalse(h.adb.last_facts.completed);self.assertTrue(h.sinks[0].closed)
            self.assertTrue(all(s.closed for s in h.used));self.assertFalse(h.queue)
    def test_pull_partial_send_and_quit_failure_never_retry(self):
        recv_start=4+len('host:transport:fixture-camera')+4+len('sync:')
        quit_start=recv_start+8+len(REMOTE)
        for position in (recv_start+1,quit_start+1):
            h=Harness();h.ready()
            s=h.selected(sync_frame(b'DATA',b'abc')+sync_frame(b'DONE'),send_chunk=1,send_error_at=position)
            with self.subTest(position=position),self.assertRaises(m.TransportError):h.pull()
            self.assertTrue(h.adb.last_facts.uncertain);self.assertFalse(h.adb.last_facts.completed)
            self.assertTrue(s.closed);self.assertFalse(h.queue)
            if h.sinks:self.assertTrue(h.sinks[0].closed)
    def test_pull_postcheck_invalidates_trust_even_after_all_bytes(self):
        h=Harness();h.ready();h.snapshots=[(PIN,),(dataclasses.replace(PIN,pid=999),)]
        h.selected(sync_frame(b'DATA',b'abc')+sync_frame(b'DONE'))
        with self.assertRaises(m.TransportError):h.pull()
        self.assertEqual(h.sinks[0].data,b'abc');self.assertFalse(h.adb.last_facts.completed)
        self.assertTrue(h.adb.trust_invalidated)
    def test_shell_combined_output_cap(self):
        h=Harness();h.ready();original=m.MAX_OUTPUT;m.MAX_OUTPUT=4
        try:
            h.selected(shell_reply(b'abc',b'de'))
            with self.assertRaises(m.TransportError):h.adb.shell(7,'fixture',25)
        finally:m.MAX_OUTPUT=original
    def test_malformed_and_oversized_host_frames(self):
        for payload in (b'OKAYzzzz',b'OKAY0011',b'FAIL1001'):
            h=Harness();h.add(payload)
            with self.assertRaises(m.TransportError):h.adb.preflight()
            self.assertFalse(h.adb.last_facts.dispatched)
            self.assertTrue(h.used[0].closed)
    def test_pull_private_exclusive_contract(self):
        for change in ({'uid':0},{'mode':stat.S_IFREG|0o644},{'parent_mode':stat.S_IFDIR|0o755},
                       {'no_symlinks':False},{'exclusive':False},{'path':'/other'}):
            h=Harness();h.ready();h.sink_change=change;s=h.selected()
            with self.assertRaises(m.TransportError):h.pull()
            self.assertNotIn(b'RECV',s.sent);self.assertTrue(h.sinks[0].closed)
    def test_pull_duplicate_destination_no_overwrite(self):
        h=Harness();h.ready();h.selected(sync_frame(b'DATA',b'abc')+sync_frame(b'DONE'));h.pull()
        h.selected()
        with self.assertRaises(m.TransportError):h.pull()
        self.assertEqual(len(h.sinks),1);self.assertEqual(h.sinks[0].data,b'abc')
    def test_sink_error_late_write_then_cleanup_shell_possible(self):
        for late in (False,True):
            h=Harness();h.ready();h.write_delay=30 if late else 0;h.write_error=not late
            h.selected(sync_frame(b'DATA',b'abc')+sync_frame(b'DONE'))
            with self.assertRaises(m.TransportError):h.pull()
            self.assertTrue(h.sinks[0].closed);self.assertFalse(h.adb.trust_invalidated)
            h.selected(shell_reply());h.adb.shell(7,'qualified-cleanup-fixture',25)

# Concrete caller methods extracted, not imported/executed at module top level.
def timed_methods():
    raw=(HERE.parent/'run_p85_timed_stock_trial.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!='69d6a563ba313c2c2ba304f4d1abc77f2186326c4c27fd0f09ed85adc54eb4f1':
        raise RuntimeError('Timed source changed')
    tree=ast.parse(raw)
    deadline=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='DeadlineTransport')
    trial=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='TimedStockTrial')
    methods=[n for n in trial.body if isinstance(n,ast.FunctionDef) and n.name in ('execute','remaining')]
    ns={'check':guard.check,'s':SimpleNamespace(now=lambda:'fixture-time'),'RuntimeError':RuntimeError}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[deadline]+methods,type_ignores=[])),
                 '<pinned-timed-methods>','exec'),ns)
    return ns

class CallerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sweep,cls.ns=guard.extracted_class(guard.source_pair()[1]);cls.timed=timed_methods()
    def concrete(self,boot=guard.AFTER,reboot_fail=False):
        h=Harness(auto=True);h.ready();h.reboot_fail=reboot_fail
        run=guard.fixture(self.sweep,self.ns,boot)
        run.g=h.adb;run.monotonic=h.clock;run.sleep=h.clock.sleep
        values={'identity':guard.IDENTITY,'root':'0','panel':self.ns['c1'].PANEL,
                'module':self.ns['MODULE_SHA']+' fixture','recovery-owner':'','recovery-dc':'0',
                'recovery-esd':'reg_read','recovery-boot':boot,'recovery-complete':'1'}
        run.current_label=None
        def shell_handler(command):return values.get(run.current_label,'').encode()
        h.shell_handler=shell_handler
        def shell(command,**kwargs):
            run.calls.append((kwargs['label'],command,kwargs));run.current_label=kwargs['label']
            remote=('su -c '+guard.shlex.quote(command)) if kwargs.get('root') else command
            rc,out,err=run.g.shell(run.target,remote,kwargs.get('timeout',25))
            guard.check(rc==0,'Nonzero fixture shell');return out.decode(errors='replace').strip()
        run.shell=shell
        return run,h,values
    def test_concrete_recovery_moved_alias_and_real_validators(self):
        run,h,_=self.concrete();run.recover()
        self.assertTrue(run.report['recovery_reboot_verified']);self.assertFalse(run.pending_read)
        self.assertEqual(run.target,7);self.assertEqual(h.adb.identities['7'],SERIALS[0])
        self.assertEqual(h.events.count(('service','reboot:')),1)
        selections=[e[1] for e in h.events if e[0]=='service' and e[1].startswith('host:transport:')]
        self.assertTrue(selections);self.assertTrue(all(v=='host:transport:fixture-target' for v in selections))
    def test_concrete_uncertain_reboot_valid_and_invalid_proof(self):
        for boot in (guard.AFTER,'',guard.BEFORE):
            run,h,_=self.concrete(boot,reboot_fail=True)
            if boot==guard.AFTER:run.recover();self.assertTrue(run.report['recovery_reboot_verified'])
            else:
                with self.assertRaises(ValueError):run.recover()
                count=len(h.events)
                with self.assertRaises(ValueError):run.restore()
                self.assertEqual(len(h.events),count);self.assertTrue(run.recovery_failed)
            self.assertEqual(h.events.count(('service','reboot:')),1)
    def test_actual_deadline_transport_active_camera_failure_requires_target_recovery(self):
        run,h,_=self.concrete();run.active_start=0;run.active_failed=False;run.panel_uncertain=False
        run.camera=8;run.current_action='camera-fixture';run.report['active_actions']=[]
        run.remaining=lambda:37-h.clock();run.return_estimate=lambda:{}
        wrapper=self.timed['DeadlineTransport'](run,h.adb)
        h.shell_handler=lambda _:TimeoutError('fixture camera failure')
        with self.assertRaises(m.TransportError):wrapper.shell(8,'camera-fixture',15)
        self.assertTrue(run.active_failed and run.panel_uncertain)
        self.assertTrue(h.adb.last_facts.uncertain)
        # Existing caller exits active window then calls concrete recovery.
        run.active_start=None
        values={'recovery-boot':guard.AFTER,'recovery-complete':'1','identity':guard.IDENTITY,
                'root':'0','panel':self.ns['c1'].PANEL,'module':self.ns['MODULE_SHA']+' fixture',
                'recovery-owner':'','recovery-dc':'0','recovery-esd':'reg_read'}
        h.shell_handler=lambda _:values[run.current_label].encode()
        run.recover();self.assertEqual(h.events.count(('service','reboot:')),1)
        reboot=h.events.index(('service','reboot:'))
        self.assertEqual(h.events[reboot-1],('service','host:transport:fixture-target'))
    def test_concrete_finally_pull_failure_does_not_create_panel_uncertainty(self):
        run,h,_=self.concrete();run.pending_read=run.inflight=False;run.panel_uncertain=False
        run.recovery_failed=False;run.short_armed=False;run.changed=False;run.temp=False;run.armed=False
        run.locked=True;run.ops['release']='fixture-release-owner'
        run.report={'stages':[]};run._persist=lambda _:None
        run.setup=lambda:None;run.observe_stage=lambda _:None
        run.identity=lambda:None;run.camera_identity=lambda:None;run.metadata=lambda _:None
        run.state=lambda _:None;run.prepare_writer=lambda _:None;run.arm_timed=lambda:None
        run.write_stage=lambda label:None;run.timed_observe=lambda label:({},0)
        run.optical_hold=lambda *args:None
        @contextmanager
        def active_window():yield
        run.active_window=active_window
        h.pull_fail=True
        def stop_camera():
            run.report['camera_stopped_verified']=True
            h.pull()
        run.stop_camera=stop_camera;run.cleanup_camera_xml=lambda:None
        with self.assertRaises(RuntimeError):self.timed['execute'](run)
        self.assertFalse(run.panel_uncertain or run.recovery_failed)
        self.assertEqual(h.events.count(('service','reboot:')),0)
        self.assertTrue(run.report['mutex_released'])  # Actual Sweep.restore issues release through A.
        self.assertIn(('service','shell,v2,raw:su -c fixture-release-owner'),h.events)
        self.assertTrue(run.report['status'].startswith('failed'))
    def test_concrete_execute_error_never_appends_next_stage(self):
        run,h,_=self.concrete();run.pending_read=run.inflight=False;run.panel_uncertain=False
        run.short_armed=False;run.changed=run.armed=run.temp=run.locked=False
        run.report={'stages':[]};run._persist=lambda _:None;stages=[]
        run.setup=lambda:None;run.observe_stage=lambda _:None
        run.camera_identity=lambda:None;run.metadata=lambda _:None;run.state=lambda _:None
        run.prepare_writer=lambda _:None;run.arm_timed=lambda:None
        @contextmanager
        def active_window():yield
        run.active_window=active_window
        def writer(label):
            stages.append(label);run.panel_uncertain=True;run.pending_read=True
            raise m.TransportError('fixture child outcome uncertain')
        run.write_stage=writer;run.stop_camera=lambda:None;run.cleanup_camera_xml=lambda:None
        with self.assertRaises(RuntimeError):self.timed['execute'](run)
        self.assertEqual(stages,['sham15']);self.assertEqual(h.events.count(('service','reboot:')),1)
        self.assertTrue(run.report['recovery_reboot_verified'])

if __name__=='__main__':unittest.main(verbosity=2)
