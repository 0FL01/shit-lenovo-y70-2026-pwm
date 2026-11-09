"""Offline AA source/finalized receipt/acceptance closure. No transfer/device APIs.
Inputs are already-held private read-only finalized descriptors. No media retrieval.
Original acquisition bytes remain unchanged; derived records are separate.
"""
import ast
import copy
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
from dataclasses import asdict,is_dataclass
from pathlib import Path
from aa_acquisition_validation import validate_acquisition,validate_run
VALIDATOR_SNAPSHOT_SHA256="f5e82bcbbaa0c5cc2ca6c42071c8a008c55eddabc9b0f809cc6d14641be22923"

def check(value,message):
    if not value:raise RuntimeError(message)

def validator(snapshot_bytes=None):
    """Exact approved original check+validator bytes, independent of live callers.
    Phase loader may pass pinned bytes; otherwise read the tracked frozen snapshot.
    This constant is reviewed, never derived from supplied/current source bytes.
    """
    raw=(Path(__file__).resolve().parent/'video_validation_split_20261109/video_validator_snapshot.py').read_bytes() if snapshot_bytes is None else snapshot_bytes
    check(isinstance(raw,bytes) and hashlib.sha256(raw).hexdigest()==VALIDATOR_SNAPSHOT_SHA256,
          'Unapproved video validator snapshot')
    tree=ast.parse(raw)
    check(len(tree.body)==2 and all(isinstance(n,ast.FunctionDef) for n in tree.body) and
          [n.name for n in tree.body]==['check','validate_video_probe'],'Invalid snapshot structure')
    namespace={}
    exec(compile(tree,'<approved-original-video-validator>','exec'),namespace)
    return namespace['validate_video_probe']

def digest(fd):
    offset=os.lseek(fd,0,os.SEEK_CUR)
    try:
        os.lseek(fd,0,os.SEEK_SET);h=hashlib.sha256()
        while True:
            data=os.read(fd,1024*1024)
            if not data:return h.hexdigest()
            h.update(data)
    finally:os.lseek(fd,offset,os.SEEK_SET)

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def identity(info):
    return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)

def snapshot(fd,*,no_concurrent_writers):
    check(no_concurrent_writers is True,'Explicit trusted no-writer assumption required')
    check(fcntl.fcntl(fd,fcntl.F_GETFL)&os.O_ACCMODE==os.O_RDONLY,'Read-only finalized descriptor required')
    before=os.fstat(fd)
    check(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode)==0o600 and
            before.st_uid==os.getuid() and before.st_size>0,'Private owned regular bytes required')
    sha256=digest(fd)
    check(identity(before)==identity(os.fstat(fd)),'Changed during finalization')
    return before.st_size,sha256

def source_evidence(acquisition_raw,fd,sink_facts,*,expected_source_identity,no_concurrent_writers):
    report=json.loads(acquisition_raw);validate_acquisition(report)
    check(isinstance(report.get('experiment_id'),str) and report['experiment_id'],'Missing run id')
    facts=asdict(sink_facts) if is_dataclass(sink_facts) else dict(sink_facts)
    size=report.get('video_bytes')
    check(type(size) is int and size>0,'Invalid acquired size')
    check(facts.get('created') is True and type(facts.get('confirmed_written')) is int and
            facts['confirmed_written']==size and facts.get('write_outcome_uncertain') is False and
            facts.get('close_outcome')=='closed' and facts.get('removed_by_sink') is False,
            'Owned transfer not finalized')
    info=os.fstat(fd)
    check(expected_source_identity is not None and
            (info.st_dev,info.st_ino,info.st_uid,info.st_mode)==tuple(expected_source_identity),
            'Finalized FD differs from owned sink inode')
    actual,digest=snapshot(fd,no_concurrent_writers=no_concurrent_writers)
    check(actual==size,'Source size mismatch')
    return {'schema':'aa-threshold-video-source-v1','status':'source_finalized','run_id':report['experiment_id'],'size':size,
            'source_sha256':digest,'acquisition_raw_sha256':sha(acquisition_raw),
            'acquisition_canonical_sha256':sha(canonical(report)),
            'sink_facts':facts,'source_identity':list(expected_source_identity),'trusted_no_concurrent_writers':True,
            'evidence_kind':report.get('evidence_kind','acquisition')}

def validate_receipt_fields(source,schema):
    check(source.get("schema")==schema and source.get("trusted_no_concurrent_writers") is True,
          "Explicit trusted finalized-source facts required")
    check(all(isinstance(source.get(k),str) and re.fullmatch(r"[0-9a-f]{64}",source[k]) is not None for k in
              ("acquisition_raw_sha256","acquisition_canonical_sha256","source_sha256")),
          "Incomplete source/report byte identities")
    facts=source.get("sink_facts",{})
    check(type(source.get("size")) is int and source["size"]>0 and
          facts.get("created") is True and type(facts.get("confirmed_written")) is int and
          facts["confirmed_written"]==source["size"] and facts.get("write_outcome_uncertain") is False and
          facts.get("close_outcome")=="closed" and facts.get("removed_by_sink") is False,
          "Incomplete trusted sink finalization")
    identity=source.get("source_identity")
    check(isinstance(identity,list) and len(identity)==4 and all(type(x) is int and x>=0 for x in identity),
          "Missing owned source identity")

def destination_receipt(acquisition_raw,source,fd,*,no_concurrent_writers):
    report=json.loads(acquisition_raw);validate_acquisition(report)
    validate_receipt_fields(source,"aa-threshold-video-source-v1")
    check(source.get('schema')=='aa-threshold-video-source-v1' and source.get('status')=='source_finalized' and source.get('trusted_no_concurrent_writers') is True,
            'Missing finalized source evidence')
    check(source.get('acquisition_raw_sha256')==sha(acquisition_raw) and
            source.get('acquisition_canonical_sha256')==sha(canonical(report)) and
            source.get('run_id')==report.get('experiment_id'),'Source/report binding mismatch')
    size,digest=snapshot(fd,no_concurrent_writers=no_concurrent_writers)
    check(size==source.get('size')==report.get('video_bytes') and digest==source.get('source_sha256'),
            'Destination differs from source bytes')
    return {**source,'schema':'aa-threshold-video-receipt-v1','status':'verified_finalized_transfer','destination_sha256':digest}

def write_private(dirfd,name,data):
    check(name in ('acquisition.json','transfer.json','video-probe.json','derived-video.json'), 'Unexpected artifact name')
    parent=os.fstat(dirfd)
    check(stat.S_ISDIR(parent.st_mode) and stat.S_IMODE(parent.st_mode)==0o700 and
            parent.st_uid==os.getuid(),'Private owned artifact directory required')
    fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=dirfd)
    try:
        info=os.fstat(fd)
        check(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode)==0o600 and info.st_uid==os.getuid(),'Bad artifact identity')
        view=memoryview(data)
        while view:
            count=os.write(fd,view);check(0<count<=len(view),'Invalid artifact write');view=view[count:]
    finally:os.close(fd)

def accept(report,fd,receipt,*,run=subprocess.run,persist_probe=None,validator_bytes=None):
    """Return separate result; never mutate/upgrade the original acquisition report."""
    result={'status':'failed','video_profile':None,'pwm_hz':None}
    try:
        validate=validator(validator_bytes)  # reject unapproved source BEFORE ffprobe
        validate_acquisition(report)
        validate_receipt_fields(receipt,"aa-threshold-video-receipt-v1")
        check(receipt.get('schema')=='aa-threshold-video-receipt-v1','Wrong AA receipt schema')
        check(receipt.get('status')=='verified_finalized_transfer' and
              receipt.get('run_id')==report.get('experiment_id') and isinstance(report.get('experiment_id'),str) and report['experiment_id'],
              'Missing trusted run-bound transfer receipt')
        report_digest=hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        check(receipt.get('acquisition_canonical_sha256')==report_digest,'Report binding mismatch')
        check(report.get('source_worktree_clean_for_runner') is True,'Unclean acquisition source')
        info=os.fstat(fd)
        check(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode)==0o600 and info.st_uid==os.getuid(),'Not private owned regular bytes')
        check(info.st_size==report.get('video_bytes')==receipt.get('size') and info.st_size>0,'Size mismatch')
        before=digest(fd)
        check(before==receipt.get('source_sha256')==receipt.get('destination_sha256'),'Byte identity mismatch')
        probe=run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',f'/proc/self/fd/{fd}'],
                  capture_output=True,timeout=20,check=True,pass_fds=(fd,))
        if persist_probe is not None:persist_probe(probe.stdout)
        after=os.fstat(fd)
        check((after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)==
              (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns) and digest(fd)==before,'Bytes changed during probe')
        profile=validate(json.loads(probe.stdout),len(report['stages'])*4.5)
        result.update(status='awaiting_optical_review',video_profile=profile,video_sha256=before,acquisition_canonical_sha256=report_digest,
                      validator_source_sha256=VALIDATOR_SNAPSHOT_SHA256)
    except BaseException as exc:
        result['error_type']=type(exc).__name__
    return result
def consumer_sources():
    parent=Path(__file__).resolve().parent
    return {name:sha((parent/name).read_bytes()) for name in (
        "aa_video_validation.py","aa_acquisition_validation.py","analyze_aa_threshold_trial.py",
        "analyze_p85_optical.py","optical_spectrum.py",
        "video_validation_split_20261109/video_validator_snapshot.py")}

def consume(acquisition_raw,fd,receipt,dirfd,*,no_concurrent_writers,run=subprocess.run,validator_bytes=None):
    """Persist exact input/probe/result exclusively. On failure retain artifacts; no retry."""
    report=json.loads(acquisition_raw)
    # Recheck destination, not just a caller-supplied receipt flag.
    source={**receipt,'schema':'aa-threshold-video-source-v1','status':'source_finalized'}
    verified=destination_receipt(acquisition_raw,source,fd,no_concurrent_writers=no_concurrent_writers)
    check(verified==receipt,'Receipt mismatch')
    write_private(dirfd,'acquisition.json',acquisition_raw)
    write_private(dirfd,'transfer.json',canonical(receipt)+b'\n')
    result=accept(report,fd,receipt,run=run,
        persist_probe=lambda raw:write_private(dirfd,'video-probe.json',raw),validator_bytes=validator_bytes)
    result.update(derived_schema='aa-threshold-video-validation-v1',
                  consumer_source_sha256=consumer_sources(),
                  acquisition_raw_sha256=sha(acquisition_raw),
                  evidence_kind=receipt.get('evidence_kind','acquisition'),
                  optical_approval=False,analyzer_join_status='requires_external_source_bindings')
    write_private(dirfd,'derived-video.json',canonical(result)+b'\n')
    return result

def joined_view(acquisition_raw,derived_raw,fd,*,expected_bindings,no_concurrent_writers):
    """External reviewed source pins required; not an optical or execution approval."""
    report=json.loads(acquisition_raw);derived=json.loads(derived_raw)
    validate_acquisition(report)
    check(report.get("evidence_kind")=="acquisition" and derived.get("evidence_kind")=="acquisition",
          "Synthetic/unknown evidence is not admission")
    check(derived.get("derived_schema")=="aa-threshold-video-validation-v1" and
          derived.get("status")=="awaiting_optical_review" and derived.get("optical_approval") is False and
          not derived.get("error_type"),"Wrong/incomplete AA derived result")
    check(derived.get("acquisition_raw_sha256")==sha(acquisition_raw) and
          derived.get("acquisition_canonical_sha256")==sha(canonical(report)),"Derived/report binding mismatch")
    check(isinstance(expected_bindings,dict) and set(expected_bindings)=={
        "acquisition_commit","acquisition_source_blob_ids","consumer_source_sha256","validator_source_sha256"},
        "External reviewed source expectations required")
    expected=expected_bindings["acquisition_source_blob_ids"]
    check(isinstance(expected,dict) and bool(expected) and report.get("source_blob_ids")==expected and
          set(report.get("source_tracked_paths",[]))==set(expected) and
          report.get("source_commit")==expected_bindings["acquisition_commit"] and
          report.get("source_worktree_clean_for_runner") is True,"Acquisition source mismatch")
    check(derived.get("consumer_source_sha256")==expected_bindings["consumer_source_sha256"]==
          consumer_sources(),"AA consumer source mismatch")
    check(derived.get("validator_source_sha256")==expected_bindings["validator_source_sha256"]==
          VALIDATOR_SNAPSHOT_SHA256,"Video validator source mismatch")
    validator()
    view=copy.deepcopy(report)
    view.update(status="awaiting_optical_review",video_profile=copy.deepcopy(derived.get("video_profile")))
    validate_run(view)
    size,sha256=snapshot(fd,no_concurrent_writers=no_concurrent_writers)
    check(size==report["video_bytes"] and sha256==derived.get("video_sha256"),"Destination bytes mismatch")
    view.update(aa_join_schema="aa-threshold-verified-optical-view-v1",
                source_acquisition_sha256=sha(acquisition_raw),video_sha256=sha256)
    return view
