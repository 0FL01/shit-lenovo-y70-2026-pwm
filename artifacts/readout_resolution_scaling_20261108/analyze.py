#!/usr/bin/env python3
"""Offline comparison of the same saved stock screen across 720p/4K/720p video."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "06-tools"))
from optical_spectrum import analyze_profiles  # noqa: E402


SOURCE = ROOT / "artifacts/pacman_readout_capture_20261106.json"
WINDOWS = ((90, 164), (115, 189), (140, 214))
GEOMETRY = {"A1": (720, 540, 190, 60, 500, 8192),
            "B": (2160, 1620, 570, 180, 1500, 32768),
            "A2": (720, 540, 190, 60, 500, 8192)}


def decode(video: Path, x: int, y: int, width: int, height: int) -> np.ndarray:
    filt = f"select='between(n,90,214)',crop={width}:{height}:{x}:{y},extractplanes=y"
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-noautorotate", "-i", str(video),
         "-map", "0:v:0", "-an", "-sn", "-vf", filt, "-fps_mode", "passthrough",
         "-pix_fmt", "gray", "-f", "rawvideo", "pipe:1"],
        check=True, capture_output=True, timeout=180,
    ).stdout
    if len(raw) != 125 * width * height:
        raise ValueError("Unexpected number of decoded Y-plane bytes")
    return np.frombuffer(raw, dtype=np.uint8).reshape(125, height, width)


def analyze() -> dict:
    capture = json.loads(SOURCE.read_text())
    if [c["label"] for c in capture["clips"]] != ["A1", "B", "A2"]:
        raise ValueError("Not the original 720p/4K/720p sequence")
    if "stockDBV3600 DC0/software120Hz" not in capture["scope"]:
        raise ValueError("Unknown panel conditions")
    results = []
    for clip in capture["clips"]:
        label = clip["label"]
        output_height, x, y, width, height, n_fft = GEOMETRY[label]
        if (clip["requested_size"] != [1280 if output_height == 720 else 3840, output_height]
                or clip["dbv_at_end"] != "3600" or clip["video_metadata"]["avg_frame_rate"] != "30/1"):
            raise ValueError("Camera or panel conditions changed")
        for meta in (clip["start_metadata"], clip["end_metadata"]):
            for key, expected in (("android.sensor.exposureTime", ["100000", "100000"]),
                                  ("android.sensor.sensitivity", ["6400", "6400"]),
                                  ("android.sensor.rollingShutterSkew", ["15047630"]),
                                  ("android.scaler.cropRegion", ["0 0 4080 3072"] * 2)):
                if meta[key] != expected:
                    raise ValueError(f"Camera metadata changed: {label}/{key}")
        video = ROOT / clip["video"]
        if video.stat().st_size != clip["bytes"]:
            raise ValueError("Saved video size changed")
        frames = decode(video, x, y, width, height)
        profiles = frames.mean(axis=2)
        windows = []
        for first, last in WINDOWS:
            profile = profiles[first - 90:last - 89]
            if profile.shape != (75, height):
                raise ValueError("Wrong central-window frame count")
            peaks = []
            for harmonic_band in (1, 2, 3):
                spectrum = analyze_profiles(
                    profile, n_fft=n_fft,
                    frequency_min=harmonic_band * 0.008 * 720 / output_height,
                    frequency_max=harmonic_band * 0.014 * 720 / output_height,
                    detrend_degree=2, peak_count=1,
                )
                peak = spectrum["peaks"][0]
                peaks.append({
                    "harmonic_band": harmonic_band,
                    "cycles_per_output_row": peak["frequency_cycles_per_row"],
                    "cycles_per_720p_equivalent_row": peak["frequency_cycles_per_row"] * output_height / 720,
                    "period_output_rows": peak["period_rows"],
                    "period_720p_equivalent_rows": peak["period_rows"] * 720 / output_height,
                    "rms_fourier_amplitude_Y_codes": peak["total_rms_amplitude"],
                    "at_band_edge": peak["at_frequency_boundary"],
                })
            windows.append({"frame_indices_inclusive": [first, last], "frames": 75,
                            "raw_mean_Y_codes": float(profile.mean()),
                            "peaks": peaks})
        results.append({"label": label, "video": clip["video"],
                        "output_size": clip["requested_size"],
                        "roi_xywh_output": [x, y, width, height],
                        "decoded_frames": 125, "saturated_fraction_selected_roi": float(np.mean(frames >= 254)),
                        "windows": windows})
    return {"source": str(SOURCE.relative_to(ROOT)),
            "method": "Original HEVC Y plane, fixed central 720p ROI and geometrically 3x 4K ROI; per-frame x-mean, degree-2 Legendre detrend, Hann FFT; band peaks at 1x/2x/3x candidate fine spatial q, 3 overlapping 75-frame windows",
            "recorded_conditions": "stock DBV3600/DC0/requested120, 100us/ISO6400; all three recorded rollingShutterSkew 15047630ns/cropRegion 4080x3072",
            "results": results,
            "limits": ["4K ROI assumes the recorded matching field of view scales by three; exact sensor mapping unverified",
                       "Encoded frame PTS are not certified exposure timestamps; window selection is based on start/hold logs, not per-frame sensor time",
                       "Peak interpolation is not extra resolution beyond the 500 or 1500-row record",
                       "Normalized spatial period is not camera row time, physical emission period, fundamental or optical PWM Hz"],
            "physical_pwm_hz": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = analyze()
    with args.output.open("x") as out:
        json.dump(result, out, indent=2, allow_nan=False)
        out.write("\n")
