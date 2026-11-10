"""Post-hoc descriptive join only; no causal inference or threshold change."""
import argparse, io, json
from guards import pinned_bytes
from pathlib import Path
import numpy as np
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
probe_sha='aa2daf3192b63a90022254a3a705709f8f3d51a133d88384ecfe400ba5299451'
series_sha='cc74aae24d50a79e63a5ad8ae4c4a9483791521c40f401d45d0e0f5dc89e7ed7'
p=json.loads(pinned_bytes('/home/opencode/.cache/legion-y70-camera-factors-03f0ed4-20261110/probe.json',probe_sha,5000000))
f=[v for v in p['packets_and_frames'] if v['type']=='frame']
if len(f)!=2553:raise ValueError('Frame count mismatch')
pts=np.array([float(v['best_effort_timestamp_time']) for v in f])
if not np.all(np.isfinite(pts)) or not np.all(np.diff(pts)>0):raise ValueError('Bad PTS')
n=np.load(io.BytesIO(pinned_bytes('/home/opencode/.cache/legion-y70-aa-optical-media-03f0ed4-01/temporal_series_02.npz',series_sha,5000000)),allow_pickle=False)
out={}
for name,start in [('baseline',861),('sham_stock',1534),('return_stock',2171)]:
 a=n['main_'+name+'_normalized_amplitude'];z=f[start:start+60]
 if a.shape!=(60,) or not np.all(np.isfinite(a)):raise ValueError('Bad amplitudes')
 expected={'baseline':(28.7,30.666667),'sham_stock':(51.133333,53.1),'return_stock':(72.366667,74.333333)}[name]
 if not np.allclose(pts[[start,start+59]],expected,rtol=0,atol=0.000001):raise ValueError('Window PTS mismatch')
 size=np.array([int(x['pkt_size']) for x in z]);is_i=np.array([x['pict_type']=='I' for x in z])
 out[name]={'n':60,'amplitude_packet_bytes_pearson_r':float(np.corrcoef(a,size)[0,1]),'p_only_r':float(np.corrcoef(a[~is_i],size[~is_i])[0,1]),'i_n':int(sum(is_i)),'i_mean_amplitude':float(a[is_i].mean()),'p_mean_amplitude':float(a[~is_i].mean())}
with args.output.open('x') as h:json.dump(out,h,indent=2);h.write('\n')
print(json.dumps(out,indent=2))
