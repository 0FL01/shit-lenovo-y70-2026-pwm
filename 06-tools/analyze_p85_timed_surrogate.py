#!/usr/bin/env python3
"""OFFLINE timed factory-15 surrogate optics; unknown14 is never accepted.

Only this exact protocol permits an explicitly unmeasured middle C1. No fake
capture is synthesized. This program does not approve a stock review/candidate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import analyze_p85_optical as common

SCOPE = "p85-timed-stock-surrogate-v1"
SCHEMA = "p85-timed-surrogate-optical-v1"
C1_NOT_MEASURED = {"status": "not_measured",
                   "reason": "diagnostic omitted by timed-stock protocol"}
require = common.require


def bounds(snapshot):
    data = snapshot.get("host_capture_bounds", {})
    start, end = data.get("begin_monotonic"), data.get("end_monotonic")
    require(common.finite(start) and common.finite(end) and end >= start,
            "Missing/invalid monotonic camera call bounds")
    require(abs((common.utc(snapshot.get("host_call_end_utc")) -
                 common.utc(snapshot.get("host_call_start_utc"))) - (end-start)) < .05,
            "UTC/monotonic camera call disagreement")
    return start, end


def validate_run(run):
    """Fail before opening video; this is NOT the legacy run validator."""
    require(isinstance(run, dict) and run.get("scope") == SCOPE,
            "Exact timed-stock surrogate scope required")
    require(run.get("candidate_enabled") is False and run.get("candidate_attempts") == 0 and
            run.get("unknown_value_write_attempted") is False and
            run.get("unknown_register_writes") is False, "Unknown14 is disabled in this protocol")
    common.utc(run.get("finished_at_utc"))
    require(run.get("status") == "awaiting_optical_review" and
            all(run.get(k) is True for k in common.CLEAN_FLAGS), "Incomplete final cleanup/return")
    require(not any(run.get(k) for k in
                    ("error", "error_type", "cleanup_error_type", "camera_cleanup_error_type",
                     "camera_ui_cleanup_pending", "recovery_reboot_attempted",
                     "physical_ddic_recovery_unverified")) and run.get("cleanup_errors", []) == [],
            "Failure/recovery cannot qualify as completed timed stock")
    stages = run.get("stages", [])
    require([s.get("label") for s in stages] == ["baseline", "sham15", "return15"],
            "Exact factory-15 sequence required")
    require(run.get("register85_writes_attempted") == ["sham15", "return15"],
            "Unexpected writer attempts")
    writes = run.get("writes", [])
    require([w.get("stage") for w in writes] == ["sham15", "return15"] and
            all(w.get("standalone_callbacks") == 3 and w.get("native_and_wire_gates") is True
                for w in writes), "Missing exact factory writes/native gates")
    require(run.get("timed_stock_exploratory") is True and
            run.get("active_limit_seconds") == 37 and run.get("host_limit_seconds") == 45 and
            run.get("recovery_reserve_seconds") == 8 and run.get("timed_watchdog_seconds") == 60 and
            run.get("timed_watchdog_renewals") == 0 and
            run.get("candidate_watchdog") == "disarmed_after_verified_return_or_boot" and
            run.get("host_alarm_restored_before_cleanup") is True and
            run.get("explicit15_readback_and_stock_c1_verified") is True,
            "Missing exact timed-watchdog/disarm evidence")
    clock_keys = ("active_start_monotonic", "arm_seconds", "return_qualified_monotonic",
                  "disarm_seconds", "active_G_seconds")
    require(all(common.finite(run.get(k)) for k in clock_keys), "Missing active-window clock evidence")
    active, arm, returned, disarm, total = [run[k] for k in clock_keys]
    require(active >= 0 and 0 < arm < total < 37 and disarm > 0 and
            returned > active + arm and abs(total-(returned-active+disarm)) < .01,
            "Timed arm/return/disarm interval inconsistent or late")
    for write in writes:
        keys = ("started_monotonic", "dispatch_monotonic", "validated_monotonic")
        require(all(common.finite(write.get(k)) for k in keys), "Missing writer timing evidence")
        start, dispatch, validated = [write[k] for k in keys]
        require(active+arm <= start <= dispatch <= validated <= returned,
                "Writer outside verified armed-to-return interval")
    for stage in stages:
        require(stage.get("qualified") is True and stage.get("hold_seconds") == 4.5 and
                stage.get("observed_sensor_frames", 0) >= 120,
                "Stage control/full 4.5s hold/continuity not qualified")
        registers = ("p85",) if stage["label"] == "sham15" else ("p85", "c1")
        require(stage.get("p85", {}).get("data") == [21, 0, 0], "P85 must remain factory15")
        for register in registers:
            capture = stage.get(register, {})
            require(capture.get("framing_qualified") is True and
                    capture.get("cleanup_verified") is True and capture.get("native_dbv") == 3600,
                    "Missing qualified register/state/ESD evidence")
        if stage["label"] == "sham15":
            require(stage.get("c1") == C1_NOT_MEASURED and
                    "c1" not in stage.get("phase_seconds", {}),
                    "Middle C1 must be explicitly not measured, without data or invented duration")
        else:
            require(stage["c1"].get("data") == [0, 0, 96] and
                    common.finite(stage.get("phase_seconds", {}).get("c1")) and
                    stage["phase_seconds"]["c1"] > 0,
                    "Baseline/return C1 measurement is mandatory and must equal60")
            require("return_prequiet" not in stage, "Prequiet belongs only to the middle hold")
        markers = stage.get("hold_markers", {})
        require(isinstance(markers.get("begin"), str) and isinstance(markers.get("end"), str)
                and markers["begin"] != markers["end"], "Missing distinct hold markers")
        h0, h1 = stage.get("hold_start_monotonic"), stage.get("hold_end_monotonic")
        require(common.finite(h0) and common.finite(h1) and h1 > h0,
                "Missing monotonic hold bounds")
        start0, start1 = bounds(stage.get("camera_start", {}))
        end0, end1 = bounds(stage.get("camera_end", {}))
        require(h0 <= start0 <= start1 <= end0 <= end1 <= h1 and end0-start1 >= 4.5,
                "Camera/end metadata shortened the full optical wait")
        require(abs((common.utc(stage.get("hold_end_utc")) -
                     common.utc(stage.get("hold_start_utc"))) - (h1-h0)) < .05,
                "UTC/monotonic hold disagreement")
        offsets = [common.utc(stage["hold_start_utc"])-h0,
                   common.utc(stage["hold_end_utc"])-h1,
                   common.utc(stage["camera_start"]["host_call_start_utc"])-start0,
                   common.utc(stage["camera_start"]["host_call_end_utc"])-start1,
                   common.utc(stage["camera_end"]["host_call_start_utc"])-end0,
                   common.utc(stage["camera_end"]["host_call_end_utc"])-end1]
        require(max(offsets)-min(offsets) < .05,
                "UTC/monotonic offset changed across hold/camera boundaries")
    require(stages[0]["hold_end_monotonic"] <= active and
            active+arm <= stages[1]["hold_start_monotonic"] < returned and
            stages[2]["hold_start_monotonic"] >= active+total,
            "Baseline/middle/return holds contradict the active interval")
    middle = stages[1]
    prequiet = middle.get("return_prequiet", {})
    start, end = prequiet.get("started_monotonic"), prequiet.get("ended_monotonic")
    wait_begin = bounds(middle["camera_start"])[1]
    wait_end = wait_begin + 4.5
    end_camera_begin, end_camera_end = bounds(middle["camera_end"])
    require(common.finite(start) and common.finite(end) and
            wait_begin <= start <= end <= end_camera_begin and end-start >= 2,
            "Return prequiet must finish inside the hold before camera_end")
    expected = {"wait_seconds": max(0., wait_end-end),
                "overlap_seconds": max(0., min(end, wait_end)-max(start, wait_begin)),
                "overshoot_seconds": max(0., end-wait_end)}
    for key, value in expected.items():
        require(common.finite(prequiet.get(key)) and prequiet[key] >= 0 and
                abs(prequiet[key]-value) <= .005, "Inconsistent prequiet timing: " + key)
    quiet = prequiet.get("quiet_evidence", {})
    native = quiet.get("native_state", {})
    kernel = quiet.get("kernel_marker_bounds", {})
    require(kernel.get("clock") == "target kernel printk monotonic; not host/camera clock" and
            common.finite(kernel.get("begin_seconds")) and common.finite(kernel.get("end_seconds")) and
            kernel["end_seconds"]-kernel["begin_seconds"] >= 2,
            "Actual target prequiet marker interval shorter than 2s or missing")
    require(quiet.get("quiet_seconds") == 2 and
            isinstance(quiet.get("begin_marker"), str) and isinstance(quiet.get("end_marker"), str) and
            quiet["begin_marker"] != quiet["end_marker"] and
            native.get("native_actual_hz") == 120 and native.get("native_group") == 3,
            "Missing full qualified native return-prequiet evidence")
    verified = middle.get("hold_verified_monotonic")
    return_started = writes[1].get("started_monotonic")
    require(common.finite(verified) and common.finite(return_started) and
            middle["hold_end_monotonic"] >= end_camera_end and
            return_started >= verified >= middle["hold_end_monotonic"],
            "Return DSI started before completed hold verification")
    require(isinstance(run.get("video_bytes"), int) and run["video_bytes"] > 0,
            "Missing finalized video size")
    video = run.get("video_profile", {})
    require(video.get("codec") == "h264" and video.get("size") == [1280, 720] and
            video.get("audio_streams") == 0, "Unqualified original video")
    return stages


def select_windows(run, pts, **kwargs):
    stages = validate_run(run)
    return common.select_windows_from_stages(stages, run.get("recording_preflight", []), pts, **kwargs)


def c1_observations(stages):
    """Explicit measurement status; never substitute a neighbouring C1 value."""
    return [{"stage": s["label"], "status": "not_measured",
             "reason": C1_NOT_MEASURED["reason"]} if s["label"] == "sham15" else
            {"stage": s["label"], "status": "measured", "data": s["c1"]["data"],
             "native_dbv": s["c1"]["native_dbv"]} for s in stages]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("video", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--review", type=Path)
    parser.add_argument("--profiles", type=Path)
    parser.add_argument("--preview-dir", type=Path)
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--snapshot-age-seconds", type=float, default=.25)
    parser.add_argument("--binding-frames", type=int, default=2)
    args = parser.parse_args(argv)
    require(not args.output.exists(), "Refusing to overwrite JSON")
    require(args.plan or (args.profiles is not None and not args.profiles.exists()),
            "Analysis requires new profile output")
    require(not (args.review and args.preview_dir), "Preview and analysis are separate steps")
    raw = args.run.read_bytes()
    run = json.loads(raw)
    stages = validate_run(run)  # BEFORE stat, ffprobe, decode or screenshot read.
    require(args.video.stat().st_size == run["video_bytes"], "Finalized video size mismatch")
    pts, stream = common.validate_pts(common.probe_video(args.video))
    options = dict(frames=args.frames, snapshot_age_seconds=args.snapshot_age_seconds,
                   binding_frames=args.binding_frames)
    windows = select_windows(run, pts, **options)
    try:
        stronger = {"snapshot_max_age_seconds": max(.5, args.snapshot_age_seconds),
                    "encoder_binding_ambiguity_frames": max(3, args.binding_frames),
                    "windows": select_windows(run, pts, frames=args.frames,
                        snapshot_age_seconds=max(.5, args.snapshot_age_seconds),
                        binding_frames=max(3, args.binding_frames))}
    except common.OpticalError:
        stronger = {"qualified": False, "reason": "Stronger timing budgets leave no qualified window"}
    digest = hashlib.sha256(raw).hexdigest()
    result = {"schema": SCHEMA, "scope": SCOPE, "mode": "window_plan" if args.plan else "analysis",
              "source_run_sha256": digest, "source_video_bytes": run["video_bytes"],
              "decoded_frame_count": len(pts), "stream": stream, "windows": windows,
              "timing_assumptions": {"snapshot_max_age_seconds": args.snapshot_age_seconds,
                                     "encoder_binding_ambiguity_frames": args.binding_frames,
                                     "minimum_edge_margin_seconds": .25},
              "stronger_timing_sensitivity": stronger,
              "c1_observations": c1_observations(stages),
              "middle_c1_measurement": "not_measured; protocol omission, not a zero or inferred value",
              "full_middle_wait_and_prequiet_timing_validated": True,
              "observed_active_G_seconds": run["active_G_seconds"],
              "timed_window_limit": "Observed factory15 run only, not a bound for future return or candidate14",
              "physical_pwm_hz": None, "stock_optics_restored": None,
              "sham_optics_unchanged": None, "lead_approved": False,
              "candidate_enabled": False,
              "limits": ["Factory15 timed surrogate only; no candidate14 outcome or permission.",
                         "Timing envelopes are conditional, not per-exposure sensor/MP4 binding.",
                         "No physical Hz, modulation-depth, comfort, or general C1-count inference.",
                         "Encoded Y includes ISP, codec, black offset and nonlinearity.",
                         "Fine/6 is a spatial diagnostic; short ROI limits broad-component inference.",
                         "Neighbouring ROIs and frame blocks are not independent experiments."]}
    if args.plan:
        if args.preview_dir:
            common.inspect_frames(args.video, windows, args.preview_dir)
        result["review_template"] = {
            "schema": "p85-optical-roi-review-v1", "run_sha256": digest,
            "video_bytes": run["video_bytes"], "decoded_frame_count": len(pts),
            "reviewed_frames": {w["stage"]: w["review_frames"] for w in windows},
            "native_y_noautorotate_inspected": False, "flat_screen_content_verified": False,
            "fixed_geometry_verified": False, "timestamp_margins_reviewed": False,
            "rois_xywh": None, "baseline_fine_search_cycles_per_row": None}
    else:
        review = json.loads(args.review.read_text())
        rois, band = common.validate_review(review, run_sha256=digest,
            video_bytes=run["video_bytes"], frame_count=len(pts), windows=windows)
        findings, arrays = common.analyze(args.video, windows, rois, band)
        result.update(findings, rois_xywh=rois, full_spatial_spectrum_cycles_per_row=[0, .5],
                      normalization="RMS Y coefficient / (mean Y - 16), not optical modulation depth.",
                      q_selection="Baseline-only fine q, fixed in every stage.",
                      detrend="Spatial per frame, None/1/2/3; temporal mean never removed.")
        arrays["pts"] = pts
        with args.profiles.open("xb") as handle:
            np.savez_compressed(handle, **arrays)
    require(args.run.read_bytes() == raw and args.video.stat().st_size == run["video_bytes"],
            "Completed run/video changed during analysis")
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print("Offline timed-stock result written; middle C1 not measured, physical PWM Hz unknown.")


if __name__ == "__main__":
    main()
