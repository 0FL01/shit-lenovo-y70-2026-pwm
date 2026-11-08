#!/usr/bin/env python3
"""Offline audit of supplied ILI97701A artifacts. Never contacts a device."""
from pathlib import Path
import json, sys
if len(sys.argv) != 2:
    raise SystemExit('Usage: python register_analysis.py ARCHIVE_ROOT')
root = Path(sys.argv[1])
dt = root / 'artifacts/device_tree/selected_boe_v4'
def parse(b):
    packets=[]; off=0; page=None
    while off < len(b):
        assert off + 7 <= len(b)
        n=int.from_bytes(b[off+5:off+7], 'big')
        payload=b[off+7:off+7+n]
        assert len(payload)==n and n>0
        if payload[:3]==bytes.fromhex('ff 5a a5'):
            assert n==4
            page=payload[3]
        packets.append({'index':len(packets),'offset':off,'page':page,'payload':payload.hex(' '),'header':b[off:off+7].hex(' ')})
        off += 7+n
    return packets
stock = (dt / 'qcom,mdss-dsi-dc-off-command').read_bytes()
on = (dt / 'qcom,mdss-dsi-dc-on-command').read_bytes()
p0,p1 = parse(stock),parse(on)
assert len(stock)==len(on)==875 and len(p0)==len(p1)==75
out={'scope':'offline only; no decoded PWM-frequency register or tested high-frequency profile',
 'dc': {'bytes':875,'packets':75,'changed_bytes':sum(a!=b for a,b in zip(stock,on)),
        'changed_packets':sum(a['payload']!=b['payload'] for a,b in zip(p0,p1))},'selector_variants':[], 'timing_arrays':[], 'dumps':[], 'short_stock_reads':[]}
for name in ['a9_only','9d_only']:
 b=(root/f'artifacts/dsi_selector_split_20261107/{name}.bin').read_bytes()
 diffs=[{'offset':i,'before':a,'after':c} for i,(a,c) in enumerate(zip(stock,b)) if a!=c]
 assert len(b)==len(stock) and len(diffs)==1
 out['selector_variants'].append({'name':name,'diff':diffs})
for t in sorted((dt/'qcom,mdss-dsi-display-timings').glob('timing@*')):
 packets=parse((t/'qcom,mdss-dsi-timing-switch-command').read_bytes())
 out['timing_arrays'].append({'name':t.name, 'metadata_refresh_hz':int.from_bytes((t/'qcom,mdss-dsi-panel-framerate').read_bytes(),'big'),
   'packet_count':len(packets), 'selected_writes':[p for p in packets if (p['page']==0x2d and bytes.fromhex(p['payload'])[0] in (0x83,0xf2)) or (p['page']==0x4f and bytes.fromhex(p['payload'])[0] in (0x81,0x88,0x8a,0x8b))]})
dr = root/'artifacts/ddic_regdump_20261107'
names=['s1_dbv3584_120','s2_dbv3646_120','s3_dbv3584_144','s4_dbv3584_60']
rawtables=[]
for name in names:
 d=json.loads((dr/name/'registers.json').read_text()); rawtables.append(d)
 rr=json.loads((dr/name/'run.json').read_text())
 pages=sorted({k.split(':')[0] for k in d})
 aliases=[f'{a:02X}' for a in range(128) if len({d[f'{page}:{a:02X}'] for page in pages})==1]
 out['dumps'].append({'name':name,'opcodes_requested_per_snapshot':len(d),'pages':pages,'all_page_identical_low_opcodes':len(aliases),
  'pass_mismatch_opcodes':[m['reg'] for m in rr['pass_mismatches']],
  'selected_responses':{k:d[k] for k in ['00:04','00:52','00:58','00:60','23:A9','23:AA','24:80','24:81','24:9D','24:9E','2D:83','2D:F2','4F:81','4F:9D','4F:9E']}})
out['changed_high_opcodes_across_all_four']={page:[k for k,v in rawtables[0].items() if k.startswith(page+':') and int(k[3:],16)>=128 and any(d[k]!=v for d in rawtables[1:])] for page in ['23','24','4F']}
for name in ['stock_latch.json','stock_timing_history.json']:
 r=json.loads((dr/name).read_text())
 out['short_stock_reads'].append({'source':name,'phases':[{'label':p.get('label',p.get('index')),'dc':p['dc'],'registers':p['registers']} for p in r['phases']]})
out['probe_responses']=json.loads((dr/'s0_probe/registers.json').read_text())
print(json.dumps(out,ensure_ascii=False,indent=2))
