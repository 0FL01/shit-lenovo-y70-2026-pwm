"""Offline R12 operator QA primitives. No device/API/command execution.
Archive adapter and restoration schema deliberately pending; this is not a run PASS.
"""
import hashlib,re
from pathlib import Path
from PIL import Image
class Reject(ValueError): pass
RESULT={'sensor.exposureTime':'156000','sensor.sensitivity':'6400',
 'sensor.frameDuration':'33350000','sensor.rollingShutterSkew':'31824000',
 'scaler.cropRegion':'0 0 3264 2448','control.aeMode':'OFF',
 'lens.focusDistance':'0.00000000','lens.focalLength':'1.63999999',
 'control.videoStabilizationMode':'OFF','lens.opticalStabilizationMode':'OFF'}
REQUEST={'sensor.exposureTime':'200000','sensor.sensitivity':'0',
 'sensor.frameDuration':'33333333','scaler.cropRegion':'0 0 3264 2448','control.aeMode':'OFF'}
def section(t,start,end):
 if t.count(start)!=1:raise Reject('Missing/ambiguous section')
 return t.split(start,1)[1].split(end,1)[0]
def fields(t):
 pairs=re.findall(r'^\s*android\.([\w.]+) \([^\n]+\n\s*\[([^\]\n]+)\]',t,re.M)
 out={}
 for k,v in pairs:
  if k in out:raise Reject('Duplicate metadata '+k)
  out[k]=v.strip()
 return out
def expect(got,expected):
 for k,v in expected.items():
  if got.get(k)!=v:raise Reject('Unexpected '+k)
def raw(path,request_exposure="200000"):
 b=Path(path).read_bytes();t=b.decode('utf8')
 d=section(t,'== Camera device 2 dynamic info: ==','== Camera device 3 dynamic info: ==')
 if 'Device 2 is open.' not in d or 'Client package: com.nothing.camera' not in d:raise Reject('Wrong camera/client')
 r=fields(section(d,'Latest received frame:','Device status:'))
 q=fields(section(d,'Last request sent:','=='))
 expect(r,RESULT);expect(q,{**REQUEST,"sensor.exposureTime":request_exposure})
 if not re.search(r'Stream\[0\]: Output.*?Dims: 1440 x 1080,',d,re.S):raise Reject('Preview size')
 try:f=int(r['request.frameCount']);ts=int(r['sensor.timestamp'])
 except (KeyError,ValueError):raise Reject('Missing frame identity')
 if f<0 or ts<=0:raise Reject('Invalid frame identity')
 return {'sha256':hashlib.sha256(b).hexdigest(),'frame':f,'timestamp_ns':ts,'result':{k:r[k] for k in RESULT},'request':{k:q[k] for k in REQUEST}}
def advancing(records):
 if not records:raise Reject('Empty metadata roster')
 for a,b in zip(records,records[1:]):
  if not(b['frame']>a['frame'] and b['timestamp_ns']>a['timestamp_ns']):raise Reject('Nonadvancing camera metadata')
 return True
def png(path,expected_size=(1080,2392)):
 p=Path(path);b=p.read_bytes()
 with Image.open(p) as im:
  if im.format!='PNG' or im.size!=expected_size:raise Reject('PNG type/dimensions')
  im.verify()
 with Image.open(p) as im:im.load()
 return {'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'dimensions':list(expected_size)}
def bracket(pre,image,post,request_exposure="200000"):
 a=raw(pre,request_exposure);b=raw(post,request_exposure);advancing([a,b]);im=png(image)
 return {'pre':a,'image':im,'post':b,'displayed_sensor_frame_identity':'unknown'}
def inside(root,name):
 root=Path(root).resolve();p=(root/name).resolve()
 if not p.is_relative_to(root) or not p.is_file():raise Reject('Invalid archive member')
 return p
