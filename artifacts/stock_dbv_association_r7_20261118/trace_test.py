"""Independent integer-mask check of all 14 primary rows, plus incomplete gate."""
import csv,itertools,importlib.util,sys
from pathlib import Path
import numpy as np
from PIL import Image
from trace_summarize import summarize
src=Path(sys.argv[1]);here=Path(__file__).resolve().parent
try:summarize(here/'trace_ordinals/ordinal_pairs.csv')
except ValueError as e:
 if '17 complete' not in str(e):raise
else:raise RuntimeError('full criterion accepted partial')
d={}
for i in range(14):
 d[f'P{i:02}']=[]
 for j in range(3):
  a=np.asarray(Image.open(src/f'P{i:02}_s{j}.png').convert('RGB'),dtype=np.int16)[1150:1240,112:540]
  counts=np.sort((a[:,:,0]+a[:,:,1]-2*a[:,:,2]>36).sum(axis=0))
  d[f'P{i:02}'].append(counts)
n=0
for r in csv.DictReader((here/'trace_ordinals/ordinal_pairs.csv').open()):
 if (r['threshold'],r['dx'],r['dy'])!=('18','0','0'):continue
 a,b=r['a'],r['b'];ps=itertools.combinations(d[a],2) if a==b else itertools.product(d[a],d[b]);v=[np.abs(x-y).sum()/(428*90) for x,y in ps]
 want=[float(r[k]) for k in ('Dmin','Dmed','Dmax')]
 if not np.allclose(np.quantile(v,[0,.5,1]),want,atol=0.00000051,rtol=0):raise RuntimeError('primary mismatch')
 n+=1
if n!=105:raise RuntimeError('row count')
print('PASS: all 105 primary min/median/max rows via integer masks; full17 rejects incomplete')
