"""All proc/OS/socket/clock operations are fakes. No real acquisition or I/O."""
import dataclasses
import hashlib
import stat
from types import SimpleNamespace
import unittest
import linux_adb_probe_dependencies as d
import test_offline_baseline_adb as f

HEADER=b'  sl local_address rem_address st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode\n'
def tcp(address='0100007F',inode=900,uid=0,port='13AD',state='0A'):
    return f'0: {address}:{port} 00000000:0000 {state} 00000000:00000000 00:00000000 00000000 {uid} 0 {inode}\n'.encode()
def statline(pid=101,start=123):
    return (str(pid)+' (adb weird ) comm) S '+' '.join(['0']*18+[str(start)])+'\n').encode()
PIN=d.VerifiedPin(f.PIN,900,'net:[123]',hashlib.sha256(b'adb').hexdigest(),3)
LIMITS=d.ProcLimits(4096,4096,4096,64,64,128,4096)

class FakeProc:
    def __init__(self,clock):
        self.clock=clock;self.calls=[];self.denied=None;self.delay_path=None;self.delay=0
        self.reads={'/proc/net/tcp':HEADER+tcp(),'/proc/net/tcp6':HEADER,
                    '/proc/101/stat':statline(),'/proc/101/status':b'Name:\tadb\nUid:\t0\t0\t0\t0\n'}
        self.dirs={'/proc':('net','self','101'),'/proc/101/fd':('0','1')}
        self.links={'/proc/self/ns/net':'net:[123]','/proc/101/exe':'/fixture/adb',
                    '/proc/101/fd/0':'/dev/null','/proc/101/fd/1':'socket:[900]'}
        self.exe=d.ExecutableSnapshot(1,2,stat.S_IFREG|0o755,0,3,PIN.executable_sha256)
        self.hooks={}
    def access(self,path):
        self.calls.append(path)
        if path==self.denied:raise PermissionError('fixture denied')
        if path==self.delay_path:self.clock.now+=self.delay
        if path in self.hooks:self.hooks[path]()
    def read(self,path,cap,deadline):self.access(path);return self.reads[path]
    def names(self,path,cap,deadline):self.access(path);return self.dirs[path]
    def link(self,path,cap,deadline):self.access(path);return self.links[path]
    def fd_links(self,pid,count_cap,link_cap,deadline):
        path='/proc/'+str(pid)+'/fd';self.access(path)
        pairs=[]
        for fd in self.dirs[path]:
            self.access(path+'/'+fd);pairs.append((fd,self.links[path+'/'+fd]))
        return tuple(pairs)
    def binary(self,pid,size,deadline):self.access('binary');return self.exe
    def other_holder(self):
        self.dirs['/proc']=('101','102');self.dirs['/proc/102/fd']=('0',)
        self.reads['/proc/102/stat']=statline(102,44);self.links['/proc/102/fd/0']='socket:[900]'

class H:
    def __init__(self,limits=LIMITS):
        self.clock=f.Clock();self.proc=FakeProc(self.clock)
        self.association=d.LinuxAssociation(pin=PIN,limits=limits,proc=self.proc,monotonic=self.clock)

class AssociationTests(unittest.TestCase):
    def test_inert_and_exact_pin(self):
        h=H();self.assertFalse(h.proc.calls)
        self.assertEqual(h.association(12),(f.PIN,));self.assertFalse(h.association.trust_invalidated)
        self.assertEqual(h.proc.calls.count('/proc/net/tcp'),2)
        self.assertEqual(h.proc.calls.count('/proc/101/fd'),2)
    def test_explicit_pins_and_limits_required(self):
        h=H()
        for pin in (dataclasses.replace(PIN,listener_inode=0),dataclasses.replace(PIN,executable_sha256='x'),
                    dataclasses.replace(PIN,network_namespace='x')):
            with self.assertRaises(ValueError):d.LinuxAssociation(pin=pin,limits=LIMITS,proc=h.proc,monotonic=h.clock)
        with self.assertRaises(ValueError):H(dataclasses.replace(LIMITS,max_pids=0))
    def assert_sticky(self,h):
        with self.assertRaises(d.ProbeError):h.association(12)
        self.assertTrue(h.association.trust_invalidated)
        count=len(h.proc.calls)
        with self.assertRaises(d.ProbeError):h.association(20)
        self.assertEqual(len(h.proc.calls),count)
        self.assertEqual(h.association.acquire_process(20),())
    def test_listener_missing_changed_duplicate_wildcard_ipv6(self):
        for raw in (HEADER,HEADER+tcp(inode=901),HEADER+tcp()+tcp(),HEADER+tcp(address='00000000'),HEADER+tcp(uid=1000)):
            h=H();h.proc.reads['/proc/net/tcp']=raw;self.assert_sticky(h)
        h=H();h.proc.reads['/proc/net/tcp6']=HEADER+tcp(address='0'*32);self.assert_sticky(h)
    def test_missing_ambiguous_holder(self):
        h=H();h.proc.links['/proc/101/fd/1']='socket:[901]';self.assert_sticky(h)
        h=H();h.proc.other_holder();self.assert_sticky(h)
    def test_unreadable_any_process_rejects_complete_association(self):
        for path in ('/proc/net/tcp6','/proc/101/fd','/proc/101/fd/0','/proc/101/status','binary'):
            h=H();h.proc.denied=path;self.assert_sticky(h)
    def test_caps_are_failure_not_partial_success(self):
        for change in ({'tcp_bytes':8},{'stat_bytes':8},{'status_bytes':8},{'max_pids':2},
                       {'max_fds_per_pid':1},{'max_total_fds':1},{'link_bytes':2}):
            h=H(dataclasses.replace(LIMITS,**change));self.assert_sticky(h)
    def test_pid_reuse_owner_path_binary_changes(self):
        for kind in ('pid','uid','path','hash','inode','namespace','missingpid'):
            h=H()
            if kind=='pid':h.proc.reads['/proc/101/stat']=statline(start=124)
            elif kind=='uid':h.proc.reads['/proc/101/status']=b'Uid: 0 0 1 0\n'
            elif kind=='path':h.proc.links['/proc/101/exe']='/fixture/wrong'
            elif kind=='hash':h.proc.exe=dataclasses.replace(h.proc.exe,sha256='0'*64)
            elif kind=='inode':h.proc.exe=dataclasses.replace(h.proc.exe,inode=3)
            elif kind=='namespace':h.proc.links['/proc/self/ns/net']='net:[456]'
            else:h.proc.dirs['/proc']=('net','self')
            self.assert_sticky(h)
    def test_changed_second_snapshot(self):
        h=H();count=[0]
        def change():
            count[0]+=1
            if count[0]==2:h.proc.reads['/proc/net/tcp']=HEADER+tcp(inode=901)
        h.proc.hooks['/proc/net/tcp']=change;self.assert_sticky(h)
    def test_changed_pid_during_fd_scan(self):
        h=H();h.proc.hooks['/proc/101/fd']=lambda:h.proc.reads.update({'/proc/101/stat':statline(start=124)})
        self.assert_sticky(h)
    def test_process_set_churn_rejected(self):
        h=H();count=[0]
        def change():
            count[0]+=1
            if count[0]==2:h.proc.dirs['/proc']=('101','102')
        h.proc.hooks['/proc']=change;self.assert_sticky(h)
    def test_late_observed_mismatch_sticky_but_matching_timeout_not(self):
        for path,mutate in (('/proc/net/tcp',lambda p:p.reads.update({'/proc/net/tcp':HEADER+tcp(inode=901)})),
                            ('/proc/101/stat',lambda p:p.reads.update({'/proc/101/stat':statline(start=124)})),
                            ('binary',lambda p:setattr(p,'exe',dataclasses.replace(p.exe,inode=3)))):
            h=H();mutate(h.proc);h.proc.delay_path=path;h.proc.delay=12;self.assert_sticky(h)
        h=H();h.proc.delay_path='/proc/net/tcp';h.proc.delay=12
        with self.assertRaises(d.ProbeError):h.association(12)
        self.assertFalse(h.association.trust_invalidated)
        h.proc.delay=0;self.assertEqual(h.association(h.clock()+12),(f.PIN,))
    def test_stat_comm_and_uid_parser_strict(self):
        self.assertEqual(d.parse_starttime(statline(),101),123)
        for raw in (b'',b'101 adb S 0',statline().replace(b'123',b'bad')):
            with self.assertRaises(d.ProbeError):d.parse_starttime(raw,101)
        for raw in (b'',b'Uid: 0 0 0\n',b'Uid: 0 0 0 0\nUid: 0 0 0 0\n'):
            with self.assertRaises(d.ProbeError):d.parse_uids(raw)
    def test_bridge_invalidates_reviewed_adapter(self):
        h=H();a=f.Harness();a.adb._acquire=h.association.acquire_process
        h.proc.exe=dataclasses.replace(h.proc.exe,inode=3)
        with self.assertRaises(f.m.TransportError):a.adb.preflight()
        self.assertTrue(a.adb.trust_invalidated);self.assertFalse(a.used)

class RawSocket:
    def __init__(self,clock,data=b'',delay=0,connect_delay=0,chunk=1):
        self.clock=clock;self.data=bytearray(data);self.delay=delay;self.connect_delay=connect_delay
        self.chunk=chunk;self.closed=False;self.sent=bytearray();self.endpoint=None;self.inheritable=None;self.timeouts=[]
    def set_inheritable(self,value):self.inheritable=value
    def settimeout(self,value):self.timeouts.append(value)
    def connect(self,endpoint):self.endpoint=endpoint;self.clock.now+=self.connect_delay
    def send(self,data):self.clock.now+=self.delay;n=min(self.chunk,len(data));self.sent.extend(data[:n]);return n
    def recv(self,count):
        self.clock.now+=self.delay;n=min(count,self.chunk,len(self.data));out=bytes(self.data[:n]);del self.data[:n];return out
    def close(self):self.closed=True

class SocketTests(unittest.TestCase):
    def build(self,**kw):
        clock=f.Clock();raw=RawSocket(clock,**kw);calls=[]
        def factory(family,kind):calls.append((family,kind));return raw
        sock=d.FixedLoopbackSocket(socket_factory=factory,monotonic=clock)
        return sock,raw,clock,calls
    def test_inert_fixed_endpoint_and_budget_not_extended(self):
        sock,raw,clock,calls=self.build(data=b'ab');self.assertFalse(calls)
        sock.settimeout(12);sock.connect(d.ENDPOINT);clock.now=5;sock.settimeout(12)
        self.assertEqual(sock.deadline,12);self.assertIs(raw.inheritable,False)
        self.assertEqual(sock.send(b'ab'),1);self.assertEqual(sock.recv(1000000),b'a')
        with self.assertRaises(d.ProbeError):sock.connect(d.ENDPOINT)
        sock.close();self.assertTrue(raw.closed);self.assertEqual(len(calls),1)
    def test_wrong_endpoint_never_creates_socket(self):
        sock,raw,clock,calls=self.build();sock.settimeout(12)
        with self.assertRaises(d.ProbeError):sock.connect(('localhost',5037))
        self.assertFalse(calls)
    def test_late_connect_closes_no_retry(self):
        sock,raw,clock,calls=self.build(connect_delay=12);sock.settimeout(12)
        with self.assertRaises(d.ProbeError):sock.connect(d.ENDPOINT)
        self.assertTrue(raw.closed)
        with self.assertRaises(d.ProbeError):sock.connect(d.ENDPOINT)
        self.assertEqual(len(calls),1)
    def test_send_recv_late_success_rejected(self):
        for method,arg in (('send',b'abc'),('recv',4)):
            sock,raw,clock,calls=self.build(data=b'abc',delay=12);sock.settimeout(12);sock.connect(d.ENDPOINT)
            with self.assertRaises(d.ProbeError):getattr(sock,method)(arg)
            sock.close();self.assertTrue(raw.closed)
    def test_nonfinite_or_missing_budget(self):
        sock,raw,clock,calls=self.build()
        with self.assertRaises(d.ProbeError):sock.connect(d.ENDPOINT)
        for n in (0,-1,float('inf'),float('nan'),True,601):
            with self.assertRaises(ValueError):sock.settimeout(n)

class SelfTestTests(unittest.TestCase):
    def probe(self,h,responses,*,delay=0):
        raws=[]
        def factory(family,kind):
            if not responses:raise AssertionError('Unexpected retry/extra socket')
            raw=RawSocket(h.clock,responses.pop(0),delay=delay,chunk=3);raws.append(raw);return raw
        create=d.make_socket_factory(socket_factory=factory,monotonic=h.clock)
        return lambda:d.inspect_existing_server(association=h.association,make_socket=create,
            expected_serials=f.SERIALS,monotonic=h.clock),raws
    def test_exact_two_host_queries_no_device_service(self):
        h=H();probe,raws=self.probe(h,[f.frame(b'0029'),f.frame(f.LIST)])
        result=probe();self.assertEqual(result['device_services_sent'],0)
        self.assertEqual([bytes(r.sent) for r in raws],[b'000chost:version',b'000ehost:devices-l'])
        self.assertTrue(all(r.closed for r in raws));self.assertEqual(h.proc.calls.count('binary'),2)
        self.assertNotIn('fixture-target',str(result))
    def test_wrong_version_sticky_no_inventory(self):
        h=H();probe,raws=self.probe(h,[f.frame(b'0028')])
        with self.assertRaises(d.ProbeError):probe()
        self.assertTrue(h.association.trust_invalidated);self.assertEqual(len(raws),1)
    def test_bad_inventory_frames_and_missing_expected(self):
        for data in (f.frame(b''),f.frame(f.LIST+f.LIST),b'OKAYzzzz',b'FAIL1001',b'OKAYffffx'):
            h=H();probe,raws=self.probe(h,[f.frame(b'0029'),data])
            with self.assertRaises(d.ProbeError):probe()
            self.assertEqual(len(raws),2);self.assertTrue(all(r.closed for r in raws))
    def test_shared_deadline_stops_without_second_connect(self):
        h=H();probe,raws=self.probe(h,[f.frame(b'0029'),f.frame(f.LIST)],delay=2)
        with self.assertRaises(d.ProbeError):probe()
        self.assertEqual(len(raws),1);self.assertTrue(raws[0].closed)
    def test_after_snapshot_change_rejects_complete_protocol(self):
        h=H();count=[0]
        def change():
            count[0]+=1
            if count[0]==3:h.proc.reads['/proc/net/tcp']=HEADER+tcp(inode=901)
        h.proc.hooks['/proc/net/tcp']=change
        probe,raws=self.probe(h,[f.frame(b'0029'),f.frame(f.LIST)])
        with self.assertRaises(d.ProbeError):probe()
        self.assertTrue(h.association.trust_invalidated);self.assertEqual(len(raws),2)

class FakeOS:
    O_RDONLY=0;O_CLOEXEC=1;O_NOFOLLOW=2
    def __init__(self):
        self.data=b'adb';self.cursor=0;self.closed=[];self.opens=[];self.active=False
        self.entries=('0','1');self.metadata_change=False;self.stat_calls=0
    def open(self,path,flags):self.opens.append((path,flags));self.cursor=0;return 77
    def read(self,fd,count):
        out=self.data[self.cursor:self.cursor+min(count,2)];self.cursor+=len(out);return out
    def close(self,fd):self.closed.append(fd)
    def fstat(self,fd):
        self.stat_calls+=1
        return SimpleNamespace(st_dev=1,st_ino=2,st_mode=stat.S_IFREG|0o755,st_uid=0,
            st_size=3,st_mtime_ns=10+(self.metadata_change and self.stat_calls>1),st_ctime_ns=10)
    def scandir(self,path):
        owner=self
        class Entries:
            def __enter__(self):owner.active=True;return iter(SimpleNamespace(name=n) for n in owner.entries)
            def __exit__(self,*args):owner.active=False
        return Entries()
    def readlink(self,path):
        if '/fd/' in path and not self.active:raise FileNotFoundError('scanner FD closed too early')
        return 'socket:[900]' if path.endswith('/1') else '/proc/101/fd'

class LowLevelProcTests(unittest.TestCase):
    def test_bounded_read_uses_nofollow_and_closes(self):
        api=FakeOS();clock=f.Clock();fs=d.LinuxProcFS(os_api=api,monotonic=clock)
        self.assertEqual(fs.read('/proc/101/stat',3,12),b'adb')
        self.assertEqual(api.closed,[77]);self.assertTrue(api.opens[0][1]&api.O_NOFOLLOW)
        api.data=b'abcd'
        with self.assertRaises(d.ProbeError):fs.read('/proc/101/stat',3,12)
        self.assertEqual(api.closed,[77,77])
    def test_executable_hash_and_change_detection(self):
        api=FakeOS();clock=f.Clock();fs=d.LinuxProcFS(os_api=api,monotonic=clock)
        self.assertEqual(fs.binary(101,3,12),d.ExecutableSnapshot(1,2,stat.S_IFREG|0o755,0,3,PIN.executable_sha256))
        self.assertFalse(api.opens[0][1]&api.O_NOFOLLOW)  # intentional /proc/PID/exe magic link
        api.stat_calls=0;api.metadata_change=True
        with self.assertRaises(d.ProbeError):fs.binary(101,3,12)
        self.assertEqual(api.closed,[77,77])
    def test_fd_links_read_while_scanner_fd_alive(self):
        api=FakeOS();clock=f.Clock();fs=d.LinuxProcFS(os_api=api,monotonic=clock)
        self.assertEqual(fs.fd_links(101,2,100,12),(('0','/proc/101/fd'),('1','socket:[900]')))
        self.assertFalse(api.active)
        with self.assertRaises(d.ProbeError):fs.fd_links(101,1,100,12)
        self.assertFalse(api.active)
    def test_directory_and_link_caps_fail_closed(self):
        api=FakeOS();clock=f.Clock();fs=d.LinuxProcFS(os_api=api,monotonic=clock)
        with self.assertRaises(d.ProbeError):fs.names('/proc',1,12)
        with self.assertRaises(d.ProbeError):fs.link('/proc/101/exe',1,12)

class SanitizedErrorTests(unittest.TestCase):
    def test_public_probe_normalizes_factory_and_socket_private_errors(self):
        for where in ('factory','connect','send','recv','close'):
            with self.subTest(where=where):
                h=H()
                class BadSocket(RawSocket):
                    def connect(self,endpoint):
                        if where=='connect':raise OSError('PRIVATE-CONNECTOR-DETAIL')
                        return super().connect(endpoint)
                    def send(self,data):
                        if where=='send':raise OSError('PRIVATE-CONNECTOR-DETAIL')
                        return super().send(data)
                    def recv(self,count):
                        if where=='recv':raise OSError('PRIVATE-CONNECTOR-DETAIL')
                        return super().recv(count)
                    def close(self):
                        if where=='close':raise OSError('PRIVATE-CONNECTOR-DETAIL')
                        return super().close()
                def factory(*args):
                    if where=='factory':raise OSError('PRIVATE-CONNECTOR-DETAIL')
                    return BadSocket(h.clock,f.frame(b'0029'),chunk=65536)
                with self.assertRaises(d.ProbeError) as caught:
                    d.inspect_existing_server(association=h.association,
                        make_socket=d.make_socket_factory(socket_factory=factory,monotonic=h.clock),
                        expected_serials=f.SERIALS,monotonic=h.clock)
                self.assertEqual(str(caught.exception),'host_probe_failed')
                self.assertEqual(caught.exception.code,'host_probe_failed')
    def test_lowlevel_proc_and_socket_surfaces_are_sanitized(self):
        h=H()
        class BadOS(FakeOS):
            def open(self,*args):raise PermissionError('PRIVATE-PATH')
        fs=d.LinuxProcFS(os_api=BadOS(),monotonic=h.clock)
        with self.assertRaises(d.ProbeError) as caught:fs.read('/proc/101/stat',12,12)
        self.assertEqual(str(caught.exception),'proc_read_failed');self.assertTrue(caught.exception.trust_invalidated)
        def factory(*args):raise OSError('PRIVATE-ENDPOINT')
        sock=d.FixedLoopbackSocket(socket_factory=factory,monotonic=h.clock);sock.settimeout(12)
        with self.assertRaises(d.ProbeError) as caught:sock.connect(d.ENDPOINT)
        self.assertEqual(str(caught.exception),'socket_connect_failed')
    def test_interrupt_is_not_relabelled_as_success_or_ordinary_error(self):
        h=H()
        def factory():raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            d.inspect_existing_server(association=h.association,make_socket=factory,
                expected_serials=f.SERIALS,monotonic=h.clock)
    def test_success_explicitly_bounds_association_claim(self):
        h=H();responses=[f.frame(b'0029'),f.frame(f.LIST)]
        def factory(*args):return RawSocket(h.clock,responses.pop(0),chunk=65536)
        result=d.inspect_existing_server(association=h.association,
            make_socket=d.make_socket_factory(socket_factory=factory,monotonic=h.clock),
            expected_serials=f.SERIALS,monotonic=h.clock)
        self.assertEqual(result['association_scope'],'visible_thread_group_leader_fd_tables')
        self.assertIs(result['unique_holder_qualified'],False)

if __name__=='__main__':unittest.main(verbosity=2)
