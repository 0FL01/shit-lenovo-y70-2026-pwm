#!/usr/bin/env python3
"""Compare sampled spatial-phase drift in archived stock 720p/4K/720p clips."""

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

import analyze as spatial


def timestamps(video: Path) -> np.ndarray:
    output = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "frame=best_effort_timestamp_time", "-of", "json",
         str(video)],
        check=True, capture_output=True, text=True, timeout=40,
    ).stdout
    pts = np.array([float(frame["best_effort_timestamp_time"])
                    for frame in json.loads(output)["frames"]])
    if pts.size < 215 or not np.isfinite(pts).all() or not (np.diff(pts) > 0).all():
        raise ValueError("Missing or non-monotonic video PTS")
    return pts


def analyze() -> dict:
    capture = json.loads(spatial.SOURCE.read_text())
    saved = json.loads((Path(__file__).with_name("analysis.json")).read_text())
    if ([clip["label"] for clip in capture["clips"]] != ["A1", "B", "A2"]
            or [item["label"] for item in saved["results"]] != ["A1", "B", "A2"]
            or "stockDBV3600 DC0/software120Hz" not in capture["scope"]):
        raise ValueError("Not the saved stock resolution-control series")
    records = []
    for clip, reference in zip(capture["clips"], saved["results"]):
        label = clip["label"]
        v, x, y, width, height, _ = spatial.GEOMETRY[label]
        video = spatial.ROOT / clip["video"]
        if (reference["roi_xywh_output"] != [x, y, width, height]
                or reference["video"] != clip["video"]
                or clip["video_metadata"]["avg_frame_rate"] != "30/1"
                or clip["dbv_at_end"] != "3600"
                or video.stat().st_size != clip["bytes"]):
            raise ValueError("Stored clip/ROI conditions changed")
        profile = spatial.decode(video, x, y, width, height).mean(axis=2)
        pts = timestamps(video)
        row = np.arange(height)
        trend = np.polynomial.legendre.legvander(np.linspace(-1, 1, height), 2)
        hann = np.hanning(height)
        q = 720 / (v * 93.43)
        basis = np.exp(-2j * np.pi * np.outer(row, q * np.arange(1, 4)))
        windows = []
        for first, last in spatial.WINDOWS:
            values = profile[first - 90:last - 89]
            times = pts[first:last + 1] - pts[first]
            uniform = np.arange(last - first + 1) / 30
            if values.shape != (75, height) or times.shape != (75,):
                raise ValueError("Wrong archived window")
            corrected = values - (trend @ np.linalg.lstsq(trend, values.T, rcond=None)[0]).T
            phasors = (corrected * hann) @ basis
            if not np.isfinite(phasors).all() or (np.abs(phasors) == 0).any():
                raise ValueError("Invalid spatial phase")
            phases = np.unwrap(np.angle(phasors), axis=0)
            components = []
            for h in range(3):
                fit = np.polyfit(uniform, phases[:, h], 1)
                components.append({
                    "image_harmonic_index": h + 1,
                    "phase_slope_cycles_per_nominal_second_not_pwm": float(fit[0] / (2 * np.pi)),
                    "single_slope_phase_coherence": float(np.abs(np.mean(
                        np.exp(1j * (phases[:, h] - np.polyval(fit, uniform)))))),
                    "mean_fourier_amplitude_Y_codes": float(
                        np.mean(2 * np.abs(phasors[:, h]) / hann.sum())),
                })
            windows.append({
                "frame_indices_inclusive": [first, last],
                "max_abs_encoded_pts_deviation_from_uniform_us": float(
                    np.max(np.abs(times - uniform)) * 1e6),
                "components": components,
            })
        records.append({"label": label, "output_height": v,
                        "q_cycles_per_output_row": q, "windows": windows})
    return {
        "scope": "Three saved STOCK 720p/4K/720p videos; no new device I/O",
        "source": str(spatial.SOURCE.relative_to(spatial.ROOT)),
        "spatial_reference": "analysis.json",
        "method": "Same Y ROI/75-frame windows as spatial comparison; degree-2 Legendre detrend, Hann, fixed q=h*720/(V*93.43); unwrap phase and fit versus nominal frame index /30",
        "records": records,
        "limits": [
            "Nominal 30fps phase drift aliases frequencies differing by integer multiples of 30Hz",
            "Encoded PTS regularity does not qualify sensor exposure timestamps",
            "Changing 4K mode is confounded with time; same-mode 720p return can also drift",
            "Spatial harmonics/phase are camera-image components, not established physical PWM harmonics or fundamental",
        ],
        "physical_pwm_hz": None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = analyze()
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
