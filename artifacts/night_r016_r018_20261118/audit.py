"""Retrospective archive audit. No device, no imaging I/O. Python 3 stdlib."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def signmap(grid):
    require(len(grid) == 8 and all(len(r) == 8 for r in grid), "grid shape")
    row = [v for r in grid for v in r]
    require(set(row) <= {-1, 1}, "non-binary cell")
    return row


def score_controls(rows):
    n = len(rows)
    require(n > 0, "no coded frames")
    pos = [sum(k[i] == 1 for _, k, _ in rows) for i in range(64)]
    total = n * 64
    return dict(frames=n, cells=total,
                decoder=sum(sum(a == b for a, b in zip(k, p)) for _, k, p in rows),
                all_positive=sum(pos), all_negative=total-sum(pos),
                fixed_upper_bound=sum(max(x, n-x) for x in pos))


def classify(i):
    r, c = divmod(i, 8)
    return "edge" if r in (0, 7) or c in (0, 7) else "center"


def error_map(rows):
    hits = defaultdict(list)
    areas = {s:dict(errors=0, opportunities=0) for s in ("edge", "center")}
    for name, key, pred in rows:
        for i, (a,b) in enumerate(zip(key,pred)):
            z = areas[classify(i)]
            z["opportunities"] += 1
            if a != b:
                z["errors"] += 1
                hits[i].append(name)
    return dict(areas=areas, cells=[dict(row=i//8+1,col=i%8+1,slots=slots,
                repeat=len(slots)>1, across_phases=len({s.split("_")[0] for s in slots})>1)
                for i,slots in sorted(hits.items())])


def match(name, digest, binding, operator):
    # Never infer sensor frame identity from a bracket, even if actuals agree.
    matches = [r for r in operator if r["image"]["sha256"] == digest]
    if len(matches) != 1 or binding.get(name) != digest:
        return dict(status="no unique matching image")
    op = matches[0]
    i,j = name[1:-4].split("_")
    if op["ordinal"] != f"P{int(i)-1:02}_{int(j)-1}":
        return dict(status="ordinal mismatch")
    pair = []
    for end in ("pre","post"):
        b = op.get(end) or {}
        res, req = b.get("result") or {}, b.get("request") or {}
        try:
            pair.append((int(res["sensor.exposureTime"]), int(res["sensor.sensitivity"]),
                         int(req["sensor.exposureTime"]), int(b["frame_offset"]),
                         int(b["timestamp_offset_ns"])))
        except (KeyError, TypeError, ValueError):
            return dict(status="incomplete bracket")
    if pair[0][:3] != pair[1][:3] or any(pair[1][j] <= pair[0][j] for j in (3,4)):
        return dict(status="inconsistent bracket")
    return dict(status="bracket only", exposure_ns=pair[0][0],iso=pair[0][1],
                request_exposure_ns=pair[0][2],
                sensor_frame=op["displayed_sensor_frame_identity"])


def run(src, manifest):
    for line in manifest.read_text().splitlines():
        digest, leaf = line.split(None,1)
        require(hashlib.sha256((src/leaf).read_bytes()).hexdigest()==digest,
                f"input changed: {leaf}")
    read = lambda p: json.loads((src/p).read_bytes())
    agg = read("analysis/preview_aggregates.json")
    key = read("analysis/revealed_codes.json")
    gate = read("analysis/outcome.json")["frames"]
    g0 = read("geometry/actual_capture.json")
    geom = {r["name"]:r["checks"]["pass_local_translation"] for r in g0}
    bind = read("binding.json")
    op = read("source/outcome_r12b.json")["frames"]
    expected = {f"p{i:02}_{j}.png" for i in range(1,7) for j in range(1,4)}
    require(set(agg)==set(gate)==set(geom)==set(bind["sha256"])==expected and len(g0)==18,
            "slot grid differs")
    require(key["order"]==[r["role"] for r in bind["source"]] and
            sorted(key["order"][:5])==sorted("CcDdU") and key["order"][5]=="C", "role grid")
    rows, first, brackets = [], [], {}
    for i,role in enumerate(key["order"],1):
        for j in range(1,4):
            name=f"p{i:02}_{j}.png"
            pred=signmap(agg[name]["rank"])
            accuracy=None
            if role!="U":
                k=[x if role.isupper() else -x for x in signmap(key[role.upper()])]
                require(all(sum(k[t:t+8])==0 for t in range(0,64,8)), "unbalanced key")
                accuracy=sum(x==y for x,y in zip(pred,k))
                require(accuracy==gate[name]["accuracy"], "archived accuracy mismatch")
                rows.append((name,k,pred))
                if i<6:
                    first.append(rows[-1])
            brackets[name] = dict(role=role, correct=accuracy, original_signal_pass=gate[name]["ok"],
                                  geometry_pass=geom[name], **match(name, agg[name]["hash"],bind["sha256"],op))
    return dict(R016={"all":score_controls(rows),"no_return":score_controls(first)},
                R017=error_map(rows),R018=brackets)


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("archive",type=Path)
    args=ap.parse_args()
    print(json.dumps(run(args.archive,Path(__file__).with_name("inputs.sha256")),indent=2))
