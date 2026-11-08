#!/usr/bin/env python3
"""Offline exact-replay check and diagnostic summaries. No device operations."""
import argparse
import json
from pathlib import Path
import numpy as np


def check(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-json", type=Path, required=True)
    parser.add_argument("--replay-profiles", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    check(not args.output.exists(), "Refusing to overwrite validation")
    here = Path(__file__).resolve().parent
    source = here / "optical_analysis.json"
    check(source.read_bytes() == args.replay_json.read_bytes(), "JSON replay not byte exact")
    report = json.loads(source.read_text())
    original = np.load(here / "optical_profiles.npz", allow_pickle=False)
    replay = np.load(args.replay_profiles, allow_pickle=False)
    check(set(original.files) == set(replay.files), "NPZ array names differ")
    for key in original.files:
        check(np.array_equal(original[key], replay[key]), "NPZ replay differs: " + key)
    q = original["q"]
    check(q[0] == 0 and q[-1] == .5, "Full spatial Nyquist range missing")
    pts_step = np.diff(original["pts"])
    pad_extra = float(pts_step.max())
    margins = [{
        "stage": w["stage"],
        "primary_window_stronger_age_binding_leading_seconds":
            w["conditional_leading_margin_seconds"] - .25 - pad_extra,
        "primary_window_stronger_age_binding_trailing_seconds":
            w["conditional_trailing_margin_seconds"] - pad_extra}
        for w in report["windows"]]
    check(all(min(x["primary_window_stronger_age_binding_leading_seconds"],
                  x["primary_window_stronger_age_binding_trailing_seconds"]) >= .25
              for x in margins), "Primary frames fail the stronger timing budgets")
    comparisons = []
    broad_blocks = []
    for roi in report["rois_xywh"]:
        entries = [m for m in report["measurements"] if m["roi"] == roi]
        base = entries[0]
        a = np.sqrt(original[f"{roi}_baseline_total_power"]) / (base["mean_y"] - 16)
        for entry in entries:
            broad_blocks.append({"roi": roi, "stage": entry["stage"],
                                 "broad_20_frame_blocks":
                                     [b["normalized_rms"][0] for b in entry["blocks"]],
                                 "fine_20_frame_blocks":
                                     [b["normalized_rms"][2] for b in entry["blocks"]]})
        for entry in entries[1:]:
            stage = entry["stage"]
            ratio = next(x["over_baseline"] for x in report["ratios"]
                         if x["roi"] == roi and x["stage"] == stage and x["degree"] == "2")
            b = np.sqrt(original[f"{roi}_{stage}_total_power"]) / (entry["mean_y"] - 16)
            diff = b - a
            comparisons.append({
                "roi": roi, "stage": stage, "mean_y_over_baseline": entry["mean_y"] / base["mean_y"],
                "fine_normalized_over_baseline": ratio[2],
                "mean_and_fine_within_predeclared_5_percent":
                    abs(entry["mean_y"] / base["mean_y"] - 1) <= .05 and abs(ratio[2] - 1) <= .05,
                "broad_fixed_q_over_baseline": ratio[0],
                "normalized_total_amplitude_spectrum_relative_l2":
                    float(np.linalg.norm(diff) / np.linalg.norm(a)),
                "maximum_absolute_normalized_spectral_difference": float(abs(diff).max()),
                "q_of_maximum_spectral_difference": float(q[abs(diff).argmax()]),
                "tail_01_to_05_max_normalized_amplitude": float(b[q >= .1].max())})
    result = {
        "schema": "p85-optical-replay-validation-v1",
        "json_full_decode_replay_byte_exact": True,
        "npz_all_arrays_full_decode_replay_exact": True,
        "checked_npz_arrays": len(original.files),
        "pts_step_min_max_seconds": [float(pts_step.min()), float(pts_step.max())],
        "primary_frames_remain_inside_stronger_05_second_3_frame_budget": margins,
        "comparisons": comparisons,
        "frame_block_diagnostics": broad_blocks,
        "interpretation": "Fine-pattern/mean-Y reproducibility is a limited diagnostic pass. "
                          "Full-spectrum identity and broad-component equivalence are not established.",
        "physical_pwm_hz": None, "stock_optics_restored": None,
        "sham_optics_unchanged": None, "lead_approved": False}
    with args.output.open("x") as file:
        json.dump(result, file, indent=2, allow_nan=False)
        file.write("\n")
    print("Exact full-decode replay passed; no optical equivalence or candidate approval granted.")


if __name__ == "__main__":
    main()
