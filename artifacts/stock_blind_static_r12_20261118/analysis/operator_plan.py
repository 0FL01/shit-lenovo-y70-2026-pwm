"""Operator only. Generate ONCE before target action; never give key/HTML to decoder until predictions frozen. No device access."""
from pathlib import Path
import sys,random,secrets,json,hashlib,os
os.umask(0o077)
d=Path(sys.argv[1]);d.mkdir(exist_ok=False,parents=True)
rng=random.SystemRandom()
def code():
 return [[1 if i in s else -1 for i in range(8)] for s in [set(rng.sample(range(8),4)) for _ in range(8)]]
C=code();D=code();o=['C','c','D','d','U'];rng.shuffle(o)
while o[-1]=='C':rng.shuffle(o)
o+=['C'];k={'salt':secrets.token_hex(16),'C':C,'D':D,'order':o}
b=(json.dumps(k,sort_keys=True)+'\n').encode();(d/'key.json').write_bytes(b)
(d/'commit.sha256').write_text(hashlib.sha256(b).hexdigest()+'\n')
for p,slug in enumerate(o,1):
 bg='#787878' if slug=='U' else '#383838'
 rs=[]
 if slug!='U':
  code_=k[slug.upper()]
  for y in range(8):
   for x in range(8):
    if code_[y][x]*(1 if slug.isupper() else -1)>0:rs.append(f'<rect x="{x*60}" y="{y*60}" width="60" height="60" fill="#b8b8b8"/>')
 h='<html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>*{margin:0;padding:0;}html,body,svg{width:100%;height:100%;display:block;overflow:hidden;}</style></head><body><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 2880" preserveAspectRatio="none"><defs><pattern id="c" patternUnits="userSpaceOnUse" x="0" y="0" width="480" height="480"><rect width="480" height="480" fill="'+bg+'"/>'+''.join(rs)+'</pattern></defs><rect width="1440" height="2880" fill="url(#c)"/></svg></body></html>'
 (d/f'p{p:02d}.html').write_text(h)
print((d/'commit.sha256').read_text().strip())
