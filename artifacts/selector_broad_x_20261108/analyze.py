#!/usr/bin/env python3
"""Offline x-strip confinement of the moving broad band in saved selector video."""

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
STRIPS = {"left": (210, 270), "mid": (350, 410), "center": (540, 600),
          "right": (640, 700), "outside_screen": (900, 960)}
Q_BROAD = (1 / 93.43 / 3, 1 / 256)
LABELS = ("baseline", "a9_only", "return_a9_only", "9d_only", "return_9d_only")


def analyze():
    archived = json.loads(SOURCE.read_text())
    with np.load(PROFILES, allow_pickle=False) as saved:
        pts = saved["pts_s"]
        original_profiles = saved["profiles"]
        roi = saved["roi_xywh"]
    if (tuple(s["label"] for s in archived["stages"]) != LABELS
            or original_profiles.shape != (2679, 500) or pts.shape != (2679,)
            or roi.tolist() != [540, 190, 60, 500]
            or not np.isfinite(original_profiles).all() or not (np.diff(pts) > 0).all()):
        raise ValueError("Saved video analysis/ROI changed")
    selected = []
    for stage in archived["stages"]:
        lo, hi = stage["window_s"]
        frames = np.flatnonzero((pts >= lo) & (pts <= hi))
        if len(frames) != stage["frames"] or len(frames) != 75 or frames[-1] - frames[0] != 74:
            raise ValueError("Unexpected selector window")
        selected.append(frames)

    # Decode only the original preselected frames. No video rewrites or new capture.
    filter_select = "+".join(f"between(n,{f[0]},{f[-1]})" for f in selected)
    args = ["ffmpeg", "-v", "error", "-noautorotate", "-i", str(VIDEO),
            "-map", "0:v:0", "-an", "-sn", "-vf",
            f"select='{filter_select}',crop=780:500:180:190,extractplanes=y",
            "-fps_mode", "passthrough", "-pix_fmt", "gray", "-f", "rawvideo", "pipe:1"]
    raw = subprocess.run(args, check=True, capture_output=True, timeout=180).stdout
    if len(raw) != 5 * 75 * 500 * 780:
        raise ValueError("Unexpected decoded frame count/size")
    decoded = np.frombuffer(raw, np.uint8).reshape(5, 75, 500, 780)

    rows = np.arange(500)
    window = np.hanning(500)
    bases = [(window * np.exp(-2j * np.pi * q * rows) * (2 / window.sum()))
             for q in Q_BROAD]
    records = []
    for degree in (1, 2, 3):
        trend = np.polynomial.legendre.legvander(np.linspace(-1, 1, 500), degree)
        for i, (stage, selected_frames) in enumerate(zip(archived["stages"], selected)):
            source_center = original_profiles[selected_frames]
            center = decoded[i, :, :, 540 - 180:600 - 180].mean(axis=2)
            if not np.array_equal(center, source_center):
                raise ValueError("Decoded original frames do not match archived ROI")
            strips = {name: decoded[i, :, :, x0 - 180:x1 - 180].mean(axis=2)
                      for name, (x0, x1) in STRIPS.items()}
            for method in ("raw", "moving_only"):
                signals = {}
                for name, image in strips.items():
                    image = image if method == "raw" else image - image.mean(axis=0)
                    residual = image - (trend @ np.linalg.lstsq(trend, image.T, rcond=None)[0]).T
                    signals[name] = [residual @ basis for basis in bases]
                for j, q in enumerate(Q_BROAD):
                    control = signals["center"][j]
                    if (np.abs(control) == 0).any():
                        raise ValueError("Undefined center phase")
                    unit_control = control / np.abs(control)
                    measured = {}
                    for name, phasors in signals.items():
                        phasor = phasors[j]
                        if (np.abs(phasor) == 0).any():
                            raise ValueError("Undefined strip phase")
                        measured[name] = {
                            "mean_fourier_amplitude_Y_codes": float(np.abs(phasor).mean()),
                            "unit_phase_coherence_with_center": float(abs(np.mean(
                                phasor / np.abs(phasor) * np.conj(unit_control)))),
                        }
                    records.append({"degree": degree, "stage": stage["label"],
                                    "method": method, "broad_cycles_per_output_row": q,
                                    "frames": len(selected_frames), "strips": measured})
    return {"video": str(VIDEO), "source": str(PROFILES),
            "scope": "Only already captured selector-split stock/A9/stock/9D/stock; original exact 5×75 video frames",
            "strips_x_original_video": STRIPS, "rows_y_original_video": [190, 690],
            "method": "Original limited-range Y; per-strip mean across 60 x-pixels, raw or subtract each stage mean 500-row profile (moving_only), Legendre detrend degrees1/2/3, Hann, spatial Fourier at two fixed broad frequencies; framewise unit-phase coherence to center",
            "record_count": len(records), "records": records,
            "limits": ["The moving_only measurement deliberately removes stationary stripes; it does not replace total optical power or the A9 q93 baseline",
                       "Less than two broad cycles across the 500-row crop; UI and detrend can affect phases",
                       "Off-screen strip can be dominated by noise; a high unit-phase resultant there is not evidence of equally strong illumination",
                       "Row-global camera/ISP variation, scene reflection and panel scanning remain alternative sources; no physical row time or PWM fundamental is identified"],
            "physical_pwm_hz": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = analyze()
    with args.output.open("x") as out:
        json.dump(result, out, indent=2, allow_nan=False)
        out.write("\n")
