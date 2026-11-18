"""Offline diagnostic witness. Not full-frame registration or acquisition gate."""
import argparse
from pathlib import Path
import sys,json
import numpy as np
from PIL import Image
ARTIFACTS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ARTIFACTS/'stock_dbv_2632_20261118'))
sys.path.insert(0,str(ARTIFACTS/'scope_exterior_registration_20261118'))
import analysis_geometry as geom
import future,legends
NAMES=('top-right/a','top-right/b','right-upper/a','right-upper/b')
def witness(im):
 s=geom.score(im)
 return dict(anchors={k:s['anchors'][k] for k in NAMES},failures=[f for f in s['failures'] if f.split(':')[0] in NAMES])
def replay(root,template):
 names=['R%02d'%i for i in range(3)]+['S%02d'%i for i in range(51)]
 frames=[dict(ordinal=n,**witness(geom.load(root/(n+'.png')))) for n in names]
 im=future.reference(template)
 h=np.eye(3)+4e-5*np.outer(np.array([140.,938.,1.]),np.array([0.,1.,-1316.]))
 inv=np.linalg.inv(h)
 warped=np.asarray(Image.fromarray(im).transform((1080,2392),Image.Transform.PERSPECTIVE,(inv/inv[2,2]).ravel()[:8],resample=Image.Resampling.BILINEAR))
 xy=np.array([554.,963.,1.]);q=h@xy;v=future.checks(im,warped)
 return dict(status='diagnostic_not_full_registration',frame_count=len(frames),corner_absolute_pass_count=sum(not v['failures'] for v in frames),frames=frames,warp=dict(corner_shift=(q[:2]/q[2]-xy[:2]).tolist(),corner=witness(warped),badges=v['geometry']['pass_exterior'],headroom=v['pass_original_upper_headroom'],legends=legends.checks(im,warped)['pass_similarity']),limits=['Old four-zone diagnostic; no new threshold or ROI.','Weak blue contrast rejects samples even at unchanged DBV.','One projective counterexample does not certify all deformations.','No pixel-registered A/B or physical metrology.'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('template',type=Path);a=p.parse_args();print(json.dumps(replay(a.root,a.template),indent=2,allow_nan=False))
