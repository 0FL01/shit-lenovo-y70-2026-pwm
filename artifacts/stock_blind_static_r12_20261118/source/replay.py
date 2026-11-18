"""Offline-only preliminary R12 bracket audit; cannot certify restoration yet."""
import argparse,json
from pathlib import Path
import operator_core as core
import state_qa
def run(root,phases,request_exposure="200000"):
 if phases!=6:raise core.Reject('Fixed six-phase roster required')
 root=Path(root);records=[];frames=[];missing=[];failures=[]
 for phase in range(phases):
  for shot in range(3):
   name=f'P{phase:02d}_{shot}'
   names=[name+'_pre_raw.txt',name+'.png',name+'_post_raw.txt']
   json_names=[name+'_pre_metadata.json',name+'_post_metadata.json']
   absent=[n for n in names+json_names if not (root/n).is_file()]
   if absent:missing.append({'ordinal':name,'missing':absent});continue
   try:
    result=core.bracket(*(core.inside(root,n) for n in names),request_exposure=request_exposure)
    for side,jn in zip(['pre','post'],json_names):
     metadata=json.loads(core.inside(root,jn).read_text())
     core.expect(metadata,{k:v for k,v in result[side]['result'].items() if k not in ['control.videoStabilizationMode','lens.opticalStabilizationMode']})
     core.expect(metadata,{'sensor.timestamp':str(result[side]['timestamp_ns']),'request.frameCount':str(result[side]['frame'])})
   except (ValueError,IndexError,AttributeError,OSError) as e:
    failures.append({'ordinal':name,'reason':str(e)});continue
   records.extend([result['pre'],result['post']]);frames.append({'ordinal':name,**result})
 if records:
  try:core.advancing(records)
  except core.Reject as e:failures.append({'reason':str(e)})
 state=False;restoration=None;release=None
 try:
  ev=state_qa.events(root/'log.jsonl')
  try:
   state=state_qa.acquisition(root,ev)
   state_qa.bracket_events(ev,frames)
  except (KeyError,ValueError,OSError) as e:failures.append({'stage':'source_state','reason':str(e)})
  try:
   restoration=state_qa.returns(root,ev)
   if 'expert_wide_orig' in ev:restoration.update(state_qa.expert_return(ev))
  except (KeyError,ValueError,OSError) as e:failures.append({'stage':'return','reason':str(e)})
 except (ValueError,OSError) as e:failures.append({'stage':'log','reason':str(e)})
 try:release=state_qa.release(root)
 except (ValueError,OSError) as e:failures.append({'stage':'release','reason':str(e)})
 hashes=[f['image']['sha256'] for f in frames]
 if frames:
  base_f=frames[0]['pre']['frame'];base_t=frames[0]['pre']['timestamp_ns']
  for f in frames:
   for side in ['pre','post']:
    r=f[side];r['frame_offset']=r.pop('frame')-base_f;r['timestamp_offset_ns']=r.pop('timestamp_ns')-base_t
 expected={f'P{i:02d}_{j}.png' for i in range(6) for j in range(3)}
 extra=[p.name for p in root.glob('P[0-9][0-9]_[0-9].png') if p.name not in expected]
 if extra:failures.append({'stage':'roster','unexpected':extra})
 if len(hashes)!=len(set(hashes)):failures.append({'stage':'images','reason':'Duplicate PNG hash'})
 return {'status':('SPEC_ACTUAL_PASS_R11_REQUEST_FAIL' if request_exposure!='200000' else 'OBSERVED_FIELDS_PASS_WITH_MODE_LIMITS') if not missing and not failures and restoration else 'INCOMPLETE_OR_REJECTED','expected_frames':phases*3,'request_exposure_ns':request_exposure,'frozen_R11_request_matches':request_exposure=='200000','exported_json_exclusions_raw_checked':['control.videoStabilizationMode','lens.opticalStabilizationMode'],
 'present_brackets':len(frames),'missing':missing,'unique_png_hashes':len(set(hashes)),
 'duplicate_png_hashes':len(hashes)-len(set(hashes)),'frames':frames,
 'failures':failures,'release':release,'restoration':restoration,'source_state_verified':state,
 'limits':['Bracket frame identity is not screenshot sensor identity.','No decoding or physical timing inference.','Source stability checks only x0:1440/y332:3090, not full page, HTML semantics or pixel budgets.','Exact R11 request reproduction is distinct from actual-result compatibility.','Missing hidden preferences and PHOTO UI verification remain explicit.']}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('private_archive');p.add_argument('--phases',type=int,default=6);p.add_argument('--request-exposure',choices=['200000','156250'],default='200000');a=p.parse_args()
 if not 1<=a.phases<=100: p.error('phases must be 1..100')
 out=run(a.private_archive,a.phases,a.request_exposure);print(json.dumps(out,indent=2));raise SystemExit(0 if out['status']=='OBSERVED_FIELDS_PASS_WITH_MODE_LIMITS' else 2)
