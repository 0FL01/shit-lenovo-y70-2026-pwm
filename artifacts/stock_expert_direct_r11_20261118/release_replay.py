"""Offline source/return checks; no device or network access."""
import argparse, hashlib, json, random
from datetime import datetime
from pathlib import Path
import numpy as np
from PIL import Image
KEYS='control.aeMode control.aeLock control.awbMode control.awbLock control.afMode lens.opticalStabilizationMode scaler.cropRegion control.zoomRatio control.aeRegions control.afRegions control.awbRegions control.aeExposureCompensation control.aeTargetFpsRange flash.mode control.captureIntent'.split()
def need(x,msg):
 if not x: raise ValueError(msg)
def audit(root):
 d=Path(root)
 def arr(n):return np.array(Image.open(d/(n+'.png')).convert('RGB'))
 def crop(n):return hashlib.sha256(arr(n)[792:2376,360:1080].tobytes()).hexdigest()
 def read(n):return json.loads((d/(n+'.json')).read_text())
 rows=[json.loads(z) for z in (d/'log.jsonl').read_text().splitlines()]
 need(all(datetime.fromisoformat(a[0])<datetime.fromisoformat(b[0]) for a,b in zip(rows,rows[1:])),'chronology')
 r={k:z for _,k,z in rows};need(len(r)==len(rows),'duplicate events')
 names=['target_pre','before_r11','staticA_begin','static_source','normalA','more_menu','expert_first','expert_wide','expert_wide_shutter','short_edge','short_drag','short2','short3','short4','held_static_after_4','wide_auto_return','expert_wide_dismiss','expert_main_return','photo_before_exit','r11_target_after','target_returned','stock_returned']
 need(list(r)==names,'sequence')
 for n in ['target_pre','before_r11','staticA_begin','held_static_after_4','r11_target_after']:
  parts=['screen_brightness=105','screen_brightness_mode=0','min_refresh_rate=120.0','peak_refresh_rate=120.0','vsyncRate=120.00 Hz','panel_brightness=6879','mPowerRequest=policy=BRIGHT','colorTransformMatrix=[[1.000,','panelDC=0','mIsRbcActive=false','mIsHdrLayerPresent=false','reduce_bright_colors_activated=null','reduce_bright_colors_level=null','reduce_bright_colors_persist_across_reboots=null']
  parts += ['com.android.htmlviewer/' if n in ('staticA_begin','held_static_after_4') else 'ZRamSettingsActivity']
  need(all(k in r[n] for k in parts),'display '+n)
 need(r['target_returned']==[['6879','BRIGHT'],['6879','BRIGHT']] and r['stock_returned'] is True,'return receipt')
 need(crop('target_pre')==crop('fresh_target')==crop('r11_target_after'),'original scene')
 rng=random.Random(103820241);cells=np.full((8,8),56,dtype=np.uint8)
 for row in cells:row[rng.sample(range(8),4)]=184
 pattern=np.tile(cells,(6,3));p1=arr('staticA_target');p2=arr('held_static_target')
 need(p1.shape==p2.shape==(3168,1440,3) and np.array_equal(p1[332:3090],p2[332:3090]),'static viewport drift')
 y=332+np.floor((np.arange(48)+.5)*2758/48).astype(int);x=30+60*np.arange(24)
 need(np.array_equal(p1[np.ix_(y,x)],np.repeat(pattern[:,:,None],3,axis=2)),'source not code A')
 raw=(d/'release_target_extra.txt').read_text();need(all(k in raw for k in ('mActualBacklight=0.40987244','mCurrentScreenBrightness=0.40987244','mHbmMode=off','value=0','ZRamSettingsActivity')),'final policy')
 def selected(t,ks):return [t[k] for k in ks]
 ks=['control.aeMode','control.aeLock','control.afMode','lens.focusDistance','lens.focalLength','scaler.cropRegion','logical_id','control.zoomRatio','control.captureIntent','flash.mode']
 wide=read('expert_wide_metadata');wide_back=read('wide_auto_return_metadata')
 need(wide['logical_id']=='2' and wide['control.aeMode']=='ON' and selected(wide,ks)==selected(wide_back,ks),'wide auto return')
 ks.remove('lens.focusDistance') # auto-focus may converge differently
 m=read('expert_first_metadata');n=read('expert_main_return_metadata');need(selected(m,ks)==selected(n,ks),'expert 1x return')
 before=read('camera_pre');a=read('restoredA');b=read('restoredB')
 need(before['control.zoomRatio']=='2.00000000' and before['control.aeMode']=='ON' and before['control.afMode']=='CONTINUOUS_PICTURE','baseline PHOTO')
 need(selected(before,KEYS)==selected(a,KEYS)==selected(b,KEYS),'stock return')
 for k in ('sensor.timestamp','request.frameCount'):need(int(a[k])<int(b[k]),'duplicate return')
 return dict(target_static='A',verified_rgb_centres=1152,pattern_first_last_pixel_identical=True,panel_DBV_before_during_after=6879,android_manual=105,android_float_return=0.40987244,active_hz=120,dc=0,hdr=False,original_scene_crop_equal=True,expert_wide_ae_return='ON',expert_main_return=True,stock_controls_equal=len(KEYS),stock_2x_return=True,stock_frames=[int(a['request.frameCount']),int(b['request.frameCount'])],limits=['Discrete state readbacks, not continuous.','Visible settings restored; hidden preferences not compared.','No shutter capture or timebase experiment.'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('archive');args=p.parse_args();print(json.dumps(audit(args.archive),indent=2))
