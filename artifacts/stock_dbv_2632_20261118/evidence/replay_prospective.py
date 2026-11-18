"""Separate frozen-geometry run audit; it never reclassifies the first abort.

Default requires all 17x3. --allow-aborted audits the observed partial run without
claiming any between-DBV contrast. No hardware calls or acquisition imports.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

import replay as base
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import analysis_geometry as geometry

FROZEN='f931a8cc847340ef708849625e6253c68df7584904a5c5f915d8b7ebe6b0e54a'


def raw_plateau(root,tag,expected,n):
    raw=(root/(tag+'_display.txt')).read_text()
    required=('ZRamSettingsActivity','vsyncRate=120.00 Hz','min_refresh_rate=120.0',
              'peak_refresh_rate=120.0','screen_brightness_float=null','screen_brightness_mode=0',
              'mIsRbcActive=false','mIsHdrLayerPresent=false')
    base.need(all(t in raw for t in required),'raw display controls drift')
    patterns={'policy':r'policy=(\w+)','user':r'mCurrentScreenBrightness=([\d.]+)',
              'out':r'mActualBacklight=([\d.]+)','android':r'screen_brightness=(\d+)',
              'DBV':r'\n(\d+)\n0\n','reason':r'mBrightnessReason=([^\n]+)'}
    state={}
    for key,pattern in patterns.items():
        match=re.search(pattern,raw);base.need(match is not None,'missing raw '+key)
        state[key]=match[1]
    base.need(state==expected,'raw/parsed plateau mismatch');base.target_state(state,n)
    provider=(root/(tag+'_provider.txt')).read_text()
    base.need(re.search(r'\bvalue=0\b',provider) is not None,'provider DC mismatch')


def scored(root,tag,reference):
    rgb=base.pixels(root,tag,(1080,2392))
    measured=geometry.score(rgb,reference)
    base.need(measured==base.read(root,tag+'_fixture'),'fixture JSON does not match actual PNG')
    trace=rgb[1080:1270,112:540]
    measured['trace_any_zero']=int((trace==0).any(2).sum())
    measured['trace_all_zero']=int((trace==0).all(2).sum())
    return measured


def replay(root,allow_aborted=False):
    for file in (root/'analysis_geometry.py',Path(geometry.__file__)):
        base.need(hashlib.sha256(file.read_bytes()).hexdigest()==FROZEN,'frozen geometry source changed')
    log=base.events(root)
    complete=(root/'manifest_complete.json').exists()
    base.need(complete or allow_aborted,'incomplete 17-by-3 prospective series')
    base.need(not complete,'this verifier audits the observed aborted prospective run only')
    base.need(len(log.get('rejected',[]))==1,'missing/duplicate rejection')
    restored=base.restoration(root,log,True,'target_full_before')
    ref=geometry.reference(base.pixels(root,'new_qual'+str(i),(1080,2392)) for i in range(3))
    base.need(ref==base.read(root,'new_ref')==base.one(log,'prospective_fixture')[1],'reference mismatch')
    last=base.stamp(base.read(root,'oc_first')['res']);fixed=None
    for i in range(3):
        m=base.metadata(root,'new_qual'+str(i)+'_read');sig=base.manual(m);fixed=fixed or sig
        base.need(sig==fixed,'qualification control drift');base.advance(last,base.stamp(m['res']));last=base.stamp(m['res'])
        # Acquisition records absolute qualification before constructing the reference.
        score=geometry.score(base.pixels(root,'new_qual'+str(i),(1080,2392)))
        base.need(score==base.read(root,'new_qual'+str(i)+'_fixture'),'qualification fixture mismatch')
    commands=[k for k in log if k.endswith('_command') and k.startswith('P')]
    base.need(commands==['P00_command','P01_command'],'unexpected partial sequence')
    original=base.scene(root,'original_app')
    result=[];previous_end=None
    expected_samples=[('P00',3),('P01',1)]
    actual_samples=[k for k in log if k.endswith('_manifest')]
    base.need(actual_samples==[p+'_s'+str(j)+'_manifest' for p,count in expected_samples for j in range(count)],
              'missing/duplicate/extra partial samples')
    for phase,count in expected_samples:
        command_time,command=base.one(log,phase+'_command');pre_time,pre=base.one(log,phase+'_pre')
        base.need(command[1:]==[base.ARGS[2632],2632],'sham control command changed')
        if previous_end is not None:base.need(command_time>previous_end,'phase timing overlap')
        base.need(command_time<pre_time,'command/pre chronology')
        base.need(pre[0]==pre[1]==2632,'native plateau early mismatch')
        raw_plateau(root,phase+'_early',pre[2],2632)
        base.need(base.scene(root,phase+'_target')==pre[3]==original,'scene changed')
        for j in range(count):
            tag=phase+'_s'+str(j);event_time,row=base.one(log,tag+'_manifest')
            base.need((row['phase'],row['sample'],row['n'],row['tag'])==(int(phase[1:]),j,2632,tag),'false sample/phase control')
            t0=datetime.fromisoformat(row['utc_meta_start']);t1=datetime.fromisoformat(row['raster_start']);t2=datetime.fromisoformat(row['raster_end'])
            base.need(pre_time<t0<t1<t2<event_time,'sample chronology')
            base.need((t0-command_time).total_seconds()>=(4,7,10)[j]-.1,'sample too early')
            pair=[]
            for side in ('pre','post'):
                m=base.metadata(root,tag+'_'+side+'_read');base.need(base.manual(m)==fixed,'camera controls drift')
                current=base.stamp(m['res']);base.advance(last,current);last=current;pair.append(list(current))
            base.need(pair==row['camera'],'manifest frame mismatch')
            value=scored(root,tag,ref);base.need(value['pass_geometry_highlights'],'accepted raster fails frozen gate')
            expected=dict(value);expected.pop('trace_any_zero');expected.pop('trace_all_zero')
            base.need(expected==row['image']['fixture'],'logged fixture mismatch')
            base.need(value['trace_any_zero']==row['image']['any_zero_count'] and value['trace_zero_rgb']==row['image']['zero_rgb_counts'],'pixel clipping mismatch')
            result.append(dict(phase=phase,sample=j,dbv=2632,frames=pair,image=value))
        if phase=='P00':
            late_time,late=base.one(log,phase+'_late');base.need(late_time>event_time and late[1]==2632,'late plateau mismatch')
            raw_plateau(root,phase+'_end',late[0],2632);previous_end=late_time
        else:base.need(phase+'_late' not in log,'false late completion')
    m=base.metadata(root,'P01_s1_pre_read');base.need(base.manual(m)==fixed,'failed sample controls')
    base.advance(last,base.stamp(m['res']))
    base.advance(base.stamp(m['res']),base.stamp(base.metadata(root,'oc_return_a_read')['res']))
    failed=scored(root,'P01_s1',ref)
    base.need(not failed['pass_geometry_highlights'] and failed['failures']==['top-left:relative'],'blocker not reproduced')
    base.need(base.one(log,'rejected')[1]=="fixture/clipping P01_s1 ['top-left:relative']",'abort mismatch')
    return dict(status='aborted_same_dbv_sham_only',issued_phases=2,completed_phases=1,completed_samples=4,
                samples=result,failed_sample=failed,restoration=restored,
                limits=['No 2633 command or cross-level contrast was reached.',
                        'The failed fifth raster is not a qualified sample; its post-camera bracket and P01 late readback do not exist.',
                        'Static anchor relative contrast failed on an A/A sham at unchanged DBV2632.',
                        '500 us preview, auto AWB/ISP, channel clipping and aliasing prevent amplitude/PWM claims.',
                        'Raw plateau files have no embedded capture timestamp; identical same-DBV substitutions cannot be independently distinguished.'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--allow-aborted',action='store_true');a=p.parse_args()
    print(json.dumps(replay(a.root,a.allow_aborted),indent=2))
