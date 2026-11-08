#!/usr/bin/env python3
"""Independent offline adversarial checks; no subprocess/network/device calls.

Primary bytes are parsed through struct; rank uses exact Walsh row
orthogonality; optical samples use Gauss-Legendre exposure integration.
No imports of Agent A/C or root audit implementation.
"""
import argparse
import cmath
import itertools
import json
import math
import struct
from datetime import datetime
from pathlib import Path


def packets(blob):
    pos, page, out = 0, None, []
    while pos < len(blob):
        datatype, last, vc, ack, wait, length = struct.unpack_from('>5BH', blob, pos)
        assert length > 0 and pos + 7 + length <= len(blob)
        payload = blob[pos + 7:pos + 7 + length]
        if payload[:3] == b'\xff\x5a\xa5' and len(payload) == 4:
            page = payload[3]
        out.append(dict(start=pos, header=[datatype,last,vc,ack,wait,length],
                        page=page, opcode=payload[0], payload=payload.hex()))
        pos += 7 + length
    assert pos == len(blob)
    return out


def gauss_legendre(n):
    """Newton roots and weights of Legendre P_n; generated independently."""
    def eval_pair(x):
        previous, current = 1.0, x
        if n == 1:
            return current, previous
        for j in range(2, n+1):
            previous, current = current, ((2*j-1)*x*current-(j-1)*previous)/j
        return current, previous
    result = []
    for k in range(1, n+1):
        x = math.cos(math.pi*(k-0.25)/(n+0.5))
        for _ in range(30):
            p, pm1 = eval_pair(x)
            dp = n*(x*p-pm1)/(x*x-1)
            step = p/dp
            x -= step
            if abs(step) < 1e-15:
                break
        p, pm1 = eval_pair(x)
        dp = n*(x*p-pm1)/(x*x-1)
        result.append((x, 2/((1-x*x)*dp*dp)))
    assert abs(sum(w for _,w in result)-2) < 1e-14
    return result


def run(root):
    panel = 'artifacts/device_tree/selected_boe_v4/'
    paths = {
        '000':panel+'qcom,mdss-dsi-dc-off-command',
        '100':'artifacts/dsi_selector_split_20261107/a9_only.bin',
        '010':'artifacts/dsi_selector_split_20261107/9d_only.bin',
        '110':'artifacts/dsi_block_trials_20261106/thresholds.bin',
        '001':'artifacts/dsi_coupled_on_20261107/on_keep_pwm_selectors.bin',
        '111':panel+'qcom,mdss-dsi-dc-on-command',
        '011':'artifacts/dsi_coupled_9d_20261107/on_keep_a9_off.bin',
    }
    blobs = {k:(root/p).read_bytes() for k,p in paths.items()}
    parsed = {k:packets(b) for k,b in blobs.items()}
    off, on = blobs['000'], blobs['111']
    a_packet = next(p for p in parsed['000'] if (p['page'],p['opcode']) == (0x23,0xA9))
    d_packet = next(p for p in parsed['000'] if (p['page'],p['opcode']) == (0x24,0x9D))
    a_pos, d_pos = a_packet['start']+8, d_packet['start']+8
    diff = {i for i in range(len(off)) if off[i] != on[i]}
    c_diff = diff-{a_pos,d_pos}
    assert (a_pos,d_pos,len(diff),len(c_diff)) == (68,97,85,83)
    comparisons = []
    for key, blob in blobs.items():
        assert len(blob) == 875 and len(parsed[key]) == 75
        assert [p['header'] for p in parsed[key]] == [p['header'] for p in parsed['000']]
        desired = set()
        for bit, positions in zip(key, ({a_pos},{d_pos},c_diff)):
            if bit == '1':
                desired |= positions
        actual = {i for i in range(len(off)) if off[i] != blob[i]}
        assert actual == desired
        assert all(blob[i] == on[i] for i in desired)
        changed_packets = sum(p['payload'] != q['payload'] for p,q in zip(parsed[key],parsed['000']))
        comparisons.append(dict(vertex=key,path=paths[key],bytes=len(blob),packets=len(parsed[key]),
                                changed_bytes=len(actual),changed_packets=changed_packets))

    corpus = []
    for path in sorted((root/panel).rglob('*')):
        if path.is_file() and 'command' in path.name and not path.name.endswith('-state'):
            try:
                parsed_array = packets(path.read_bytes())
            except (AssertionError, struct.error, IndexError):
                continue
            if parsed_array:
                corpus.append((str(path.relative_to(root)),parsed_array))
    assert len(corpus)==52 and sum(len(ps) for _,ps in corpus)==1101
    queried = [(0x4f,k) for k in (0x80,0x81,0xc0,0xc1,0xc8,0xc9,0xd0,0xd1,0xd8,0xd9)]+[(7,0xec),(0x23,0xc1)]
    writers = {f'{pg:02X}:{op:02X}':[dict(path=path,packet=p) for path,ps in corpus for p in ps
                                  if (p['page'],p['opcode'])==(pg,op)] for pg,op in queried}
    assert len(writers['4F:81'])==4 and sum(len(v) for k,v in writers.items() if k!='4F:81')==0

    # Walsh columns are sign-coded full-factorial monomials. Their invertible
    # affine recoding into 0/1 monomials preserves rank. Six orthogonal rows
    # with norm^2 8 are a rank-6 certificate, without Gaussian elimination.
    known = {'000':0,'100':1,'010':0,'110':1,'001':0,'111':1}
    vertices = list(itertools.product((0,1),repeat=3))
    walsh = [[(-1)**sum(a*b for a,b in zip(v,s)) for s in vertices]
             for v in (tuple(map(int,k)) for k in known)]
    gram = [[sum(x*y for x,y in zip(r,s)) for s in walsh] for r in walsh]
    assert gram == [[8 if i==j else 0 for j in range(6)] for i in range(6)]
    completion_checks = []
    for u,v in itertools.product((0,1),repeat=2):
        truth = {tuple(map(int,k)):val for k,val in known.items()}
        truth[(0,1,1)],truth[(1,0,1)] = u,v
        # Boolean subset Moebius inversion, independent of A's supplied formula.
        coeff = {}
        for index in vertices:
            coeff[index] = sum((-1)**(sum(index)-sum(sub))*truth[sub] for sub in vertices
                               if all(a<=b for a,b in zip(sub,index)))
        for a,d,c in vertices:
            calculated = sum(value*(a if p else 1)*(d if q else 1)*(c if r else 1)
                             for (p,q,r),value in coeff.items())
            assert calculated == truth[(a,d,c)]
            assert calculated == a+(v-1)*a*c+u*d*c+(1-v-u)*a*d*c
        completion_checks.append(dict(u=u,v=v,coefficients={''.join(map(str,k)):val for k,val in coeff.items()}))

    rp = 'artifacts/dsi_stock_on_control_20261106/with_redraw/run.json'
    rr = json.loads((root/rp).read_text())
    stages = {s['label']:s for s in rr['stages']}
    on_stage, redraw = stages['native_on'],stages['native_on_redraw']
    t0 = datetime.fromisoformat(on_stage['same_dbv_replay']['at_utc'])
    def elapsed(t):
        return (datetime.fromisoformat(t)-t0).total_seconds()
    timing = dict(source=rp,on_verified=on_stage['transmission_verified_at_utc'],
                  replay=on_stage['same_dbv_replay']['at_utc'],
                  before_hold_start=elapsed(on_stage['hold_start_utc']),
                  before_hold_end=elapsed(on_stage['hold_end_utc']),
                  after_hold_start=elapsed(redraw['hold_start_utc']),
                  after_hold_end=elapsed(redraw['hold_end_utc']),
                  new_table=redraw['new_table_sent'],logged_control_writes=redraw['writes_during_redraw_and_hold'])
    assert timing['before_hold_end']==7.357898 and timing['after_hold_start']==14.796735
    assert timing['new_table'] is False and timing['logged_control_writes']==[]

    # Read C's recorded model PARAMETERS only, not C's implementation/output
    # samples; directly quadrature-integrate E at the 37,500 grid points.
    cp = 'artifacts/horizon_r3_20261108/agent_c_identifiability.json'
    cr = json.loads((root/cp).read_text())
    ar, ma = cr['archive_values_used_only_to_set_an_illustrative_grid'],cr['additional_model_assumptions']
    tau, T, fps = ma['hypothetical_known_seconds_per_output_row'],ar['exposure_seconds'],ma['uniform_sensor_fps']
    frames, rows = ar['frames'],ar['rows']
    quadrature = gauss_legendre(8)
    def exposure_average(m,n,y,exposure):
        f,A,beta,phi = (m[k] for k in ('local_temporal_frequency_hz_hypothetical',
                        'optical_amplitude','optical_spatial_phase_cycles_per_output_row','phase_offset_radians'))
        # Time-domain light, positive baseline=1. No sinc/analytic integral here.
        base_phase = 2*math.pi*(f*(n/fps+tau*y)+beta*y)+phi
        return 1+sum(0.5*w*A*math.cos(base_phase+2*math.pi*f*exposure*(x+1)/2)
                     for x,w in quadrature)
    models = cr['frequency_exchange_models']
    max_error = 0.0
    for n in range(frames):
        for y in range(rows):
            vals = [exposure_average(m,n,y,T) for m in models]
            max_error = max(max_error,max(vals)-min(vals))
    assert max_error < 1e-10
    minimum_bound = min(1-abs(m['optical_amplitude']) for m in models)
    assert minimum_bound>0
    # Hold the SAME emitters fixed; at a different exposure the observational
    # equivalence should fail. This tests the important scope caveat, not target.
    other_T=4*T
    second_exposure_max = max(abs(exposure_average(models[0],n,y,other_T)-exposure_average(models[2],n,y,other_T))
                              for n in range(frames) for y in range(rows))
    assert second_exposure_max>0.05
    # Broad-term check uses a complex quadrature response, not sinc/phase
    # formulas from C. Solve K(f)*C=B*exp(i*phi0) for emission coefficient C.
    broad_q=1/ar['reference_period_rows']/3
    broad_models=[]
    for frequency in (models[0]['local_temporal_frequency_hz_hypothetical'],
                      models[0]['local_temporal_frequency_hz_hypothetical']-480):
        response=sum(w/2*cmath.exp(2j*math.pi*frequency*T*(x+1)/2) for x,w in quadrature)
        coefficient=0.1*cmath.exp(0.37j)/response
        broad_models.append(dict(local_temporal_frequency_hz_hypothetical=frequency,
                                 optical_amplitude=abs(coefficient),phase_offset_radians=cmath.phase(coefficient),
                                 optical_spatial_phase_cycles_per_output_row=broad_q-frequency*tau))
    broad_error=max(abs(exposure_average(broad_models[0],n,y,T)-exposure_average(broad_models[1],n,y,T))
                    for n in range(frames) for y in range(rows))
    broad_positive=min(1-abs(models[0]['optical_amplitude'])-abs(b['optical_amplitude']) for b in broad_models)
    assert broad_error<1e-10 and broad_positive>0
    return dict(scope='Independent offline verification. No new physical measurement.',
                methods=dict(packet_parser='struct.unpack_from >5BH',
                             rank='exact integer orthogonality of six Walsh design rows',
                             interpolants='Boolean subset Moebius inversion',
                             optics='eight-node Gauss-Legendre integration generated through Legendre root iteration'),
                primary_program_binding=comparisons,A_offset=a_pos,D_offset=d_pos,C_bytes=len(c_diff),C_packets=32,
                selected_command_corpus=dict(arrays=len(corpus),packets=sum(len(ps) for _,ps in corpus),writers=writers),
                target_esync_gate=dict(property_count=sum(p.is_file() for p in (root/panel).rglob('*')),
                                      panel_type=(root/panel/'qcom,mdss-dsi-panel-type').read_bytes().hex(' '),
                                      named_properties=[str(p.relative_to(root/panel)) for p in (root/panel).rglob('*')
                                                        if p.is_file() and ('esync' in p.name.lower() or 'em-pulse-switch' in p.name.lower())]),
                qualitative_design=dict(rank=6,columns=8,walsh_gram_matrix=gram,completions=completion_checks,
                                        limitation='Historical state exchangeability is assumed, not proven. ABA measures whole profile.'),
                redraw_timing=timing,
                optics=dict(parameter_source=cp,grids=3,samples_per_grid=frames*rows,quadrature_points_per_sample=8,
                            max_abs_equal_exposure_difference=max_error,positive_irradiance_lower_bound=minimum_bound,
                            fixed_emitters_second_exposure_seconds=other_T,
                            second_exposure_max_pair_difference=second_exposure_max,
                            broad_quadrature_max_abs_difference=broad_error,broad_positive_irradiance_lower_bound=broad_positive,
                            limited_claim='Equal sampled image at one granted exposure/fps/geometry does not uniquely identify f.',
                            exclusions=['No fit to archived movie or complete exposure sweep.','No physically implementable DDIC waveform is established.',
                                        'Sinusoidal local emission is a modulation counterexample; not a discovered rectangular PWM mode.']))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    result=run(Path(__file__).resolve().parents[2])
    with args.output.open('x',encoding='utf-8') as handle:
        json.dump(result,handle,ensure_ascii=False,indent=2,allow_nan=False)
        handle.write('\n')
