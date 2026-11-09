"""INACTIVE ordinary trusted-host evidence; no transport/device/protected producer.
No-concurrent-writer is an explicit caller assertion, not a security primitive.
No CLI and no automatic analyzer admission. Descriptors remain caller-owned.
"""
import fcntl
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path
from dataclasses import asdict,is_dataclass
import offline_acceptance as a


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def identity(info):
    return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)

def snapshot(fd,*,no_concurrent_writers):
    a.check(no_concurrent_writers is True,'Explicit trusted no-writer assumption required')
    a.check(fcntl.fcntl(fd,fcntl.F_GETFL)&os.O_ACCMODE==os.O_RDONLY,'Read-only finalized descriptor required')
    before=os.fstat(fd)
    a.check(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode)==0o600 and
            before.st_uid==os.getuid() and before.st_size>0,'Private owned regular bytes required')
    digest=a.digest(fd)
    a.check(identity(before)==identity(os.fstat(fd)),'Changed during finalization')
    return before.st_size,digest

def source_evidence(acquisition_raw,fd,sink_facts,*,expected_source_identity,no_concurrent_writers):
    report=json.loads(acquisition_raw);a.check_acquisition(report)
    a.check(isinstance(report.get('experiment_id'),str) and report['experiment_id'],'Missing run id')
    facts=asdict(sink_facts) if is_dataclass(sink_facts) else dict(sink_facts)
    size=report.get('video_bytes')
    a.check(type(size) is int and size>0,'Invalid acquired size')
    a.check(facts.get('created') is True and type(facts.get('confirmed_written')) is int and
            facts['confirmed_written']==size and facts.get('write_outcome_uncertain') is False and
            facts.get('close_outcome')=='closed' and facts.get('removed_by_sink') is False,
            'Owned transfer not finalized')
    info=os.fstat(fd)
    a.check(expected_source_identity is not None and
            (info.st_dev,info.st_ino,info.st_uid,info.st_mode)==tuple(expected_source_identity),
            'Finalized FD differs from owned sink inode')
    actual,digest=snapshot(fd,no_concurrent_writers=no_concurrent_writers)
    a.check(actual==size,'Source size mismatch')
    return {'status':'source_finalized','run_id':report['experiment_id'],'size':size,
            'source_sha256':digest,'acquisition_raw_sha256':sha(acquisition_raw),
            'acquisition_canonical_sha256':sha(canonical(report)),
            'sink_facts':facts,'source_identity':list(expected_source_identity),'trusted_no_concurrent_writers':True,
            'evidence_kind':report.get('evidence_kind','acquisition')}

def destination_receipt(acquisition_raw,source,fd,*,no_concurrent_writers):
    report=json.loads(acquisition_raw);a.check_acquisition(report)
    a.check(source.get('status')=='source_finalized' and source.get('trusted_no_concurrent_writers') is True,
            'Missing finalized source evidence')
    a.check(source.get('acquisition_raw_sha256')==sha(acquisition_raw) and
            source.get('acquisition_canonical_sha256')==sha(canonical(report)) and
            source.get('run_id')==report.get('experiment_id'),'Source/report binding mismatch')
    size,digest=snapshot(fd,no_concurrent_writers=no_concurrent_writers)
    a.check(size==source.get('size')==report.get('video_bytes') and digest==source.get('source_sha256'),
            'Destination differs from source bytes')
    return {**source,'status':'verified_finalized_transfer','destination_sha256':digest}

def write_private(dirfd,name,data):
    a.check(name in ('acquisition.json','transfer.json','video-probe.json','derived-video.json'), 'Unexpected artifact name')
    parent=os.fstat(dirfd)
    a.check(stat.S_ISDIR(parent.st_mode) and stat.S_IMODE(parent.st_mode)==0o700 and
            parent.st_uid==os.getuid(),'Private owned artifact directory required')
    fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=dirfd)
    try:
        info=os.fstat(fd)
        a.check(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode)==0o600 and info.st_uid==os.getuid(),'Bad artifact identity')
        view=memoryview(data)
        while view:
            count=os.write(fd,view);a.check(0<count<=len(view),'Invalid artifact write');view=view[count:]
    finally:os.close(fd)

def consumer_sources():
    parent=Path(__file__).resolve().parent
    return {name:sha((parent/name).read_bytes()) for name in
            ('host_evidence.py','offline_acceptance.py','video_validator_snapshot.py')}

def consume(acquisition_raw,fd,receipt,dirfd,*,no_concurrent_writers,run=subprocess.run,validator_bytes=None):
    """Persist exact input/probe/result exclusively. On failure retain artifacts; no retry."""
    report=json.loads(acquisition_raw)
    # Recheck destination, not just a caller-supplied receipt flag.
    source={**receipt,'status':'source_finalized'}
    verified=destination_receipt(acquisition_raw,source,fd,no_concurrent_writers=no_concurrent_writers)
    a.check(verified==receipt,'Receipt mismatch')
    write_private(dirfd,'acquisition.json',acquisition_raw)
    write_private(dirfd,'transfer.json',canonical(receipt)+b'\n')
    result=a.accept(report,fd,receipt,run=run,
        persist_probe=lambda raw:write_private(dirfd,'video-probe.json',raw),validator_bytes=validator_bytes)
    result.update(derived_schema='p85-deferred-video-validation-v2',
                  consumer_source_sha256=consumer_sources(),
                  acquisition_raw_sha256=sha(acquisition_raw),
                  evidence_kind=receipt.get('evidence_kind','acquisition'),
                  optical_approval=False,analyzer_join_status='not_implemented')
    write_private(dirfd,'derived-video.json',canonical(result)+b'\n')
    return result
