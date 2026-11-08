#!/usr/bin/env python3
"""Offline HEVC keyframe control for the archived selector-split optical trace."""

import argparse
import json
from pathlib import Path
import subprocess

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
VIDEO = ROOT / "artifacts/optical/pacman_dsi_selector_split_20261107.mp4"
SOURCE = ROOT / "artifacts/dsi_selector_split_20261107/analysis_spatial_v2.json"
PROFILES = Path(
    "/home/stfu/.cache/opencode-tmp/opencode/dsi-selector-split-20261107/analysis-profiles-spatial-v2.npz"
)
LABELS = ("baseline", "a9_only", "return_a9_only", "9d_only", "return_9d_only")
FREQUENCIES = {"broad": 1 / (3 * 93.43), "fine": 1 / 93.43}


def analyze():
    archived = json.loads(SOURCE.read_text())
    with np.load(PROFILES, allow_pickle=False) as data:
        profiles, pts = data["profiles"], data["pts_s"]
        roi = data["roi_xywh"]
    if (profiles.shape != (2679, 500) or pts.shape != (2679,)
            or roi.tolist() != [540, 190, 60, 500]
            or tuple(s["label"] for s in archived["stages"]) != LABELS
            or not np.isfinite(profiles).all() or not (np.diff(pts) > 0).all()):
        raise ValueError("Archived video profiles/stages changed")
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "frame=key_frame,pict_type,best_effort_timestamp_time", "-of", "json", str(VIDEO)],
        check=True, capture_output=True, text=True, timeout=90,
    )
    frames = json.loads(probe.stdout)["frames"]
    if len(frames) != len(profiles) or any(f.get("pict_type") not in ("I", "P") for f in frames):
        raise ValueError("Unexpected HEVC frame types/count")
    keys = np.array([f["key_frame"] == 1 for f in frames])
    key_indices = np.flatnonzero(keys)
    if (len(key_indices) != 112 or not np.array_equal(key_indices, np.arange(0, 2679, 24))
            or any((f["pict_type"] == "I") != bool(k) for f, k in zip(frames, keys))):
        raise ValueError("Expected 24-frame periodic I/P sequence")
    frame_pts = np.array([float(f["best_effort_timestamp_time"]) for f in frames])
    offset = frame_pts - pts
    if not np.isfinite(offset).all() or np.ptp(offset) > 0.000002:
        raise ValueError("Encoded frame index and archived profiles are misaligned")

    rows = np.arange(500)
    window = np.hanning(500)
    trend = np.polynomial.legendre.legvander(np.linspace(-1, 1, 500), 2)
    basis = {name: window * np.exp(-2j * np.pi * q * rows) * (2 / window.sum())
             for name, q in FREQUENCIES.items()}
    records = []
    for stage in archived["stages"]:
        lo, hi = stage["window_s"]
        selected = np.flatnonzero((pts >= lo) & (pts <= hi))
        if (len(selected) != stage["frames"] or len(selected) != 75
                or selected[-1] - selected[0] != 74):
            raise ValueError("Unexpected preselected stage window")
        signal = profiles[selected]
        signal = signal - signal.mean(axis=0)  # Same moving-only diagnostic as x-strip control.
        residual = signal - (trend @ np.linalg.lstsq(trend, signal.T, rcond=None)[0]).T
        interior = selected[1:-1]
        for name, base in basis.items():
            phasor = residual @ base
            interpolation_error = np.abs(phasor[1:-1] - (phasor[:-2] + phasor[2:]) / 2)
            if not np.isfinite(interpolation_error).all():
                raise ValueError("Undefined Fourier interpolation error")
            phases = [float(np.median(interpolation_error[interior % 24 == shift]))
                      for shift in range(24)]
            i_error = interpolation_error[keys[interior]]
            p_error = interpolation_error[~keys[interior]]
            if len(i_error) != int(keys[interior].sum()) or len(i_error) < 3:
                raise ValueError("Insufficient internal keyframes")
            records.append({
                "stage": stage["label"], "component": name,
                "selected_inclusive_frame_range": [int(selected[0]), int(selected[-1])],
                "interior_I_frames": interior[keys[interior]].tolist(),
                "interior_I_count": len(i_error), "interior_P_count": len(p_error),
                "median_local_phasor_interpolation_error_I_Y": float(np.median(i_error)),
                "median_local_phasor_interpolation_error_P_Y": float(np.median(p_error)),
                "actual_I_phase_rank_among_24": 1 + sum(v > phases[0] for v in phases[1:]),
                "all_24_GOP_phase_median_errors_Y": phases,
            })
    return {
        "source_video": str(VIDEO), "source_profiles": str(PROFILES),
        "scope": "Saved selector stock/A9/stock/9D/stock windows; no new device capture",
        "camera_video_pts_minus_archived_pts_s": float(np.median(offset)),
        "encoded_frame_types": {"I": len(key_indices), "P": len(frames) - len(key_indices), "B": 0},
        "keyframe_stride_frames": 24, "records": records,
        "method": "Center ROI original Y; per-stage moving-only subtraction, degree-2 spatial Legendre detrend, Hann Fourier; |z_i-(z_{i-1}+z_{i+1})/2| at HEVC I and P frames. The 24 phase medians shift the keyframe-label position, not decoded pixel data.",
        "limits": ["A negative I-frame discontinuity does not exclude inter-frame codec/ISP artefacts",
                   "Near 1.3 cycles/s sampled temporal alias is close to 30/24=1.25 Hz GOP cadence, so fixed GOP-phase metrics can be confounded",
                   "Decoded camera Y and encoded PTS do not establish physical PWM, sensor timestamps, or low-frequency-envelope absence"],
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
