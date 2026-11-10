#!/usr/bin/env python3
"""Pinned separate observation launcher. Default source/config check only.

Externally authenticate THIS file before Python -I. Explicit --execute-capture
uses independently pinned private configs and a real prior visual review.
No credentials, package install, AA entrypoint, daemon launch, or retries.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time
from types import ModuleType


def need(ok):
    if not ok:raise ValueError('capture_launcher_rejected')


def pairs(values):
    out={}
    for k,v in values:
        need(k not in out);out[k]=v
    return out


def read_file(path, cap, *, private=False):
    need(type(path) is str and path.startswith('/') and path!='/')
    parts=path.split('/')[1:];need(all(x and x not in ('.','..') for x in parts))
    parent=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        for part in parts[:-1]:
            nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
            old,parent=parent,nxt;os.close(old)
        fd=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
        try:
            before=os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and 0<before.st_size<=cap and before.st_nlink==1)
            if private:
                directory=os.fstat(parent)
                need(before.st_uid==os.getuid() and before.st_mode==stat.S_IFREG|0o600 and
                     directory.st_uid==os.getuid() and directory.st_mode==stat.S_IFDIR|0o700)
            raw=bytearray()
            while len(raw)<=cap:
                b=os.read(fd,min(65536,cap+1-len(raw)))
                if not b:break
                raw.extend(b)
            after=os.fstat(fd)
            keys=('st_dev','st_ino','st_mode','st_uid','st_size','st_nlink','st_mtime_ns','st_ctime_ns')
            need(len(raw)==before.st_size and all(getattr(before,k)==getattr(after,k) for k in keys))
            return bytes(raw)
        finally:os.close(fd)
    finally:os.close(parent)


def read_json(path,cap=65536):
    return json.loads(read_file(path,cap,private=True),object_pairs_hook=pairs,
          parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite')))


def exact(obj,keys):need(type(obj) is dict and set(obj)==set(keys))


def sha(value):need(type(value) is str and re.fullmatch('[a-f0-9]{64}',value))


def prior_review(config, sources, expected_serials, reader=read_file):
    exact(config,('inspection_path','inspection_sha256','camera_png_path','camera_png_sha256',
                  'target_png_path','target_png_sha256','roi','scene_component','decision'))
    for key in ('inspection_sha256','camera_png_sha256','target_png_sha256'):sha(config[key])
    need(config['decision']=='geometry_layout_approved_for_observation_only')
    raw=reader(config['inspection_path'],1024*1024,private=True)
    need(hashlib.sha256(raw).hexdigest()==config['inspection_sha256'])
    receipt=json.loads(raw,object_pairs_hook=pairs)
    exact(receipt,('schema','receipt_phase','source_provenance','roles','inspection_boot_before',
                   'inspection_boot_after','screenshot_custody','summary'))
    need(receipt['schema']==1 and receipt['receipt_phase']=='before_descriptor_close' and
         type(receipt['summary']) is dict and receipt['summary'].get('status')=='prestart_inspected')
    before,after=receipt['inspection_boot_before'],receipt['inspection_boot_after']
    need(type(before) is dict and set(before)=={'target','camera'} and before==after)
    need(all(re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',x) for x in before.values()))
    need(tuple(receipt['roles'][r]['serial'] for r in ('target','camera'))==tuple(expected_serials))
    provenance=receipt['source_provenance'];m=sources.modules
    need(provenance['helper_sha256']==sources.hashes['prestart_inspection'] and
         provenance['probe_sha256']==sources.hashes['stock_readonly_probe'] and
         provenance['launch_sha256']==sources.hashes['readonly_launch'])
    need(provenance['parser_source_sha256']=={p:h for p,h in m['prestart_inspection'].PARSER_SOURCES.values()})
    for key,name in (('probe','stock_readonly_probe'),('offline_baseline_adb','offline_baseline_adb'),
                     ('linux_adb_probe_dependencies','linux_adb_probe_dependencies'),('camera_capture_metadata','camera_capture_metadata')):
        need(provenance['dependency_sha256'][key]==sources.hashes[name])
    summary=receipt['summary'];need(summary['status']=='prestart_inspected' and summary['boot_stable'] is True)
    target=summary['target'];need(target['settings_foreground'] is True and target['unlocked'] is True)
    need(target['native_mode']['native_actual_hz']==120 and target['native_mode']['native_group']==3 and abs(target['software_hz']-120)<.03)
    for role in ('camera','target'):
        image=reader(config[role+'_png_path'],16*1024*1024,private=True)
        info=sources.modules['prestart_inspection'].validate_png(image)
        need(info['sha256']==config[role+'_png_sha256']==summary['screenshots'][role]['sha256']==receipt['screenshot_custody'][role]['sha256'])
        need(info['bytes']==receipt['screenshot_custody'][role]['size'])
    protocol=sources.modules['protocol_v2']
    roi={k:tuple(v) for k,v in config['roi'].items()}
    result=protocol.PriorGeometryReview(boots=before,source=dict(sources.provenance),
        inspection_sha256=config['inspection_sha256'],camera_png_sha256=config['camera_png_sha256'],
        target_png_sha256=config['target_png_sha256'],scene_component=config['scene_component'],
        roi=roi,decision=config['decision'])
    result.validate(before,dict(sources.provenance))
    return result


def prepare(source_root, process_config_path, capture_config_path):
    need(type(source_root) is str and source_root.startswith('/') and not source_root.endswith('/'))
    need(all(x and x not in ('.','..') for x in source_root.split('/')[1:]))
    cfg=read_json(capture_config_path)
    exact(cfg,('schema','source_commit','construction_sha256','launcher_sha256','source_sha256','directory_name','token',
               'max_video_bytes','reserve_bytes','no_concurrent_writers','no_concurrent_namespace_mutation','review'))
    need(type(cfg['schema']) is int and cfg['schema']==1 and re.fullmatch('[a-f0-9]{40}',cfg['source_commit']))
    sha(cfg['construction_sha256']);sha(cfg['launcher_sha256'])
    def git(*args):
        p=subprocess.run(['/usr/bin/git','-C',source_root,*args],capture_output=True,timeout=10,check=False)
        need(p.returncode==0 and len(p.stdout)<=65536)
        return p.stdout.strip().decode('ascii')
    need(git('rev-parse','--verify','HEAD')==cfg['source_commit'])
    def source(relative, expected):
        raw=read_file(source_root+'/'+relative,512*1024)
        need(hashlib.sha256(raw).hexdigest()==expected)
        blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        need(git('rev-parse',cfg['source_commit']+':'+relative)==blob)
        return raw
    construction_path='06-tools/stock_observation_20261110/construction.py'
    raw=source(construction_path,cfg['construction_sha256'])
    launcher_path='06-tools/stock_observation_20261110/launch.py'
    launcher_raw=source(launcher_path,cfg['launcher_sha256'])
    need(Path(__file__).resolve()==Path(source_root+'/'+launcher_path).resolve())
    need(hashlib.sha256(read_file(str(Path(__file__).resolve()),512*1024)).hexdigest()==cfg['launcher_sha256'])
    need('stock_observation_construction' not in sys.modules)
    construction=ModuleType('stock_observation_construction');construction.__file__=construction_path
    sys.modules[construction.__name__]=construction
    exec(compile(raw,construction_path,'exec',dont_inherit=True),construction.__dict__)
    need(type(cfg['source_sha256']) is dict and set(cfg['source_sha256'])==set(construction.SOURCES))
    for value in cfg['source_sha256'].values():sha(value)
    sources=construction.load_sources({n:source(path,cfg['source_sha256'][n]) for n,path in construction.SOURCES.items()},
                                     cfg['source_sha256'],commit=cfg['source_commit'],bootstrap_sha256={
        construction_path:cfg['construction_sha256'],launcher_path:cfg['launcher_sha256']})
    m=sources.modules
    pc=m['readonly_launch'].parse_config(read_file(process_config_path,16384,private=True))
    # Reuse actual pinned server/role config only; old source commit is NOT promoted
    # to new code provenance. Relevant immutable dependency bytes must still match.
    for key,name in (('probe','stock_readonly_probe'),('offline_baseline_adb','offline_baseline_adb'),
                     ('linux_adb_probe_dependencies','linux_adb_probe_dependencies'),('camera_capture_metadata','camera_capture_metadata')):
        need(pc['source_sha256'][key]==sources.hashes[name])
    process=dict(pc['process']);process['uids']=tuple(process['uids']);process['version']=process['version'].encode('ascii')
    adb,dep=m['offline_baseline_adb'],m['linux_adb_probe_dependencies']
    pin=dep.VerifiedPin(process=adb.ProcessIdentity(endpoint=adb.ENDPOINT,**process),**pc['association'])
    need(type(cfg['max_video_bytes']) is int and 0<cfg['max_video_bytes']<=256*1024*1024 and
         type(cfg['reserve_bytes']) is int and 0<=cfg['reserve_bytes']<=2**63-1)
    need(cfg['no_concurrent_writers'] is True and cfg['no_concurrent_namespace_mutation'] is True)
    fm,sm=m['fresh_private_directory'],m['private_video_sink'];e=pc['evidence']
    inputs=construction.Inputs(process_pin=pin,proc_limits=dep.ProcLimits(**pc['limits']),
        serials=tuple(x.encode('ascii') for x in pc['serials']),base_path=e['directory'],
        base_pin=fm.BasePin(e['device'],e['inode'],pc['host_uid'],stat.S_IFDIR|0o700),
        directory_name=cfg['directory_name'],capacity=sm.CapacityPolicy(cfg['max_video_bytes'],cfg['reserve_bytes']),
        token=cfg['token'],no_concurrent_writers=True,no_concurrent_namespace_mutation=True)
    fm.checked_path(inputs.base_path,inputs.directory_name)
    need(re.fullmatch('[a-z][a-z0-9_]{7,63}',inputs.token))
    review=prior_review(cfg['review'],sources,pc['serials'])
    return construction,sources,inputs,review


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root',required=True);p.add_argument('--process-config',required=True)
    p.add_argument('--capture-config',required=True);p.add_argument('--execute-capture',action='store_true')
    args=p.parse_args(argv);prepared=None
    try:
        construction,sources,inputs,review=prepare(args.source_root,args.process_config,args.capture_config)
        if not args.execute_capture:
            print('{"status":"source_config_review_checked","device_services_sent":0,"capture_admitted":false}')
            return 0
        dep=sources.modules['linux_adb_probe_dependencies']
        prepared=construction.prepare(sources,inputs,os_api=os,socket_factory=socket.socket,
            proc=dep.LinuxProcFS(),monotonic=time.monotonic,sleep=time.sleep)
        coordinator=prepared.select()
        result=coordinator.run(review)
        prepared.close();prepared=None
        # Public allowlist only. Never print private tokens, roles, receipts/errors.
        public={k:result[k] for k in ('schema','status','camera_stopped_verified','originals_restored',
             'mutex_released','cleanup_pending','geometry_review_status','pwm_hz') if k in result}
        public['host_cleanup_verified']=True
        print(json.dumps(public,allow_nan=False,separators=(',',':')))
        return 0 if result['status']=='geometry_review_pending' and result.get('mutex_released') is True else 1
    except BaseException:
        if prepared is not None:
            try:prepared.close()
            except BaseException:pass
        print('{"status":"capture_launch_failed","capture_admitted":false}')
        return 1


if __name__=='__main__':sys.exit(main())
