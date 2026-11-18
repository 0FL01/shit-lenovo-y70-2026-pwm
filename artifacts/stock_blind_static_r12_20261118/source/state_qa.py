"""Offline target and visible stock-camera return checks, no assignment reads."""
import re,json
from datetime import datetime
from PIL import Image
import operator_core as c
SETTINGS=['screen_brightness','screen_brightness_mode','min_refresh_rate','peak_refresh_rate','reduce_bright_colors_activated','reduce_bright_colors_level','reduce_bright_colors_persist_across_reboots','panelDC','panel_bl_power']
def one(pattern,t):
 v=re.findall(pattern,t,re.M)
 if not v or len(set(v))!=1:raise c.Reject('Missing/ambiguous state field '+pattern)
 return v[0]
def target(t):
 s={k:one(r'^'+k+r'=(.*)$',t) for k in SETTINGS}
 s.update(native=one(r'^panel_brightness=(\d+)$',t),policy=one(r'mPowerRequest=policy=(\w+)',t),foreground=one(r'mCurrentFocus=Window\{\S+ u\d+ ([^}]+)\}',t),refresh=one(r'vsyncRate=([0-9.]+) Hz',t),rbc=one(r'mIsRbcActive=(\w+)',t),hdr=one(r'mIsHdrLayerPresent=(\w+)',t),matrix=one(r'colorTransformMatrix=(\S+)',t),strength=one(r'mStrength = (\d+)',t))
 if s['refresh']!='120.00' or s['panelDC']!='0' or s['hdr']!='false' or s['rbc']!='false':raise c.Reject('Target acquisition state')
 return s
def events(path):
 rows=[json.loads(l) for l in path.read_text().splitlines() if l.strip()];out={};last=None
 for row in rows:
  if not isinstance(row,list) or len(row)!=3:raise c.Reject('Log schema')
  time,tag,value=row;now=datetime.fromisoformat(time)
  if last is not None and now<last:raise c.Reject('Reordered event time')
  last=now
  if tag in out:raise c.Reject('Duplicate event tag')
  out[tag]=(now,value)
 return out
CAM=['control.aeMode','control.aeLock','control.afMode','control.awbMode','control.awbLock','control.zoomRatio','control.captureIntent','flash.mode','scaler.cropRegion','lens.opticalStabilizationMode','control.aeExposureCompensation']
def returns(root,ev):
 a=target(ev['before_r12'][1]);b=target(ev['target_after'][1])
 for k in SETTINGS+['foreground','refresh','rbc','hdr','matrix','strength']:
  if a[k]!=b[k]:raise c.Reject('Target restoration mismatch '+k)
 phase_times=[v[0] for k,v in ev.items() if re.fullmatch(r'P[0-9]{2}_(early|late)',k)]
 if phase_times and ev['target_after'][0]<=max(phase_times):raise c.Reject('Early target return')
 with Image.open(root/'fresh_target.png') as x,Image.open(root/'returned_target.png') as y:
  if x.size!=y.size or x.size!=(1440,3168):raise c.Reject('Target return dimensions')
  if x.convert('RGB').crop((360,792,1080,2376)).tobytes()!=y.convert('RGB').crop((360,792,1080,2376)).tobytes():raise c.Reject('Target return crop')
 if ev['target_returned'][1]!=[[a['native'],a['policy']],[b['native'],b['policy']]]:raise c.Reject('Target return receipt')
 if not(ev['target_returned'][0]>=ev['target_after'][0] and ev['stock_returned'][0]>ev['target_returned'][0]) or ev['stock_returned'][1] is not True:raise c.Reject('Return event order/value')
 before=json.loads((root/'camera_pre.json').read_text());after=[json.loads((root/(n+'.json')).read_text()) for n in ['restoredA','restoredB']]
 for s in after:
  c.expect(s,{'control.aeMode':'ON','control.aeLock':'OFF','control.afMode':'CONTINUOUS_PICTURE','control.zoomRatio':'2.00000000','control.captureIntent':'PREVIEW'})
  for k in CAM:
   if k not in before or s.get(k)!=before[k]:raise c.Reject('Camera restoration '+k)
 if int(after[0]['sensor.timestamp'])<=int(before['sensor.timestamp']):raise c.Reject('Stale camera return')
 c.advancing([{'frame':int(s['request.frameCount']),'timestamp_ns':int(s['sensor.timestamp'])} for s in after])
 return {'target_observed_settings_and_crop':True,'camera_observed_stock_settings':True,'original_policy_native':[a['policy'],a['native']],'returned_policy_native':[b['policy'],b['native']],'hidden_preferences_verified':False,'expert_mode_saved_controls_verified':False,'photo_ui_mode_verified':False}
def acquisition(root,ev):
 baseline=target(ev['target_awake'][1]);prev=ev['target_awake'][0]
 for i in range(6):
  phase=f'P{i:02d}'
  for edge in ['early','late']:
   tag=phase+'_'+edge;t,raw=ev[tag];s=target(raw)
   if t<=prev:raise c.Reject('Phase ordering')
   prev=t
   for k in SETTINGS+['refresh','rbc','hdr','matrix','strength','native','policy']:
    if s[k]!=baseline[k]:raise c.Reject('Target drift '+k)
   if s['policy']!='BRIGHT' or 'HTMLViewerActivity' not in s['foreground']:raise c.Reject('Target scene/policy')
   if json.loads((root/(tag+'.json')).read_text())!=[s['native'],'BRIGHT']:raise c.Reject('Target summary mismatch')
  with Image.open(root/(phase+'_source.png')) as a,Image.open(root/(phase+'_last_source.png')) as b:
   if a.size!=(1440,3168) or b.size!=a.size:raise c.Reject('Source dimensions')
   # Android status/toolbar excluded; target image area stable pixel-for-pixel.
   if a.convert('RGB').crop((0,332,1440,3090)).tobytes()!=b.convert('RGB').crop((0,332,1440,3090)).tobytes():raise c.Reject('Source changed within phase')
 return True
def bracket_events(ev,frames):
 for f in frames:
  n=f['ordinal'];phase=n.split('_')[0]
  tags=[phase+'_early',n+'_pre',n+'_post',n+'_bracket',phase+'_late']
  ts=[ev[t][0] for t in tags]
  if not all(b>a for a,b in zip(ts,ts[1:])):raise c.Reject('Bracket outside phase/order')
  expected=[]
  for side in ['pre','post']:
   r=f[side];e=ev[n+'_'+side][1]
   if int(e['request.frameCount'])!=r['frame'] or int(e['sensor.timestamp'])!=r['timestamp_ns']:raise c.Reject('Raw/log metadata identity')
   expected.append([r['frame'],r['timestamp_ns']])
  if ev[n+'_bracket'][1]!=expected:raise c.Reject('Bracket receipt identity')
 return True
def expert_return(ev):
 pairs=[('expert_wide_orig','expert_wide_auto'),('expert_main_orig','expert_main_back')]
 keys=['control.aeMode','control.aeLock','control.afMode','control.zoomRatio','control.captureIntent','flash.mode','scaler.cropRegion','lens.focalLength','logical_id']
 for a,b in pairs:
  ta,x=ev[a];tb,y=ev[b]
  if tb<=ta or int(y['sensor.timestamp'])<=int(x['sensor.timestamp']):raise c.Reject('Stale Expert restore')
  c.expect(y,{k:x[k] for k in keys});c.expect(y,{'control.aeMode':'ON','control.aeLock':'OFF'})
 return {'expert_observed_auto_modes_verified':True,'expert_hidden_preferences_verified':False}
def release(root):
 p=root/'release_target_extra.txt'
 if not p.exists():return {'available':False,'verified':False}
 t=p.read_text()
 a=one(r'^\s*mActualBacklight=(\S+)',t);b=one(r'^\s*mCurrentScreenBrightness=(\S+)',t);h=one(r'^\s*mHbmMode=(\S+)',t)
 if a!='0.40987244' or b!=a or h!='off' or 'Result: Bundle[{value=0}]' not in t:raise c.Reject('Release float/HBM/DC')
 if 'ZRamSettingsActivity' not in t:raise c.Reject('Release foreground')
 return {'available':True,'verified':True,'actual_backlight':a,'current_brightness':b,'hbm':h,'provider_dc':'0','timestamp_embedded':False}
