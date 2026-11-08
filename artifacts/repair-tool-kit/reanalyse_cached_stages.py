#!/usr/bin/env python3
"""Reanalyse saved frame/row profiles in the original stage windows, offline.

Uses the NPZ written by analyze_dsi_redraw.py and its historical analysis.json.
No video decoding, historical private logs, ADB, or phone connection is needed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from optical_spectrum import analyze_profiles, json_ready


def reanalyse(profiles: np.ndarray, pts: np.ndarray, stages: list[dict],
              reference_period_rows: float = 93.43) -> tuple[dict, dict]:
    profiles = np.asarray(profiles, dtype=float)
    pts = np.asarray(pts, dtype=float)
    if (profiles.ndim != 2 or pts.ndim != 1 or len(profiles) != len(pts)
            or not np.all(np.isfinite(pts)) or np.any(np.diff(pts) <= 0)):
        raise ValueError("Profiles and strictly increasing pts_s must describe the same frames")
    if not np.isfinite(reference_period_rows) or reference_period_rows < 2:
        raise ValueError("reference_period_rows must be finite and >= 2")
    if not stages:
        raise ValueError("No historical stages supplied")
    results, spectra = [], {}
    seen_labels = set()
    for index, stage in enumerate(stages):
        label = str(stage["label"])
        if label in seen_labels:
            raise ValueError(f"Duplicate stage label: {label}")
        seen_labels.add(label)
        start, end = map(float, stage["window_s"])
        if not np.isfinite([start, end]).all() or start >= end:
            raise ValueError(f"Invalid window for {label}")
        mask = (pts >= start) & (pts < end)
        count = int(mask.sum())
        if count < 2:
            raise ValueError(f"Fewer than two frames in {label}")
        if "frames" in stage and count != stage["frames"]:
            raise ValueError(f"Frame count differs from historical window for {label}: "
                             f"{count} versus {stage['frames']}; check PTS origin")
        selected = profiles[mask]
        full = analyze_profiles(selected)
        ref = analyze_profiles(selected, frequencies=[1 / reference_period_rows], peak_count=0)
        prefix = f"stage_{index:02d}"
        for key in ("frequencies_cycles_per_row", "total_power", "coherent_power",
                    "incoherent_power", "raw_mean_per_frame"):
            spectra[f"{prefix}_{key}"] = full[key]
        spectra[f"{prefix}_pts_s"] = pts[mask]
        results.append({
            "label": label, "window_s": [start, end], "frames": count,
            "spectrum_npz_prefix": prefix, "raw_mean": full["raw_mean"],
            "peaks": full["peaks"],
            "reference_component": {
                "period_rows": reference_period_rows,
                "total_rms_amplitude": float(ref["total_rms_amplitude"][0]),
                "coherent_amplitude": float(ref["coherent_amplitude"][0]),
                "incoherent_rms_amplitude": float(ref["incoherent_rms_amplitude"][0]),
            },
            "power_partition_max_abs_error": full["power_partition_max_abs_error"],
        })
    report = {
        "method": "spatial_v2; same historical windows; quadratic spatial detrend only; "
                  "Hann Fourier; total/coherent/incoherent power; no temporal mean subtraction",
        "stages": results,
        "units": {"frequency": "cycles_per_camera_row", "amplitude": "input_Y_code_units"},
        "pwm_hz": None, "at_least_2000_hz_verified": False,
        "limits": [
            "No original pixels re-decoded; provenance and ROI follow the supplied profile cache.",
            "Historical time-window alignment is retained, not independently calibrated.",
            "Static screen content can contribute peaks; inspect original flat-ROI frames.",
            "Quadratic detrend attenuates broad spatial components; inspect raw profiles separately.",
            "Spatial harmonics and total power alone do not certify physical PWM frequency.",
        ],
    }
    return report, spectra


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=Path, required=True, help="NPZ keys: profiles and pts_s")
    parser.add_argument("--analysis", type=Path, required=True, help="Old JSON containing stages")
    parser.add_argument("--output", type=Path, required=True, help="New JSON; must not exist")
    parser.add_argument("--spectra", type=Path, required=True, help="New full-spectrum NPZ; must not exist")
    parser.add_argument("--reference-period", type=float, default=93.43, help="Old component, in rows")
    args = parser.parse_args()
    all_paths = [args.profiles.resolve(), args.analysis.resolve(),
                 args.output.resolve(), args.spectra.resolve()]
    if len(set(all_paths)) != 4:
        parser.error("Input and output paths must all be distinct")
    if args.output.exists() or args.spectra.exists():
        parser.error("Output already exists; choose new names to preserve evidence")
    original = json.loads(args.analysis.read_text())
    with np.load(args.profiles, allow_pickle=False) as loaded:
        report, spectra = reanalyse(loaded["profiles"], loaded["pts_s"],
                                   original["stages"], args.reference_period)
    report["input_profiles"] = str(args.profiles)
    report["input_analysis"] = str(args.analysis)
    report["full_spectra_npz"] = str(args.spectra)
    with args.spectra.open("xb") as handle:
        np.savez_compressed(handle, **spectra)
    with args.output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(json_ready(report), ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"stages": len(report["stages"]), "output": str(args.output),
                      "spectra": str(args.spectra), "physical_hz_calibrated": False}))


if __name__ == "__main__":
    main()
