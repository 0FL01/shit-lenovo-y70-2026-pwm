"""Analyse native decoded camera-row profiles; no Hz or duty inference."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SHA = '4727d6aced276496795896f87d4b92b0a6befe37c12780145db9fde070f1b191'
STARTS = (135, 375, 615)
H = np.arange(1, 11)
R = 22 / 3
U = np.arange(500)
Z = (U - 249.5) / 249.5
W = np.hanning(500)


def validate(a):
    if a.shape != (3, 90, 3, 500) or a.dtype != np.uint16 or a.max() > 5100:
        raise ValueError("Invalid strip-sum tensor")
    return a


def extract(path):
    with path.open('rb') as f:
        if hashlib.file_digest(f, 'sha256').hexdigest() != SHA:
            raise ValueError("Not the indexed MP4: SHA256 mismatch")
    cmd = ['ffmpeg','-loglevel','error','-nostdin','-noautorotate','-i',str(path),
           '-vf','extractplanes=y,crop=60:500:540:190','-fps_mode','passthrough',
           '-f','rawvideo','-pix_fmt','gray','pipe:1']
    a = np.zeros((3,90,3,500), np.uint16)
    index = {s+j:(i,j) for i,s in enumerate(STARTS) for j in range(90)}
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as proc:
        n = 0
        while data := proc.stdout.read(60*500):
            if len(data) != 60*500:
                raise ValueError("Truncated frame")
            if n in index:
                pix = np.frombuffer(data, np.uint8).reshape(500,3,20)
                a[index[n]] = pix.sum(axis=2, dtype=np.uint16).T
            n += 1
        if proc.wait() or n != 815:
            raise ValueError("Incomplete archive decode")
    return validate(a)


def design(p, harmonics):
    cols = [np.ones(500), Z, Z**2]
    for k in harmonics:
        t = 2*np.pi*k*U/p
        cols.extend([np.cos(t), np.sin(t)])
    return np.stack(cols, axis=1)


def projection(m):
    return (np.linalg.pinv(m * np.sqrt(W[:,None])) * np.sqrt(W)).T


def coef(d,p,hh):
    a = d @ projection(design(p,hh))
    return a[:,3::2] - 1j*a[:,4::2]


def best(d):
    grid = np.arange(91.5,95.01,.05)
    scores = []
    for p in grid:
        m = design(p,H)
        e = d - (d@projection(m))@m.T
        scores.append(np.median(np.mean(W*e**2,axis=1)))
    return grid[np.argmin(scores)]


def rnd(v):
    return np.around(v,4).tolist()


def stats(d,p,ratio=R):
    c = coef(d,p,[*H,ratio])
    a = abs(c)
    v = [c[:,k-1]*c[:,0].conj()**k for k in (2,3,4)]
    return dict(A1=rnd(np.median(a[:,0])), Ah_over_A1=rnd(np.median(a[:,:10]/a[:,:1],axis=0)),
                cos_phase_2_3_4=rnd([np.median((b/abs(b)).real) for b in v]),
                frac_amp=rnd(np.median(a[:,-1])), frac_over_A1=rnd(np.median(a[:,-1]/a[:,0])))


def synthetic(p):
    phase = 2*np.pi*U/p
    rect, sigmoid, gaussian = {}, {}, {}
    for duty in [.2,.8]:
        d = duty + sum(2*np.sin(np.pi*k*duty)/(np.pi*k)*np.cos(k*phase) for k in H)
        rect[str(duty)] = stats(d[None,:],p)
    for dc in [-13,13]:
        d = 100/(1+np.exp(-(dc+10*np.cos(phase))))
        sigmoid[str(dc)] = stats(d[None,:],p)
    for sigma in [0,1,3,6]:
        gains = np.exp(-2*np.pi**2*(np.array([1,R])*sigma/p)**2)
        gaussian[str(sigma)] = rnd([*gains,gains[1]/gains[0]])
    return dict(rectangular=rect,sigmoid=sigmoid,gaussian_gains_base_test_relative=gaussian,
                boxcar_width_gain_base_gain_test=rnd([p/R,np.sinc(1/R),0]))


def injections(d,p):
    f = projection(design(p,[*H,R]))
    def amp(y):
        c = y@f
        return np.hypot(c[:,3],c[:,4]), np.hypot(c[:,-2],c[:,-1])
    a1, ax = amp(d)
    q95 = np.quantile(ax/a1,.95)
    rng = np.random.default_rng(20261118)
    out = {}
    for frac in [0,.02,.05,.10,.20]:
        hit, med = [], []
        for _ in range(32):
            phi = rng.uniform(0,2*np.pi,len(d))
            inj = frac*a1[:,None]*np.cos(2*np.pi*U[None,:]*R/p+phi[:,None])
            b1,bx = amp(d+inj)
            med.append(np.median(bx/b1)); hit.append(np.mean(bx/b1 > q95))
        out[str(frac)] = dict(median_observed=rnd(np.median(med)),exceedance=rnd(np.median(hit)))
    return dict(seed=20261118,unmodified_q95=rnd(q95),fractions=out)


def rectangle_double_ratios(primary):
    # Conditional model only: one rectangular interval per observed period,
    # C1/720 as its duty and identical linear image transfer in all phases.
    def relative(n, duty):
        return abs(np.sin(n*np.pi*duty)/(n*np.sin(np.pi*duty)))
    orders = (2,3,4)
    return dict(orders=list(orders),
                predicted=rnd([relative(n,704/720)/relative(n,96/720) for n in orders]),
                observed=rnd([primary[1][n-1]/((primary[0][n-1]+primary[2][n-1])/2) for n in orders]))


def analyse(a):
    validate(a)
    y = np.concatenate([a.sum(axis=2,keepdims=True)/60, a/20],axis=2)
    ps = [best(d[::4,0]) for d in y]
    p = (ps[0]+ps[2])/2
    d = y[1,:,0]
    primary = []
    for t in y:
        aabs = abs(coef(t[:,0],p,[*H,R]))
        primary.append(np.median(aabs[:,:10]/aabs[:,:1],axis=0))
    return dict(units="decoded Y; spatial camera rows only", phase_DBV=[3600,460,3600],
                phase_starts=list(STARTS), phase_frames=90, periods=rnd(ps), fixed_p=rnd(p),
                roi_names=["x540:600","x540:560","x560:580","x580:600"],
                by_roi_then_phase=[[stats(t[:,r],p) for t in y] for r in range(4)],
                low_15frame_blocks=[stats(t,p) for t in np.array_split(d,6)],
                low_frac_controls={f"{k}/3":stats(d,p,k/3)["frac_over_A1"] for k in [19,20,22,23,25,26]},
                conditional_off_time_model=rectangle_double_ratios(primary),
                injections=injections(d,p), synthetic=synthetic(p))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--video',type=Path,help='Optional indexed MP4, otherwise reads shipped strip_sums.npz')
    ap.add_argument('--save-sums',type=Path,help='Write .npz (only with --video)')
    args = ap.parse_args()
    if args.save_sums and (not args.video or args.save_sums.suffix != '.npz'):
        ap.error('--save-sums requires --video and a .npz output')
    if args.video:
        a = extract(args.video)
        if args.save_sums:
            np.savez_compressed(args.save_sums,strip_sums=a)
    else:
        with np.load(HERE/'strip_sums.npz',allow_pickle=False) as f:
            a = validate(f['strip_sums'])
    print(json.dumps(analyse(a),indent=2,allow_nan=False))


if __name__ == '__main__':
    main()
