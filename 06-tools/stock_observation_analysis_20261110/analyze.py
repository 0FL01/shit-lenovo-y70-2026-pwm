"""Offline v2 adapter. No acquisition/device API; no actual run exists yet.

The numeric core reuses the existing fixed-frequency estimator. Production
qualification always stays false. Actual diagnostics require the concrete
source/custody capsule and byte-bound fresh ROI review; never readiness booleans.
"""
import hashlib
import json
import math
from pathlib import Path
import sys
import subprocess

import numpy as np

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / 'stock_observation_20261110'))
import analyze_p85_optical as optical
import protocol_v2 as protocol

SCHEMA = 'stock-observation-v2-native10s-offline-analysis'
WINDOWS = tuple(protocol.WINDOWS)
ROI = dict(protocol.ROI)
Q = protocol.Q
THRESHOLD_PCT = 5.0


def need(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def finite(v):
    return type(v) in (int, float) and math.isfinite(v)


def fixed_windows():
    return [dict(stage='window' + str(i + 1), start_inclusive=a,
                 end_exclusive=b, encoded_frames=b-a,
                 review_frames=[a, a+(b-a)//2, b-1])
            for i, (a, b) in enumerate(WINDOWS)]


def probe_video(video):
    """Existing native PTS/profile check, with explicit duration/rate fields."""
    return json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_entries',
        'stream=codec_type,codec_name,width,height,pix_fmt,color_range,nb_frames,avg_frame_rate,duration:'
        'format=duration:frame=best_effort_timestamp_time', '-of', 'json', str(video)], text=True))


def validate_probe(probe):
    pts, stream = optical.validate_pts(probe)
    durations = []
    for item in (probe.get('format', {}), probe['streams'][0]):
        try:
            duration = float(item['duration'])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('explicit stream and container durations required') from exc
        need(finite(duration) and 9 <= duration <= 15,
             'nominal10s media duration outside frozen 9..15s bounds')
        durations.append(duration)
    need(abs(durations[0]-durations[1]) <= 1/30+.001, 'duration disagreement')
    need(270 <= len(pts) <= 450, 'native10s decoded frame count outside bounds')
    need(abs(pts[0]) <= 1/30+.001, 'nonzero media origin')
    need(abs(pts[-1]+1/30-durations[1]) <= 1/30+.001, 'duration/PTS endpoint mismatch')
    # Timeline only: never pass a fabricated early_controls_bound=True into
    # protocol.timeline. Actual controls require the separate unavailable proof.
    need(np.all(np.abs(np.diff(pts)-1/30) <= .001), 'cadence/gap failure')
    need(pts[-1]-pts[0] < durations[1], 'PTS span exceeds duration')
    rate = probe['streams'][0].get('avg_frame_rate', '').split('/')
    need(len(rate)==2 and all(s.isdigit() for s in rate) and int(rate[1])>0,
         'missing average frame rate')
    need(abs(int(rate[0])/int(rate[1])-30) <= .03, 'average frame rate changed')
    return pts, dict(stream, duration_seconds=durations[1], delta_from_native10s_seconds=durations[1]-10, native10s_cap_proven_by_duration=False), fixed_windows()


def inspect_records(raw_records, *, conditional=False):
    """Structural projection of CURRENT writer records; never qualification.

    Exact original bytes must be retained privately. No guessed boot field,
    synthetic ready booleans, source03 supplementation or writer repair.
    """
    need(set(raw_records)=={'before','recording-snapshots','outcome'}, 'actual recording records missing')
    need(all(type(v) is bytes for v in raw_records.values()), 'original record bytes required')
    before, snaps, out = [json.loads(raw_records[k]) for k in
                          ('before','recording-snapshots','outcome')]
    need(out.get('schema')==protocol.SCHEMA, 'not prospective v2')
    late = (conditional and out.get('status')=='inconclusive' and
            out.get('capture_validity_failure')=='early_controls_unbound' and
            out.get('recording_observation_complete') is True and
            out.get('control_coverage_status')=='unknown_first_window' and out.get('early_controls_bound') is False)
    need(out.get('status') in ('awaiting_offline_media_validation','geometry_review_pending') or late, 'failed or incomplete recording')
    need(out.get('windows')==[list(w) for w in WINDOWS], 'fixed windows changed')
    need(out.get('source')==before.get('source') and isinstance(out.get('source'),dict), 'source binding missing')
    import re
    source=out['source']
    need(re.fullmatch('[a-f0-9]{40}',str(source.get('commit'))) and
         re.fullmatch('[a-f0-9]{64}',str(source.get('closure_sha256'))), 'source identity missing')
    for key in ('boot_id','camera_boot_id'):
        need(re.fullmatch('[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',str(before.get(key))),
             'actual before boot missing')
    need(type(out.get('candidate_attempts')) is int and out['candidate_attempts']==0 and
         type(out.get('custom_dsi_writes')) is int and out['custom_dsi_writes']==0 and
         out.get('pwm_hz') is None, 'not unchanged-stock scope')
    need(all(out.get(k) is True for k in ('camera_stopped_verified',
         'advancing_recording_observed','originals_restored','mutex_released')),
         'recording/cleanup incomplete')
    need(not any(out.get(k) for k in ('cleanup_pending','cleanup_error_type',
         'transfer_error_type','late_probe_attempted')), 'failed or late run')
    need(not out.get('error_type') or (late and out['error_type']=='ValueError' and
         out.get('failure_reason')=='frame30 controls unbound'), 'unrelated recording error')
    need(out.get('early_controls_bound') is True or late, 'early controls absent')
    need(out.get('camera_limit_readback')=={'duration_seconds':10,'restart_count':0,'filesize_restart':False},
         'native cap evidence missing')
    need(finite(out.get('start_attempt_monotonic')) and out['start_attempt_monotonic']>=0 and
         finite(out.get('stop_observed_elapsed')) and 0<out['stop_observed_elapsed']<=15,
         'start-to-verified-stop budget invalid')
    need(type(snaps) is list and len(snaps)>=2, 'recording snapshots missing')
    elapsed=[s.get('elapsed') for s in snaps]
    need(all(finite(t) and 0<t<out['stop_observed_elapsed'] for t in elapsed) and
         all(a<b for a,b in zip(elapsed,elapsed[1:])) and (elapsed[1]<=1 or late),
         'early advancing snapshots absent')
    need(snaps[1].get('snapshot',{}).get('progress_verified') is True,
         'early recording pair not advancing')
    media=out.get('media',{})
    need(type(media.get('bytes')) is int and media['bytes']>0 and
         re.fullmatch('[a-f0-9]{64}',str(media.get('sha256'))) and
         media.get('created_inode_verified') is True, 'media receipt incomplete')
    return {'records_sha256':{k:digest(v) for k,v in raw_records.items()},
            'structural_records_consistent':True, 'status':'inconclusive',
            'qualification_blockers':['structural intake alone does not verify capsule/media custody'],
            'actual_measurements':None, 'acquisition_admitted':False,
            'qualification_eligible':False, 'physical_pwm_hz':None,
            'control_interpretation':'advancing snapshots only; not sensor-to-file calibration'}


def validate_roi_review(review, *, media_sha256, records_sha256):
    need(review.get('schema')=='stock-observation-v2-roi-review', 'fresh v2 ROI review missing')
    need(review.get('media_sha256')==media_sha256 and review.get('records_sha256')==records_sha256,
         'review not bound to actual bytes')
    need(review.get('reviewed_frames')=={w['stage']:w['review_frames'] for w in fixed_windows()},
         'first/middle/last native frames not reviewed')
    need(review.get('rois_xywh')=={k:list(v) for k,v in ROI.items()}, 'frozen ROI changed')
    need(review.get('whole_screen_flat') is False and
         all(review.get(k) is True for k in ('native_y_noautorotate_inspected',
         'roi_background_content_verified','fixed_geometry_verified')), 'flat ROI review incomplete')
    need(type(review.get('reviewer')) is str and bool(review['reviewer'].strip()), 'reviewer missing')
    return ROI


def measure_profiles(profiles):
    """Pure numeric core for synthetic tests or FUTURE qualified caller only.

    No source/acquisition acceptance. Do not use this to bypass record intake.
    Reuses fixed_metrics -> optical_spectrum.analyze_profiles (Hann/degree2).
    Q is the frozen 8192-grid coefficient, not reselected from a new recording.
    """
    need(set(profiles)==set(ROI), 'three frozen ROIs required')
    values={}; changes={}; all_within=True
    for name in ROI:
        p=np.asarray(profiles[name], dtype=float)
        need(p.shape==(4,60,330) and np.isfinite(p).all(), 'four 60-frame native strip profiles required')
        need(np.all((p>=0)&(p<=255)), 'invalid encoded Y values')
        values[name]=[optical.fixed_metrics(window,[Q],degree=2) for window in p]
        baseline=values[name][0]['normalized_rms'][0]
        need(baseline>1e-9, 'baseline fine coefficient too small for ratios')
        changes[name]=[100*(v['normalized_rms'][0]/baseline-1) for v in values[name][1:]]
        all_within=all_within and all(abs(v)<=THRESHOLD_PCT for v in changes[name])
    return {'schema':SCHEMA,'recording_kind':'one continuous unchanged-stock movie',
            'windows_independent':False, 'windows':fixed_windows(),
            'q_cycles_per_camera_row':Q,'fft_grid_size':8192,'window':'hann','detrend_degree':2,
            'normalization':'RMS Y coefficient / (mean Y - 16)',
            'change_windows2_to4_vs_window1_pct':changes,
            'all_roi_nominal_5pct_met':bool(all_within),
            'acquisition_admitted':False,'qualification_eligible':False,
            'candidate_admission':False,'physical_pwm_hz':None}, values


def extract_profiles(video):
    """Existing native-Y decoder, no new image processing or FFT machinery."""
    pixels=optical.decode_y(video,list(range(30,270)),(225,245,80,330)).reshape(4,60,330,80)
    return {name:pixels[:,:,:,r[0]-225:r[0]-225+r[2]].mean(axis=3) for name,r in ROI.items()}





def stable_identity(st):
    """Read access may update atime; all mutation/custody fields stay checked."""
    return (st.st_dev, st.st_ino, st.st_mode, st.st_uid, st.st_nlink,
            st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def private_bytes(path, cap=4*1024*1024):
    """Owned private regular file; reject links and concurrent inode mutation."""
    import os, stat
    path=Path(path)
    parent=path.parent.lstat()
    need(stat.S_ISDIR(parent.st_mode) and stat.S_IMODE(parent.st_mode)==0o700 and
         parent.st_uid==os.getuid(), 'owned private directory required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode)==0o600 and
             before.st_uid==os.getuid() and before.st_nlink==1 and 0<before.st_size<=cap,
             'owned private regular file required')
        chunks=[];left=before.st_size
        while left:
            b=os.read(fd,min(left,1024*1024));need(bool(b),'short private read');chunks.append(b);left-=len(b)
        need(not os.read(fd,1) and stable_identity(before)==stable_identity(os.fstat(fd)), 'private input changed')
        return b''.join(chunks), before
    finally:os.close(fd)


def validate_controls(snaps):
    """Recheck saved controls and advancing counters; NOT per-frame calibration."""
    previous=None
    for item in snaps:
        snap=item['snapshot']
        need(snap.get('recording_verified') is True and snap.get('session_token'), 'recording session missing')
        for which in ('request','result'):
            values=snap.get(which,{})
            for key,expected in optical.PROFILE.items():
                need(values.get(key)==expected, 'camera control mismatch: '+which+'.'+key)
            need(finite(values.get('frame_duration_ns')) and 32000000<=values['frame_duration_ns']<=35000000,
                 'camera frame duration changed')
        r=snap['result'];request=snap['request']
        need(request.get('request_id')==r.get('request_id') and request.get('request_id') is not None,
             'unsettled request/result')
        need(snap.get('rolling_shutter_skew_ns')==r.get('rolling_shutter_skew_ns')==15047630,
             'rolling shutter geometry changed')
        for key in ('frame_count','timestamp_ns'):
            need(type(snap.get(key)) is int and snap[key]>0 and snap[key]==r.get(key), 'counter mismatch')
        enc=[s for s in snap.get('streams',[]) if s.get('id')==snap.get('encoder_stream_id')]
        need(len(enc)==1, 'encoder missing')
        e=enc[0]
        need((e.get('width'),e.get('height'),e.get('consumer_kind'),e.get('state'),e.get('requested'))==
             (1280,720,'GraphicBufferSource',4,True), 'encoder profile changed')
        need(all(type(e.get(k)) is int and e[k]>0 for k in ('frames_produced','last_timestamp_ns')), 'encoder counters missing')
        if previous:
            old,old_encoder=previous
            need(snap['session_token']==old['session_token'] and snap['encoder_stream_id']==old['encoder_stream_id'] and
                 snap.get('progress_verified') is True, 'session/progress changed')
            need(all(snap[k]>old[k] for k in ('frame_count','timestamp_ns')) and
                 all(e[k]>old_encoder[k] for k in ('frames_produced','last_timestamp_ns')), 'counters not advancing')
            fps=(snap['frame_count']-old['frame_count'])*1e9/(snap['timestamp_ns']-old['timestamp_ns'])
            need(29.5<fps<30.5, 'sensor counter cadence changed')
        previous=(snap,e)


def load_capsule(capsule_path, *, expected_source):
    """Expected source must be independently pinned reviewed launcher identity.

    Capsule hashes bind bytes, not their truth; this caller-supplied trusted source
    identity must NOT be copied automatically out of the untrusted capsule.
    """
    import re
    raw,_=private_bytes(capsule_path);cap=json.loads(raw)
    need(cap.get('schema')=='stock-observation-analysis-evidence-v1', 'actual capsule missing')
    need(cap.get('source')==expected_source and type(expected_source) is dict and
         set(expected_source)=={'commit','closure_sha256'}, 'independently pinned source required')
    need(re.fullmatch('[a-f0-9]{40}',str(expected_source['commit'])) and
         re.fullmatch('[a-f0-9]{64}',str(expected_source['closure_sha256'])), 'bad pinned source')
    keys={'before','recording-snapshots','outcome','source-closure'}
    need(set(cap.get('records',{}))==keys and set(cap.get('records_sha256',{}))==keys, 'capsule records missing')
    records={}
    for key,receipt in cap['records'].items():
        name=receipt.get('file','')
        need(re.fullmatch('[0-9]{4}-'+re.escape(key)+r'\.json',name), 'unsafe record filename')
        data,_=private_bytes(Path(capsule_path).parent/name)
        need(len(data)==receipt.get('bytes') and digest(data)==receipt.get('sha256')==cap['records_sha256'][key],
             'record byte binding mismatch')
        records[key]=data
    closure=json.loads(records.pop('source-closure'))
    need(closure.get('source')==expected_source and type(closure.get('sha256')) is dict and closure['sha256'],
         'source closure record missing')
    need(all(type(k) is str and re.fullmatch('[a-f0-9]{64}',str(v)) for k,v in closure['sha256'].items()), 'bad closure members')
    encoded=json.dumps(closure['sha256'],sort_keys=True,separators=(',',':')).encode()
    need(digest(encoded)==expected_source['closure_sha256'], 'source closure digest mismatch')
    structural=inspect_records(records,conditional=True)
    before=json.loads(records['before']);out=json.loads(records['outcome']);snaps=json.loads(records['recording-snapshots'])
    need(before['source']==out['source']==expected_source,'record source mismatch')
    need(cap.get('final_boots')=={'target':before['boot_id'],'camera':before['camera_boot_id']}, 'final boot mismatch')
    binding=cap.get('control_binding',{})
    need(binding.get('first_window_start_index')==30 and binding.get('last_window_end_exclusive')==270 and
         binding.get('method')=='camera_snapshots_progress_with_pts_validation_pending' and
         binding.get('evidence_sha256')==cap['records_sha256']['recording-snapshots'] and
         binding.get('per_frame_controls_proven') is False and binding.get('sensor_to_file_calibrated') is False,
         'conditional controls receipt mismatch')
    need(out.get('recording_observation_complete') is True, 'recording observation incomplete')
    validate_controls(snaps)
    early=snaps[1]['elapsed']<=1
    need(out.get('early_controls_bound') is early, 'early bound contradicts observations')
    if 'first_advancing_recording_elapsed' in out:
        need(out['first_advancing_recording_elapsed']==snaps[1]['elapsed'], 'first advancing pair mismatch')
    media=cap.get('media',{});facts=media.get('sink_facts',{})
    need(media.get('bytes')==out['media']['bytes'] and media.get('sha256')==out['media']['sha256'], 'media identity mismatch')
    need(facts.get('created') is True and facts.get('confirmed_written')==media['bytes'] and
         facts.get('write_outcome_uncertain') is False and facts.get('close_outcome')=='closed' and
         facts.get('removed_by_sink') is False, 'sink custody incomplete')
    identity=media.get('created_identity')
    need(type(identity) is list and len(identity)==4 and all(type(i) is int and i>=0 for i in identity), 'created inode missing')
    return cap,structural,{'early_pair_observed':early,'first_advancing_recording_elapsed':snaps[1]['elapsed'],
                         'first_window_control_coverage':'conditional_snapshot_bound' if early else 'unknown',
                         'per_frame_controls_proven':False,'sensor_to_file_calibrated':False}


def analyze_actual(capsule_path=None, *, expected_source=None, review_path=None,
                   video=None, no_concurrent_writers=False, transfer_path=None,
                   expected_transfer_sources=None, authenticated_peer=None, receiver_exit_code=None, **unexpected):
    """Actual saved bytes -> conditional diagnostic only, NEVER acquisition PASS.

    In-memory detailed output stays private; use write_outputs for controlled
    serialization. No recording, network, device access, or source03 fallback.
    """
    need(not unexpected and capsule_path is not None and review_path is not None and video is not None,
         'actual capsule, media and fresh ROI review required')
    need(no_concurrent_writers is True, 'explicit no-concurrent-writers assumption required')
    cap,structural,controls=load_capsule(capsule_path,expected_source=expected_source)
    video=Path(video)
    need(video.parent==Path(capsule_path).parent, 'media outside capsule custody directory')
    data,st=private_bytes(video,256*1024*1024)
    transfer_raw=None
    if transfer_path is None:
        need(expected_transfer_sources is None and authenticated_peer is None and receiver_exit_code is None, 'transfer evidence missing')
        need([st.st_dev,st.st_ino,st.st_uid,st.st_mode]==cap['media']['created_identity'], 'original media inode mismatch')
    else:
        import types
        helper_path=Path(__file__).with_name('transfer.py');helper_raw=helper_path.read_bytes()
        need(type(expected_transfer_sources) is dict and digest(helper_raw)==expected_transfer_sources.get(
             '06-tools/stock_observation_analysis_20261110/transfer.py'), 'independently pinned transfer helper required')
        helper=types.ModuleType('stock_observation_transfer');helper.__file__=str(helper_path)
        exec(compile(helper_raw,str(helper_path),'exec'),helper.__dict__)
        need(Path(transfer_path).parent==video.parent, 'transfer receipt outside destination directory')
        transfer_raw,_=private_bytes(transfer_path)
        helper.validate_destination(json.loads(transfer_raw),capsule_raw=private_bytes(capsule_path)[0],
            capsule_file=Path(capsule_path).name,
            records_raw={k:private_bytes(video.parent/v['file'])[0] for k,v in cap['records'].items()},
            cap=cap,st=st,expected_helpers=expected_transfer_sources,authenticated_peer=authenticated_peer,
            receiver_exit_code=receiver_exit_code)
    need(len(data)==cap['media']['bytes'] and digest(data)==cap['media']['sha256'], 'media bytes mismatch')
    del data
    review_raw,_=private_bytes(review_path)
    validate_roi_review(json.loads(review_raw),media_sha256=cap['media']['sha256'],records_sha256=cap['records_sha256'])
    probe=probe_video(video);pts,stream,windows=validate_probe(probe)
    profiles=extract_profiles(video)
    summary,details=measure_profiles(profiles)
    data,after=private_bytes(video,256*1024*1024)
    need(stable_identity(st)==stable_identity(after) and digest(data)==cap['media']['sha256'], 'media changed during analysis')
    # Recheck every original evidence file and review after long subprocess work.
    cap_after,_,controls_after=load_capsule(capsule_path,expected_source=expected_source)
    need(cap_after==cap and controls_after==controls and private_bytes(review_path)[0]==review_raw, 'evidence changed during analysis')
    if transfer_path is not None:
        need(private_bytes(transfer_path)[0]==transfer_raw,'transfer receipt changed during analysis')
    summary.update(status='conditional_diagnostic_only',strict_acquisition_status='inconclusive',
                   control_limits=controls,stream=stream,
                   native10s_cap_proven_by_duration=False,
                   limits=['One continuous movie; adjacent windows and ROIs are not independent trials.',
                           'Snapshot controls and PTS do not calibrate exposure to encoded frames.',
                           'Nominal 5% arithmetic is not acquisition acceptance or candidate admission.'])
    private={'capsule':cap,'record_projection':structural,'review_sha256':digest(review_raw),
             'probe':probe,'measurements':details,'control_limits':controls,
             'transfer_receipt':json.loads(transfer_raw) if transfer_raw is not None else None,
             'receiver_exit_code_observed_by_caller':receiver_exit_code,
             'analysis_sources_sha256':{name:digest(path.read_bytes()) for name,path in {
                 'adapter':Path(__file__), 'optical':Path(optical.__file__),
                 'spectrum':TOOLS/'optical_spectrum.py', 'protocol_v2':Path(protocol.__file__)}.items()}}
    arrays={'pts':pts,**{'profiles_'+k:v for k,v in profiles.items()}}
    for roi,p in profiles.items():
        arrays[roi+'_normalized_amplitude_per_frame']=np.asarray([
            [optical.fixed_metrics(frame[None,:],[Q],degree=2)['normalized_rms'][0] for frame in window]
            for window in p])
        arrays[roi+'_mean_y_per_frame']=p.mean(axis=2)
    return summary,private,arrays


def write_outputs(summary, private, arrays, *, private_json, private_npz, summary_json):
    """New files only; detailed data private, summary explicitly allowlisted."""
    import os,stat
    for path in (Path(private_json),Path(private_npz)):
        parent=path.parent.lstat()
        need(stat.S_ISDIR(parent.st_mode) and stat.S_IMODE(parent.st_mode)==0o700 and
             parent.st_uid==os.getuid(), 'private output directory required')
    paths=[Path(p) for p in (private_json,private_npz,summary_json)]
    need(len(set(paths))==3 and not any(p.exists() or p.is_symlink() for p in paths),'new distinct outputs required')
    allowed={'schema','recording_kind','windows_independent','windows','q_cycles_per_camera_row',
             'fft_grid_size','window','detrend_degree','normalization','change_windows2_to4_vs_window1_pct',
             'all_roi_nominal_5pct_met','acquisition_admitted','qualification_eligible','candidate_admission',
             'physical_pwm_hz','status','strict_acquisition_status','control_limits','stream',
             'native10s_cap_proven_by_duration','limits'}
    need(set(summary)<=allowed and summary.get('status')=='conditional_diagnostic_only' and
         summary.get('acquisition_admitted') is False and summary.get('qualification_eligible') is False,
         'invalid sanitized summary')
    for path,value in ((paths[0],private),(paths[2],summary)):
        raw=json.dumps(value,indent=2,allow_nan=False).encode()+b'\n'
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as handle:handle.write(raw)
    fd=os.open(paths[1],os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as handle:np.savez_compressed(handle,**arrays)
