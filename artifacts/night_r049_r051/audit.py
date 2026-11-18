"""Offline clipping and phase-median checks on two named Nothing PHOTO archives."""
import argparse
import json
import math
from pathlib import Path
from statistics import median

import numpy as np
from PIL import Image

BOXES = {"C": (370, 310, 690, 530), "R": (760, 310, 990, 530)}
PUBLIC = Path(__file__).resolve().parents[1] / "r8_raster_context_20261118/results.json"
PHASES = {"WBW": ("1_white", "2_black", "3_white"), "spatial": tuple(
    f"{i}{v}" for i, v in enumerate("ABABA", 1))}
PREFIX = {"WBW": "color", "spatial": "spatial"}


def counts(rgb):
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8 or not rgb.size:
        raise ValueError("expected nonempty RGB8")
    low = (rgb == 0).any(axis=2)
    high = (rgb == 255).any(axis=2)
    return [int(low.sum()), int(high.sum()), int((low | high).sum())]


def veto(n_union, pixels):
    return 100 * n_union >= pixels


def audit(folder, key, ref):
    phases = PHASES[key]
    prefix = PREFIX[key]
    names = [f"{prefix}-{p}-{i}.png" for p in phases for i in (1, 2, 3)]
    actual = {p.name for p in folder.glob(f"{prefix}-[0-9]*.png")}
    if actual != set(names):
        raise ValueError("incomplete or unexpected phase-slot inventory")
    out = []
    for k, phase in enumerate(phases):
        rows = {key: [] for key in BOXES}
        ratios = []
        for name in names[3*k:3*k+3]:
            means = []
            with Image.open(folder / name) as im:
                if im.format != "PNG" or im.size != (1080, 2392) or im.mode not in ("RGB", "RGBA"):
                    raise ValueError("unexpected PNG geometry/mode")
                for label, box in BOXES.items():
                    crop = im.crop(box)
                    if im.mode == "RGBA" and crop.getchannel("A").getextrema() != (255, 255):
                        raise ValueError("nonopaque ROI")
                    rgb = np.asarray(crop.convert("RGB"))
                    rows[label].append((counts(rgb), int(rgb.min()), int(rgb.max())))
                    means.append(float(rgb.mean()))
            if min(means) <= 0:
                raise ValueError("undefined log-ratio")
            ratios.append(math.log(means[0]/means[1]))
        triple = [round(v, 8) for v in (min(ratios), median(ratios), max(ratios))]
        if triple != ref["phase_log_center_right_min_median_max"][k]:
            raise ValueError("archive does not reproduce R8 phase log-ratio")
        result = {"phase": phase, "log_C_over_R_median": triple[1], "regions": {}}
        for label, entries in rows.items():
            a, b, c, d = BOXES[label]
            pixels = (c-a)*(d-b)
            slots = [e[0] for e in entries]
            result["regions"][label] = {
                "pixels_per_slot": pixels, "slot_counts_floor_ceiling_union": slots,
                "range_across_channels_slots_DN": [min(e[1] for e in entries),
                                                    max(e[2] for e in entries)],
                "phase_union_pct": round(100*sum(e[2] for e in slots)/(3*pixels), 8),
                "slots_at_or_above_1pct_union": sum(veto(e[2], pixels) for e in slots)}
        out.append(result)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("wbw", type=Path)
    p.add_argument("spatial", type=Path)
    a = p.parse_args()
    ref = json.loads(PUBLIC.read_text())["context"]
    print(json.dumps({k: audit(path, k, ref[k]) for k, path in
                      (("WBW", a.wbw), ("spatial", a.spatial))},
                     indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
