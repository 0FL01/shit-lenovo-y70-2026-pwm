"""Offline only. Four original private PNG directories in; only derived numbers to stdout."""
from argparse import ArgumentParser
import json
from pathlib import Path
import re

import numpy as np
from PIL import Image

TRACE = (112, 1150, 540, 1240)
UPPER = ((60, 310, 280, 530), (370, 310, 690, 530), (760, 310, 990, 530))
OC = ((640, 950, 1000, 1280), (100, 1500, 540, 1640))
N = 428
K = (8, 16, 32, 64, 128)
H = (.01, .02, .04, .08, .16)


def read_box_files(folder, names, boxes):
    out = []
    for name in names:
        with Image.open(folder / name) as im:
            if im.format != "PNG" or im.size != (1080, 2392):
                raise ValueError("unexpected source format or geometry: " + name)
            rgb = im.convert("RGB")
            out.append([np.asarray(rgb.crop(box), dtype=np.int16) for box in boxes])
    return out


def rounded(x):
    return np.round(x, 8).tolist()


def trace(rows):
    def profile(v):
        return (v[..., 0] + v[..., 1] - 2 * v[..., 2] > 36).mean(0)
    return np.stack([profile(row[0]) for row in rows])


def spectrum(s, r):
    x = np.arange(N)
    w = 2*np.pi*x/N
    def amp(v, k):
        return 2 * np.abs(np.mean(v*np.exp(-1j*k*w), axis=-1))
    def power(v):
        q = np.abs(np.fft.rfft(v-v.mean(1, keepdims=True), axis=1)[:, 1:])**2
        if np.any(q.sum(1) <= 0):
            raise ValueError("constant profile")
        return q/q.sum(1, keepdims=True)
    indices = 3*x % N
    if len(set(indices)) != N:
        raise ValueError("not a permutation")
    perm = s[:, indices]
    tv = np.abs(power(s)-power(perm)).sum(1)*.5
    res = []
    for k in K:
        ref = amp(s, k)
        obs = amp(r, k)
        ceiling = ref.max()
        trials = []
        for h in H:
            a = np.stack([amp(np.clip(s+h*np.cos(k*w+j*np.pi/4), 0, 1), k)
                          for j in range(8)])
            trials.append(dict(h=h, min=rounded(a.min()), max=rounded(a.max()),
                               over=int(np.count_nonzero(a > ceiling)), n=int(a.size)))
        res.append(dict(k=k, px_per_cycle=N/k, archive_sham_range=rounded([ref.min(), ceiling]),
                        accepted_R7_range=rounded([obs.min(), obs.max()]),
                        R7_over_sham_max=int(np.count_nonzero(obs > ceiling)), synthetic=trials))
    return dict(spectral_bins=res, permutation=dict(
        D_max=rounded(np.max(np.mean(np.abs(np.sort(s)-np.sort(perm)), axis=1))),
        power_TV_min_median_max=rounded(np.quantile(tv, [0, .5, 1]))))


def context(rows, ratio):
    m = np.array([[crop.mean((0, 1)) for crop in row] for row in rows])
    dn = m.mean(2).reshape((-1, 3, m.shape[1]))
    any0 = np.array([[np.mean(np.min(v, axis=2) == 0)*100 for v in row] for row in rows])
    all0 = np.array([[np.mean(np.max(v, axis=2) == 0)*100 for v in row] for row in rows])
    out = dict(phase_median_rgb_DN=rounded(np.median(dn, 1)),
               any_channel_zero_percent_min_max=rounded([any0.min(0), any0.max(0)]),
               all_channels_zero_percent_min_max=rounded([all0.min(0), all0.max(0)]))
    if ratio:
        if np.any(m.sum(2) <= 0):
            raise ValueError("undefined log ratio")
        z = np.log(m[:, 1].sum(1) / m[:, 2].sum(1)).reshape(-1, 3)
        out["phase_log_center_right_min_median_max"] = rounded(np.stack(
            (z.min(1), np.median(z, 1), z.max(1)), axis=1))
    return out


def main():
    parser = ArgumentParser(description=__doc__)
    for key in ("sham", "r7", "white_black_white", "spatial"):
        parser.add_argument(key, type=Path)
    a = parser.parse_args()
    s_names = [f"S{i:02d}.png" for i in range(51)]
    r_names = [f"P{i:02d}_s{j}.png" for i in range(14) for j in range(3)]
    actual = {p.name for p in a.r7.iterdir() if re.fullmatch(r"P\d{2}_s\d+\.png", p.name)}
    if actual != set(r_names) | {"P14_s0.png"}:
        raise ValueError("expected original stopped R7 run; missing or unexpected phase PNG")
    w_names = [f"color-{i}_{state}-{j}.png" for i, state in enumerate(
        ("white", "black", "white"), 1) for j in range(1, 4)]
    a_names = [f"spatial-{i}{state}-{j}.png" for i, state in enumerate(
        "ABABA", 1) for j in range(1, 4)]
    rr = read_box_files(a.r7, r_names, (TRACE, *OC))
    result = dict(included=dict(sham=51, r7=42, wbw=9, spatial=15),
                  profile=spectrum(trace(read_box_files(a.sham, s_names, (TRACE,))), trace(rr)),
                  context=dict(WBW=context(read_box_files(a.white_black_white, w_names, UPPER), True),
                               spatial=context(read_box_files(a.spatial, a_names, UPPER), True),
                               R7=context([row[1:] for row in rr], False)))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
