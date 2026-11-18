"""Replay public R099 CSVs. No image extraction or hardware dependency."""
import csv
import json
import math
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "scope_dc_divergence_20261118"
PHASE = ("1_0", "2_1", "3_0")
ARMS = {("1_0", "2_1"), ("2_1", "3_0")}
PAIRS = {(a, b) for i, a in enumerate(PHASE) for b in PHASE[i:]}
VARIANTS = {("0.97", "0", "0"), ("0.95", "0", "0"), ("0.98", "0", "0"),
            ("0.97", "-4", "0"), ("0.97", "4", "0"),
            ("0.97", "0", "-2"), ("0.97", "0", "2")}


def read(name):
    with (SRC / (name + ".csv")).open(newline="") as handle:
        return list(csv.DictReader(handle))


def index(rows, key):
    found = {r[key]: r for r in rows}
    if len(found) != len(rows):
        raise ValueError("duplicate frame")
    return found


def run(frames, qc, pairs):
    f, q = index(frames, "capture"), index(qc, "frame")
    ids = {f"dc-{p}-{i}": p for p in PHASE for i in (1, 2, 3)}
    if ids.keys() != f.keys() or q.keys() != f.keys():
        raise ValueError("incomplete or unexpected frame set")
    for k, p in ids.items():
        if (f[k]["phase"] != p or q[k]["phase"] != p or f[k]["status"] != "ok"
                or (int(q[k]["grid_dx"]), int(q[k]["grid_dy"])) != (0, 0)
                or not 0.99 <= float(q[k]["grid_rho"]) <= 1):
            raise ValueError("frame failed QC")
    groups = {}
    for r in pairs:
        variant = tuple(r[t] for t in ("ref_q", "dx", "dy"))
        ab = r["a"], r["b"]
        g = groups.setdefault(variant, {})
        vals = tuple(float(r[t]) for t in ("Dmin", "Dmed", "Dmax"))
        if (ab in g or ab not in PAIRS or int(r["n"]) != (3 if ab[0] == ab[1] else 9)
                or not all(map(math.isfinite, vals)) or not 0 <= vals[0] <= vals[1] <= vals[2] <= 1):
            raise ValueError("invalid pair summary")
        g[ab] = vals
    if groups.keys() != VARIANTS or any(g.keys() != PAIRS for g in groups.values()):
        raise ValueError("incomplete or unexpected pair matrix")
    out = []
    for variant, g in sorted(groups.items()):
        trans = min(g[ab][0] for ab in ARMS)
        ctrl = max(g[ab][2] for ab in PAIRS - ARMS)
        out.append(dict(variant=list(variant), min_transition=trans, max_control=ctrl,
                        margin=round(trans - ctrl, 6), separated=trans > ctrl))
    base = groups[("0.97", "0", "0")]
    return dict(frames=len(f), phases=len(PHASE), physical_series=1, min_grid_rho=min(
        float(r["grid_rho"]) for r in q.values()), nominal_Dmed={
            a + ":" + b: base[a, b][1] for a, b in sorted(ARMS | {("1_0", "3_0")})},
        variants=out, raster_separated_all=all(r["separated"] for r in out))


if __name__ == "__main__":
    print(json.dumps(run(read("frames"), read("raster_qc"), read("pairs")), indent=2))
