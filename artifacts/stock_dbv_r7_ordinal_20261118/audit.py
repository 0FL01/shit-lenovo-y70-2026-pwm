"""Read original 42 PNG and check D independently; print only derived statistics."""
import argparse
import csv
import datetime as dt
import itertools
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

ORDER = (2632,2632,2633,2632,2631,2632,2633,2634,2633,2632,2633,2633,2634,2633,2632,2631,2632)
VARIANTS=((18,0,0),(12,0,0),(24,0,0),(18,-3,0),(18,3,0),(18,0,-3),(18,0,3))
N=14

def groups(i,j, order):
    a,b=order[i],order[j]
    if i==j: return "within"
    if a==b: return "sham" if j==i+1 else "repeated"
    if j!=i+1: return None
    return {2631:"lower_neighbor",2632:"up" if b>a else "down",2633:"upper_neighbor"}[min(a,b)]

def require(condition, message):
    if not condition:
        raise ValueError(message)

def strict_json(s):
    def unique(pairs):
        data={}
        for k,v in pairs:
            require(k not in data, "duplicate JSON object key")
            data[k]=v
        return data
    def invalid(value):
        raise ValueError("non-finite JSON number")
    return json.loads(s, object_pairs_hook=unique, parse_constant=invalid)

def read_events(path):
    expected=[]
    for i in range(N):
        p=f"P{i:02d}"
        expected += [p+"_command",p+"_pre"]
        for j in range(3):
            expected += [f"{p}_s{j}_qc",f"{p}_s{j}_manifest"]
        expected.append(p+"_late")
    expected += ["P14_command","P14_pre","P14_s0_qc"]
    raw={}
    for n,line in enumerate(path.read_text().splitlines(),1):
        try:
            event=strict_json(line)
            require(type(event) is list and len(event)==3,"invalid event schema")
            ts,key,dat=event
            require(type(ts) is str and type(key) is str,"invalid event metadata")
            dt.datetime.fromisoformat(ts)
            if key.startswith("P"):
                require(key not in raw,f"duplicate phase event: {key}")
                raw[key]=dat
        except (TypeError,ValueError) as e:
            raise ValueError(f"invalid log line {n}: {e}") from e
    require(list(raw)==expected,"unexpected, missing or misordered phase event")
    return raw

def read_reference(path):
    columns="threshold dx dy a b n Dmin Dmed Dmax Lmin Lmed Lmax".split()
    keys={(v,i,j) for v in VARIANTS for i,j in itertools.combinations_with_replacement(range(N),2)}
    ref={}
    with path.open(newline="") as f:
        reader=csv.DictReader(f,strict=True)
        require(reader.fieldnames==columns,"unexpected ordinal CSV header")
        for row in reader:
            require(None not in row and all(row.get(k) is not None for k in columns),"malformed CSV row")
            require(all(re.fullmatch(r"P[0-9]{2}",row[k]) for k in ("a","b")),"invalid block label")
            v=tuple(int(row[k]) for k in ("threshold","dx","dy"))
            i,j=[int(row[k][1:]) for k in ("a","b")]
            key=(v,i,j)
            require(key in keys,"unexpected pair/variant")
            require(key not in ref,"duplicate pair/variant")
            require(int(row["n"])==(3 if i==j else 9),"wrong number of frame pairs")
            data=[float(row[k]) for k in columns[-6:]]
            require(all(math.isfinite(z) for z in data),"nonfinite CSV value")
            ref[key]=np.array(data[:3])
    require(set(ref)==keys,"incomplete ordinal CSV")
    return ref

def _check(src, ordinal):
    raw=read_events(src/"oc.log")
    ref=read_reference(ordinal)
    expected_png={f"P{i:02d}_s{j}.png" for i in range(N) for j in range(3)}|{"P14_s0.png"}
    require({p.name for p in src.glob("P*_s*.png")}==expected_png,"unexpected or missing sample PNG")
    count=defaultdict(list); timeline=[]; corners=0; blue=[]; frames=[]
    for i in range(N):
        tag=f"P{i:02d}"; cmd=raw[tag+"_command"]; pre=raw[tag+"_pre"]; late=raw[tag+"_late"]
        require((cmd[2],pre[0],pre[1],int(pre[2]["DBV"]),late[1],int(late[0]["DBV"]))==(ORDER[i],)*6, "readback/command mismatch: "+tag)
        t0=dt.datetime.fromisoformat(cmd[0])
        for j in range(3):
            f=tag+f"_s{j}"; qc=raw[f+"_manifest"]
            gate=raw[f+"_qc"]
            require(isinstance(gate,dict) and gate==strict_json((src/(f+"_qc.json")).read_text()), "QC/log mismatch: "+f)
            require(all(k in qc and qc[k]==value for k,value in gate.items()), "QC/manifest mismatch: "+f)
            require((qc["tag"],qc["phase"],qc["sample"],qc["n"])==(f,i,j,ORDER[i]), "manifest identity mismatch: "+f)
            require(qc["fixture"]["geometry"]["pass_exterior"] is True and qc["fixture"]["pass_original_upper_headroom"] is True,"fixture rejection: "+f)
            require(qc["legend"]["pass_similarity"] is True and qc["legend"]["pass_modes"] is True and qc["clear_displacement"]==[],"legend/displacement rejection: "+f)
            corners+=int(qc["corner_supported"])
            blue.append(qc["shadows"]["per_channel_zero"][2]/qc["fixture"]["trace_pixels"])
            t1,t2=[dt.datetime.fromisoformat(qc[k]) for k in ("raster_start","raster_end")]
            if j==0: timeline.append((t1-t0).total_seconds())
            frames.append((t1,t2))
            with Image.open(src/(f+".png")) as img:
                require(img.size==(1080,2392) and img.format=="PNG","PNG geometry: "+f)
                rgb=img.convert("RGB")
                for v in VARIANTS:
                    th,dx,dy=v
                    a=np.array(rgb.crop((112+dx,1150+dy,540+dx,1240+dy)),dtype=np.int16)
                    mask=a[:,:,0]+a[:,:,1]-2*a[:,:,2]>2*th
                    count[v].append(np.sort(mask.sum(axis=0)))
    stopped=strict_json((src/"P14_s0_qc.json").read_text())
    require(stopped==raw["P14_s0_qc"] and stopped["tag"]=="P14_s0","P14 QC/log mismatch")
    require(stopped["legend"]["pass_similarity"] is False,"missing P14 legend rejection")
    failed={k:g["ncc"] for k,g in stopped["legend"]["glyphs"].items() if not g["ok"]}
    require(set(failed)=={"AUTO","X1"} and all(v<.8 for v in failed.values()),"unexpected reason for stop")
    result={"n_full":N,"first_last_png_start_span_s":round((frames[-1][0]-frames[0][0]).total_seconds(),6),
            "first_png_delay_per_block_s":timeline,"supported_corner_count":corners,
            "blue_zero_fraction_range": [min(blue),max(blue)], "P14_failed_glyph_ncc":failed,"variants":{}}
    for v in VARIANTS:
        a=np.array(count[v]); d=np.abs(a[:,None,:]-a[None,:,:]).sum(axis=-1)/(90*428)
        blocks=defaultdict(list)
        for i,j in itertools.combinations_with_replacement(range(N),2):
            ii,jj=range(3*i,3*i+3),range(3*j,3*j+3)
            pairs=itertools.combinations(ii,2) if i==j else itertools.product(ii,jj)
            values=np.quantile([d[x,y] for x,y in pairs],[0,.5,1])
            require(np.allclose(values,ref[v,i,j],atol=0.500001e-6,rtol=0),f"D mismatch: {v} P{i:02d}/P{j:02d}")
            key=groups(i,j,ORDER)
            if key:blocks[key].append([i,j,round(float(values[1]),6)])
        t=blocks["up"]+blocks["down"]
        c=[p for k,entries in blocks.items() if k not in ("up","down") for p in entries]
        require((len(t),len(c))==(5,46),"incorrect target/control counts")
        result["variants"][str(v)]={"margin_at_csv_precision":round(min(p[2] for p in t)-max(p[2] for p in c),6),
            "groups":{k:[len(b),min(p[2] for p in b),max(p[2] for p in b)] for k,b in blocks.items()},
            "crossings":sorted(t)}
    return result

def check(src, ordinal):
    try:
        return _check(src, ordinal)
    except (TypeError, KeyError, IndexError, ZeroDivisionError, csv.Error, OSError) as e:
        raise ValueError("invalid audit evidence: "+str(e)) from e

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("source",type=Path)
    p.add_argument("ordinal_pairs",type=Path)
    args=p.parse_args()
    print(json.dumps(check(args.source,args.ordinal_pairs),indent=2))
