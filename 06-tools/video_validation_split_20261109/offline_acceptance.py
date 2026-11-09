"""INACTIVE nc-lab acceptance prototype; no CLI, transport, recovery or device I/O.
Caller supplies an already held finalized private regular-file descriptor and a
trusted transfer receipt bound to this run. This module does not produce receipts.
"""
import ast
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path
VALIDATOR_SNAPSHOT_SHA256="f5e82bcbbaa0c5cc2ca6c42071c8a008c55eddabc9b0f809cc6d14641be22923"

def check(value,message):
    if not value:raise RuntimeError(message)

def validator(snapshot_bytes=None):
    """Exact approved original check+validator bytes, independent of live callers.
    Phase loader may pass pinned bytes; otherwise read the tracked frozen snapshot.
    This constant is reviewed, never derived from supplied/current source bytes.
    """
    raw=(Path(__file__).resolve().parent/'video_validator_snapshot.py').read_bytes() if snapshot_bytes is None else snapshot_bytes
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

def check_acquisition(report):
    required=('camera_stopped_verified','explicit15_readback_and_stock_c1_return',
        'original_settings_dbv_logger_restored','camera_ui_temp_removed',
        'watchdog_disarmed','mutex_released','video_transfer_verified','video_lifecycle_complete')
    check(all(report.get(k) is True for k in required),'Incomplete lifecycle')
    check(report.get('status')=='awaiting_offline_video_validation' and
        report.get('video_validation_status')=='pending_offline','Not a pending successful acquisition')
    check(not any(report.get(k) for k in
          ('error','error_type','cleanup_error_type','camera_cleanup_error_type',
           'camera_ui_cleanup_pending','recovery_reboot_attempted',
           'physical_ddic_recovery_unverified')) and report.get('cleanup_errors',[])==[],
          'Failure/recovery cannot qualify as completed timed stock')
    check(report.get('source_worktree_clean_for_runner') is True,'Unclean acquisition source')

def accept(report,fd,receipt,*,run=subprocess.run,persist_probe=None,validator_bytes=None):
    """Return separate result; never mutate/upgrade the original acquisition report."""
    result={'status':'failed','video_profile':None,'pwm_hz':None}
    try:
        validate=validator(validator_bytes)  # reject unapproved source BEFORE ffprobe
        check_acquisition(report)
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
