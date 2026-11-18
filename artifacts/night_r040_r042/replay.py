"""Archive-only: R7 accepted phases, and the explicitly censored slots."""
import argparse
import importlib.util
import itertools
import json
from pathlib import Path

import numpy as np
from PIL import Image

ART = Path(__file__).resolve().parents[1]
OLD = ART / "stock_dbv_r7_ordinal_20261118"
spec = importlib.util.spec_from_file_location("r7_audit", OLD / "audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def require(ok, why):
    if not ok:
        raise ValueError(why)


def stats(rgb):
    """Pixel observations pooled within phase, equal-size frames only."""
    require(rgb.ndim == 4 and rgb.shape[0] == 3 and rgb.shape[-1] == 3
            and rgb.dtype == np.uint8, "expected exactly three RGB8 rasters")
    z = rgb == 0
    floor = z.any(-1)
    black = z.all(-1)
    return dict(n_pixel_observations=int(floor.size),
                channel_zero=[int(x) for x in z.sum(axis=(0, 1, 2))],
                any_zero=int(floor.sum()), all_zero=int(black.sum()),
                any_255=int((rgb == 255).any(-1).sum()),
                chroma_s1=int((floor & ~black).sum()), max_rgb=int(rgb.max()),
                n_coordinates=int(floor[0].size),
                identical_rgb_across_three=int(np.all(rgb == rgb[:1], axis=(0, 3)).sum()))


def mask(rgb):
    a = rgb.astype(np.int16)
    return a[..., 0] + a[..., 1] - 2 * a[..., 2] > 36


def profile(mask3):
    require(mask3.shape == (3, 90, 428), "incomplete phase or wrong primary band")
    return np.median(np.sort(mask3.sum(axis=1), axis=-1), axis=0)


def run(src):
    # Original independent reviewer reconstructs all seven D variants, checks QC,
    # PNG set, terminal failure, and both readbacks for each finished triplet.
    checked = audit.check(src, OLD / "results" / "ordinal_pairs.csv")
    ev = audit.read_events(src / "oc.log")
    require((ev["P14_command"][2], ev["P14_pre"][0], ev["P14_pre"][1],
             int(ev["P14_pre"][2]["DBV"])) == (2632,)*4, "P14 pre/command")
    phases, profiles = [], []
    for i, code in enumerate(audit.ORDER):
        name = f"P{i:02d}"
        state = "accepted" if i < 14 else "rejected-slot-0" if i == 14 else "not-issued"
        row = dict(phase=name, planned_dbv=code, state=state, planned=3,
                   captured=3 if i < 14 else int(i == 14), accepted=3 if i < 14 else 0,
                   early_dbv=code if i <= 14 else None, late_dbv=code if i < 14 else None)
        phases.append(row)
        if i >= 14:
            continue
        data = []
        for j in range(3):
            with Image.open(src / f"{name}_s{j}.png") as im:
                tile = np.asarray(im.crop((112, 1080, 540, 1270)).convert("RGB"))
            data.append(tile)
            qc = ev[f"{name}_s{j}_qc"]
            zero = tile == 0
            require(qc["fixture"]["trace_pixels"] == 81320 and
                    qc["fixture"]["trace_max"] == int(tile.max()) and
                    qc["shadows"] == dict(any_zero=int(zero.any(-1).sum()),
                        all_zero=int(zero.all(-1).sum()),
                        per_channel_zero=zero.sum(axis=(0, 1)).tolist()), "RGB provenance")
        raster = np.stack(data)
        row.update(stats(raster))
        yellow = mask(raster)
        narrow = yellow[:, 70:160, :]
        row.update(bottom_yellow_wide=int(yellow[:, -1, :].sum()),
                   bottom_yellow_primary=int(narrow[:, -1, :].sum()), bottom_n=3*428)
        profiles.append(profile(narrow))
    out = {}
    for i, j in itertools.combinations(range(14), 2):
        g = audit.groups(i, j, audit.ORDER)
        if g:
            d = float(np.abs(profiles[i]-profiles[j]).sum()/(428*90))
            out.setdefault(g, []).append(dict(i=i, j=j, distance=round(d, 9)))
    require({key:len(rows) for key,rows in out.items()} ==
            dict(sham=2, repeated=24, lower_neighbor=2, upper_neighbor=4, up=3, down=2),
            "incomplete phase comparisons")
    return dict(phases=phases, median_profile_pairs=out,
                original_primary=checked["variants"]["(18, 0, 0)"],
                failed_glyphs=checked["P14_failed_glyph_ncc"])


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("r7", type=Path)
    print(json.dumps(run(p.parse_args().r7), ensure_ascii=False, indent=2))
