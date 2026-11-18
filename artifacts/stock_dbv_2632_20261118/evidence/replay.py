"""Read-only offline verifier. Never imports or executes device-facing helpers.

Usage: python replay.py PRIVATE_DIRECTORY [--allow-aborted]
An aborted run is explicitly not a completed 17-by-3 comparison.
"""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

STEPS = [2632,2632,2633,2632,2631,2632,2633,2634,2633,2632,2633,2633,2634,2633,2632,2631,2632]
ARGS = {2631:'0.140316456',2632:'0.140379747',2633:'0.140443038',2634:'0.140506329'}
OC_KEYS = ('control.aeMode control.afMode control.aeLock control.awbMode control.awbLock '
           'lens.focusDistance sensor.sensitivity sensor.exposureTime control.zoomRatio '
           'scaler.cropRegion flash.mode control.captureIntent lens.opticalStabilizationMode '
           'control.videoStabilizationMode').split()
STOCK_KEYS = ('control.aeMode control.aeLock control.awbMode control.awbLock control.afMode '
              'lens.opticalStabilizationMode scaler.cropRegion control.zoomRatio control.aeRegions '
              'control.afRegions control.awbRegions control.aeExposureCompensation '
              'control.aeTargetFpsRange flash.mode control.captureIntent').split()
FIXED = dict(zip(('control.aeMode control.afMode sensor.exposureTime sensor.sensitivity '
                 'lens.focusDistance control.zoomRatio scaler.cropRegion control.captureIntent '
                 'flash.mode control.awbMode control.awbLock').split(),
                ['OFF','OFF','500000','6400','6.69673395','1.00000000','0 0 4080 3072',
                 'PREVIEW','OFF','AUTO','OFF']))


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def read(root, name):
    return json.loads((root / (name + '.json')).read_text())


def metadata(root, stem, camera=True):
    """Only a missing-timestamp read permits the next bounded retry."""
    seen = []
    for i in range(3):
        path = root / (stem + str(i) + '.json')
        if not path.exists():
            break
        item = json.loads(path.read_text())
        res = item['res'] if camera else item
        if res.get('sensor.timestamp'):
            need(not seen, 'duplicate fully formed metadata: ' + stem)
            seen.append(item)
        else:
            need(not seen, 'metadata after completed read: ' + stem)
    need(len(seen) == 1, 'missing complete metadata: ' + stem)
    return seen[0]


def stamp(result):
    return tuple(int(result[k]) for k in ('request.frameCount','sensor.timestamp'))


def advance(a, b):
    need(all(x < y for x,y in zip(a,b)), 'nonadvancing frameCount/timestamp')


def signature(meta):
    need(meta['camera'] == '0', 'unexpected camera ID')
    sig = {side: {k: meta[side][k] for k in OC_KEYS} for side in ('req','res')}
    return sig


def manual(meta):
    sig = signature(meta)
    for side in ('req','res'):
        need(all(sig[side].get(k) == v for k,v in FIXED.items()), 'manual control mismatch')
    return sig


def pixels(root, name, size):
    with Image.open(root / (name + '.png')) as image:
        need(image.format == 'PNG' and image.size == size, 'invalid PNG geometry: ' + name)
        return np.asarray(image.convert('RGB'))


def scene(root, name):
    rgb = pixels(root, name, (1440,3168))
    return hashlib.sha256(rgb[792:2376,360:1080].tobytes()).hexdigest()


def raster(root, name, enforce=True):
    rgb = pixels(root,name,(1080,2392))
    face = rgb[930:1340,80:575]
    trace = rgb[1080:1270,112:540]
    profiles = [np.median(rgb[947:994,200:315,1].astype(float),axis=1),
                np.median(rgb[1008:1052,518:588,1].astype(float),axis=0)]
    edges = [(float(np.abs(np.diff(p)).max()),int(np.abs(np.diff(p)).argmax())) for p in profiles]
    geometry_ok = all(v>18 and abs(pos-expected)<=4 for (v,pos),expected in zip(edges,[18,35]))
    if enforce:
        need(geometry_ok, 'static edge/geometry gate: ' + name)
        need(not (face == 255).any(), 'highlight clipping: ' + name)
    return dict(geometry_ok=geometry_ok,highlight_pixels=int((face==255).any(2).sum()),edges=edges,face_max=face.max((0,1)).tolist(),trace_max=trace.max((0,1)).tolist(),
                zero_rgb_counts=(trace == 0).sum((0,1)).tolist(),
                any_zero_count=int((trace == 0).any(2).sum()),
                all_zero_count=int((trace == 0).all(2).sum()),trace_pixels=int(trace.shape[0]*trace.shape[1]))


def target_state(state, n):
    need(state['DBV']==str(n) and state['policy']=='BRIGHT' and state['reason']=='manual', 'DBV/policy drift')
    need(state['android']=='37' and state['user']==state['out'] and
         abs(float(state['user'])-float(ARGS[n])) < 1e-7, 'float-to-DBV mismatch')


def events(root):
    rows = [json.loads(line) for line in (root/'oc.log').read_text().splitlines()]
    out = {}
    last = None
    for timestamp, name, value in rows:
        current = datetime.fromisoformat(timestamp)
        if last is not None:
            need(current >= last, 'log UTC regression')
        last = current
        out.setdefault(name,[]).append((current,value))
    return out


def one(log, name):
    need(len(log.get(name,[]))==1, 'missing/duplicate event: ' + name)
    return log[name][0]


def restoration(root, log, require_target, before_tag="before"):
    original = read(root,'oc_first')
    oldsig = signature(original)
    a = metadata(root,'oc_return_a_read'); b = metadata(root,'oc_return_b_read')
    need(signature(a)==signature(b)==oldsig, 'OC restore settings')
    advance(stamp(a['res']),stamp(b['res']))
    need(one(log,'oc_restored')[1] is True, 'missing OC restore attestation')
    old = read(root,'stock_baseline')
    a = metadata(root,'stock_final_a',False); b = metadata(root,'stock_final_b',False)
    need(all(k in old and a.get(k)==b.get(k)==old[k] for k in STOCK_KEYS), 'stock restore settings')
    need(old['control.zoomRatio']=='2.00000000' and old['control.afMode']=='CONTINUOUS_PICTURE'
         and old['control.aeMode']=='ON' and old['control.aeLock']=='OFF', 'unexpected stock baseline')
    advance(stamp(a),stamp(b))
    need(one(log,'stock_restored')[1] is True, 'missing stock restore attestation')
    if require_target:
        s = one(log,'target_restored')[1]
        need(s['user']=='0.40987244' and s['android']=='105', 'target brightness restore')
        need((s['policy'],s['DBV'],s['out'],s['reason']) in
             [('BRIGHT','6879','0.40987244','manual'),('DIM','828','0.025906963','manual [ dim ]')],
             'target restored policy/output')
        need(scene(root,'final_native_target')==scene(root,'original_app'), 'target scene restore')
    if require_target:
        raw_return(root, before_tag)
    return dict(oc_observed_fields=len(OC_KEYS),stock_observed_fields=len(STOCK_KEYS),
                hidden_preferences='not bytewise checked',sole_camera='live guard attestation, not raw metadata')


def raw_return(root, before_tag="before"):
    rows = [json.loads(line) for line in (root/'log.jsonl').read_text().splitlines()]
    before = [v for _,k,v in rows if k==before_tag]; after = [v for _,k,v in rows if k=='final_target_full']
    need(len(before)==len(after)==1,'missing/duplicate raw target baseline/return')
    required = ['showing=false','ZRamSettingsActivity','screen_brightness=105',
                'screen_brightness_mode=0','min_refresh_rate=120.0','peak_refresh_rate=120.0',
                'reduce_bright_colors_activated=null','reduce_bright_colors_level=null',
                'reduce_bright_colors_persist_across_reboots=null','Activated: false',
                'mIsHdrLayerPresent=false','mIsRbcActive=false','vsyncRate=120.00 Hz',
                'panel_actual_brightness=0','panel_bl_power=0','panelDC=0',
                'colorTransformMatrix=[[1.000,0.000,0.000,0.000][0.000,1.000,0.000,0.000][0.000,0.000,1.000,0.000][0.000,0.000,0.000,1.000]]']
    need(all(t in raw for raw in (before[0],after[0]) for t in required),'raw target baseline/return drift')


def calibration(root):
    rows = [json.loads(line) for line in (root/'log.jsonl').read_text().splitlines()]
    calibrations = [v for _,k,v in rows if k=='reach']
    need(len(calibrations)==6,'calibration evidence count')
    values=[]
    for arg,n,state in calibrations:
        need(str(n)==state['DBV'] and state['user']==state['out'] and
             state['policy']=='BRIGHT' and state['reason']=='manual' and
             abs(float(arg)-float(state['user']))<1e-7,'calibration mismatch')
        if n in ARGS:
            need(arg==ARGS[n],'calibration command mismatch');target_state(state,n);values.append(n)
    need(values==[2632,2633,2634,2631],'calibration sequence mismatch')
    return values


def replay(root, allow_aborted=False):
    log = events(root)
    complete = (root/'manifest_complete.json').exists()
    rejected = log.get('rejected',[])
    need(complete or allow_aborted, 'incomplete 17-by-3 series')
    need(not complete, 'this verifier audits the observed aborted run only')
    commands = [k for k in log if k.endswith('_command') and k.startswith('P')]
    restored = restoration(root,log,bool(commands))
    fixed = None; last = stamp(read(root,'oc_first')['res'])
    for i in range(3):
        meta = metadata(root,'new_qual'+str(i)+'_read')
        sig = manual(meta)
        fixed = fixed or sig
        need(sig==fixed,'qualification controls drift')
        advance(last,stamp(meta['res']));last=stamp(meta['res'])
        raster(root,'new_qual'+str(i))
    if not complete:
        need(len(rejected)==1,'incomplete without unique rejection')
        need(commands==['P00_command'],'unexpected aborted phase sequence')
        command_time,command=one(log,'P00_command')
        need(command[1:]==[ARGS[2632],2632],'aborted command mismatch')
        pre_time,pre=one(log,'P00_pre')
        need(pre[0]==pre[1]==2632,'aborted native DBV mismatch')
        target_state(pre[2],2632)
        need(scene(root,'P00_target')==pre[3]==scene(root,'original_app'),'aborted target scene mismatch')
        need(command_time<pre_time<rejected[0][0],'aborted chronology')
        meta=metadata(root,'P00_s0_pre_read')
        need(manual(meta)==fixed,'aborted camera controls mismatch')
        advance(last,stamp(meta['res']))
        advance(stamp(meta['res']),stamp(metadata(root,'oc_return_a_read')['res']))
        value=raster(root,'P00_s0',False)
        need(not value['geometry_ok'] and value['highlight_pixels']==0,'blocker not reproduced')
        need('image geometry/clipping failure P00_s0' in rejected[0][1],'unexpected abort reason')
        need(not any(k.endswith('_manifest') or k.endswith('_late') for k in log),
             'false completed sample/phase on aborted run')
        values=calibration(root)
        return dict(status='aborted_not_comparative_evidence',rejection='P00_s0 static right-edge gate',
                    issued_phases=1,completed_phases=0,completed_samples=0,blocker_image=value,
                    reachable_dbv=values,restoration=restored,
                    limits=['Calibration/phase DBV are parsed live readbacks, not archived full raw snapshots at each level.',
                            'Raw baseline and return independently show 120 Hz, DC off, SDR, Extra Dim off; per-level proof is live-guard only.',
                            'No 2632-versus-2633 optical comparison; 500 us preview may alias and ISP/AWB remain active.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);parser.add_argument('--allow-aborted',action='store_true')
    args=parser.parse_args()
    print(json.dumps(replay(args.root,args.allow_aborted),indent=2))
