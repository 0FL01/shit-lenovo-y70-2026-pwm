"""Offline sham-only audit. No acquisition imports or hardware calls.

Public dependency is the preceding stock_dbv_2632_20261118 package. Private
captures remain private; only measurement summaries are returned.
"""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path

FROZEN='f931a8cc847340ef708849625e6253c68df7584904a5c5f915d8b7ebe6b0e54a'
DEFAULT_DEPENDENCY=Path(__file__).resolve().parents[1]/'stock_dbv_2632_20261118'


def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def dependencies(directory):
    base=load_module('sham_evidence_base',directory/'evidence/replay.py')
    path=directory/'analysis_geometry.py'
    base.need(hashlib.sha256(path.read_bytes()).hexdigest()==FROZEN,'frozen public scorer changed')
    return base,load_module('sham_frozen_geometry',path)


def plateau(base,root,tag,expected):
    import re
    raw=(root/(tag+'_display.txt')).read_text()
    required=('ZRamSettingsActivity','vsyncRate=120.00 Hz','min_refresh_rate=120.0',
              'peak_refresh_rate=120.0','screen_brightness_float=null','screen_brightness_mode=0',
              'mIsRbcActive=false','mIsHdrLayerPresent=false')
    base.need(all(t in raw for t in required),'raw display controls drift')
    patterns={'policy':r'policy=(\w+)','user':r'mCurrentScreenBrightness=([\d.]+)',
              'out':r'mActualBacklight=([\d.]+)','android':r'screen_brightness=(\d+)',
              'DBV':r'\n(\d+)\n0\n','reason':r'mBrightnessReason=([^\n]+)'}
    parsed={}
    for key,pattern in patterns.items():
        match=re.search(pattern,raw);base.need(match is not None,'missing raw '+key);parsed[key]=match[1]
    base.need(parsed==expected,'raw/receipt plateau mismatch');base.target_state(parsed,2632)
    provider=(root/(tag+'_provider.txt')).read_text()
    base.need(re.search(r'\bvalue=0\b',provider) is not None,'provider DC mismatch')


def replay(root,dependency=DEFAULT_DEPENDENCY,allow_partial=False):
    base,geo=dependencies(dependency)
    base.need(hashlib.sha256((root/'analysis_geometry.py').read_bytes()).hexdigest()==FROZEN,'private frozen scorer changed')
    log=base.events(root)
    complete=(root/'sham_validity_series.json').exists()
    base.need(complete or allow_partial,'incomplete sham-only series')
    base.need(not complete,'unexpected complete marker for commissioning abort')
    entry=log.get('single_entry_command',[])
    restored=base.restoration(root,log,bool(entry),'target_full_before')
    base.need(len(entry)==1,'expected one single-entry command')
    entry_time,command=base.one(log,'single_entry_command')
    base.need(command[1]==base.ARGS[2632],'wrong entry command')
    settled_time,settled=base.one(log,'single_entry_settled')
    base.need(entry_time<settled_time and settled[0]==2632,'entry native readback')
    plateau(base,root,'sham_enter',settled[1])
    original=base.scene(root,'original_app')
    base.need(base.scene(root,'enter_sham_target')==original,'entry scene changed')
    last=base.stamp(base.read(root,'oc_first')['res']);fixed=None
    for name in ('baseline_bright','initial_at_sham','return_sham'):
        text=(root/(name+'_display.txt')).read_text()
        expected=('policy=BRIGHT','mBrightnessReason=manual','mActualBacklight=0.40987244',
                  'mCurrentScreenBrightness=0.40987244','screen_brightness=105',
                  'screen_brightness_mode=0','min_refresh_rate=120.0','peak_refresh_rate=120.0',
                  'mIsRbcActive=false','mIsHdrLayerPresent=false','vsyncRate=120.00 Hz',
                  '\n6879\n0\n','ZRamSettingsActivity')
        base.need(all(t in text for t in expected),'raw 6879 baseline/return mismatch')
    # The 6879 health-control reference must not replace the new native reference.
    preliminary=[]
    for i in range(3):
        tag='new_qual'+str(i);m=base.metadata(root,tag+'_read');sig=base.manual(m);fixed=fixed or sig
        base.need(sig==fixed,'preliminary camera drift');base.advance(last,base.stamp(m['res']));last=base.stamp(m['res'])
        image=base.pixels(root,tag,(1080,2392));score=geo.score(image)
        base.need(score==base.read(root,tag+'_fixture'),'preliminary PNG/fixture mismatch')
        preliminary.append(image)
    geo.reference(preliminary)
    references=log.get('native_reference',[])
    base.need(len(references)==3,'missing/duplicate native commissioning frames')
    rr=[];ref_scores=[]
    for i,(event_time,row) in enumerate(references):
        tag='R%02d'%i
        base.need(row[0]==tag,'reference order/label mismatch')
        t0=datetime.fromisoformat(row[1]);t1=datetime.fromisoformat(row[2])
        base.need(settled_time<t0<t1<event_time and (t0-entry_time).total_seconds()>=12,'reference timing')
        pair=[]
        for side in ('pre','post'):
            m=base.metadata(root,tag+'_'+side+'_read');base.need(base.manual(m)==fixed,'reference camera drift')
            current=base.stamp(m['res']);base.advance(last,current);last=current;pair.append(list(current))
        base.need(pair==row[3:5],'reference bracket mismatch')
        image=base.pixels(root,tag,(1080,2392));score=geo.score(image)
        base.need(score==row[5]==base.read(root,tag+'_fixture'),'reference PNG/fixture mismatch')
        rr.append(image);ref_scores.append(score)
    try:
        ref=geo.reference(rr)
    except ValueError as error:
        base.need(not complete and 'reference_verified' not in log and not any(k.endswith('_receipt') for k in log)
                  and not (root/'sham_ref.json').exists() and not list(root.glob('S[0-9][0-9]*')),
                  'false commissioning success')
        base.advance(last,base.stamp(base.metadata(root,'oc_return_a_read')['res']))
        base.need(str(error)=='commissioning absolute gate' and
                  [s['failures'] for s in ref_scores]==[['right-upper/b:absolute'],[],[]],
                  'unexpected commissioning failure')
        details=[]
        for image,score in zip(rr,ref_scores):
            zero=image[1080:1270,112:540]==0
            details.append(dict(score=score,any_zero=int(zero.any(2).sum()),all_zero=int(zero.all(2).sum())))
        return dict(status='commissioning_rejected',samples=0,native_reference_count=3,
                    reference_failure=str(error),reference_scores=details,restoration=restored,
                    limits=['Only observed commissioning rejection is reproduced; no long sham statistics or DBV comparison.',
                            '2632 raw settled readback precedes the three references; no late 2632 plateau readback was captured.',
                            'Raw before/after return readbacks are 6879; do not call them late 2632 evidence.',
                            'Preview at 500 us can alias; auto AWB/ISP and channel zeros prevent amplitude or PWM conclusions.'])
    raise ValueError('commissioning unexpectedly succeeded; this verifier supports the observed commissioning abort only')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--dependency',type=Path,default=DEFAULT_DEPENDENCY);p.add_argument('--allow-partial',action='store_true');a=p.parse_args()
    print(json.dumps(replay(a.root,a.dependency,a.allow_partial),indent=2))
