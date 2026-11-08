#!/usr/bin/env python3
"""Offline broad/fine phase test on the completed selector-split video only."""

import argparse
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PROFILES = Path(
    "/home/stfu/.cache/opencode-tmp/opencode/dsi-selector-split-20261107/analysis-profiles-spatial-v2.npz"
)
SOURCE = ROOT / "artifacts/dsi_selector_split_20261107/analysis_spatial_v2.json"
FINE = 1 / 93.43  # Same fixed spatial frequency as the archived q93 RMS.
BROAD = (FINE / 3 - 0.001, FINE / 3, FINE / 3 + 0.001)
LABELS = ("baseline", "a9_only", "return_a9_only", "9d_only", "return_9d_only")


def analyze():
    with np.load(PROFILES, allow_pickle=False) as saved:
        profiles, pts, roi = (saved[k] for k in ("profiles", "pts_s", "roi_xywh"))
    archived = json.loads(SOURCE.read_text())
    if (profiles.shape != (2679, 500) or pts.shape != (2679,)
            or roi.tolist() != [540, 190, 60, 500]
            or not np.isfinite(profiles).all() or not np.isfinite(pts).all()
            or not (np.diff(pts) > 0).all()
            or tuple(s["label"] for s in archived["stages"]) != LABELS):
        raise ValueError("Unexpected saved selector source/ROI/stages")
    rows = np.arange(500)
    window = np.hanning(500)
    scale = 2 / window.sum()
    basis_fine = window * np.exp(-2j * np.pi * FINE * rows)
    records = []
    for degree in (1, 2, 3):
        trend = np.polynomial.legendre.legvander(np.linspace(-1, 1, 500), degree)
        for stage in archived["stages"]:
            lo, hi = stage["window_s"]
            indices = np.flatnonzero((pts >= lo) & (pts <= hi))
            if len(indices) != 75 or stage["frames"] != 75:
                raise ValueError("Selector window no longer has 75 frames")
            values = profiles[indices]
            values = values - (trend @ np.linalg.lstsq(trend, values.T, rcond=None)[0]).T
            fine = values @ basis_fine * scale
            if (np.abs(fine) == 0).any():
                raise ValueError("Undefined fine phase")
            if degree == 2 and not np.isclose(
                np.sqrt(np.mean(np.abs(fine) ** 2)), stage["q93_total_rms_Y_codes"],
                rtol=1e-8, atol=1e-8,
            ):
                raise ValueError("Historical fine RMS changed")
            record = {"degree": degree, "stage": stage["label"], "frames": len(indices),
                      "fine_mean_amplitude_Y_codes": float(np.abs(fine).mean()),
                      "broad_frequency_checks": []}
            for broad_q in BROAD:
                broad = values @ (window * np.exp(-2j * np.pi * broad_q * rows)) * scale
                if (np.abs(broad) == 0).any():
                    raise ValueError("Undefined broad phase")
                phase_relation = fine / np.abs(fine) * (np.conj(broad) / np.abs(broad)) ** 3
                record["broad_frequency_checks"].append({
                    "cycles_per_output_row": float(broad_q),
                    "mean_broad_amplitude_Y_codes": float(np.abs(broad).mean()),
                    "third_harmonic_phase_lock_resultant": float(abs(phase_relation.mean())),
                })
            records.append(record)
    return {
        "input": str(PROFILES), "archived_analysis": str(SOURCE),
        "scope": "Historical stock→A9-only→stock→9D-only→stock; no new capture",
        "fixed_fine_cycles_per_output_row": FINE,
        "hypothesis": "If broad is the fine component's third-harmonic fundamental, the fixed 1:3 phase relation should be coherent and more specific at fine/3 than adjacent broad frequencies",
        "method": "Per-frame Legendre degree 1/2/3 detrend, Hann, 2/sum(Hann) amplitude in camera Y codes, unit-phasor resultant |mean(exp(i*(fine_phase - 3*broad_phase)))|; fixed broad controls ±0.001 cycles/output row",
        "records": records,
        "limits": ["Only ~1.8 broad cycles in 500 rows; polynomial trend affects phase",
                   "High phase resultant can reflect camera/scene coupling, not OLED emission",
                   "A9-only weak fine component makes its phase unreliable",
                   "No sensor row time or physical harmonic order/Hz established"],
        "physical_pwm_hz": None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = analyze()
    with args.output.open("x") as out:
        json.dump(result, out, indent=2, allow_nan=False)
        out.write("\n")
