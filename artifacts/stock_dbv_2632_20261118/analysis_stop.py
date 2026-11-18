"""Apply predeclared yellow metric only to the four actually admitted same-DBV previews."""
import argparse
import itertools
import json
from pathlib import Path

import numpy as np

from analysis_geometry import load, reference, score
from analysis_ordinals import descriptor, feature


def summary(src):
    # A replay summaries metadata, state, timing, and return separately; do not substitute
    # this narrow descriptive audit for evidence/replay_prospective.py --allow-aborted.
    events=[json.loads(line) for line in (src/"oc.log").read_text().splitlines()]
    approved=[(tag,row) for _,tag,row in events if tag.endswith("_manifest")]
    tags=["P00_s0","P00_s1","P00_s2","P01_s0"]
    if [k for k,_ in approved]!=[k+"_manifest" for k in tags] or any(row["n"]!=2632 for _,row in approved):
        raise ValueError("not the four accepted same-DBV frames from this run")
    rejection=[v for _,k,v in events if k=="rejected"]
    if len(rejection)!=1 or "P01_s1" not in rejection[0]:
        raise ValueError("unexpected abort")
    ref=reference(load(src/f"new_qual{i}.png") for i in range(3))
    rows=[]; desc=[]
    for tag,(_,row) in zip(tags,approved):
        a=load(src/(tag+".png"))
        if not score(a,ref)["pass_geometry_highlights"]: raise ValueError("accepted frame fails geometry")
        z=descriptor(a,18,0,0); f=feature(a,z[2])
        desc.append(z)
        rows.append(dict(tag=tag,host_raster_start=row["raster_start"],host_raster_end=row["raster_end"],
                         n=2632,yellow_fraction=f[0],center_argmax_y=f[1],center_max_fraction=f[2],
                         trace_lags_px_r=json.loads(f[3]),grid_lags_px_r=json.loads(f[4])))
    distances=[]
    for i,j in itertools.combinations(range(len(tags)),2):
        d,l=[round(float(abs(desc[i][k]-desc[j][k]).mean()),6) for k in (0,1)]
        distances.append(dict(a=tags[i],b=tags[j],D=d,L=l))
    rejected=score(load(src/"P01_s1.png"),ref)
    if rejected["failures"]!=["top-left:relative"]:
        raise ValueError("unexpected rejected-frame diagnosis")
    return dict(complete_blocks=1,partial_block="1 of 3",comparison_at_2633=None,
                accepted=rows,same_dbv_pairs_only=distances,rejected_not_scored_for_waveform="P01_s1",
                top_left_reference=ref["top-left"],top_left_rejected=rejected["anchors"]["top-left"],
                unchanged_ridge_positions=sum(rejected["anchors"][k]["pos"]==v["pos"] for k,v in ref.items()))


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("src",type=Path)
    print(json.dumps(summary(ap.parse_args().src),indent=2,allow_nan=False))
