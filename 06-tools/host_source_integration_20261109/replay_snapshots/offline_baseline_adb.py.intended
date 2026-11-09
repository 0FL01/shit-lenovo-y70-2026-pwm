"""Variant A OFFLINE model, not runtime or a standalone lifecycle controller.

All process/socket/filesystem/sleep dependencies are injected; no real acquisition,
CLI, daemon, fallback, automatic recovery or mutation retry. Caller owns panel
uncertainty/recovery/cleanup. Close/timeout never proves remote cancellation.
Trusted host/kernel/root/server: snapshots do not authenticate a TCP peer atomically.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import math
from pathlib import PurePosixPath
import re
import stat
import struct
import subprocess
import time
from types import MappingProxyType

ENDPOINT = ('127.0.0.1', 5037)
PROTOCOL = b'0029'
MAX_OUTPUT = 16 * 1024 * 1024


@dataclass(frozen=True)
class ProcessIdentity:
    endpoint: tuple
    pid: int
    starttime: int
    uids: tuple
    executable: str
    executable_device: int
    executable_inode: int
    executable_mode: int
    executable_uid: int
    version: bytes


@dataclass(frozen=True)
class OperationFacts:
    operation: str
    dispatched: bool = False
    accepted: bool = False
    completed: bool = False
    uncertain: bool = False
    bytes_received: int = 0
    trust_invalidated: bool = False


class TransportError(RuntimeError):
    def __init__(self, reason, *, facts=None):
        super().__init__(reason)
        self.facts = facts
        self.uncertain = bool(facts and facts.uncertain)


class Refused(TransportError):
    pass


@dataclass(frozen=True)
class SinkIdentity:
    path: str
    uid: int
    mode: int
    parent_uid: int
    parent_mode: int
    exclusive: bool
    no_symlinks: bool
    # Fixture corroboration, NOT a production filesystem implementation.


class OfflineBaselineADB:
    """Small baseline API model, deliberately no push.

    acquire(deadline) must associate ALL endpoint listeners to one pinned process.
    make_socket() returns an unconnected socket fixture.
    create_sink(exact_path, deadline) returns a fresh exclusive sink with identity,
    write(bytes)->count, close(). It MUST refuse an existing destination; close
    retains partial private data, never deletes/overwrites/retries another path.
    There is no production implementation of these contracts here.
    expected_serials is ordered (research target, camera).
    expected_destination pins exactly one private capture.mp4 path. expected_uid
    pins its owner and parent owner, independently of modeled ADB-server UID0.
    """
    def __init__(self, *, expected_process, expected_serials, acquire, make_socket,
                 create_sink, expected_destination, expected_uid, sleep,
                 monotonic=time.monotonic):
        if not isinstance(expected_process, ProcessIdentity):
            raise ValueError('Explicit process pin required')
        self._validate_process(expected_process)
        serials = tuple(expected_serials)
        if len(serials) != 2 or len(set(serials)) != 2 or any(
            not isinstance(s, bytes) or not re.fullmatch(rb'[A-Za-z0-9_.-]{1,256}',s)
            or s == b'unknown' for s in serials):
            raise ValueError('Two distinct expected serials required')
        path = PurePosixPath(expected_destination)
        if (not isinstance(expected_destination,str) or not path.is_absolute()
                or str(path) != expected_destination or '..' in path.parts
                or path.name != 'capture.mp4' or len(path.parts)<3
                or type(expected_uid) is not int or expected_uid < 0):
            raise ValueError('Exact private capture destination and owner required')
        if not all(callable(x) for x in (acquire,make_socket,create_sink,sleep,monotonic)):
            raise ValueError('Explicit fixture dependencies required')
        self._pin, self._serials = expected_process, serials
        self._acquire, self._make_socket, self._create_sink = acquire, make_socket, create_sink
        self._destination, self._uid = expected_destination, expected_uid
        self._sleep, self._clock = sleep, monotonic
        self._identities = {}
        self.protocol = None
        self.trust_invalidated = False
        self._busy = False
        self.last_facts = None

    @property
    def identities(self):
        return MappingProxyType(self._identities)

    @staticmethod
    def _validate_process(p):
        if (p.endpoint != ENDPOINT or type(p.pid) is not int or p.pid <= 0
                or type(p.starttime) is not int or p.starttime <= 0
                or p.uids != (0,0,0,0) or p.executable_uid != 0
                or not p.executable.startswith('/') or p.executable.endswith('/')
                or not stat.S_ISREG(p.executable_mode) or p.executable_mode & 0o022
                or not p.executable_mode & 0o111 or p.executable_device < 0
                or p.executable_inode <= 0 or not isinstance(p.version,bytes)
                or p.version.splitlines()[:1] != [b'Android Debug Bridge version 1.0.41']):
            raise ValueError('Invalid fixed existing-server process pin')

    def _remaining(self, deadline):
        left = deadline-self._clock()
        if left <= 0:
            raise TimeoutError('Absolute operation deadline exceeded')
        return left

    def _invalidate(self, reason):
        self.trust_invalidated = True
        raise TransportError(reason)

    def _process(self, deadline):
        self._remaining(deadline)
        found = self._acquire(deadline)
        # Observed mismatch remains terminal even if acquisition returned late.
        if type(found) is not tuple or len(found)!=1 or found[0]!=self._pin:
            self._invalidate('Process association missing, ambiguous or changed')
        self._remaining(deadline)

    @contextmanager
    def _operation(self, name, timeout):
        if self.trust_invalidated or self._busy:
            raise TransportError('Server trust invalidated or operation busy', facts=
                OperationFacts(name,trust_invalidated=self.trust_invalidated))
        if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not math.isfinite(timeout) or not 0<timeout<=600:
            raise ValueError('Finite bounded positive timeout required')
        deadline=self._clock()+timeout
        state=dict(operation=name,dispatched=False,accepted=False,completed=False,
                   uncertain=False,bytes_received=0,trust_invalidated=False)
        self._busy=True
        try:
            self._process(deadline)
            try:
                yield deadline,state
            finally:
                self._process(deadline)
            state['completed']=True
        except BaseException as error:
            state['uncertain']=state['dispatched'] and not isinstance(error,Refused)
            state['trust_invalidated']=self.trust_invalidated
            self.last_facts=OperationFacts(**state)
            if isinstance(error,(KeyboardInterrupt,SystemExit)):
                raise
            if isinstance(error,TransportError):
                error.facts=self.last_facts;error.uncertain=self.last_facts.uncertain
                raise
            raise TransportError('Transport operation failed',facts=self.last_facts) from None
        else:
            self.last_facts=OperationFacts(**state)
        finally:
            self._busy=False

    @contextmanager
    def _socket(self,deadline):
        self._remaining(deadline)
        sock=self._make_socket()
        try:
            sock.settimeout(self._remaining(deadline));sock.connect(ENDPOINT)
            self._remaining(deadline)
            yield sock
        finally:
            sock.close()

    def _send(self,sock,payload,deadline):
        view=memoryview(payload)
        while view:
            sock.settimeout(self._remaining(deadline));count=sock.send(view)
            self._remaining(deadline)
            if type(count) is not int or count<=0 or count>len(view):
                raise TransportError('Invalid or closed send')
            view=view[count:]

    def _exact(self,sock,count,deadline):
        data=bytearray()
        while len(data)<count:
            sock.settimeout(self._remaining(deadline));part=sock.recv(count-len(data))
            self._remaining(deadline)
            if not part or len(part)>count-len(data):
                raise TransportError('Truncated or invalid response')
            data.extend(part)
        return bytes(data)

    def _frame(self,sock,cap,deadline):
        header=self._exact(sock,4,deadline)
        if re.fullmatch(rb'[0-9a-fA-F]{4}',header) is None:
            raise TransportError('Malformed length')
        size=int(header,16)
        if size>cap:raise TransportError('Oversized frame')
        return self._exact(sock,size,deadline)

    def _request(self,sock,service,deadline,state=None):
        data=service.encode('ascii')
        if not data or len(data)>65535:raise ValueError('Invalid service size')
        if state is not None:state['dispatched']=True
        self._send(sock,f'{len(data):04x}'.encode()+data,deadline)
        status=self._exact(sock,4,deadline)
        if status==b'FAIL':
            self._frame(sock,4096,deadline)
            raise Refused('ADB service refused; no retry')
        if status!=b'OKAY':raise TransportError('Malformed ADB status')
        if state is not None:state['accepted']=True

    def _host(self,service,cap,deadline):
        with self._socket(deadline) as sock:
            self._request(sock,service,deadline)
            return self._frame(sock,cap,deadline)

    def _version(self,deadline):
        if self._host('host:version',16,deadline)!=PROTOCOL:
            self._invalidate('Expected ADB protocol 41')

    def _ready(self):
        if self.protocol!=PROTOCOL:raise TransportError('Preflight required')

    def preflight(self):
        with self._operation('preflight',12) as (deadline,_):self._version(deadline)
        self.protocol=PROTOCOL

    def host(self,service):
        if service not in ('host:version','host:devices-l'):raise ValueError('Unsupported host service')
        with self._operation('host',12) as (deadline,_):
            self._ready();self._version(deadline)
            # _version already validated this response; do not make a second
            # unchecked protocol query that could observe and ignore a change.
            return PROTOCOL if service=='host:version' else self._host(service,65535,deadline)

    @staticmethod
    def _transport(transport):
        value=str(transport)
        if re.fullmatch(r'[1-9][0-9]{0,19}',value) is None:
            raise ValueError('Positive canonical transport alias required')
        return value

    def _inventory(self,deadline):
        raw=self._host('host:devices-l',65535,deadline)
        rows,ids={},set()
        for line in raw.splitlines():
            fields=line.split()
            if not fields:continue
            tids=[v[13:] for v in fields[2:] if v.startswith(b'transport_id:')]
            if len(fields)<2 or len(tids)!=1:raise TransportError('Malformed device listing')
            tid=self._transport(tids[0].decode('ascii'))
            if tid in ids or fields[0] in rows:raise TransportError('Duplicate serial or transport ID')
            ids.add(tid);rows[fields[0]]=(tid,fields[1],tuple(fields[2:]))
        return rows

    def _bound(self,transport,deadline):
        tid=self._transport(transport)
        if tid not in self._identities:raise TransportError('Immutable serial binding required')
        serial=self._identities[tid]
        rows=self._inventory(deadline)
        if serial not in rows or rows[serial][1]!=b'device':
            raise TransportError('Expected selected device absent or not ready')
        return serial

    def bind(self,transport,timeout=12):
        tid=self._transport(transport)
        with self._operation('bind',timeout) as (deadline,_):
            self._ready();self._version(deadline)
            if tid in self._identities:
                # Alias survives numeric-ID reuse. Never reassign from inventory.
                serial=self._bound(tid,deadline)
                with self._socket(deadline) as sock:
                    self._request(sock,'host:transport:'+serial.decode('ascii'),deadline)
            else:
                rows=self._inventory(deadline)
                if any(s not in rows or rows[s][1]!=b'device' for s in self._serials):
                    raise TransportError('Initial expected two-device map incomplete')
                matches=[s for s in self._serials if rows[s][0]==tid]
                if len(matches)!=1:raise TransportError('Transport not an expected device')
                serial=matches[0]
                actual=self._host('host-transport-id:'+tid+':get-serialno',256,deadline)
                if actual!=serial:raise TransportError('Selected transport serial mismatch')
        self._identities[tid]=serial
        return serial

    @contextmanager
    def _selected(self,transport,service,deadline,state):
        self._ready();self._version(deadline)
        serial=self._bound(transport,deadline)
        with self._socket(deadline) as sock:
            self._request(sock,'host:transport:'+serial.decode('ascii'),deadline)
            self._request(sock,service,deadline,state)
            yield sock

    def shell(self,transport,command,timeout):
        self._transport(transport)
        if not isinstance(command,str) or not command or '\x00' in command:
            raise ValueError('Explicit shell command required')
        service='shell,v2,raw:'+command
        if len(service.encode('ascii'))>65535:raise ValueError('Service too long')
        with self._operation('shell',timeout) as (deadline,state):
            with self._selected(transport,service,deadline,state) as sock:
                out,err=bytearray(),bytearray()
                while True:
                    channel,size=struct.unpack('<BI',self._exact(sock,5,deadline))
                    if size>MAX_OUTPUT or (channel!=3 and len(out)+len(err)+size>MAX_OUTPUT):
                        raise TransportError('Shell output bound exceeded')
                    if channel not in (1,2,3) or (channel==3 and size!=1):
                        raise TransportError('Malformed shell-v2 frame')
                    data=self._exact(sock,size,deadline)
                    if channel==3:return data[0],bytes(out),bytes(err)
                    state['bytes_received']+=size
                    (out if channel==1 else err).extend(data)

    def reboot(self,transport,timeout=15):
        if self._identities.get(self._transport(transport)) != self._serials[0]:
            raise ValueError('Original research-target alias required for reboot')
        with self._operation('reboot',timeout) as (deadline,state):
            with self._selected(transport,'reboot:',deadline,state) as sock:
                sock.settimeout(self._remaining(deadline));data=sock.recv(1)
                self._remaining(deadline)
                if data:raise TransportError('Unexpected reboot response payload')
        # completed describes request exchange only, NOT observed reboot/changed boot.

    def wait_target(self,serial,timeout=75):
        if not isinstance(serial,str):raise ValueError('Exact expected target serial required')
        expected=serial.encode('ascii')
        if expected != self._serials[0] or expected not in self._identities.values():
            raise ValueError('Original bound serial required')
        with self._operation('wait_target',timeout) as (deadline,_):
            self._ready()
            while True:
                self._version(deadline);rows=self._inventory(deadline)
                if expected in rows:
                    tid,status,metadata=rows[expected]
                    if status==b'device':
                        if metadata.count(b'device:avr')!=1:
                            raise TransportError('Expected target metadata mismatch')
                        return int(tid)
                self._sleep(min(1,self._remaining(deadline)))
                self._remaining(deadline)

    def sync(self,transport,local,remote,*,pull,timeout,expected_size,byte_cap):
        self._transport(transport)
        if self._identities.get(str(transport)) != self._serials[1]:
            raise ValueError('Original camera alias required for pull')
        if pull is not True:raise ValueError('Only actual caller pull is modeled')
        if str(local)!=self._destination:raise ValueError('Exact private destination required')
        if not isinstance(remote,str) or re.fullmatch(r'/sdcard/DCIM/OpenCamera/[A-Za-z0-9_.-]+\.mp4',remote) is None:
            raise ValueError('Exact selected camera path required')
        if (type(expected_size) is not int or type(byte_cap) is not int
                or not 0<expected_size<=byte_cap<=2**63-1):
            raise ValueError('Explicit positive observed size and finite byte cap required')
        with self._operation('pull',timeout) as (deadline,state):
            # Sink is created only after protocol and exact device selection checks.
            with self._selected(transport,'sync:',deadline,state) as sock:
                sink=self._create_sink(self._destination,deadline,observed_size=expected_size)
                try:
                    self._remaining(deadline)
                    ident=sink.identity
                    if not isinstance(ident,SinkIdentity) or (ident.path!=self._destination
                            or ident.uid!=self._uid or ident.parent_uid!=self._uid
                            or ident.mode!=stat.S_IFREG|0o600 or ident.parent_mode!=stat.S_IFDIR|0o700
                            or ident.exclusive is not True or ident.no_symlinks is not True):
                        raise TransportError('Private exclusive sink contract rejected')
                    path=remote.encode('ascii')
                    self._send(sock,b'RECV'+struct.pack('<I',len(path))+path,deadline)
                    while True:
                        kind,size=struct.unpack('<4sI',self._exact(sock,8,deadline))
                        if kind==b'DONE':
                            if size!=0:raise TransportError('Malformed sync DONE')
                            if state['bytes_received']!=expected_size:
                                raise TransportError('Pull size differs from observed size')
                            break
                        if kind==b'FAIL':
                            if size>4096:raise TransportError('Oversized sync error')
                            self._exact(sock,size,deadline)
                            raise TransportError('Sync pull refused; no retry')
                        if kind!=b'DATA' or not 0<size<=65536 or state['bytes_received']+size>min(expected_size,byte_cap):
                            raise TransportError('Invalid or oversized sync DATA')
                        data=self._exact(sock,size,deadline)
                        state['bytes_received']+=size
                        view=memoryview(data)
                        while view:
                            self._remaining(deadline);count=sink.write(view);self._remaining(deadline)
                            if type(count) is not int or not 0<count<=len(view):
                                raise TransportError('Invalid sink write')
                            view=view[count:]
                    self._send(sock,b'QUIT'+struct.pack('<I',0),deadline)
                finally:
                    sink.close()
                    self._remaining(deadline)

    def run(self,argv,*,capture_output=True,text=False,timeout=25,check=False,
            expected_size=None,byte_cap=None):
        if len(argv)<4 or argv[:2]!=['adb','-t'] or capture_output is not True:
            raise ValueError('Only explicit captured transport commands supported')
        tid,action,*args=argv[2:]
        rc,out,err=0,b'',b''
        if action!='pull' and (expected_size is not None or byte_cap is not None):
            raise ValueError('Pull metadata on wrong action')
        if action=='shell' and len(args)==1:rc,out,err=self.shell(tid,args[0],timeout)
        elif action=='get-serialno' and not args:out=self.bind(tid,timeout)
        elif action=='reboot' and not args:self.reboot(tid,timeout)
        elif action=='pull' and len(args)==2:
            self.sync(tid,args[1],args[0],pull=True,timeout=timeout,expected_size=expected_size,byte_cap=byte_cap)
        else:raise ValueError('Unsupported guarded action; no push')
        if text:out,err=out.decode(errors='replace'),err.decode(errors='replace')
        result=subprocess.CompletedProcess(['adb','<redacted>'],rc,out,err)
        if check and rc:raise TransportError('Guarded shell returned nonzero',facts=self.last_facts)
        return result
