"""Inert Linux dependency source. Production syscalls NOT qualified by fixtures.

No acquisition, socket, process spawn, directory creation or CLI at import/default
construction. Execute only after separate authorization. Proc/regular-file reads
have checked absolute deadlines but cannot promise cancellation of blocked OS I/O.
"""
from dataclasses import dataclass
import hashlib
from functools import wraps
import math
import os
import re
import socket
import stat
import time

from offline_baseline_adb import ENDPOINT, PROTOCOL, ProcessIdentity, OfflineBaselineADB

class ProbeError(RuntimeError):
    """Sanitized failure, with sticky observed trust-invalidation classification."""
    def __init__(self, reason, *, trust_invalidated=False, code='probe_failed'):
        super().__init__(reason)
        self.trust_invalidated=trust_invalidated
        self.code=code



def safe_errors(code):
    """Normalize external exceptions; no raw callback/OS/private details escape.

    No storage/evidence sink is implemented. KeyboardInterrupt/SystemExit remain
    interrupts. Stable context code and sticky classification are public facts.
    """
    def decorate(function):
        @wraps(function)
        def wrapped(*args,**kwargs):
            try:return function(*args,**kwargs)
            except (KeyboardInterrupt,SystemExit):raise
            except Exception as error:
                invalidated=bool(isinstance(error,ProbeError) and error.trust_invalidated)
                if code.startswith('proc_') and isinstance(error,OSError) and not isinstance(error,TimeoutError):
                    invalidated=True
                raise ProbeError(code,trust_invalidated=invalidated,code=code) from None
        return wrapped
    return decorate


def remaining(clock,deadline):
    value=deadline-clock()
    if not math.isfinite(value) or value<=0:raise ProbeError('Absolute probe deadline exceeded')
    return value


@dataclass(frozen=True)
class VerifiedPin:
    process: ProcessIdentity
    listener_inode: int
    network_namespace: str
    executable_sha256: str
    executable_size: int
    # All fields must be independently reviewed/private. Never learn-and-trust.


@dataclass(frozen=True)
class ProcLimits:
    tcp_bytes: int
    stat_bytes: int
    status_bytes: int
    max_pids: int
    max_fds_per_pid: int
    max_total_fds: int
    link_bytes: int
    # Explicit resource ceilings, NOT evidence that a capped scan is complete.
    # No unqualified host-wide count defaults. Exceeding any limit rejects.


@dataclass(frozen=True)
class ExecutableSnapshot:
    device: int
    inode: int
    mode: int
    uid: int
    size: int
    sha256: str


class LinuxProcFS:
    """Small real proc reader; all OS primitives/clock can be injected.

    Only fixed proc paths selected by LinuxAssociation call this implementation.
    Follow /proc/PID/exe intentionally to hash the held executable FD, never to
    execute it. Other content reads reject final symlinks. No permissions change.
    """
    def __init__(self,*,os_api=os,monotonic=time.monotonic):
        self.os=os_api;self.clock=monotonic

    @safe_errors('proc_read_failed')
    def read(self,path,cap,deadline):
        remaining(self.clock,deadline)
        fd=self.os.open(path,self.os.O_RDONLY|self.os.O_CLOEXEC|self.os.O_NOFOLLOW)
        try:
            data=bytearray()
            while len(data)<=cap:
                remaining(self.clock,deadline)
                chunk=self.os.read(fd,min(65536,cap+1-len(data)))
                remaining(self.clock,deadline)
                if not chunk:break
                data.extend(chunk)
            if len(data)>cap:raise ProbeError('Proc byte cap exceeded',trust_invalidated=True)
            return bytes(data)
        finally:self.os.close(fd)

    @safe_errors('proc_scan_failed')
    def names(self,path,cap,deadline):
        remaining(self.clock,deadline);names=[]
        with self.os.scandir(path) as entries:
            for entry in entries:
                remaining(self.clock,deadline)
                names.append(entry.name)
                if len(names)>cap:raise ProbeError('Proc entry cap exceeded',trust_invalidated=True)
        remaining(self.clock,deadline)
        return tuple(names)

    @safe_errors('proc_link_failed')
    def link(self,path,cap,deadline):
        remaining(self.clock,deadline);value=self.os.readlink(path)
        remaining(self.clock,deadline)
        if len(value.encode('utf-8'))>cap:raise ProbeError('Proc link cap exceeded',trust_invalidated=True)
        return value

    @safe_errors('proc_fd_scan_failed')
    def fd_links(self,pid,count_cap,link_cap,deadline):
        # Keep scandir alive while reading links. Closing it before readlink can
        # make our own /proc/self/fd listing contain a vanished scanner FD.
        path='/proc/'+str(pid)+'/fd';remaining(self.clock,deadline);pairs=[];visited=0
        with self.os.scandir(path) as entries:
            for entry in entries:
                remaining(self.clock,deadline)
                visited+=1
                if visited>count_cap:raise ProbeError('FD count cap exceeded',trust_invalidated=True)
                # Existential listener possession, not a complete FD snapshot.
                # Only a vanished individual enumerated FD may be omitted.
                # Directory errors and permission failures are never ignored.
                try:value=self.os.readlink(path+'/'+entry.name)
                except FileNotFoundError:
                    remaining(self.clock,deadline)
                    continue
                remaining(self.clock,deadline)
                if len(value.encode('utf-8'))>link_cap:
                    raise ProbeError('Proc link cap exceeded',trust_invalidated=True)
                pairs.append((entry.name,value))
        remaining(self.clock,deadline)
        return tuple(pairs)

    @safe_errors('proc_binary_failed')
    def binary(self,pid,size,deadline):
        remaining(self.clock,deadline)
        fd=self.os.open('/proc/'+str(pid)+'/exe',self.os.O_RDONLY|self.os.O_CLOEXEC)
        try:
            before=self.os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size!=size:
                raise ProbeError('Executable size or type changed',trust_invalidated=True)
            total=0;digest=hashlib.sha256()
            while total<=size:
                remaining(self.clock,deadline)
                chunk=self.os.read(fd,min(65536,size+1-total))
                remaining(self.clock,deadline)
                if not chunk:break
                total+=len(chunk);digest.update(chunk)
            after=self.os.fstat(fd)
            attrs=('st_dev','st_ino','st_mode','st_uid','st_size','st_mtime_ns','st_ctime_ns')
            if total!=size or any(getattr(before,k)!=getattr(after,k) for k in attrs):
                raise ProbeError('Executable changed during bounded read',trust_invalidated=True)
            remaining(self.clock,deadline)
            return ExecutableSnapshot(before.st_dev,before.st_ino,before.st_mode,before.st_uid,size,digest.hexdigest())
        finally:self.os.close(fd)


def parse_starttime(raw,pid):
    # proc_pid_stat(5): field2 comm is parenthesized and can contain spaces/')'.
    # Following fields begin at field3 state; field22 starttime is suffix[19].
    text=raw.decode('ascii');end=text.rfind(')')
    if not text.startswith(str(pid)+' (') or end<0:raise ProbeError('Malformed process stat',trust_invalidated=True)
    fields=text[end+1:].split()
    if len(fields)<20 or len(fields[0])!=1 or not fields[19].isdigit() or int(fields[19])<=0:
        raise ProbeError('Malformed process starttime',trust_invalidated=True)
    return int(fields[19])


def parse_uids(raw):
    rows=[line.split()[1:] for line in raw.splitlines() if line.startswith(b'Uid:')]
    if len(rows)!=1 or len(rows[0])!=4 or any(not x.isdigit() for x in rows[0]):
        raise ProbeError('Malformed process UID fields',trust_invalidated=True)
    return tuple(int(x) for x in rows[0])


def parse_listeners(raw,*,ipv6):
    """Conservative proc_net_tcp parser; reject any IPv6 LISTEN at this port.

    Linux /proc/net/tcp columns: sl/local/remote/st/queues/timer/retrans/uid/
    timeout/inode. State0A is LISTEN. Address words use proc little-endian layout.
    No tcp6 fallback or claim that an unchecked dual-stack socket is harmless.
    """
    lines=raw.splitlines()
    if not lines or b'local_address' not in lines[0] or b'inode' not in lines[0]:
        raise ProbeError('Malformed TCP table header',trust_invalidated=True)
    rows=[]
    width=32 if ipv6 else 8
    for line in lines[1:]:
        if not line.strip():continue
        fields=line.split()
        if len(fields)<10:raise ProbeError('Truncated TCP table row',trust_invalidated=True)
        match=re.fullmatch(rb'([0-9A-Fa-f]{'+str(width).encode()+rb'}):([0-9A-Fa-f]{4})',fields[1])
        if not match or re.fullmatch(rb'[0-9A-Fa-f]{2}',fields[3]) is None or not fields[7].isdigit() or not fields[9].isdigit():
            raise ProbeError('Malformed TCP table row',trust_invalidated=True)
        if fields[3].upper()!=b'0A' or int(match[2],16)!=ENDPOINT[1]:continue
        address=match[1].upper()
        if ipv6 or address in (b'0100007F',b'00000000'):
            rows.append((address,int(fields[7]),int(fields[9]),ipv6))
    return tuple(rows)


class LinuxAssociation:
    """Pinned server identity and listener possession, not sole-holder proof.

    Only the independently pinned PID is inspected. Unrelated process churn and
    other processes sharing the listener are outside this contract. Trusted host,
    root, kernel and server remain required; snapshots are not atomic peer auth.
    """
    def __init__(self,*,pin,limits,proc,monotonic):
        if not isinstance(pin,VerifiedPin):raise ValueError('Independent verified pin required')
        OfflineBaselineADB._validate_process(pin.process)
        if (type(pin.listener_inode) is not int or pin.listener_inode<=0
            or re.fullmatch(r'net:\[[1-9][0-9]*\]',pin.network_namespace) is None
            or re.fullmatch(r'[0-9a-f]{64}',pin.executable_sha256) is None
            or type(pin.executable_size) is not int or pin.executable_size<=0):
            raise ValueError('Complete namespace/listener/executable pin required')
        if not isinstance(limits,ProcLimits) or any(type(v) is not int or v<=0 for v in vars(limits).values()):
            raise ValueError('Explicit positive proc resource ceilings required')
        self.pin=pin;self.limits=limits;self.proc=proc;self.clock=monotonic
        self.trust_invalidated=False

    def fail(self,reason):
        self.trust_invalidated=True
        raise ProbeError(reason,trust_invalidated=True)

    def call(self,method,*args,deadline):
        remaining(self.clock,deadline)
        value=getattr(self.proc,method)(*args,deadline)
        # Returned values are checked by callers before the after-deadline check,
        # so an observed mismatch cannot be discarded as an ordinary timeout.
        return value

    def namespace(self,deadline):
        value=self.call('link','/proc/self/ns/net',self.limits.link_bytes,deadline=deadline)
        if value!=self.pin.network_namespace:self.fail('Network namespace changed')
        remaining(self.clock,deadline)

    def listeners(self,deadline):
        wanted=(b'0100007F',self.pin.process.uids[0],self.pin.listener_inode,False)
        raw=self.call('read','/proc/net/tcp',self.limits.tcp_bytes,deadline=deadline)
        if len(raw)>self.limits.tcp_bytes:self.fail('Incomplete TCP scan')
        if parse_listeners(raw,ipv6=False)!=(wanted,):
            self.fail('IPv4 listener absent, ambiguous or changed')
        remaining(self.clock,deadline)
        raw6=self.call('read','/proc/net/tcp6',self.limits.tcp_bytes,deadline=deadline)
        if len(raw6)>self.limits.tcp_bytes:self.fail('Incomplete TCP6 scan')
        if parse_listeners(raw6,ipv6=True):self.fail('Ambiguous IPv6 listener at pinned port')
        remaining(self.clock,deadline)

    def holders(self,deadline):
        # Historical method name retained for callers; this proves possession by
        # the pinned server only, never absence of other holders.
        p=self.pin.process;base='/proc/'+str(p.pid)
        first=self.call('read',base+'/stat',self.limits.stat_bytes,deadline=deadline)
        if len(first)>self.limits.stat_bytes or parse_starttime(first,p.pid)!=p.starttime:
            self.fail('Pinned PID missing or reused')
        remaining(self.clock,deadline)
        pairs=self.call('fd_links',p.pid,self.limits.max_fds_per_pid,self.limits.link_bytes,deadline=deadline)
        fds=tuple(fd for fd,link in pairs)
        if (len(fds)>min(self.limits.max_fds_per_pid,self.limits.max_total_fds)
            or len(fds)!=len(set(fds))
            or any(re.fullmatch(r'0|[1-9][0-9]*',n) is None for n in fds)):
            self.fail('Incomplete or malformed pinned FD scan')
        held=False
        for fd,link in pairs:
            if len(link.encode('utf-8'))>self.limits.link_bytes:self.fail('Incomplete FD link')
            if link=='socket:['+str(self.pin.listener_inode)+']':held=True
            remaining(self.clock,deadline)
        second=self.call('read',base+'/stat',self.limits.stat_bytes,deadline=deadline)
        if len(second)>self.limits.stat_bytes or parse_starttime(second,p.pid)!=p.starttime:
            self.fail('Pinned PID changed during FD scan')
        if not held:self.fail('Pinned server no longer holds listener')
        remaining(self.clock,deadline)

    def server_identity(self,deadline):
        p=self.pin.process;base='/proc/'+str(p.pid)
        raw=self.call('read',base+'/stat',self.limits.stat_bytes,deadline=deadline)
        if len(raw)>self.limits.stat_bytes or parse_starttime(raw,p.pid)!=p.starttime:
            self.fail('Pinned PID missing or reused')
        remaining(self.clock,deadline)
        ns=self.call('link',base+'/ns/net',self.limits.link_bytes,deadline=deadline)
        if ns!=self.pin.network_namespace:self.fail('Server network namespace changed')
        uidraw=self.call('read',base+'/status',self.limits.status_bytes,deadline=deadline)
        if len(uidraw)>self.limits.status_bytes or parse_uids(uidraw)!=p.uids:self.fail('Process owner changed')
        exe=self.call('link',base+'/exe',self.limits.link_bytes,deadline=deadline)
        if exe!=p.executable:self.fail('Executable path changed')
        observed=self.call('binary',p.pid,self.pin.executable_size,deadline=deadline)
        expected=ExecutableSnapshot(p.executable_device,p.executable_inode,p.executable_mode,
            p.executable_uid,self.pin.executable_size,self.pin.executable_sha256)
        if observed!=expected:self.fail('Executable identity or digest changed')
        remaining(self.clock,deadline)
        raw=self.call('read',base+'/stat',self.limits.stat_bytes,deadline=deadline)
        if len(raw)>self.limits.stat_bytes or parse_starttime(raw,p.pid)!=p.starttime:
            self.fail('Pinned PID changed during identity check')
        remaining(self.clock,deadline)

    @safe_errors('association_failed')
    def __call__(self,deadline):
        if self.trust_invalidated:raise ProbeError('Association trust invalidated; no repin',trust_invalidated=True)
        try:
            # Bracket pinned FD possession with full identity checks; check the
            # exact endpoint tables and both namespaces at both boundaries.
            self.namespace(deadline);self.listeners(deadline)
            self.server_identity(deadline);self.holders(deadline)
            self.holders(deadline);self.server_identity(deadline)
            self.listeners(deadline);self.namespace(deadline)
            p=self.pin.process
            remaining(self.clock,deadline)
            # Full build/version comes from independently approved digest manifest,
            # NOT from a proc "version" field or an executed adb subprocess.
            return (p,)
        except ProbeError as error:
            if error.trust_invalidated:self.trust_invalidated=True
            raise
        except (OSError,ValueError,UnicodeError,TypeError,AttributeError):
            self.fail('Proc association inaccessible, incomplete or malformed')


    def acquire_process(self,deadline):
        """Bridge sticky invalidation into the reviewed adapter tuple contract.

        () is explicitly NOT a trusted process. Reviewed _process makes its own
        sticky invalidation on this result. No source edit/repin is required.
        Ordinary timeout still raises and any later explicit call rechecks pins.
        """
        try:return self(deadline)
        except ProbeError:
            if self.trust_invalidated:return ()
            raise


class FixedLoopbackSocket:
    """Absolute-budget socket wrapper; no retry of connect or alternate address."""
    def __init__(self,*,socket_factory,monotonic):
        self.factory=socket_factory;self.clock=monotonic;self.sock=None;self.deadline=None
        self.connected=False;self.closed=False

    def settimeout(self,seconds):
        if isinstance(seconds,bool) or not isinstance(seconds,(int,float)) or not math.isfinite(seconds) or not 0<seconds<=600:
            raise ValueError('Finite positive operation budget required')
        proposed=self.clock()+seconds
        self.deadline=proposed if self.deadline is None else min(self.deadline,proposed)

    def budget(self):
        if self.closed or self.deadline is None:raise ProbeError('Socket closed or budget missing')
        return remaining(self.clock,self.deadline)

    @safe_errors('socket_connect_failed')
    def connect(self,endpoint):
        if endpoint!=ENDPOINT or self.sock is not None:raise ProbeError('Only one fixed endpoint connect allowed')
        self.budget()
        self.sock=self.factory(socket.AF_INET,socket.SOCK_STREAM)
        try:
            self.sock.set_inheritable(False)
            self.sock.settimeout(self.budget());self.sock.connect(ENDPOINT)
            self.budget();self.connected=True
        except BaseException:
            self.close();raise

    @safe_errors('socket_send_failed')
    def send(self,data):
        if not self.connected:raise ProbeError('Socket not connected')
        self.sock.settimeout(self.budget());count=self.sock.send(data);self.budget()
        if type(count) is not int or not 0<count<=len(data):raise ProbeError('Invalid socket send')
        return count

    @safe_errors('socket_recv_failed')
    def recv(self,count):
        if not self.connected or type(count) is not int or not 0<count<=16*1024*1024:
            raise ProbeError('Invalid bounded socket read')
        self.sock.settimeout(self.budget());data=self.sock.recv(min(count,65536));self.budget()
        if not isinstance(data,bytes) or len(data)>count:raise ProbeError('Invalid socket response')
        return data

    @safe_errors('socket_close_failed')
    def close(self):
        if not self.closed:
            self.closed=True
            if self.sock is not None:self.sock.close()


def make_socket_factory(*,socket_factory=socket.socket,monotonic=time.monotonic):
    # Returning a callable is inert; OS socket is only created in explicit connect.
    return lambda:FixedLoopbackSocket(socket_factory=socket_factory,monotonic=monotonic)


@safe_errors('host_probe_failed')
def inspect_existing_server(*,association,make_socket,expected_serials,monotonic):
    """Explicitly executed read-only probe only; no CLI/default invocation.

    One shared12s budget: association, host:version once, host:devices-l once,
    association. No selected service, shell, bind, sink or process execution.
    Separate host-execution authorization remains mandatory.
    """
    serials=tuple(expected_serials)
    if len(serials)!=2 or len(set(serials))!=2 or any(not isinstance(s,bytes) or
            re.fullmatch(rb'[A-Za-z0-9_.-]{1,256}',s) is None or s==b'unknown' for s in serials):
        raise ValueError('Two private independent serial pins required')
    start=monotonic();deadline=start+12
    association(deadline)
    def exact(sock,count):
        data=bytearray()
        while len(data)<count:
            sock.settimeout(remaining(monotonic,deadline));part=sock.recv(min(65536,count-len(data)))
            remaining(monotonic,deadline)
            if not part or len(part)>count-len(data):raise ProbeError('Truncated probe response')
            data.extend(part)
        return bytes(data)
    def request(service,cap):
        sock=make_socket()
        try:
            sock.settimeout(remaining(monotonic,deadline));sock.connect(ENDPOINT)
            data=service.encode('ascii');view=memoryview(f'{len(data):04x}'.encode()+data)
            while view:
                sock.settimeout(remaining(monotonic,deadline));n=sock.send(view);remaining(monotonic,deadline)
                if type(n) is not int or not 0<n<=len(view):raise ProbeError('Invalid probe send')
                view=view[n:]
            status=exact(sock,4)
            if status not in (b'OKAY',b'FAIL'):raise ProbeError('Malformed probe status')
            header=exact(sock,4)
            if re.fullmatch(rb'[0-9a-fA-F]{4}',header) is None:raise ProbeError('Malformed probe length')
            size=int(header,16)
            if size>(4096 if status==b'FAIL' else cap):raise ProbeError('Probe response cap exceeded')
            payload=exact(sock,size)
            if status==b'FAIL':raise ProbeError('Host service refused')
            return payload
        finally:sock.close()
    try:
        if request('host:version',16)!=PROTOCOL:
            association.fail('Expected ADB protocol41')
        raw=request('host:devices-l',65535)
        rows={};ids=set()
        for line in raw.splitlines():
            fields=line.split()
            if not fields:continue
            tids=[x[13:] for x in fields[2:] if x.startswith(b'transport_id:')]
            if len(fields)<2 or len(tids)!=1 or re.fullmatch(rb'[1-9][0-9]{0,19}',tids[0]) is None:
                raise ProbeError('Malformed inventory')
            if fields[0] in rows or tids[0] in ids:raise ProbeError('Ambiguous inventory')
            rows[fields[0]]=fields[1];ids.add(tids[0])
        if any(rows.get(s)!=b'device' for s in serials):raise ProbeError('Expected devices not ready')
    finally:
        association(deadline)
    remaining(monotonic,deadline)
    return {'protocol':41,'process_pin_matched':True,'expected_map_matched':True,
            'elapsed_seconds':monotonic()-start,'device_services_sent':0,
            'association_scope':'pinned_server_fd_table',
            'unique_holder_qualified':False}
