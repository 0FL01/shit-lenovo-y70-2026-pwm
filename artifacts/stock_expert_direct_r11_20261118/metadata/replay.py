"""Offline-only, standard-library extractor; never imports acquisition code."""
import sys,re,json,hashlib
from pathlib import Path
def fields(s):
 return {m[0]:m[1].strip() for m in re.findall(r'^\s*((?:android|com\.mediatek)\.[\w.]+) \([^\n]+\n\s*\[([^\]\n]+)\]',s,re.M)}
def run(root):
 out=[]
 for name in ['short_drag','short2','short3','short4']:
  b=(root/(name+'_raw.txt')).read_bytes(); t=b.decode(); d=t.split('== Camera device 2 dynamic info: ==')[1].split('== Camera device 3 dynamic info: ==')[0]
  if not re.search(r'Device 2 is open\.',d) or 'Client package: com.nothing.camera' not in d: raise ValueError('Wrong camera/client')
  a=fields(d.split('Latest received frame:')[1].split('Device status:')[0]); q=fields(d.split('Last request sent:')[1]); st=fields(t.split('== Camera HAL device device@1.1/internal/2 (v1.2) static information: ==')[1].split('dumpState:')[0])
  keys=['sensor.exposureTime','sensor.sensitivity','sensor.frameDuration','sensor.rollingShutterSkew','sensor.timestamp','request.frameCount','scaler.cropRegion','control.aeMode','control.postRawSensitivityBoost','lens.focusDistance','lens.focalLength','control.videoStabilizationMode','lens.opticalStabilizationMode']
  r={'sample':name,'raw_sha256':hashlib.sha256(b).hexdigest(),'result':{k:a.get('android.'+k) for k in keys},'last_request':{k:q.get('android.'+k) for k in keys},'static_id2':{k:st.get('android.'+k) for k in ['sensor.info.activeArraySize','sensor.info.preCorrectionActiveArraySize','sensor.info.pixelArraySize','sensor.orientation','sensor.info.timestampSource','sensor.maxAnalogSensitivity']},'alternate_result':{k:v for k,v in a.items() if k.startswith('com.mediatek.') and any(x in k.lower() for x in ['gain','iso','shutter','exposure','crop','scenario'])},'stream0_dimensions':re.search(r'Stream\[0\]: Output.*?Dims: ([^\n]+)',d,re.S).group(1)}
  if r['result']['sensor.exposureTime']!='156000' or r['last_request']['sensor.exposureTime']!='200000': raise ValueError('Unexpected exposure')
  expected={'sensor.exposureTime':'156000','sensor.sensitivity':'6400','sensor.frameDuration':'33350000','sensor.rollingShutterSkew':'31824000','scaler.cropRegion':'0 0 3264 2448','control.aeMode':'OFF'}
  for k,v in expected.items():
   if r['result'][k]!=v: raise ValueError('Unexpected result '+k)
  for k,v in {'sensor.exposureTime':'200000','sensor.sensitivity':'0','sensor.frameDuration':'33333333','scaler.cropRegion':'0 0 3264 2448','control.aeMode':'OFF'}.items():
   if r['last_request'][k]!=v: raise ValueError('Unexpected last request '+k)
  for k,v in {'sensor.info.activeArraySize':'0 0 3264 2448','sensor.info.preCorrectionActiveArraySize':'0 0 3264 2448','sensor.info.pixelArraySize':'3264 2448','sensor.orientation':'90','sensor.info.timestampSource':'REALTIME'}.items():
   if r['static_id2'][k]!=v: raise ValueError('Unexpected static '+k)
  if not r['stream0_dimensions'].startswith('1440 x 1080,'):raise ValueError('Wrong preview dimensions')
  out.append(r)
 for k in ['request.frameCount','sensor.timestamp']:
  v=[int(x['result'][k]) for x in out]
  if not all(b>a for a,b in zip(v,v[1:])):raise ValueError('Nonadvancing '+k)
 # Publish only offsets: absolute device clock/frame identities are unnecessary.
 base_t=int(out[0]['result']['sensor.timestamp']);base_f=int(out[0]['result']['request.frameCount'])
 for r in out:
  r['result']['timestamp_offset_ns']=int(r['result'].pop('sensor.timestamp'))-base_t
  r['result']['frame_offset']=int(r['result'].pop('request.frameCount'))-base_f
 return {'four_results_advance':True,'samples':out,'calibrated_preview_row_time':None,'physical_pwm_frequency':None,'limits':['Last request is not proven paired with latest result or screenshot.','Static pixel dimensions and skew do not establish sensor sampling mode or UI spatial transform.','No independent optical timebase or sensor-to-preview frame identifier.']}
if __name__=='__main__': print(json.dumps(run(Path(sys.argv[1])),indent=2))
