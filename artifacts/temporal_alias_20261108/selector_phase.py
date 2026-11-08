#!/usr/bin/env python3
"""Offline q93 phase comparison of the saved stock/A9-only/9D-only trial."""

import argparse
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PROFILES = Path(
    "/home/stfu/.cache/opencode-tmp/opencode/dsi-selector-split-20261107/analysis-profiles-spatial-v2.npz"
)
ANALYSIS = ROOT / "artifacts/dsi_selector_split_20261107/analysis_spatial_v2.json"
LABELS = ("baseline", "a9_only", "return_a9_only", "9d_only", "return_9d_only")


def analyze():
    with np.load(PROFILES, allow_pickle=False) as saved:
        profiles = saved["profiles"]
        pts = saved["pts_s"]
        roi = saved["roi_xywh"]
    source = json.loads(ANALYSIS.read_text())
    stages = source["stages"]
    if (
        profiles.shape != (2679, 500)
        or pts.shape != (2679,)
        or roi.tolist() != [540, 190, 60, 500]
        or not np.isfinite(profiles).all()
        or not np.isfinite(pts).all()
        or not (np.diff(pts) > 0).all()
        or tuple(s["label"] for s in stages) != LABELS
    ):
        raise ValueError("selector-series source/ROI/stages changed")
    period = 93.43  # Same explicitly fixed q as analyze_dsi_redraw.py:148.
    if not np.isclose(stages[0]["dominant_period_px"], 93.0909090909091, rtol=0, atol=1e-12):
        raise ValueError("baseline spatial period changed")
    rows = np.arange(500)
    trend = np.polynomial.legendre.legvander(np.linspace(-1, 1, 500), 2)
    window = np.hanning(500)
    basis = np.exp(-2j * np.pi * rows / period) * window
    records = []
    for stage in stages:
        lo, hi = stage["window_s"]
        chosen = np.flatnonzero((pts >= lo) & (pts <= hi))
        if len(chosen) != 75 or stage["frames"] != 75:
            raise ValueError("selector stage frames changed")
        values = profiles[chosen]
        values = values - (trend @ np.linalg.lstsq(trend, values.T, rcond=None)[0]).T
        phasors = (values * basis).sum(axis=1) * (2 / window.sum())
        if (np.abs(phasors) == 0).any():
            raise ValueError("undefined fine-component phase")
        if not np.isclose(
            np.sqrt(np.mean(np.abs(phasors) ** 2)),
            stage["q93_total_rms_Y_codes"],
            rtol=1e-8,
            atol=1e-8,
        ):
            raise ValueError("q93 reference/window no longer matches archived analysis")
        units = phasors / np.abs(phasors)
        uniform = np.arange(len(chosen)) / 30
        beat = np.polyfit(uniform, np.unwrap(np.angle(units)), 1)[0] / (2 * np.pi)
        coherence = abs(np.mean(units * np.exp(-2j * np.pi * beat * uniform)))
        records.append({
            "stage": stage["label"],
            "first_frame_index": int(chosen[0]),
            "frames": len(chosen),
            "spatial_q93_rms_Y_codes_existing": stage["q93_total_rms_Y_codes"],
            "mean_q93_fourier_amplitude_Y_codes": float(np.abs(phasors).mean()),
            "min_q93_fourier_amplitude_Y_codes": float(np.abs(phasors).min()),
            "frame_index_phase_slope_cycles_per_nominal_second": float(beat),
            "unit_phase_coherence_at_fitted_slope": float(coherence),
            "max_abs_encoded_pts_jitter_vs_30fps_us": float(
                np.max(np.abs((pts[chosen] - pts[chosen[0]]) - uniform)) * 1e6
            ),
        })
    return {
        "scope": "Historical stock→A9-only→stock→9D-only→stock; offline optical archive only",
        "input": str(PROFILES),
        "q_reference_period_output_rows": period,
        "method": "degree-2 Legendre detrend; Hann; normalized 2/sum(window); fixed spatial q=1/93.43 as original q93 RMS; nominal frame-index/30 phase slope",
        "stages": records,
        "limits": [
            "Suppressed A9-only fine amplitude makes its phase-fit unstable",
            "Nominal 30fps phase slope aliases at 30Hz and cannot establish fundamental PWM",
            "The 9D-only phase slope persists after return to stock; temporal drift is a confounder",
        ],
        "physical_pwm_hz": None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    result = analyze()
    with parser.parse_args().output.open("x") as out:
        json.dump(result, out, indent=2, ensure_ascii=False)
        out.write("\n")
