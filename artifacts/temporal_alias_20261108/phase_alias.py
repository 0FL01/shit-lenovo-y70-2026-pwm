#!/usr/bin/env python3
"""Offline phase/PTS alias check on the saved stock exposure-notch profiles."""

import argparse
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PROFILES = Path(
    "/home/stfu/.cache/opencode-tmp/opencode/exposure-notch-20261107-supported/profiles.npz"
)
ANALYSIS = ROOT / "artifacts/exposure_notch_20261107/supported/analysis.json"


def analyze():
    with np.load(PROFILES, allow_pickle=False) as saved:
        frames = saved["profiles"]
        pts = saved["pts_s"]
        roi = saved["roi_xywh"]
    stages = json.loads(ANALYSIS.read_text())["stages"]
    if (
        frames.shape != (5939, 500)
        or pts.shape != (5939,)
        or roi.tolist() != [540, 190, 60, 500]
        or not np.isfinite(frames).all()
        or not np.isfinite(pts).all()
        or not (np.diff(pts) > 0).all()
        or len(stages) != 6
    ):
        raise ValueError("saved stock input/ROI/timebase changed")
    period = 93.43
    rows = np.arange(500)
    trend = np.polynomial.legendre.legvander(np.linspace(-1, 1, 500), 2)
    basis = np.exp(-2j * np.pi * np.outer(rows, np.arange(1, 4) / period))
    output = []
    for stage in (stages[0], stages[5]):
        if stage["exposure_ns"] != 100000 or stage["reference_period_rows"] != period:
            raise ValueError("100-us stock control/period changed")
        start, end = stage["window_s"]
        chosen = np.flatnonzero((pts >= start) & (pts <= end))
        if len(chosen) != 75 or stage["frames"] != 75:
            raise ValueError("control window changed")
        values = frames[chosen]
        values = values - (trend @ np.linalg.lstsq(trend, values.T, rcond=None)[0]).T
        phasors = (values * np.hanning(500)) @ basis
        if (np.abs(phasors) == 0).any():
            raise ValueError("undefined phase")
        seconds = pts[chosen] - pts[chosen[0]]
        uniform = np.arange(len(chosen)) / 30
        beat = np.polyfit(uniform, np.unwrap(np.angle(phasors[:, 0])), 1)[0] / (2 * np.pi)
        unit = phasors[:, 0] / np.abs(phasors[:, 0])

        def coherence(frequency):
            return float(np.abs(np.mean(unit * np.exp(-2j * np.pi * frequency * seconds))))

        output.append({
            "stage": stage["phase"],
            "frames": len(chosen),
            "exposure_ns": stage["exposure_ns"],
            "frame_index_phase_beat_hz_not_physical_pwm": float(beat),
            "harmonic_phase_slopes_per_second": [
                float(np.polyfit(uniform, np.unwrap(np.angle(phasors[:, i])), 1)[0] / (2 * np.pi))
                for i in range(3)
            ],
            "max_abs_pts_deviation_from_uniform_us": float(np.max(np.abs(seconds - uniform)) * 1e6),
            "coherence_at_30hz_aliases_not_frequency_evidence": {
                str(add): coherence(beat + add) for add in (0, 30, 720, 1440, 2160, 2880)
            },
        })
    return {
        "scope": "Saved STOCK Pacman camera profiles; no device activity or absolute PWM inference",
        "source": str(PROFILES),
        "method": "degree-2 Legendre detrend; Hann; q=harmonics/93.43 output rows; 75-frame controls; frame-index phase fit and encoded-PTS coherence",
        "controls": output,
        "limits": [
            "30 fps samples alias temporal frequencies separated by 30 Hz",
            "Encoded PTS deviation is not qualified as sensor exposure timestamp jitter",
            "Spatial harmonics need not equal physical emission harmonics or the fundamental",
        ],
        "physical_pwm_hz": None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = analyze()
    with args.output.open("x") as out:
        json.dump(result, out, indent=2, ensure_ascii=False)
        out.write("\n")
