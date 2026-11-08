#!/usr/bin/env python3
"""Check screen-image geometry in saved 720p/4K/720p stock camera frames."""

import argparse
import json
from pathlib import Path
import subprocess

import numpy as np

import analyze as spatial


FRAMES = (125, 150, 175)


def selected_y(video: Path, height: int, width: int) -> np.ndarray:
    selection = "+".join(f"eq(n,{index})" for index in FRAMES)
    data = subprocess.run(
        ["ffmpeg", "-v", "error", "-noautorotate", "-i", str(video),
         "-map", "0:v:0", "-an", "-sn", "-vf",
         f"select='{selection}',extractplanes=y", "-fps_mode", "passthrough",
         "-pix_fmt", "gray", "-f", "rawvideo", "pipe:1"],
        capture_output=True, check=True, timeout=180,
    ).stdout
    if len(data) != len(FRAMES) * height * width:
        raise ValueError("Wrong number of selected native-Y frame bytes")
    return np.frombuffer(data, dtype=np.uint8).reshape(len(FRAMES), height, width)


def landmarks(frame: np.ndarray) -> dict:
    col = frame[190:690, :].mean(axis=0)
    grad_x = np.abs(np.diff(col))
    left = int(120 + np.argmax(grad_x[120:160]))
    right = int(730 + np.argmax(grad_x[730:760]))
    contrast = frame[:, 300:650].mean(axis=1) - frame[:, 900:1100].mean(axis=1)
    smooth = np.convolve(contrast, np.ones(21) / 21, mode="same")
    top = int(40 + np.argmax(np.diff(smooth)[40:70]))
    return {"screen_left_edge_output_x": left, "screen_right_edge_output_x": right,
            "screen_top_transition_output_y": top, "column_profile": col}


def analyze() -> dict:
    capture = json.loads(spatial.SOURCE.read_text())
    reference = json.loads((Path(__file__).with_name("analysis.json")).read_text())
    if ([item["label"] for item in capture["clips"]] != ["A1", "B", "A2"]
            or [item["label"] for item in reference["results"]] != ["A1", "B", "A2"]
            or "stockDBV3600 DC0/software120Hz" not in capture["scope"]):
        raise ValueError("Not the saved stock resolution-control clips")
    images = {}
    for clip, old in zip(capture["clips"], reference["results"]):
        name = clip["label"]
        height = spatial.GEOMETRY[name][0]
        width = 1280 if height == 720 else 3840
        path = spatial.ROOT / clip["video"]
        if (clip["requested_size"] != [width, height]
                or old["output_size"] != [width, height]
                or old["video"] != clip["video"]
                or path.stat().st_size != clip["bytes"]):
            raise ValueError("Saved video identity/geometry changed")
        frames = selected_y(path, height, width).astype(np.float64)
        if name == "B":
            frames = frames.reshape(len(FRAMES), 720, 3, 1280, 3).mean(axis=(2, 4))
        images[name] = frames
    results = []
    for label in ("A1", "B", "A2"):
        frames = images[label]
        for index, frame in zip(FRAMES, frames):
            point = landmarks(frame)
            reference_col = landmarks(images["A1"][FRAMES.index(index)])["column_profile"]
            col = point.pop("column_profile")
            if not np.isfinite(col).all() or not np.isfinite(reference_col).all():
                raise ValueError("Nonfinite column profile")
            corr = float(np.corrcoef(reference_col[90:950], col[90:950])[0, 1])
            if not np.isfinite(corr):
                raise ValueError("Undefined spatial correlation")
            results.append({"clip": label, "frame_index": index, **point,
                            "column_profile_correlation_to_A1_same_index": corr})
    return {
        "source": str(spatial.SOURCE.relative_to(spatial.ROOT)),
        "video_frames": list(FRAMES),
        "method": "Native HEVC Y plane; 4K area-reduced exactly 3x3 to 720p; x edges from columns averaged over y190:690; screen-top transition from smoothed screen-minus-background contrast; same-frame A1 x-profile correlation",
        "records": results,
        "limits": [
            "These are three selected static image frames, not a calibrated sensor or emission timing experiment",
            "Matching screen-image edges does not establish identical active-array row mapping or rolling readout time",
            "Temporal flicker bands and UI changes can affect profiles; fixed edge windows were chosen after initial inspection of frame 150, then applied unchanged to frames 125/150/175",
            "No physical PWM frequency or absence of low-frequency modulation is established",
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
