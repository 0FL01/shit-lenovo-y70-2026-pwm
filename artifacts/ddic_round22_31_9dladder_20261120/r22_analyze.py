#!/usr/bin/env python3
"""Round-local analyzer for the R22-R31 campaign (re-based rig).

The owner re-assembled the bench on 2026-11-19 evening: the white field no
longer covers the day-campaign ROI (raw y90-270, x1860-2020), so the default
pipeline of analyze_2d_modulation.py cannot be used unchanged. This script
reuses that analyzer's functions with the campaign's OWN re-based parameters
(reference flat shot tonight at PWM DBV 6879, ROI inside tonight's white core,
wave k measured tonight) and adds per-frame error capture for phases too dark
for the flat normalization.

No existing analyzer code is modified; all comparisons in this campaign are
internal to tonight's rig (cross-references to R9-R21 are qualitative).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent / "pwm_06x_dng_bench_20261119"
NIGHT = HERE.parent / "night_r113_camera_notch"
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(NIGHT))

from analyze_2d_modulation import analyze_patch_2d, load_bayer2x2_green  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--spec-json", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    args = parser.parse_args(argv)

    spec = json.loads(args.spec_json.read_text())
    ev = args.evidence_dir
    ref_file = spec["reference_dng"]
    ref = load_bayer2x2_green(ev / ref_file)[0]

    roi = tuple(spec["b2_roi"])
    target_k = tuple(spec["target_wave_vector_k"])
    nc0, nc1 = spec["narrow_col_slice"]

    def resolve(name: str) -> Path:
        for cand in (ev / name, ev / "frames" / name):
            if cand.exists():
                return cand
        raise FileNotFoundError(name)

    out = {
        "experiment": spec["experiment"],
        "reference_dng": ref_file,
        "b2_roi": list(roi),
        "target_wave_vector_k": list(target_k),
        "narrow_col_slice": [nc0, nc1],
        "phases": {},
    }
    for phase, files in spec["phases"].items():
        frames = []
        for f in files:
            try:
                cur = load_bayer2x2_green(resolve(f))[0]
                m = analyze_patch_2d(
                    cur, ref, b2_roi=roi, target_k=target_k, narrow_col_slice=(nc0, nc1)
                )
                frames.append(m)
            except ValueError as exc:
                frames.append({"error": str(exc)})
        out["phases"][phase] = frames

    args.out_json.write_text(json.dumps(out, indent=2) + "\n")
    n_ok = sum(1 for ph in out["phases"].values() for fr in ph if "error" not in fr)
    n_err = sum(1 for ph in out["phases"].values() for fr in ph if "error" in fr)
    print(f"wrote {args.out_json}: {n_ok} frames ok, {n_err} error frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
