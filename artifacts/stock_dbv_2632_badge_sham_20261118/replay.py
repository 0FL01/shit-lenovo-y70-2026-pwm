"""Offline fixed-template badge sham replay. No device or acquisition imports."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ARTIFACTS=Path(__file__).resolve().parents[1]
# Actual scorer source hashes are verified separately from the PNG template hash.
SOURCE_HASHES={'future.py':'41e707a7056a112bf45a5e73beada978852d5e9a5791c1ba1d7da04b66c7de73',
               'exterior.py':'7f4a92eef40f70ec679219b4409917f5c82dd1d295dd5a7c6df4fbb4b1604bdb',
               'legends.py':'d031b54395e091ed4d66f9ebd1102d2d82b6d77eebf6571302491607d41b62cf'}


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj


def dependencies(scope_package):
    base=module('badge_base',ARTIFACTS/'stock_dbv_2632_20261118/evidence/replay.py')
    sham=module('badge_sham_base',ARTIFACTS/'stock_dbv_2632_sham_20261118/replay.py')
    src=scope_package
    exterior=module('exterior',src/'exterior.py');sys.modules['exterior']=exterior
    future=module('future',src/'future.py');sys.modules['future']=future
    gate=module('badge_legends',src/'legends.py')
    return base,sham,future,gate


def source_check(base,root,scope_package):
    registry={}
    for line in (root/'sources.sha256').read_text().splitlines():
        digest,name=line.split();base.need(name not in registry,'duplicate source registration')
        registry[name]=digest
    required=dict(SOURCE_HASHES)
    base.need(registry==required,'frozen source registry mismatch')
    for name,digest in required.items():
        base.need(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,'private source changed: '+name)
    for name,digest in SOURCE_HASHES.items():
        path=scope_package/name
        base.need(hashlib.sha256(path.read_bytes()).hexdigest()==digest,'public scorer changed')


def shadows(image):
    zeros=image[1080:1270,112:540]==0
    return dict(any_zero=int(zeros.any(2).sum()),all_zero=int(zeros.all(2).sum()),per_channel_zero=zeros.sum((0,1)).tolist())


def passes(g,m):
    return g['geometry']['pass_exterior'] and g['pass_original_upper_headroom'] and m['pass_modes']


def replay(root,template,scope_package,allow_partial=False):
    base,sham,future,gate=dependencies(scope_package)
    source_check(base,root,scope_package)
    ref=future.reference(template)  # immutable original PNG SHA, not a new frame
    log=base.events(root)
    complete=(root/'sham_validity_series.json').exists()
    base.need(complete or allow_partial,'incomplete 51-slot badge sham')
    entry=log.get('single_entry_command',[])
    restored=base.restoration(root,log,bool(entry),'target_full_before')
    base.need(len(entry)==1,'expected exactly one entry')
    entry_time,command=base.one(log,'single_entry_command')
    base.need(command[1]==base.ARGS[2632],'wrong single-entry command')
    settled_time,settled=base.one(log,'single_entry_settled')
    base.need(entry_time<settled_time and settled[0]==2632,'entry readback/order')
    sham.plateau(base,root,'sham_enter',settled[1])
    original=base.scene(root,'original_app')
    base.need(base.scene(root,'enter_sham_target')==original,'entry scene changed')
    for name in ('baseline_bright','initial_at_sham','immediately_before_entry','return_sham'):
        text=(root/(name+'_display.txt')).read_text()
        expected=('policy=BRIGHT','mBrightnessReason=manual','mActualBacklight=0.40987244',
                  'mCurrentScreenBrightness=0.40987244','screen_brightness=105',
                  'screen_brightness_mode=0','min_refresh_rate=120.0','peak_refresh_rate=120.0',
                  'mIsRbcActive=false','mIsHdrLayerPresent=false','vsyncRate=120.00 Hz',
                  '\n6879\n0\n','ZRamSettingsActivity')
        base.need(all(s in text for s in expected),'raw baseline/return mismatch')
    last=base.stamp(base.read(root,'oc_first')['res']);fixed=None
    def camera(tag):
        nonlocal last,fixed
        meta=base.metadata(root,tag+'_read');sig=base.manual(meta);fixed=fixed or sig
        base.need(sig==fixed,'camera request/result drift');current=base.stamp(meta['res']);base.advance(last,current);last=current
        return list(current)
    def measured(tag,semantics=True):
        image=base.pixels(root,tag,(1080,2392));g=future.checks(ref,image)
        base.need(g==base.read(root,tag+'_fixture'),'PNG/fixture mismatch: '+tag)
        m=None
        if semantics:
            raw=gate.checks(ref,image);m=dict(raw,pass_modes=raw['pass_similarity']);base.need(m==base.read(root,tag+'_legends'),'PNG/semantics mismatch: '+tag)
        return g,m,shadows(image)
    for i in range(3):
        tag='new_qual'+str(i);camera(tag);g,_,_=measured(tag,False)
        base.need(g['geometry']['pass_exterior'] and g['pass_original_upper_headroom'],'initial health control failed')
    base.need(base.one(log,'starting_bright_badge_health')[1] is True,'missing initial health success')
    references=log.get('native_reference',[]);base.need(len(references)==3,'missing/duplicate reference')
    ref_scores=[]
    for i,(event_time,row) in enumerate(references):
        tag='R%02d'%i;base.need(row[0]==tag,'reference order')
        t0=datetime.fromisoformat(row[1]);t1=datetime.fromisoformat(row[2])
        base.need(settled_time<t0<t1<event_time and (t0-entry_time).total_seconds()>=12,'reference timing')
        pair=[camera(tag+'_pre'),camera(tag+'_post')];base.need(pair==row[3:5],'reference frame brackets')
        g,m,z=measured(tag);base.need([g,m]==row[5:7],'reference logged scores')
        ref_scores.append(dict(fixture=g,legends=m,shadows=z))
    end_time,end_state=base.one(log,'native_reference_end_dbv');sham.plateau(base,root,'after_native_reference',end_state)
    base.need(end_time>references[-1][0],'native reference end order')
    if not all(passes(r['fixture'],r['legends']) for r in ref_scores):
        base.need(not complete and 'reference_verified' not in log and not any(k.endswith('_receipt') for k in log)
                  and not list(root.glob('S[0-9][0-9]*')),'false commissioning success')
        base.advance(last,base.stamp(base.metadata(root,'oc_return_a_read')['res']))
        return dict(status='commissioning_rejected',samples=0,references=ref_scores,restoration=restored,
                    limits=['No long sham or cross-level comparison completed.'])
    verified_time,_=base.one(log,'reference_verified');base.need(verified_time>end_time,'commissioning order')
    names=[k for k in log if k.endswith('_receipt')];count=len(names)
    base.need(names==['S%02d_receipt'%i for i in range(count)] and 0<count<=51,'missing/reordered slots')
    if complete:
        base.need(count==51 and base.one(log,'sham_finished')[1]==51,'not 51 slots')
        manifest=base.read(root,'sham_validity_series');base.need(len(manifest)==51,'wrong manifest length')
    else:
        base.need(count<51 and 'sham_finished' not in log,'false partial completion');manifest=None
    rows=[];previous_complete=verified_time;origin=None;first_meta=None;last_meta=None
    expected_targets=[];meta_times=[];png_times=[]
    for i in range(count):
        tag='S%02d'%i;event_time,row=base.one(log,tag+'_receipt')
        base.need(row['index']==i and row['scheduled_s']==9*i,'index/schedule mismatch')
        if manifest is not None:base.need(row==manifest[i],'manifest/log mismatch')
        t0=datetime.fromisoformat(row['meta_utc']);t1=datetime.fromisoformat(row['png_utc'][0]);t2=datetime.fromisoformat(row['png_utc'][1]);t3=datetime.fromisoformat(row['complete_utc'])
        base.need(previous_complete<t0<t1<t2<t3<=event_time,'sample timing order');previous_complete=t3
        meta_times.append(t0);png_times.append(t1)
        current_origin=t3.timestamp()-row['elapsed_complete'];origin=origin or current_origin
        base.need(abs(current_origin-origin)<.02,'moving schedule origin')
        base.need(t0.timestamp()-origin>=9*i-.1,'compressed/early slot')
        if first_meta is None:first_meta=t0
        last_meta=t0
        if i%3==0:
            key=tag+'_target_pre';expected_targets.append(key);target_time,pre=base.one(log,key)
            sham.plateau(base,root,tag+'_before',pre[0]);base.need(base.scene(root,tag+'_target')==pre[1]==original,'sham scene changed')
            base.need(target_time<t0,'target pre timing')
        pair=[camera(tag+'_pre'),camera(tag+'_post')];base.need(pair==row['frame_span'],'sample frame brackets')
        g,m,z=measured(tag);base.need(g==row['fixture'] and m==row['legends'] and z==row['shadows'],'receipt scores mismatch')
        if i%3==2:
            key=tag+'_target_post';expected_targets.append(key);target_time,state=base.one(log,key)
            sham.plateau(base,root,tag+'_after',state);base.need(target_time>event_time,'target post timing')
        rows.append(dict(index=i,elapsed_complete=row['elapsed_complete'],frame_span=pair,fixture=g,legends=m,shadows=z))
    actual_targets=[k for k in log if k.endswith('_target_pre') or k.endswith('_target_post')]
    base.need(actual_targets==expected_targets,'missing/extra target brackets')
    base.advance(last,base.stamp(base.metadata(root,'oc_return_a_read')['res']))
    passed=[passes(r['fixture'],r['legends']) for r in rows]
    longest=streak=0
    for ok in passed:streak=streak+1 if ok else 0;longest=max(longest,streak)
    reasons=Counter()
    for row in rows:
        for patch,v in row['fixture']['geometry']['patches'].items():
            reasons.update(patch+':'+f for f in v['failures'])
        if not row['fixture']['pass_original_upper_headroom']:reasons.update(['original_upper_headroom'])
        if not row['legends']['pass_modes']:reasons.update(['semantic_mode_or_marker'])
        for name,value in row['legends']['glyphs'].items():
            if not value['ok']:reasons.update(['glyph:'+name])
        for name,value in row['legends']['arrows'].items():
            if not value['ok']:reasons.update(['arrow:'+name])
    def timing(points):
        gaps=[(b-a).total_seconds() for a,b in zip(points,points[1:])]
        return dict(span_seconds=(points[-1]-points[0]).total_seconds(),
                    min_interval_seconds=min(gaps) if gaps else None,
                    max_interval_seconds=max(gaps) if gaps else None)
    return dict(status='complete_sham_recording' if complete else 'partial_sham_recording',sample_count=count,
                pass_count=sum(passed),pass_fraction=sum(passed)/count,all_51_pass=complete and all(passed),
                first_failure=next((i for i,v in enumerate(passed) if not v),None),longest_pass_run=longest,
                reasons=dict(reasons),host_first_to_last_meta_seconds=(last_meta-first_meta).total_seconds(),
                timing=dict(nominal_slot_span_seconds=9*(count-1),metadata_start=timing(meta_times),
                            png_start=timing(png_times)),
                references=ref_scores,samples=rows,restoration=restored,
                limits=['One unchanged DBV2632, not a brightness intervention or optical PWM measurement.',
                        '500 us preview may alias; AWB/ISP and channel zeros prevent amplitude/linearity conclusions.',
                        'Raw plateau files have no embedded timestamp; host and Camera2 clocks are separate.',
                        'Nine-second nominal slots do not imply constant nine-second raster intervals; native checks add cadence variation.',
                        'State sampled per triple is not continuous monitoring. Semantic checks are raster proxies, not instrument telemetry.'])


def render(outcome):
    """Deterministic, lossless JSON: one line per sample/reference, no rounding."""
    def compact(value):
        return json.dumps(value,ensure_ascii=True,allow_nan=False,separators=(',',':'))
    lines=['{']
    items=list(outcome.items())
    for index,(key,value) in enumerate(items):
        suffix=',' if index<len(items)-1 else ''
        prefix='  '+compact(key)+':'
        if key in ('samples','references') and isinstance(value,list):
            lines.append(prefix+'[')
            lines.extend('    '+compact(row)+(',' if j<len(value)-1 else '') for j,row in enumerate(value))
            lines.append('  ]'+suffix)
        else:
            lines.append(prefix+compact(value)+suffix)
    lines.append('}')
    return '\n'.join(lines)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('template',type=Path);p.add_argument('--scope-package',type=Path,default=ARTIFACTS/'scope_exterior_registration_20261118');p.add_argument('--allow-partial',action='store_true');a=p.parse_args()
    print(render(replay(a.root,a.template,a.scope_package,a.allow_partial)))
