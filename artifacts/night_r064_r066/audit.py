"""Scoped offline replay. No Git, device or image access required."""
import importlib.util
import json
import math
import struct
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
ART = HERE.parent
sys.path.insert(0, str(ART.parent / '06-tools'))
from audit_pwm_archive import parse_packets


def need(ok, why):
    if not ok:
        raise ValueError(why)


def read(name):
    return json.loads((ART / name).read_text())


def f32(x):
    return struct.unpack('!f', struct.pack('!f', float(x)))[0]


def half_up(x):
    return math.floor(x + 0.5)


def spline(x, segment):
    (a, y, dy), (b, z, dz) = segment
    need(a <= x <= b and a < b, 'not on archived segment')
    t = (x-a)/(b-a)
    return ((1+2*t)*(1-t)**2*y + t*(1-t)**2*(b-a)*dy +
            t*t*(3-2*t)*z + t*t*(t-1)*(b-a)*dz)


def calibration(p, repeats):
    rows, direct = p['android_calibration'], p['native_direct']
    need([n for _, _, _, n in rows] == [2626,2784,2632,2633,2634,2631], 'calibration order')
    need([r[0] for r in direct] == [6879,3600,3601,3602,3601,3600,6879]
         and all(r[1:] == ['0.40987244',105,16180] for r in direct), 'direct controls')
    codes = {}; mismatches = []
    for cmd, saved, android, n in rows:
        x = f32(cmd)
        need(x == f32(saved), 'binary32 drift')
        need(half_up(414+15800*x) == n and half_up(1+254*x) == android, 'local fit differs')
        predicted = half_up(spline(x,p['spline_segment'])*direct[0][3])
        if predicted != n:
            mismatches.append([cmd,predicted,n])
        codes[n] = [cmd,android]
    phases = repeats['phase_summaries']
    need([s['phase'] for s in phases] == list(range(14)) and repeats['issued_phases']==15
         and all(s['dbv'] in range(2631,2635) and s['float_command']==codes[s['dbv']][0]
                 for s in phases), 'R7 projection')
    return {'int_37_dbv': sorted(k for k,v in codes.items() if v[1] == 37),
            'binary32_matches':len(rows),'local_affine_fit_rows':len(rows),
            'normalized_spline_times_max_nearest_disagreements':mismatches,
            'r7_repeated_complete_phases':len(phases), 'direct_native_series':[r[0] for r in direct]}


def tables():
    s = importlib.util.spec_from_file_location('band_audit',ART/'dbv_band_map_20261118/audit.py')
    band = importlib.util.module_from_spec(s); s.loader.exec_module(band)
    d = band.run()
    need(d['passes']==8 and d['4F_pairs']==[2632,2633] and
         d['adjacent_pairs'][:2]==[[3600,3601],[2632,2633]],'saved read prefixes')
    root = ART/'device_tree/selected_boe_v4'
    target = [2632,2633,3600,3601]
    seq_hits = {n:0 for n in target}
    marked = {}; scanned=0; total=0
    for path in sorted(root.rglob('*-command')):
        if path.name=='qcom,mdss-dsi-te-dcs-command':
            need(path.read_bytes() == bytes.fromhex('00000001'),'TE scalar')
            continue
        scanned+=1
        for packet in parse_packets(path.read_bytes()):
            total+=1
            if packet['is_page_selector']:
                continue
            data=bytes.fromhex(packet['data'])
            for n in target:
                seq_hits[n]+=int(n.to_bytes(2,'big') in data)
            page, op=packet['page'],packet['opcode']
            if ((page==0x24 and op in (0xd2,0xd3)) or (page==0x4f and 0xa2<=op<=0xa5)
                    or (page==0x23 and op in (0xa9,0xaa))):
                marked.setdefault(path.relative_to(root).as_posix(),[]).append((page,op,data.hex()))
    need(scanned==52 and total==1101,'incomplete DT corpus')
    need(marked=={f'qcom,mdss-dsi-dc-{mode}-command':[(35,169,v),(35,170,'11')]
                  for mode,v in [('off','0e'),('on','8e')]},'explicit field writes')
    return {'archived_passes':d['passes'], '24_D2':d['24_D2'],'24_D3':d['24_D3'],
            '4F_pairs':d['4F_pairs'],'command_arrays':scanned,'packets':total,
            'literal_BE16_hits_in_single_data_payload':seq_hits,'explicit_field_hits':marked}


def als(xml):
    cfg = {}
    for rec in xml.findall(".//config[@type='default']/configuration"):
        k = rec.findtext('name')
        need(k not in cfg,'ambiguous default config key')
        cfg[k] = rec.findtext('value')
    need(cfg.get('pwmToDcDbv')=='3601' and cfg.get('brightnessRange')=='14056'
         and 'backLightCorrespondingArray' not in cfg, 'ALS configuration')
    return [[dbv,dc, dc if dbv<3601 else 0] for dbv in (2632,2633,3600,3601)
            for dc in (0,1)]


def dispatch(j):
    phases=j['phases']; packets=j['native_brightness_packets']
    expect=[3600,3601]*2
    need(len(phases)==len(packets)==4 and j['levels']==expect and j['native_return_counts']=={'0':4}
         and j['probe_misses']==0 and j['probe_hits']==4,'native counts')
    for i,(phase,p,n) in enumerate(zip(phases,packets,expect),1):
        need(phase['index']==p['phase']==i and phase['requested_dbv']==phase['held_sysfs_value']==p['dbv']==n
             and p['transport']=='hs' and p['page_context']==0 and
             bytes.fromhex(p['payload'])==b'\x51'+n.to_bytes(2,'big'), 'native dispatch mismatch')
    return expect


def run():
    profile=read('post_ota_display_observation.json')['properties']['ro.build.display.id']['stdout']
    need(profile=='W3WWS36.65-64-4-1','target build')
    return {'target_build':profile, 'tables':tables(), 'effective_ALS_if_branch_reached':als(
        ET.parse(ART/'current_display_path/als/als_comp_config.xml')),
        'actual_native_setter_dispatch':dispatch(read('exact_dbv_dispatch_20261106.json')),
        'calibration':calibration(json.loads((HERE/'projection.json').read_text()),
                                  read('stock_dbv_association_r7_20261118/outcome.json')),
        'actual_ALS_branch_trace':None,'actual_DDIC_interval_branch_trace':None,
        'optical_hz':None}


if __name__=='__main__':
    print(json.dumps(run(),indent=2))
