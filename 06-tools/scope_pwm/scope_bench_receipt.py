"""Structural guard for trusted receipts from the 2026-11-18 bench.

Not an authenticity check: the operator verifies provenance, phase semantics,
device identity, settings, frame association and image bytes separately.
"""
from datetime import datetime, timedelta
import json
from pathlib import Path
import re

FIELDS = frozenset("brightness actual_brightness max_brightness bl_power dc panel android manual min peak provider sf focus float".split())

def utc(value):
    if not isinstance(value,str):
        raise ValueError("incomplete or invalid UTC timestamp")
    dt=datetime.fromisoformat(value)
    if dt.utcoffset()!=timedelta(0):
        raise ValueError("receipt timestamp must explicitly be UTC")
    return dt

def state(obj):
    if not isinstance(obj,dict) or not all(isinstance(obj.get(k),str) and obj[k].strip() for k in FIELDS):
        raise ValueError("incomplete bench state")
    return {k:obj[k] for k in FIELDS},utc(obj.get("utc"))

def read_receipt(path:Path):
    obj=json.loads(path.read_text())
    if not isinstance(obj,dict) or not isinstance(obj.get("phases"),list) or len(obj["phases"])<3:
        raise ValueError("incomplete phases")
    original,t0=state(obj.get("initial"))
    restored,tr=state(obj.get("restored"))
    if restored!=original or tr<=t0:
        raise ValueError("initial/restored mismatch")
    seen_phases=set()
    seen_stems=set()
    previous=t0
    for ph in obj["phases"]:
        previous_end = previous
        if not isinstance(ph,dict):
            raise ValueError("invalid phase")
        name=ph.get("phase")
        if not isinstance(name,str) or not name.strip() or name in seen_phases:
            raise ValueError("missing or duplicate phase")
        seen_phases.add(name)
        start,ts=state(ph.get("start"))
        end,te=state(ph.get("end"))
        if end!=start or ts<=previous:
            raise ValueError("phase endpoints changed or out of order")
        frames=ph.get("frames")
        if not isinstance(frames,list) or len(frames)!=3:
            raise ValueError("incomplete bench frame triplet")
        previous=ts
        for item in frames:
            if not isinstance(item,list) or len(item)!=2:
                raise ValueError("invalid frame record")
            stem,date=item
            if not isinstance(stem,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*",stem) or stem in seen_stems:
                raise ValueError("invalid or duplicate frame basename")
            seen_stems.add(stem)
            tf=utc(date)
            if not previous<tf<te:
                raise ValueError("frame outside phase or out of order")
            previous=tf
        previous=te
    # Accept a check after all phases, or just before a final triplet
    # that still matches the original state. An early matching snapshot
    # must not count as restoration of a later experimental state.
    if not (tr > te or (previous_end < tr < ts and end == restored)):
        raise ValueError("restoration time or final state mismatch")
    return obj
