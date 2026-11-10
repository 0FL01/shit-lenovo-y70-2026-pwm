"""Offline, allowlisted saved-camera and encoded-frame diagnostic only."""
import argparse, collections, hashlib, json, os, pathlib, subprocess
import numpy as np
from guards import private_destination
RUN=pathlib.Path('/home/opencode/.cache/legion-y70-aa-full-stock-03f0ed4-proposal01/run.json')
VIDEO=pathlib.Path('/home/opencode/.cache/legion-y70-aa-optical-media-03f0ed4-01/capture.mp4')
OUT=pathlib.Path(__file__).parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--private-output', type=pathlib.Path, required=True)
parser.add_argument('--summary-output', type=pathlib.Path, required=True)
args=parser.parse_args()
PRIVATE=private_destination(args.private_output)
def check(ok, message):
 if not ok: raise ValueError(message)
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(65536),b''):h.update(b)
 return h.hexdigest()
check(digest(RUN)=='a2875aba1a9c7446eadb2272f3f6ed8c975d4ac50c183a193c9e2a1eb86a268a', 'Run digest mismatch')
check(VIDEO.stat().st_size==96172619 and digest(VIDEO)=='ed4cb72fbb4052d256e4fa02eb706d2634929b953e656eec96501ad1249f6d8f', 'Video mismatch')
os.umask(0o077);PRIVATE.mkdir(exist_ok=False)
d=json.loads(RUN.read_text())
# Never open raw camera receipts, output identifiers, or copy arbitrary keys.
fields=('exposure_ns','iso','ae_mode','af_mode','focus_diopters','crop','zoom','eis_mode','ois_mode','capture_intent','frame_duration_ns','rolling_shutter_skew_ns')
snaps=[('preflight_'+str(i),s) for i,s in enumerate(d['recording_preflight'])]
for i,s in enumerate(d['stages']):
 for edge in ('start','end'):snaps.append((('baseline','sham','return')[i]+'_'+edge,s['camera_'+edge]))
safe=[]
for label,s in snaps:
 safe.append(dict(label=label,**{t:{k:s[t][k] for k in fields if k in s[t]} for t in ('request','result')},streams=[{k:v[k] for k in ('width','height','pixel_format','state','consumer_kind','requested') if k in v} for v in s['streams']]))
entries='stream=codec_name,profile,width,height,coded_width,coded_height,pix_fmt,color_range,color_space,color_transfer,color_primaries,field_order,has_b_frames,r_frame_rate,avg_frame_rate,time_base,start_time,duration,nb_frames,bit_rate:frame=key_frame,best_effort_timestamp_time,pkt_dts_time,pkt_duration_time,pkt_size,pict_type,width,height,crop_top,crop_bottom,crop_left,crop_right:packet=pts_time,dts_time,duration_time,size,flags'
p=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries',entries,'-of','json',str(VIDEO)]))
(PRIVATE/'probe.json').write_text(json.dumps(p))
# ffprobe interleaves frames and packets if both were requested.
f=p.get('frames',[]) or [x for x in p.get('packets_and_frames',[]) if x['type']=='frame']
pack=p.get('packets',[]) or [x for x in p.get('packets_and_frames',[]) if x['type']=='packet']
check(len(f)==2553, 'Frame count mismatch')
pts=np.array([float(x['best_effort_timestamp_time']) for x in f]);dt=np.diff(pts)
keys=[i for i,x in enumerate(f) if x['key_frame']]
def stats(a):return dict(min=float(np.min(a)),median=float(np.median(a)),max=float(np.max(a)),mean=float(np.mean(a)))
windows={}
for name,a,b in [('baseline',861,920),('sham',1534,1593),('return',2171,2230)]:
 z=f[a:b+1];sizes=[int(x['pkt_size']) for x in z]
 windows[name]=dict(indices=[a,b],pts_seconds=[float(pts[a]),float(pts[b])],types=dict(collections.Counter(x['pict_type'] for x in z)),keyframe_indices=[i for i in keys if a<=i<=b],packet_bytes=stats(sizes),thirds_packet_mean_bytes=[float(np.mean(sizes[j:j+20])) for j in (0,20,40)],gop_age_frames=[a-max(i for i in keys if i<=a),b-max(i for i in keys if i<=b)])
result=dict(schema='saved-camera-codec-audit-v1',acquisition_admitted=False,physical_pwm_hz=None,snapshots=safe,stream=p['streams'],frame_count=len(f),packet_count=len(pack),frame_types=dict(collections.Counter(x['pict_type'] for x in f)),keyframe_count=len(keys),keyframe_interval_frames=dict(collections.Counter(np.diff(keys).tolist())),pts_delta_seconds=stats(dt),nonpositive_pts_deltas=int(np.sum(dt<=0)),pts_deltas_outside_30fps_1ms=int(np.sum(abs(dt-1/30)>.001)),frame_dimensions=sorted(set((x['width'],x['height']) for x in f)),crop_values={k:sorted(set(x.get(k) for x in f)) for k in ('crop_top','crop_bottom','crop_left','crop_right')},windows=windows)
check(digest(RUN)=='a2875aba1a9c7446eadb2272f3f6ed8c975d4ac50c183a193c9e2a1eb86a268a' and digest(VIDEO)=='ed4cb72fbb4052d256e4fa02eb706d2634929b953e656eec96501ad1249f6d8f', 'Inputs changed')
with args.summary_output.open('x') as out: out.write(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
