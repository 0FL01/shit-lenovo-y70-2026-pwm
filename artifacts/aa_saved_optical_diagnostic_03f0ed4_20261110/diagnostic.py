"""One saved stock recording only. Never AA admission or runtime permission.

Original acquisition remains rejected. Only an explicitly recorded in-memory
diagnostic projection adds /before/boot_id from a separately hashed raw event.
No acceptance monkeypatch, accepted view, candidate or qualification output.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parent
PRIVATE = Path('/home/opencode/.cache/legion-y70-aa-optical-media-03f0ed4-01')
RUN = Path('/home/opencode/.cache/legion-y70-aa-full-stock-03f0ed4-proposal01/run.json')
SUP = Path('/home/opencode/.cache/legion-y70-aa-calibration-boot-03f0ed4-01')
RUN_SHA = 'a2875aba1a9c7446eadb2272f3f6ed8c975d4ac50c183a193c9e2a1eb86a268a'
VIDEO_SHA = 'ed4cb72fbb4052d256e4fa02eb706d2634929b953e656eec96501ad1249f6d8f'
VIDEO_SIZE = 96172619
FAILURE = 'Missing same-trial semantic/structural redraw calibration'
PINS = {'aa_acquisition_validation.py':'2009d9d5a9845fca4fff27930ca699f58f57cf8049069f53a1dc0f9369418ad3',
        'analyze_p85_optical.py':'60023bb5ff44339efd4db04c96815e869e8edbd3298175a82df98629ca22a3c6',
        'optical_spectrum.py':'414497032b763f815d1ec48eb0d00af48a0526a1f0e31012384ddd537886db7b'}

def check(ok, message):
    if not ok: raise ValueError(message)

def sha(raw): return hashlib.sha256(raw).hexdigest()
def identity(s): return [s.st_dev,s.st_ino,s.st_uid,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns]

def read(path, cap):
    fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        check(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_size<=cap,'Unsafe input')
        data=b''
        while len(data)<=cap:
            block=os.read(fd,min(65536,cap+1-len(data)))
            if not block: break
            data+=block
        check(len(data)==before.st_size and identity(before)==identity(os.fstat(fd)),'Input changed')
        return data
    finally: os.close(fd)

for name,digest in PINS.items():
    check(sha(read(PRIVATE/'pinned_tools'/name,100000))==digest,'Pinned analysis source changed')
sys.path.insert(0,str(PRIVATE/'pinned_tools'))
import aa_acquisition_validation as acquisition
import analyze_p85_optical as optical
import numpy as np

def protocol():
    raw=read(RUN,200000);check(sha(raw)==RUN_SHA,'Original acquisition changed')
    original=json.loads(raw)
    check(original['candidate_enabled'] is False,'Stock only')
    try: acquisition.validate_acquisition(original)
    except ValueError as exc: check(str(exc)==FAILURE,'Unexpected original failure')
    else: raise ValueError('Original unexpectedly admitted')
    linkage=json.loads(read(SUP/'event_linkage.json',20000))
    check(linkage['acquisition_sha256']==RUN_SHA and linkage['source_commit']==original['source_commit'],'Supplement binding changed')
    expected={'0019-before-boot.stdout':'14ac8af8452c1413eaf3195af1fd4fbe7ecc9e143b15fbf0db1101cdc2dc7374',
              '0183-envelope-return_stock-write.stdout':'1fc25a38a67b0fa22132b24232dd2f98d49e12c309149f2ebbb9d78d2af3466b'}
    check([e['name'] for e in linkage['events']]==list(expected),'Wrong supplementary events')
    receipts={}
    for event in linkage['events']:
        data=read(SUP/event['name'],1000000)
        check(len(data)==event['bytes'] and sha(data)==event['sha256']==expected[event['name']],'Supplement bytes mismatch')
        matches=[e for e in original['events']+original['envelope_timings'] if e.get('raw_record')==event['name'][:-7]]
        check(matches==event['acquisition_records'] and len(matches)==1 and matches[0]['return_code']==0,'Supplement event linkage mismatch')
        receipts[event['name']]={'bytes':len(data),'sha256':sha(data)}
    boot=read(SUP/'0019-before-boot.stdout',37).decode('ascii').strip()
    check('boot_id' not in original['before'] and boot==original['redraw_ui_calibration']['boot_id'],'Unexpected missing-field mapping')
    projection=copy.deepcopy(original)
    projection['before']['boot_id']=boot
    stages=acquisition.validate_acquisition(projection)
    restored=copy.deepcopy(projection);del restored['before']['boot_id']
    check(restored==original and read(RUN,200000)==raw,'Projection changed any other field')
    return original,stages,{'schema':'aa-saved-stock-diagnostic-projection-v1',
        'original_acquisition_sha256':RUN_SHA,'original_strict_validation':'rejected',
        'original_rejection':FAILURE,'projection_changes':[{'op':'add','path':'/before/boot_id',
        'source':'0019-before-boot.stdout','source_sha256':expected['0019-before-boot.stdout']}],
        'projection_strict_predicates_pass':True,'projection_is_acquisition':False,
        'raw_return_boot_framing_review':'Independently checked with original strict framed parser; hashed bytes bound here.',
        'supplement':receipts,'acquisition_admitted':False,'qualification_eligible':False,'candidate_enabled':False}

def video_snapshot(video):
    fd=os.open(video,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        before=os.fstat(fd)
        check(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode)==0o600 and before.st_uid==os.getuid() and before.st_size==VIDEO_SIZE,'Wrong private video')
        digest=hashlib.sha256();n=0
        while n<VIDEO_SIZE:
            data=os.read(fd,min(65536,VIDEO_SIZE-n));check(bool(data),'Short video');n+=len(data);digest.update(data)
        check(not os.read(fd,1) and digest.hexdigest()==VIDEO_SHA and identity(before)==identity(os.fstat(fd)),'Video changed')
        return identity(before)
    finally:os.close(fd)

def save(path,value):
    with path.open('x') as f: json.dump(value,f,indent=2,allow_nan=False);f.write('\n')

def output_parent(path):
    check(path.parent.resolve()==PRIVATE,'Full diagnostic outputs must stay in the private analysis directory')
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        s=os.fstat(fd)
        check(s.st_uid==os.getuid() and stat.S_IMODE(s.st_mode)==0o700,'Private owned output directory required')
    finally:os.close(fd)

def preview_parent(path,video):
    output_parent(path)
    check(path.parent.resolve()==video.parent.resolve(),'Preview must be a child of the private video directory')
    check(not path.exists() and not path.is_symlink(),'New preview directory required')

def review_rois(review,windows):
    check(review['original_acquisition_sha256']==RUN_SHA and review['video_sha256']==VIDEO_SHA,'Review binding mismatch')
    check(review['reviewed_frames']=={w['stage']:w['review_frames'] for w in windows},'Wrong review frames')
    check(all(review.get(k) is True for k in ['native_y_noautorotate_inspected','roi_background_content_verified','fixed_geometry_verified','timestamp_margins_reviewed']) and review.get('whole_screen_flat') is False and 'flat_screen_content_verified' not in review,'Incomplete or misleading visual review')
    rois=review['rois_xywh'];check(set(rois)=={'main','left','right'},'Three ROIs required')
    for r in rois.values():
        check(type(r) is list and len(r)==4 and all(type(x) is int for x in r),'Bad ROI')
        x,y,w,h=r;check(0<=x<x+w<=1280 and 0<=y<y+h<=720 and w>=20 and h>=300,'ROI bounds')
    check(len({(r[1],r[3]) for r in rois.values()})==1,'ROI vertical mismatch')
    ordered=sorted(rois.values());check(all(a[0]+a[2]<=b[0] for a,b in zip(ordered,ordered[1:])),'ROI overlap')
    band=review['baseline_fine_search_cycles_per_row']
    check(len(band)==2 and all(optical.finite(x) for x in band) and .006<band[0]<band[1]<.1,'Fine search band')
    return rois,band

def main():
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('video',type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--review',type=Path);p.add_argument('--profiles',type=Path);p.add_argument('--preview-dir',type=Path)
    p.add_argument('--no-concurrent-writers',action='store_true',required=True)
    args=p.parse_args();output_parent(args.output);check(not args.output.exists(),'New output only')
    if args.profiles:output_parent(args.profiles)
    if args.preview_dir:preview_parent(args.preview_dir,args.video)
    original,stages,projection=protocol();before=video_snapshot(args.video)
    probe=optical.probe_video(args.video);pts,stream=optical.validate_pts(probe)
    windows=optical.select_windows_from_stages(stages,original['recording_preflight'],pts,frames=60,edge_seconds=.25,snapshot_age_seconds=.25,binding_frames=2)
    try: stronger=optical.select_windows_from_stages(stages,original['recording_preflight'],pts,frames=60,edge_seconds=.25,snapshot_age_seconds=.5,binding_frames=3)
    except optical.OpticalError as exc: stronger={'inconclusive':True,'reason':str(exc)}
    result={'schema':'aa-saved-stock-unqualified-optical-diagnostic-v1','mode':'analysis' if args.review else 'window_plan',
        'acquisition_admitted':False,'qualification_eligible':False,'candidate_enabled':False,'physical_pwm_hz':None,
        'stock_optics_restored':None,'optical_return_approval':False,'projection':projection,
        'source_acquisition_sha256':RUN_SHA,'source_video_sha256':VIDEO_SHA,'source_video_bytes':VIDEO_SIZE,
        'acquisition_source_commit':original['source_commit'],'acquisition_source_blob_ids':original['source_blob_ids'],
        'analysis_source_sha256':PINS,'harness_sha256':sha(read(Path(__file__),40000)),
        'windows':windows,'timing_assumptions':{'snapshot_max_age_seconds':.25,'encoder_binding_ambiguity_frames':2,'minimum_edge_margin_seconds':.25},
        'stronger_timing_sensitivity':stronger,'decoded_frame_count':len(pts),'stream':stream,
        'historical_created_inode_custody':'not_available','trusted_no_concurrent_writers':True,
        'limits':['Original acquisition remains rejected; projection is diagnostic only.',
        'New current-file integrity receipts do not reconstruct acquisition-time custody.',
        'Conditional timing envelopes are not exposure-to-MP4 calibration.',
        'Spatial encoded Y is not linear radiance, physical Hz or modulation depth.',
        'No comfort, full-waveform equivalence, optical return approval or candidate admission.',
        'Neighbouring ROI/frame blocks are not independent experiments; short ROI limits broad-band inference.']}
    if args.preview_dir:
        check(not args.review,'Preview and analysis separate');optical.inspect_frames(args.video,windows,args.preview_dir)
    if args.review:
        check(args.profiles is not None and not args.profiles.exists(),'New profiles required')
        review_raw=read(args.review,30000);review=json.loads(review_raw);rois,band=review_rois(review,windows)
        findings,arrays=optical.analyze(args.video,windows,rois,band)
        result.update(findings,rois_xywh=rois,review_sha256=sha(review_raw),normalization='RMS Y coefficient / (mean Y - 16)')
        arrays['pts']=pts
        check(before==video_snapshot(args.video) and sha(read(RUN,200000))==RUN_SHA,'Inputs changed during analysis')
        with args.profiles.open('xb') as f:np.savez_compressed(f,**arrays)
    check(before==video_snapshot(args.video) and sha(read(RUN,200000))==RUN_SHA,'Inputs changed during analysis')
    save(args.output,result)
    print(json.dumps({'output':str(args.output),'mode':result['mode'],'acquisition_admitted':False,'candidate_enabled':False}))

if __name__=='__main__':main()
