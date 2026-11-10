"""Bounded trusted-host stream transfer. Stdlib only; no network/device code.

Caller owns authenticated transport, process timeout and actual exit status.
Exact source capsule is immutable. No media conversion or acquisition admission.
"""
from contextlib import contextmanager
from dataclasses import asdict
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
import types

ROOT=Path(__file__).resolve().parents[2]
SELF='06-tools/stock_observation_analysis_20261110/transfer.py'
SOURCES={
 'offline_baseline_adb':'06-tools/host_adb_full_api_spike/offline_baseline_adb.py',
 'private_video_sink':'06-tools/host_private_sink_20261109/private_video_sink.py',
 'fresh_private_directory':'06-tools/host_source_integration_20261109/fresh_private_directory.py',
 'offline_acceptance':'06-tools/video_validation_split_20261109/offline_acceptance.py',
 'host_evidence':'06-tools/video_validation_split_20261109/host_evidence.py',
}
CAP=256*1024*1024
HEADER_CAP=32*1024*1024
KEYS={'before','recording-snapshots','outcome','source-closure'}


def need(ok,msg):
    if not ok:raise ValueError(msg)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def identity(st):return [st.st_dev,st.st_ino,st.st_uid,st.st_mode]
def stable(st):return identity(st)+[st.st_nlink,st.st_size,st.st_mtime_ns,st.st_ctime_ns]


def verify_sources(expected):
    need(type(expected) is dict and set(expected)=={SELF,*SOURCES.values()},'independent transfer helper pins required')
    raw={p:(ROOT/p).read_bytes() for p in expected}
    need(all(re.fullmatch('[a-f0-9]{64}',str(expected[p])) and sha(raw[p])==expected[p] for p in raw),
         'transfer helper source mismatch')
    return raw


@contextmanager
def dependencies(expected):
    raw=verify_sources(expected)
    need(not set(SOURCES).intersection(sys.modules),'transfer dependency already loaded')
    loaded={}
    try:
        for name,path in SOURCES.items():
            module=types.ModuleType(name);module.__file__=str(ROOT/path)
            loaded[name]=module;sys.modules[name]=module
            exec(compile(raw[path],str(ROOT/path),'exec'),module.__dict__)
        yield loaded
    finally:
        for name,module in loaded.items():
            if sys.modules.get(name) is module:del sys.modules[name]


def open_private(path):
    path=Path(path);parent=path.parent.lstat()
    need(stat.S_ISDIR(parent.st_mode) and stat.S_IMODE(parent.st_mode)==0o700 and parent.st_uid==os.getuid(),
         'owned private parent required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        st=os.fstat(fd)
        need(stat.S_ISREG(st.st_mode) and stat.S_IMODE(st.st_mode)==0o600 and
             st.st_uid==os.getuid() and st.st_nlink==1,'owned private regular file required')
        return fd,st
    except BaseException:os.close(fd);raise


def private_read(path,cap):
    fd,st=open_private(path)
    try:
        need(0<st.st_size<=cap,'private input byte cap')
        with os.fdopen(os.dup(fd),'rb') as f:raw=f.read(cap+1)
        need(len(raw)==st.st_size and stable(st)==stable(os.fstat(fd)),'private input changed')
        return raw
    finally:os.close(fd)


def tick(deadline):need(type(deadline) in (int,float) and math.isfinite(deadline) and time.monotonic()<deadline,'transfer deadline')
def read_exact(stream,n,deadline):
    need(type(n) is int and 0<=n<=HEADER_CAP,'bounded wire read')
    parts=[];left=n
    while left:
        tick(deadline);part=stream.read(min(left,65536));tick(deadline)
        need(type(part) is bytes and 0<len(part)<=left,'short or invalid stream')
        parts.append(part);left-=len(part)
    return b''.join(parts)
def write_all(stream,data,deadline):
    view=memoryview(data)
    while view:
        tick(deadline);n=stream.write(view[:65536]);tick(deadline)
        need(type(n) is int and 0<n<=min(65536,len(view)),'invalid stream write');view=view[n:]
def packet_write(stream,value,deadline):
    raw=canonical(value);need(len(raw)<=HEADER_CAP,'wire metadata cap')
    write_all(stream,len(raw).to_bytes(8,'big')+raw,deadline)
def packet_read(stream,deadline):
    n=int.from_bytes(read_exact(stream,8,deadline),'big')
    need(0<n<=HEADER_CAP,'wire metadata cap')
    return json.loads(read_exact(stream,n,deadline))


def decode_header(header,expected_source,expected_helpers):
    need(header.get('schema')=='stock-observation-transfer-stream-v1' and header.get('helper_sources')==expected_helpers,
         'wrong stream/helper closure')
    need(header.get('source')==expected_source,'capture source mismatch')
    name=header.get('capsule_file','')
    need(re.fullmatch(r'[0-9]{4}-analysis-evidence\.json',name),'capsule filename')
    raw=base64.b64decode(header['capsule_raw'],validate=True)
    need(len(raw)<=4*1024*1024 and sha(raw)==header.get('capsule_sha256'),'capsule bytes changed')
    cap=json.loads(raw)
    need(cap.get('schema')=='stock-observation-analysis-evidence-v1' and cap.get('source')==expected_source,
         'capture capsule mismatch')
    need(set(cap.get('records',{}))==KEYS and set(header.get('record_raw',{}))==KEYS,'four records required')
    files={name:raw}
    for key,item in cap['records'].items():
        filename=item.get('file','')
        need(re.fullmatch('[0-9]{4}-'+re.escape(key)+r'\.json',filename),'record filename')
        data=base64.b64decode(header['record_raw'][key],validate=True)
        need(0<len(data)<=4*1024*1024 and len(data)==item.get('bytes') and
             sha(data)==item.get('sha256')==cap.get('records_sha256',{}).get(key),'record byte binding')
        files[filename]=data
    closure=json.loads(files[cap['records']['source-closure']['file']])
    need(closure.get('source')==expected_source and sha(canonical(closure.get('sha256')))==expected_source.get('closure_sha256'),
         'capture closure binding')
    media=cap.get('media',{})
    need(type(media.get('bytes')) is int and 0<media['bytes']<=CAP and
         re.fullmatch('[a-f0-9]{64}',str(media.get('sha256'))),'media bounds')
    need(header.get('source_identity')==media.get('created_identity'),'original source identity mismatch')
    need(type(header.get('source_stat')) is list and len(header['source_stat'])==8 and
         header['source_stat'][:4]==media['created_identity'] and header['source_stat'][5]==media['bytes'],
         'source stat binding')
    return cap,files


def send_bundle(capsule_path,stream,*,expected_source,expected_helpers,deadline,no_concurrent_writers):
    """Write to authenticated transport stdout; caller must enforce process timeout."""
    tick(deadline)
    need(no_concurrent_writers is True,'trusted no-writer assumption required')
    capsule_path=Path(capsule_path)
    with dependencies(expected_helpers) as modules:
        evidence=modules['host_evidence']
        capsule_raw=private_read(capsule_path,4*1024*1024);cap=json.loads(capsule_raw)
        records={}
        need(set(cap.get('records',{}))==KEYS,'four records required')
        for key,item in cap['records'].items():
            need(re.fullmatch('[0-9]{4}-'+re.escape(key)+r'\.json',item.get('file','')),'record filename')
            records[key]=private_read(capsule_path.parent/item['file'],4*1024*1024)
        fd,st=open_private(capsule_path.parent/'capture.mp4')
        try:
            need(0<st.st_size<=CAP and type(cap.get('media',{}).get('bytes')) is int and
                 st.st_size==cap['media']['bytes'], 'source media prehash byte cap')
            size,digest=evidence.snapshot(fd,no_concurrent_writers=True)
            need(size==cap['media']['bytes'] and digest==cap['media']['sha256'] and
                 identity(st)==cap['media']['created_identity'],'original capture custody mismatch')
            header={'schema':'stock-observation-transfer-stream-v1','helper_sources':expected_helpers,
                'source':expected_source,'capsule_file':capsule_path.name,'capsule_raw':base64.b64encode(capsule_raw).decode(),
                'capsule_sha256':sha(capsule_raw),'record_raw':{k:base64.b64encode(v).decode() for k,v in records.items()},
                'source_identity':identity(st),'source_stat':stable(st)}
            decode_header(header,expected_source,expected_helpers)
            packet_write(stream,header,deadline)
            os.lseek(fd,0,os.SEEK_SET);left=size;sent=hashlib.sha256()
            while left:
                tick(deadline);chunk=os.read(fd,min(65536,left));need(bool(chunk),'short source media')
                write_all(stream,chunk,deadline);sent.update(chunk);left-=len(chunk)
            need(not os.read(fd,1) and stable(st)==stable(os.fstat(fd)),'source changed during transfer')
            after_size,after_digest=evidence.snapshot(fd,no_concurrent_writers=True)
            need(after_size==size and after_digest==digest==sent.hexdigest(),'source changed during transfer')
            need(private_read(capsule_path,4*1024*1024)==capsule_raw and all(
                 private_read(capsule_path.parent/cap['records'][k]['file'],4*1024*1024)==v for k,v in records.items()),
                 'capture evidence changed during transfer')
            packet_write(stream,{'header_sha256':sha(canonical(header)),'source_before':stable(st),
                'source_after':stable(os.fstat(fd)),'source_sha256':digest,'bytes':size,
                'status':'source_read_complete'},deadline)
            stream.flush();tick(deadline)
        finally:os.close(fd)


def write_new(dirfd,name,raw):
    need('/' not in name and name not in ('.','..'),'output basename')
    fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=dirfd)
    with os.fdopen(fd,'wb') as f:f.write(raw)


def receive_bundle(stream,*,base_path,base_pin,directory_name,expected_source,
                   expected_helpers,authenticated_peer,finish_sender,deadline,no_concurrent_writers):
    """Receive trusted authenticated stdout; finish_sender must return actual exit code.

    No transport constructed. Failure may retain partial artifacts, including a
    pending receipt. Only externally observed receiver process exit0 can complete
    it. Never swallow final close failure or retry a spent destination.
    """
    tick(deadline)
    need(no_concurrent_writers is True and type(authenticated_peer) is str and authenticated_peer.strip(),
         'authenticated peer and trusted no-writer assumption required')
    need(callable(finish_sender),'actual sender exit observer required')
    with dependencies(expected_helpers) as modules:
        header=packet_read(stream,deadline);cap,files=decode_header(header,expected_source,expected_helpers)
        fm=modules['fresh_private_directory'];sm=modules['private_video_sink'];he=modules['host_evidence']
        owned=fm.OwnedDirectory(base_path=str(base_path),base_pin=fm.BasePin(*base_pin),directory_name=directory_name,
                                os_api=os,monotonic=time.monotonic)
        owned.create(deadline);sink=None
        try:
            for name,raw in files.items():write_new(owned.fd,name,raw)
            dest=owned.path/'capture.mp4';size=cap['media']['bytes']
            factory=sm.PrivateSinkFactory(exact_path=str(dest),parent_pin=sm.ParentPin(*owned.identity[:3]),
                    observed_size=size,capacity=sm.CapacityPolicy(CAP,16*1024*1024))
            sink=factory(str(dest),deadline)
            created_identity=identity(os.fstat(sink.fd));left=size
            while left:
                chunk=read_exact(stream,min(65536,left),deadline);offset=0
                while offset<len(chunk):offset+=sink.write(chunk[offset:])
                left-=len(chunk)
            sink.close();facts=asdict(sink.facts)
            footer=packet_read(stream,deadline)
            need(footer=={'header_sha256':sha(canonical(header)),'source_before':header['source_stat'],
                'source_after':header['source_stat'],'source_sha256':cap['media']['sha256'],'bytes':size,
                'status':'source_read_complete'},'source completion binding mismatch')
            tick(deadline);need(stream.read(1)==b'','trailing transfer bytes');tick(deadline)
            code=finish_sender();tick(deadline);need(type(code) is int and code==0,'sender did not exit successfully')
            fd,st=open_private(dest)
            try:
                need(identity(st)==created_identity,'destination differs from created sink inode')
                actual,digest=he.snapshot(fd,no_concurrent_writers=True)
                need(actual==size and digest==cap['media']['sha256'],'destination bytes mismatch')
            finally:os.close(fd)
            need(facts=={'created':True,'confirmed_written':size,'write_outcome_uncertain':False,
                        'close_outcome':'closed','removed_by_sink':False},'destination sink incomplete')
            owned.deadline=deadline;owned.verify()
            receipt={'schema':'stock-observation-transfer-receipt-v1','status':'destination_bytes_verified_receiver_exit_pending',
                'receiver_exit_observation_required':True,
                'helper_sources':expected_helpers,'authenticated_peer':authenticated_peer,
                'capsule_sha256':header['capsule_sha256'],'capture_source':expected_source,
                'source_identity':cap['media']['created_identity'],'source_stat':header['source_stat'],
                'source_sha256':digest,'bytes':size,'source_completion':footer,
                'stream_header_sha256':sha(canonical(header)),
                'destination_identity':identity(st),'destination_stat':stable(st),'destination_sha256':digest,
                'destination_sink_facts':facts,'sender_exit_code':code,'trusted_no_concurrent_writers':True,
                'acquisition_admitted':False,'qualification_eligible':False}
            write_new(owned.fd,'transfer.json',canonical(receipt)+b'\n')
            return Path(owned.path),receipt
        finally:
            if sink is not None and not sink.closed:sink.close()
            owned.close()


def validate_destination(receipt,*,capsule_raw,capsule_file,records_raw,cap,st,expected_helpers,authenticated_peer,receiver_exit_code):
    """Additional local inode binding; NEVER replaces capsule source identity."""
    verify_sources(expected_helpers)
    need(receipt.get('schema')=='stock-observation-transfer-receipt-v1' and
         receipt.get('status')=='destination_bytes_verified_receiver_exit_pending' and
         receipt.get('receiver_exit_observation_required') is True,'verified transfer bytes receipt missing')
    need(type(receiver_exit_code) is int and receiver_exit_code==0,
         'independently observed successful receiver process exit required')
    need(receipt.get('helper_sources')==expected_helpers and receipt.get('authenticated_peer')==authenticated_peer and
         type(authenticated_peer) is str and bool(authenticated_peer),'transfer source/peer mismatch')
    need(receipt.get('capsule_sha256')==sha(capsule_raw) and receipt.get('capture_source')==cap['source'] and
         receipt.get('source_identity')==cap['media']['created_identity'],'original capsule/custody binding mismatch')
    need(receipt.get('source_sha256')==receipt.get('destination_sha256')==cap['media']['sha256'] and
         receipt.get('bytes')==cap['media']['bytes']==st.st_size,'transfer byte binding mismatch')
    need(receipt.get('destination_identity')==identity(st) and receipt.get('destination_stat')==stable(st),
         'fresh destination inode changed')
    need(type(receipt.get('sender_exit_code')) is int and receipt['sender_exit_code']==0 and
         receipt.get('trusted_no_concurrent_writers') is True,'incomplete sender/no-writer evidence')
    need(receipt.get('destination_sink_facts')=={'created':True,'confirmed_written':st.st_size,
         'write_outcome_uncertain':False,'close_outcome':'closed','removed_by_sink':False},'destination custody incomplete')
    source_stat=receipt.get('source_stat');footer=receipt.get('source_completion',{})
    need(type(source_stat) is list and len(source_stat)==8 and source_stat[:4]==cap['media']['created_identity'] and
         source_stat[5]==st.st_size,'source stat binding missing')
    reconstructed={'schema':'stock-observation-transfer-stream-v1','helper_sources':expected_helpers,
        'source':cap['source'],'capsule_file':capsule_file,'capsule_raw':base64.b64encode(capsule_raw).decode(),
        'capsule_sha256':sha(capsule_raw),'record_raw':{k:base64.b64encode(v).decode() for k,v in records_raw.items()},
        'source_identity':cap['media']['created_identity'],'source_stat':source_stat}
    decode_header(reconstructed,cap['source'],expected_helpers)
    need(receipt.get('stream_header_sha256')==sha(canonical(reconstructed)), 'stream header binding mismatch')
    need(footer=={'header_sha256':receipt.get('stream_header_sha256'),'source_before':source_stat,
         'source_after':source_stat,'source_sha256':cap['media']['sha256'],'bytes':st.st_size,
         'status':'source_read_complete'},'source completion mismatch')
    return receipt
