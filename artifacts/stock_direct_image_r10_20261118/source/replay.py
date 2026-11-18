"""Private offline acquisition/source audit. Never imports acquisition or accesses devices."""
from pathlib import Path
import argparse,json,random,re,hashlib
from datetime import datetime
import numpy as np
from PIL import Image
ROOT=None
TAGS=['A1','Ai','B','Bi','A2']
KEYS=('control.aeMode control.aeLock control.awbMode control.awbLock control.afMode lens.opticalStabilizationMode scaler.cropRegion control.zoomRatio control.aeRegions control.afRegions control.awbRegions control.aeExposureCompensation control.aeTargetFpsRange flash.mode control.captureIntent').split()
def code(seed):
 r=random.Random(seed);a=np.zeros((8,8),np.uint8)
 for y in range(8):a[y,r.sample(range(8),4)]=1
 return a
A=code(103820241);B=code(937015809);CODES=dict(A1=A,Ai=1-A,B=B,Bi=1-B,A2=A)
def need(x,s):
 if not x:raise ValueError(s)
def pixels(name,size):
 with Image.open(ROOT/(name+'.png')) as f:
  need(f.format=='PNG' and f.size==size,'PNG shape '+name);return np.asarray(f.convert('RGB'))
def centre(a):return hashlib.sha256(a[792:2376,360:1080].tobytes()).hexdigest()
def meta(name):return json.loads((ROOT/(name+'.json')).read_text())
def stamp(m):return (int(m['request.frameCount']),int(m['sensor.timestamp']))
def advance(a,b):need(all(x<y for x,y in zip(a,b)),'camera nonadvancing')
def events():
 result={};previous=None
 for ts,k,v in [json.loads(x) for x in (ROOT/'log.jsonl').read_text().splitlines()]:
  t=datetime.fromisoformat(ts);need(previous is None or t>=previous,'event UTC regression');previous=t
  result.setdefault(k,[]).append([t,v])
 return result
def one(log,k):
 need(len(log.get(k,[]))==1,'missing/duplicate '+k);return log[k][0]
def state(raw,app):
 required=[app,'showing=false','mWakefulness=Awake','screen_brightness=105','screen_brightness_mode=0','min_refresh_rate=120.0','peak_refresh_rate=120.0','vsyncRate=120.00 Hz','panelDC=0','panel_bl_power=0','mIsRbcActive=false','mIsHdrLayerPresent=false','reduce_bright_colors_activated=null','reduce_bright_colors_level=null','reduce_bright_colors_persist_across_reboots=null','colorTransformMatrix=[[1.000,0.000,0.000,0.000][0.000,1.000,0.000,0.000][0.000,0.000,1.000,0.000][0.000,0.000,0.000,1.000]]']
 need(all(v in raw for v in required),'raw target state mismatch')
 n=re.search(r'panel_brightness=(\d+)',raw)[1];p=re.search(r'mPowerRequest=policy=(\w+)',raw)[1];reason=re.search(r'mBrightnessReason=([^\n]+)',raw)[1]
 need((n,p,reason) in [('828','DIM','manual [ dim ]'),('6879','BRIGHT','manual')],'brightness policy mismatch')
 return [n,p]
def source(tag):
 a=pixels(tag+'_target',(1440,3168));bits=CODES[tag];need((bits.sum(1)==4).all(),'source row budget')
 html=(ROOT/(tag+'.html')).read_text();rects=re.findall(r'<rect x="(\d+)" y="(\d+)" width="60" height="60" fill="#b8b8b8"/>',html)
 decoded=np.zeros((8,8),np.uint8)
 for x,y in rects:
  x,y=int(x),int(y);need(x%60==y%60==0 and 0<=x<480 and 0<=y<480,'HTML rect');need(decoded[y//60,x//60]==0,'duplicate rect');decoded[y//60,x//60]=1
 need(np.array_equal(decoded,bits) and len(rects)==32,'source code mismatch')
 need('viewBox="0 0 1440 2880"' in html and 'preserveAspectRatio="none"' in html and 'width="480" height="480"' in html and 'fill="#383838"' in html,'HTML geometry')
 grey=(a.max(2)==a.min(2)).all(1);low=a.min((1,2));high=a.max((1,2));c=np.flatnonzero(grey&(low>=40)&(high<=184)&(high-low>70))
 need(len(c)>2400 and np.array_equal(c,np.arange(c.min(),c.max()+1)),'contiguous content')
 lo,hi=int(c.min()),int(c.max()+1);need((lo,hi)==(332,3090),'viewport differs from measured A1')
 # Independently decode every physical row-cell centre, using true content extent.
 ys=(lo+(np.arange(48)+.5)*(hi-lo)/48).astype(int);xs=np.arange(30,1440,60)
 expected=np.tile(bits,(6,3))*128+56
 need(np.array_equal(a[ys[:,None],xs[None,:],:],np.repeat(expected[:,:,None],3,2)),'raster centres code/order')
 samples=np.empty((48,24),float);spread=[]
 for y in range(48):
  t=int(np.ceil(lo+(y+.3)*(hi-lo)/48));b=int(np.floor(lo+(y+.7)*(hi-lo)/48))+1
  for x in range(24):
   cell=a[t:b,x*60+18:x*60+42,0];samples[y,x]=np.median(cell);spread.append(int(cell.max())-int(cell.min()))
 need(np.array_equal(samples,expected),'central40% cell medians')
 v=a[lo:hi];row=v[:,:,0].sum(1).astype(int);interior=(v[:,:,0]==56)|(v[:,:,0]==184)
 result=dict(viewport=[lo,hi],dimensions=list(a.shape),row_count=48,column_count=24,source_ones_per_row=bits.sum(1).tolist(),source_RGB_budget_per_row=960,rendered_RGB_total=v.sum((0,1)).tolist(),rendered_row_sum=row.tolist(),ideal_row_sum=172800,exact_budget_rows=int((row==172800).sum()),deviant_rows=int((row!=172800).sum()),row_deficit_max=int((172800-row).max()),intermediate_pixels=int((~interior).sum()),central40_median_correct=1152,central40_nonuniform_cells=int(np.count_nonzero(spread)),all_RGB_equal=bool((v[:,:,0]==v[:,:,1]).all() and (v[:,:,1]==v[:,:,2]).all()))
 return result
def audit():
 log=events();original=state(one(log,'before')[1],'ZRamSettingsActivity');before=meta('beforestock');last=stamp(meta('wide_start'));seen=set();out={};brackets=[];baseline=None;last_event=one(log,'before')[0]
 for tag in TAGS:
  if not (ROOT/(tag+'_target.png')).exists():break
  result=source(tag);dt,raw=one(log,tag+'_display');need(dt>last_event,'display chronology');st=state(raw,'com.android.htmlviewer/');need(st==original,'source power/brightness drift')
  source_time,source_state=one(log,tag+'_source');need(source_time>=dt and source_state[1]==st,'source state event');last_event=source_time
  if baseline is None:baseline=result
  need(result['viewport']==baseline['viewport'],'viewport drift')
  frames=[]
  for j in range(2):
   name=tag+str(j)
   if not (ROOT/(name+'post.json')).exists():break
   pre=meta(name+'pre');post=meta(name+'post')
   advance(last,stamp(pre));advance(stamp(pre),stamp(post));last=stamp(post)
   for m in (pre,post):
    need(m['control.captureIntent']=='PREVIEW' and m['flash.mode']=='OFF' and m['control.aeLock']=='OFF' and m['control.afMode']=='CONTINUOUS_PICTURE' and abs(float(m['control.zoomRatio'])-.6)<.055,'camera mode drift')
   image=pixels(name,(1080,2392));digest=hashlib.sha256(image.tobytes()).hexdigest();need(digest not in seen,'duplicate camera PNG');seen.add(digest)
   bt,bv=one(log,name+'_bracket');need(bt>last_event and bv==post['request.frameCount'],'bracket log/order mismatch');last_event=bt
   frames.append(dict(camera_before=stamp(pre),camera_after=stamp(post),ISO=[pre['sensor.sensitivity'],post['sensor.sensitivity']],exposure_ns=[pre['sensor.exposureTime'],post['sensor.exposureTime']],focus=[pre['lens.focusDistance'],post['lens.focusDistance']]))
  result['camera_frames']=frames
  if len(frames)==2:
   et,raw=one(log,tag+'_end');need(et>last_event and state(raw,'com.android.htmlviewer/')==st,'late target state/order drift');last_event=et
  out[tag]=result
 complete=all(k in out and len(out[k]['camera_frames'])==2 for k in TAGS)
 if complete:
  et,val=one(log,'acquisition_complete');need(et>last_event and val is True,'completion/order mismatch');last_event=et
 restore={}
 if 'target_restored' in log:
  ft,raw=one(log,'stock_target_final');rt,restore_value=one(log,'target_restored');returned=state(raw,'ZRamSettingsActivity');need(last_event<ft<rt,'target restoration chronology')
  need(centre(pixels('returned_app',(1440,3168)))==centre(pixels('fresh_baseline',(1440,3168)))==centre(pixels('target_pre',(1440,3168))),'target scene restoration')
  need(restore_value==[original,returned,centre(pixels('fresh_baseline',(1440,3168)))],'target restoration receipt mismatch');last_event=rt
  restore['target']={'before':original,'after':returned,'confirmed':True}
 if 'camera_restored' in log:
  a,b=meta('stock_final1'),meta('stock_final2');need(all(a[k]==b[k]==before[k] for k in KEYS),'camera exact controls restore');advance(stamp(a),stamp(b));advance(last,stamp(a));ct,cv=one(log,'camera_restored');need(ct>last_event and cv is True,'false camera restore/order')
  restore['camera']={'observed_fields':len(KEYS),'confirmed':True,'frame_pair':[stamp(a),stamp(b)]}
 budgets={}
 for tag,r in out.items():
  rr=np.array(r['rendered_row_sum']);bb=np.array(baseline['rendered_row_sum'])
  regions={}
  rgb=pixels(tag+'_target',(1440,3168));rgb0=pixels('A1_target',(1440,3168))
  for name,lo,hi in [('top_system_toolbar',0,332),('pattern_plateau',332,3090),('bottom_system_navigation',3090,3168)]:
   v=rgb[lo:hi].astype(np.int64);w=rgb0[lo:hi].astype(np.int64);regions[name]=dict(RGB_sum=v.sum((0,1)).tolist(),sum_difference_vs_A1=(v.sum((0,1))-w.sum((0,1))).tolist(),different_pixels_vs_A1=int((v!=w).any(2).sum()))
  changed=np.flatnonzero(rr!=bb)+332
  distance=np.min(abs(changed[:,None]-(332+np.arange(49)*2758/48)[None,:]),axis=1) if len(changed) else np.array([])
  budgets[tag]=dict(regions=regions,max_changed_row_distance_from_boundary=float(distance.max()) if len(distance) else 0,absolute_changed_rows=(np.flatnonzero(rr!=bb)+332).tolist(),total_difference_vs_A1=[v-w for v,w in zip(r['rendered_RGB_total'],baseline['rendered_RGB_total'])],max_abs_row_difference_vs_A1=int(abs(rr-bb).max()),exact_row_equality_vs_A1=int((rr==bb).sum()))
 if len(restore)==2:
  final=(ROOT/'readback_release.txt').read_text()
  need(all(x in final for x in ['mCurrentScreenBrightness=0.40987244','mActualBacklight=0.40987244','mHbmMode=off','screen_brightness=105','screen_brightness_mode=0','screen_brightness_float=null','min_refresh_rate=120.0','peak_refresh_rate=120.0','value=0','ZRamSettingsActivity']),'fresh release settings mismatch')
  restore['fresh_release']=dict(user_brightness_float='0.40987244',hbm='off',vendor_dc=0)
 return dict(status='acquisition_complete_return_confirmed' if complete and len(restore)==3 else 'acquisition_complete_return_pending' if complete else 'partial',phase_order=list(out),phases=out,budget_comparisons=budgets,restoration=restore,source_lock='matched periodic raw source snapshots; not continuous',limits=['Source HTML is exactly row-balanced; rendered antialiasing/title shadow makes strict every-row equality false. No preregistered raster-budget tolerance found, so no retrospective exact-budget pass.','Camera is automatic AE/AF, not fixed sensor exposure. Report actual metadata, no optical linearity claim.','Device identity/sole-client attribution rests on acquisition guards, not independently archived raw identity per shot.','This audit does not inspect heldout camera-code recognition or certify its frozen homography.'])
def render(result):
 def compact(v):return json.dumps(v,separators=(',',':'),allow_nan=False)
 lines=['{']
 for index,(key,value) in enumerate(result.items()):
  lines.append('  '+json.dumps(key)+':'+compact(value)+(',' if index<len(result)-1 else ''))
 lines.append('}')
 return '\n'.join(lines)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('private_directory',type=Path);args=p.parse_args();ROOT=args.private_directory
 print(render(audit()))
