"""Finite OFFLINE sensitivity diagnostic, not acquisition admission or PWM Hz.
Only existing reviewed 20x330 strip profiles; no image/ADB/device access.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import numpy as np

Q = 0.019775390625
PROFILE_SHA = 'c674abc2a36f9549651cda4248b917dcc34008cd31dcd062bb8392198037b963'
PRIVATE = Path('/home/opencode/.cache/legion-y70-aa-optical-media-03f0ed4-01')
STAGES = ('baseline', 'sham_stock', 'return_stock')
ROIS = ('left', 'main', 'right')
# Frozen before running comparisons. All are contained in already reviewed strips.
SUBRANGES = {'full':(0,330), 'inset30':(30,300), 'upper220':(0,220), 'lower220':(110,330)}

def check(ok, msg):
    if not ok: raise ValueError(msg)

def residual(p, degree):
    if degree is None: return p.copy()
    b = np.polynomial.legendre.legvander(np.linspace(-1,1,p.shape[-1]), degree)
    return p - (b @ np.linalg.lstsq(b,p.T,rcond=None)[0]).T

def coeff(p, q=Q, degree=2, window='hann'):
    n=p.shape[-1]; w=np.hanning(n) if window=='hann' else np.ones(n)
    return (residual(p,degree)*w) @ np.exp(-2j*np.pi*np.arange(n)*q)*2/w.sum()

def metric(p, **kw):
    return float(np.sqrt(np.mean(np.abs(coeff(p,**kw))**2))/(p.mean()-16))

def stats(x):
    x=np.asarray(x)
    return {'min':float(x.min()),'median':float(np.median(x)),'max':float(x.max()),'std':float(x.std())}

def change(a):
    return [float((v/a[0]-1)*100) for v in a]

def corr(a,b):
    if np.std(a)<1e-12 or np.std(b)<1e-12: return None
    return float(np.corrcoef(a,b)[0,1])

def joint(p, q=Q, broad=False):
    n=p.shape[-1]; y=np.arange(n); poly=np.polynomial.legendre.legvander(np.linspace(-1,1,n),2)
    basis=np.column_stack([poly,np.cos(2*np.pi*q*y),np.sin(2*np.pi*q*y)])
    if broad: basis=np.column_stack([basis,np.cos(2*np.pi*Q/6*y),np.sin(2*np.pi*Q/6*y)])
    beta=np.linalg.lstsq(basis,p.T,rcond=None)[0].T
    fit=beta@basis.T
    return np.hypot(beta[:,3],beta[:,4]), np.arctan2(-beta[:,4],beta[:,3]), p-fit, float(np.linalg.cond(basis))

def envelope_model(p):
    """Descriptive spatial amplitude/phase envelope, not causal identification."""
    n=p.shape[-1];y=np.arange(n);x=np.linspace(-1,1,n)
    poly=np.polynomial.legendre.legvander(x,2)
    basis=np.column_stack([poly,poly*np.cos(2*np.pi*Q*y)[:,None],poly*np.sin(2*np.pi*Q*y)[:,None]])
    beta=np.linalg.lstsq(basis,p.T,rcond=None)[0].T
    fit=beta@basis.T
    return fit,float(np.sqrt(np.mean((p-fit)**2))),float(np.linalg.cond(basis))

def broad_leakage(p, frequencies=(Q/6,)):
    n=p.shape[-1];y=np.arange(n)
    poly=np.polynomial.legendre.legvander(np.linspace(-1,1,n),2)
    basis=np.column_stack([poly,np.cos(2*np.pi*Q*y),np.sin(2*np.pi*Q*y)]+[fn(2*np.pi*f*y) for f in frequencies for fn in (np.cos,np.sin)])
    beta=np.linalg.lstsq(basis,p.T,rcond=None)[0].T
    nuisance=beta[:,:3]@basis[:,:3].T+beta[:,5:]@basis[:,5:].T
    leak=coeff(nuisance)
    return float(np.sqrt(np.mean(abs(leak)**2))/np.sqrt(np.mean(abs(coeff(p))**2))*100)

def peak(p):
    # Existing baseline search band, not a replacement primary estimator.
    f=np.fft.rfftfreq(8192); use=np.flatnonzero((f>=.012)&(f<=.03))
    w=np.hanning(p.shape[-1]); c=np.fft.rfft(residual(p,2)*w,n=8192,axis=-1)*2/w.sum()
    idx=use[np.argmax(abs(c[:,use]),axis=1)]
    return f[idx],np.abs(c[np.arange(len(p)),idx]),int(np.sum((idx==use[0])|(idx==use[-1])))

def analyze(profiles):
    results={}; saved={}; primary={}; sensitivity={}
    for roi in ROIS:
        p3=profiles[roi]; primary[roi]=[metric(p) for p in p3]
        rr={}
        for s,p in zip(STAGES,p3):
            c=coeff(p); a=abs(c); norm=a/(p.mean(axis=1)-16)
            qpk,apk,edge=peak(p)
            ja,jphase,jres,cond=joint(p)
            ba,bphase,bres,bcond=joint(p,broad=True)
            ef,er,ec=envelope_model(p)
            # Constant-amplitude fine-only surrogates using observed phase and q.
            # These isolate estimator leakage under the assumed single-sinusoid model.
            y=np.arange(330)
            phase=np.angle(c)
            fixed_synth=100+np.cos(2*np.pi*Q*y[None,:]+phase[:,None])
            drift_synth=100+np.cos(2*np.pi*qpk[:,None]*y[None,:]+phase[:,None])
            phase_steps=np.angle(c[1:]*c[:-1].conj())
            broad=abs(coeff(p,Q/6))
            rr[s]={'mean_y_per_frame':stats(p.mean(axis=1)), 'normalized_amplitude_per_frame':stats(norm),
                'amplitude_first_last20_change_pct':float((metric(p[-20:])/metric(p[:20])-1)*100),
                'block20_change_vs_full_baseline_pct':[(metric(b)/primary[roi][0]-1)*100 for b in np.array_split(p,3)],
                'coherent_fraction':float(abs(c.mean())**2/np.mean(abs(c)**2)),
                'phase_step_radians':stats(phase_steps),'phase_unwrapped_span_radians':float(np.ptp(np.unwrap(phase))),
                'phase_equivalent_row_span_not_motion':float(np.ptp(np.unwrap(phase))/(2*np.pi*Q)),
                'peak_q_cycles_per_row':stats(qpk),'peak_at_band_edge_frames':edge,
                'peak_vs_fixed_rms_pct':float((np.sqrt(np.mean(apk**2))/np.sqrt(np.mean(a**2))-1)*100),
                'corr_amplitude_mean_y':corr(norm,p.mean(axis=1)), 'corr_amplitude_broad_coefficient':corr(norm,broad),
                'corr_amplitude_peak_q':corr(norm,qpk),
                'joint_fine_normalized_rms':float(np.sqrt(np.mean(ja**2))/(p.mean()-16)),
                'joint_fine_plus_broad_normalized_rms':float(np.sqrt(np.mean(ba**2))/(p.mean()-16)),
                'joint_residual_rms_y':float(np.sqrt(np.mean(jres**2))),
                'joint_plus_broad_residual_rms_y':float(np.sqrt(np.mean(bres**2))),
                'fitted_broad_nuisance_fine_leakage_rms_pct':broad_leakage(p),
                'fitted_harmonic_nuisance_fine_leakage_rms_pct':broad_leakage(p,(2*Q,3*Q)),
                'envelope_model_normalized_rms':metric(ef),
                'envelope_model_residual_rms_y':er, 'envelope_model_condition_number':ec,
                'envelope_model_first_last20_change_pct':float((metric(ef[-20:])/metric(ef[:20])-1)*100),
                'joint_condition_number':cond, 'joint_plus_broad_condition_number':bcond,
                'phase_only_constant_amplitude_measured_range_pct':float(np.ptp(abs(coeff(fixed_synth)))*100),
                'phase_and_q_constant_amplitude_measured_range_pct':float(np.ptp(abs(coeff(drift_synth)))*100),
                'phase_and_q_surrogate_first_last20_change_pct':float((metric(drift_synth[-20:])/metric(drift_synth[:20])-1)*100)}
            for key,value in {'coefficient':c,'normalized_amplitude':norm,'peak_q':qpk,'peak_amplitude':apk,'mean_y':p.mean(axis=1),'joint_phase':jphase}.items(): saved[roi+'_'+s+'_'+key]=value
        rr['envelope_model_change_pct']=change([rr[s]['envelope_model_normalized_rms'] for s in STAGES])
        rr['joint_change_pct']=change([rr[s]['joint_fine_normalized_rms'] for s in STAGES])
        rr['joint_plus_broad_change_pct']=change([rr[s]['joint_fine_plus_broad_normalized_rms'] for s in STAGES])
        results[roi]=rr
        sensitivity[roi]={}
        for name,(start,stop) in SUBRANGES.items():
            sensitivity[roi][name]={}
            for degree in (None,1,2,3):
                for window in ('hann','rectangular'):
                    sensitivity[roi][name][str(degree)+'_'+window]=change([metric(p[:,start:stop],degree=degree,window=window) for p in p3])
    common={}
    for s in STAGES:
        common[s]={}
        for a,b in (('left','main'),('main','right'),('left','right')):
            ca=saved[a+'_'+s+'_coefficient'];cb=saved[b+'_'+s+'_coefficient']
            common[s][a+'_'+b]={'amplitude_correlation':corr(abs(ca),abs(cb)),
                'phase_difference_radians':stats(np.angle(ca*cb.conj())),
                'mean_y_correlation':corr(saved[a+'_'+s+'_mean_y'],saved[b+'_'+s+'_mean_y'])}
    return {'schema':'saved-fine-temporal-diagnostic-v1','acquisition_admitted':False,'qualification_eligible':False,
        'physical_pwm_hz':None,'q_cycles_per_camera_row':Q,'source_profiles_sha256':PROFILE_SHA,
        'primary_change_pct':{r:change(v) for r,v in primary.items()},'per_roi':results,
        'common_variation':common,'exploratory_subranges_relative_rows':SUBRANGES,
        'exploratory_sensitivity_change_pct':sensitivity},saved

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary',type=Path,required=True)
    parser.add_argument('--private-series',type=Path,required=True)
    args=parser.parse_args()
    check(args.private_series.parent.resolve()==PRIVATE,'Series must stay private')
    check(not args.summary.exists() and not args.private_series.exists(),'New outputs only')
    os.umask(0o077)
    raw=(PRIVATE/'final_profiles.npz').read_bytes()
    check(hashlib.sha256(raw).hexdigest()==PROFILE_SHA,'Profile identity mismatch')
    with np.load(io.BytesIO(raw),allow_pickle=False) as npz: profiles={r:npz['profiles_'+r] for r in ROIS}
    for p in profiles.values(): check(p.shape==(3,60,330) and np.isfinite(p).all(),'Invalid profiles')
    result,series=analyze(profiles)
    with args.private_series.open('xb') as f: np.savez_compressed(f,**series)
    with args.summary.open('x') as f: json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'primary_change_pct':result['primary_change_pct'],'summary_written':True}))

if __name__=='__main__':main()
