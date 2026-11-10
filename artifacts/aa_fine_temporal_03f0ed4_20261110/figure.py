"""Sanitized SVG from the same hash-bound saved profiles, no screenshots."""
import hashlib
import io
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import analyze as a

raw=(a.PRIVATE/'final_profiles.npz').read_bytes()
a.check(hashlib.sha256(raw).hexdigest()==a.PROFILE_SHA,'Profile identity mismatch')
with np.load(io.BytesIO(raw),allow_pickle=False) as data:
    profiles={r:data['profiles_'+r] for r in a.ROIS}
parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="480" viewBox="0 0 1100 480">',
'<rect width="1100" height="480" fill="white"/>',
'<g font-family="sans-serif" fill="#17212b"><text x="48" y="32" font-size="21">Saved stock: per-frame fine amplitude</text>',
'<text x="48" y="57" font-size="13">Encoded-Y coefficient / (frame mean Y − 16); q = 0.019775390625 cycles/camera-row, Hann, degree 2</text>']
colors={'left':'#0072B2','main':'#D55E00','right':'#009E73'}
ylo,yhi=.21,.32
for si,stage in enumerate(a.STAGES):
    x0=70+350*si;y0=105;w=290;h=260
    fx=lambda x:x0+w*x/59
    fy=lambda y:y0+h*(yhi-y)/(yhi-ylo)
    parts.append(f'<text x="{x0}" y="88" font-size="17">{stage.replace("_"," ")}</text>')
    for tick in (.22,.24,.26,.28,.30,.32):
        yy=fy(tick);parts.append(f'<path d="M{x0},{yy}h{w}" stroke="#e2e5e8"/>')
        if si==0:parts.append(f'<text x="{x0-9}" y="{yy+4}" text-anchor="end" font-size="12">{tick:.2f}</text>')
    for cut in (19.5,39.5):parts.append(f'<path d="M{fx(cut)},{y0}v{h}" stroke="#8a9299" stroke-dasharray="4 4"/>')
    for tick in (0,19,39,59):parts.append(f'<text x="{fx(tick)}" y="{y0+h+20}" text-anchor="middle" font-size="12">{tick}</text>')
    for roi in a.ROIS:
        p=profiles[roi][si];v=abs(a.coeff(p))/(p.mean(axis=1)-16)
        a.check(np.all((v>=ylo)&(v<=yhi)),'Figure would clip data')
        points=' '.join(f'{fx(i):.3f},{fy(z):.3f}' for i,z in enumerate(v))
        parts.append(f'<polyline points="{points}" fill="none" stroke="{colors[roi]}" stroke-width="1.8"/>')
    parts.append(f'<text x="{x0+w/2}" y="410" text-anchor="middle" font-size="12">Frame offset in fixed 60-frame window</text>')
for i,r in enumerate(a.ROIS):
    xx=70+110*i;parts.append(f'<path d="M{xx},440h25" stroke="{colors[r]}" stroke-width="3"/><text x="{xx+32}" y="444" font-size="13">{r}</text>')
parts.append('<text x="430" y="444" font-size="12">Dashed lines: 20-frame blocks. Not independent trials; not physical Hz.</text></g></svg>')
svg='\n'.join(parts)+'\n';ET.fromstring(svg)
out=Path(__file__).with_name('fine_temporal.svg')
with out.open('x') as f:f.write(svg)
print('SVG validated; 9 complete curves, no clipping')
