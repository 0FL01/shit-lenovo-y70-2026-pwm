"""Offline replay; no ADB, network, private paths or images in the repository."""
import sys, json
from pathlib import Path
from PIL import Image
import numpy as np

def require(v, reason):
    if not v:
        raise ValueError(reason)

def measure(path):
    with Image.open(path) as im:
        im.load()
        require(im.size == (4080, 3072), "unexpected image size")
        m=im.getexif().get_ifd(34665)
        meta=(float(m[33434]),int(m[34855]),float(m[33437]),float(m[37386]),int(m[41986]),int(m[41987]),int(m[37385]))
        rgb=im.convert("RGB").crop((1120,620,2920,2930)).rotate(-90,expand=True).resize((550,429),Image.Resampling.LANCZOS)
    r=np.asarray(rgb)[:,:,0].astype(float)
    dy=np.diff(r[34:62,50:480].mean(1)); borders=[int(np.argmax(dy))+34]; gradients=[round(float(dy.max()),3)]
    for start,end in ((15,45),(513,544)):
        dx=np.diff(r[65:110,start:end].mean(0)); idx=int(np.argmax(np.abs(dx)))
        borders.append(idx+start); gradients.append(round(abs(float(dx[idx])),3))
    roi=r[276:322,51:508]
    return meta,borders,gradients,round(float(np.mean(roi>192)),3)

def replay(root):
    lines=[json.loads(l) for l in (root/'log.jsonl').read_text().splitlines()]
    require(len({k for _,k,_ in lines})==len(lines),'duplicate event tag')
    ev={k:(t,p) for t,k,p in lines}
    require(ev['series_complete'][1] is True and ev['target_restore_exact'][1] is True
            and ev['camera_restored'][1] is True and ev['camera_control_diff'][1]=={},'missing finish markers')
    states=lambda tag:ev[tag][1].splitlines()[1:]
    base=states('target_initial')
    require(all(base==states(k) for k in ('pre_enable','return_target','target_final')), 'original target not restored')
    require(states('on_target')==states('on_tail'),'changed ON snapshot')
    deltas=[(a.strip(),b.strip()) for a,b in zip(base,states('on_target')) if a!=b]
    require(len(base)==len(states('on_target')) and len(deltas)==4,'unexpected target delta')
    need=['reduce_bright_colors_activated=null','Activated: false','mIsRbcActive=false','colorTransformMatrix=']
    require(all(any(a.startswith(v) for a,b in deltas) for v in need),'wrong fields changed')
    for stage in ('target_initial','on_target','on_tail','return_target','target_final'):
        raw=ev[stage][1]
        require(all(s in raw for s in ('vsyncRate=120.00 Hz','mIsHdrLayerPresent=false','ZRamSettingsActivity','policy=DIM','screen_brightness=105','panel_brightness=828','panel_actual_brightness=0','panelDC=0','displayBrightnessNits=4.835865 sdrWhitePointNits=4.835865')),'unexpected display state')
        diag='0.522' if stage.startswith('on_') else '1.000'
        expected='colorTransformMatrix=[['+diag+',0.000,0.000,0.000][0.000,'+diag+',0.000,0.000][0.000,0.000,'+diag+',0.000][0.000,0.000,0.000,1.000]]'
        require(expected in raw,'unexpected transform')
    original=json.loads((root/'camera_initial_read0.json').read_text())
    returns=[json.loads((root/name).read_text()) for name in ('recovery_final0.json','recovery_final_b0.json')]
    restore_keys='control.aeMode control.aeLock control.awbMode control.awbLock control.afMode lens.opticalStabilizationMode scaler.cropRegion control.zoomRatio control.aeRegions control.afRegions control.awbRegions control.aeExposureCompensation control.aeTargetFpsRange flash.mode control.captureIntent'.split()
    require(all(c[k]==original[k] for c in returns for k in restore_keys) and int(returns[1]['sensor.timestamp'])>int(returns[0]['sensor.timestamp']),'camera control restore did not replay')
    cam=[(k,m) for _,k,m in lines if k.endswith('_ts')]; require(len(cam)==20,'missing camera brackets')
    stamps=[int(m['sensor.timestamp']) for _,m in cam]; frame=[int(m['request.frameCount']) for _,m in cam]
    require(all(a<b for a,b in zip(stamps,stamps[1:])) and all(a<b for a,b in zip(frame,frame[1:])),'nonadvancing samples')
    dec=lambda key: {m[key] for _,m in cam}
    require(dec('control.aeLock')=={'ON'} and dec('control.aeState')=={'LOCKED'} and dec('control.afState')=={'FOCUSED_LOCKED'} and dec('control.zoomRatio')=={'2.00000000'},'lock condition lost')
    keys=('sensor.sensitivity','sensor.exposureTime','lens.focusDistance','control.awbMode','control.awbLock','scaler.cropRegion','flash.mode')
    require(all(len(dec(k))==1 for k in keys),'capture configuration drift')
    camera={k:next(iter(dec(k))) for k in keys}
    pixels=[json.loads(l) for l in (root/'scene_checks.jsonl').read_text().splitlines()]
    require([p[1] for p in pixels]==['held1_ts','on_target','return_target'] and [p[2:4] for p in pixels]==[['null','null'],['1','1'],['null','null']] and len({p[-1] for p in pixels})==1,'target scene evidence failed')
    names=[s+str(i) for s in ('off','on','return') for i in (1,2,3)]
    results=[];allmeta=[]
    for n in names:
        meta,border,gradient,fraction=measure(root/(n+'.jpg'));allmeta.append(meta)
        require([n+'_pre_ts',n+'_shutter',n+'_photo',n+'_post_ts']==[k for _,k,_ in lines if k in (n+'_pre_ts',n+'_shutter',n+'_photo',n+'_post_ts')], 'photographic brackets disorder')
        results.append(dict(label=n,shutter_command_host_utc=ev[n+'_shutter'][0],
              border_positions=border,border_edge_gradients=gradient,bright_red_pixel_fraction=fraction))
    require(len(set(allmeta))==1 and allmeta[0][1]==int(camera['sensor.sensitivity'])
            and abs(allmeta[0][0]-float(camera['sensor.exposureTime'])/1e9)<1e-9,'JPEG metadata mismatch')
    edges=[(k,v) for t,k,v in lines if k.endswith('_edge')]
    require(len(edges)==5,'missing preview edge samples')
    for tag,(y,up,yd,down) in edges[1:]:
        _,b=edges[0]
        require(abs(y-b[0])<=4 and abs(yd-b[2])<=4 and up>=.65*b[1] and down>=.65*b[3],'preview border drifted')
    require(all(max(r['border_positions'][i] for r in results)-min(r['border_positions'][i] for r in results)<=1 for i in range(3)),'JPEG registration exceeds described result')
    return dict(photos=results,photo_exif=dict(zip(('exposure_s','ISO','f_number','focal_mm','exposure_mode','white_balance','flash'),allmeta[0])),
            camera2=dict(samples=len(cam),advancing_frames=frame[-1]-frame[0],**camera),
            preview_grid_edges=edges,target_scene_equal_720x1584=True,restore_target=True,restore_camera_controls=True,
            target_change_fields=[b.split('=')[0].split(':')[0] for a,b in deltas],
            missing_camera_result_reads=sum('_missing_sensor_result_' in k for _,k,_ in lines),
            notes='Raster metric is not optical modulation or duty cycle. AE/AF/Capture metadata are checked at sampled brackets; AWB/ISP not locked.')
if __name__=='__main__':
    print(json.dumps(replay(Path(sys.argv[1])),indent=2))
