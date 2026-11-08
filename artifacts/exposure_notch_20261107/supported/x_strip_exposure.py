#!/usr/bin/env python3
"""Offline broad-band x-strip check across saved stock exposure windows."""

import argparse
import json
from pathlib import Path
import subprocess

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
VIDEO = ROOT / "artifacts/optical/pacman_exposure_notch_supported_20261107.mp4"
SOURCE = ROOT / "artifacts/exposure_notch_20261107/supported/analysis.json"
PROFILES = Path("/home/stfu/.cache/opencode-tmp/opencode/exposure-notch-20261107-supported/profiles.npz")
STRIPS = {"left": (210, 270), "mid": (350, 410), "center": (540, 600),
          "right": (640, 700), "outside_screen": (900, 960)}
FREQUENCIES = (1 / (3 * 93.43), 1 / 256)


def analyze() -> dict:
    archived = json.loads(SOURCE.read_text())
    with np.load(PROFILES, allow_pickle=False) as saved:
        pts = saved["pts_s"]
        original = saved["profiles"]
        roi = saved["roi_xywh"]
    if (tuple(s["exposure_ns"] for s in archived["stages"])
            != (100000, 500000, 1000000, 1428571, 2000000, 100000)
            or original.shape != (5939, 500) or pts.shape != (5939,)
            or roi.tolist() != [540, 190, 60, 500]
            or not np.isfinite(original).all() or not (np.diff(pts) > 0).all()):
        raise ValueError("Archived exposure sweep changed")
    selected = []
    for stage in archived["stages"]:
        lo, hi = stage["window_s"]
        frames = np.flatnonzero((pts >= lo) & (pts <= hi))
        if (len(frames) != 75 or stage["frames"] != 75
                or frames[-1] - frames[0] != 74 or stage["iso"] != 1600):
            raise ValueError("Unexpected exposure window")
        selected.append(frames)

    selection = "+".join(f"between(n,{frames[0]},{frames[-1]})" for frames in selected)
    command = ["ffmpeg", "-v", "error", "-noautorotate", "-i", str(VIDEO),
               "-map", "0:v:0", "-an", "-sn", "-vf",
               f"select='{selection}',crop=780:500:180:190,extractplanes=y",
               "-fps_mode", "passthrough", "-pix_fmt", "gray", "-f", "rawvideo", "pipe:1"]
    raw = subprocess.run(command, check=True, capture_output=True, timeout=240).stdout
    if len(raw) != 6 * 75 * 500 * 780:
        raise ValueError("Unexpected video bytes or frame count")
    decoded = np.frombuffer(raw, np.uint8).reshape(6, 75, 500, 780)
    window = np.hanning(500)
    row = np.arange(500)
    bases = [window * np.exp(-2j * np.pi * q * row) * (2 / window.sum())
             for q in FREQUENCIES]
    records = []
    for degree in (1, 2, 3):
        trend = np.polynomial.legendre.legvander(np.linspace(-1, 1, 500), degree)
        for i, (stage, frames) in enumerate(zip(archived["stages"], selected)):
            center = decoded[i, :, :, 540 - 180:600 - 180].mean(axis=2)
            if not np.array_equal(center, original[frames]):
                raise ValueError("Original center ROI does not match archived profiles")
            strips = {name: decoded[i, :, :, x0 - 180:x1 - 180].mean(axis=2)
                      for name, (x0, x1) in STRIPS.items()}
            for mode in ("raw", "moving_only"):
                phasors = {}
                for name, strip in strips.items():
                    signal = strip if mode == "raw" else strip - strip.mean(axis=0)
                    residual = signal - (trend @ np.linalg.lstsq(trend, signal.T, rcond=None)[0]).T
                    phasors[name] = [residual @ basis for basis in bases]
                for j, q in enumerate(FREQUENCIES):
                    reference = phasors["center"][j]
                    if (np.abs(reference) == 0).any():
                        raise ValueError("Undefined center phase")
                    unit_reference = reference / np.abs(reference)
                    strips_out = {}
                    for name, components in phasors.items():
                        values = components[j]
                        if (np.abs(values) == 0).any():
                            raise ValueError("Undefined strip phase")
                        strips_out[name] = {
                            "mean_fourier_amplitude_Y_codes": float(np.abs(values).mean()),
                            "unit_phase_coherence_with_center": float(abs(np.mean(
                                values / np.abs(values) * np.conj(unit_reference)))),
                        }
                    records.append({"degree": degree, "phase": stage["phase"],
                                    "exposure_ns": stage["exposure_ns"], "mode": mode,
                                    "broad_cycles_per_output_row": q,
                                    "frames": len(frames), "strips": strips_out})
    return {"video": str(VIDEO), "source": str(SOURCE), "profiles": str(PROFILES),
            "window_frame_indices_inclusive": [[int(f[0]), int(f[-1])] for f in selected],
            "strips_x_original_video": STRIPS, "rows_y_original_video": [190, 690],
            "method": "Native limited-range Y, stage windows 6x75; raw or subtract each stage mean row profile (moving_only); degree1/2/3 Legendre detrend, Hann Fourier, two fixed broad q; per-frame unit-phase coherence to center",
            "records": records, "physical_pwm_hz": None,
            "limits": ["Moving-only subtraction discards stationary camera-image structure and is not total panel modulation",
                       "Camera Y codes vary nonlinearly with exposure; ratios are not calibrated optical modulation",
                       "Less than two cycles of broad band fit the 500-row ROI; UI, ISP and detrend can change the result",
                       "Offscreen strip has low signal; its phase resultant is not a positive optical control",
                       "No sensor row-time, panel-emission origin, low-frequency envelope or fundamental PWM Hz is established"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = analyze()
    with args.output.open("x") as out:
        json.dump(result, out, indent=2, allow_nan=False)
        out.write("\n")
