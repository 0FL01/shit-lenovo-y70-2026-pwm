"""Offline AA full-table acquisition and optical admission. Never authorizes hardware.
Original P85 validators and numerical analysis are unchanged.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import aa_video_validation as media
from pathlib import Path
import numpy as np
import analyze_p85_optical as common
from aa_acquisition_validation import (ALGORITHM,QUALIFICATION_SCHEMA,canonical_sha,validate_stock_qualification,require,SCHEMA,ACQUISITION_SCHEMA,SCOPES,HASHES,SELECTORS,CLEAN_FLAGS,validate_acquisition,validate_run)

def select_windows(run,pts,**kwargs):
    return common.select_windows_from_stages(validate_run(run),run.get("recording_preflight",[]),pts,**kwargs)

def c1_observations(stages):
    return [{"stage":s["label"],"status":"measured","data":s["c1"]["data"],
             "native_dbv":s["c1"]["native_dbv"]} for s in stages]

def validate_review(review, *, run_sha256, video_bytes, frame_count, windows):
    require(review.get("schema") == "aa-threshold-roi-review-v1" and
            review.get("run_sha256") == run_sha256 and review.get("video_bytes") == video_bytes and
            review.get("decoded_frame_count") == frame_count,
            "ROI review not bound to this completed run/video")
    require(review.get("native_y_noautorotate_inspected") is True and
            review.get("flat_screen_content_verified") is True and
            review.get("fixed_geometry_verified") is True and
            review.get("timestamp_margins_reviewed") is True,
            "Fresh native ROI/timing inspection missing")
    require(review.get("reviewed_frames") == {w["stage"]: w["review_frames"] for w in windows},
            "Inspect first/middle/last selected native frame for every stage")
    rois = review.get("rois_xywh", {})
    require(set(rois) == {"main", "left", "right"}, "Three explicit screen ROIs required")
    for rect in rois.values():
        require(isinstance(rect, list) and len(rect) == 4 and
                all(isinstance(v, int) and not isinstance(v, bool) for v in rect), "Bad ROI")
        x, y, width, height = rect
        require(0 <= x < x + width <= 1280 and 0 <= y < y + height <= 720 and
                width >= 20 and height >= 300, "ROI outside frame or too small")
    require(len({(v[1], v[3]) for v in rois.values()}) == 1, "ROI vertical geometry differs")
    ordered = sorted(rois.values())
    require(all(a[0] + a[2] <= b[0] for a, b in zip(ordered, ordered[1:])),
            "ROI strips overlap")
    band = review.get("baseline_fine_search_cycles_per_row")
    require(isinstance(band, list) and len(band) == 2 and all(common.finite(x) for x in band) and
            .006 < band[0] < band[1] < .1, "Explicit baseline-only fine search band required")
    return rois, band


def aa_contrasts(findings):
    """Descriptive ratios to BOTH controls, with no threshold/return approval."""
    output=[]
    for roi in ("main","left","right"):
        selected={m["stage"]:m for m in findings["measurements"] if m["roi"]==roi}
        if "aa10" not in selected: continue
        for degree in ("None","1","2","3"):
            value=selected["aa10"]["degrees"][degree]["normalized_rms"]
            output.append({"roi":roi,"degree":degree,
                "over_baseline":common.ratio(value,selected["baseline"]["degrees"][degree]["normalized_rms"]),
                "over_return_stock":common.ratio(value,selected["return_stock"]["degrees"][degree]["normalized_rms"])})
    return output

def stock_qualification(acquisition_raw,analysis_raw):
    """Freeze a completed AA stock diagnostic for later same-version comparison."""
    acquisition=json.loads(acquisition_raw);analysis=json.loads(analysis_raw)
    validate_acquisition(acquisition)
    require(acquisition["scope"]==SCOPES[0] and analysis.get("schema")==SCHEMA and
            analysis.get("scope")==SCOPES[0] and analysis.get("mode")=="analysis" and
            analysis.get("source_acquisition_sha256")==hashlib.sha256(acquisition_raw).hexdigest() and
            analysis.get("source_video_bytes")==acquisition["video_bytes"],
            "Stock analysis does not belong to acquisition")
    require(analysis.get("timing_assumptions")=={"snapshot_max_age_seconds":.25,
            "encoder_binding_ambiguity_frames":2,"minimum_edge_margin_seconds":.25} and
            all(w.get("encoded_frames")==60 for w in analysis.get("windows",[])) and
            len(analysis.get("windows",[]))==3,"Qualification requires fixed60-frame timing algorithm")
    rows=[]
    for roi in ("main","left","right"):
        selected={m["stage"]:m for m in analysis["measurements"] if m["roi"]==roi}
        require(set(selected)=={"baseline","sham_stock","return_stock"},"Missing optical measurements")
        baseline=selected["baseline"]["degrees"]["2"]
        for stage in ("sham_stock","return_stock"):
            value=selected[stage]["degrees"]["2"]
            require(baseline["normalized_rms"][2]>1e-9 and baseline["mean_y"]>20,
                    "Insufficient stock fine/mean reference")
            rows.append({"roi":roi,"stage":stage,
                "normalized_fine_over_baseline":value["normalized_rms"][2]/baseline["normalized_rms"][2],
                "mean_y_over_baseline":value["mean_y"]/baseline["mean_y"]})
    result={"schema":QUALIFICATION_SCHEMA,"status":"limited_stock_diagnostic_pass",
        "acquisition_canonical_sha256":canonical_sha(acquisition),
        "source_commit":acquisition["source_commit"],"source_blob_ids":acquisition["source_blob_ids"],
        "optical_analysis_sha256":hashlib.sha256(analysis_raw).hexdigest(),
        "rois_xywh":analysis["rois_xywh"],
        "baseline_fine_search_cycles_per_row":analysis["baseline_fine_search_cycles_per_row"],
        "algorithm":ALGORITHM.copy(),"fine_relative_tolerance":.05,"mean_y_relative_tolerance":.05,
        "stock_ratios":rows,"observed_active_G_seconds":acquisition["active_G_seconds"],
        "prearm_planning_estimate":acquisition["prearm_planning_estimate"],
        "physical_pwm_hz":None,"full_waveform_equivalence":None,"future_latency_bound":False,
        "optical_return_approval":False,
        "candidate_geometry_rule":"Use frozen ROI/band; baseline-only geometry review; mismatch is inconclusive, no B-driven reselection"}
    return validate_stock_qualification(acquisition,result,acquisition)

def frozen_candidate_geometry(qualification,review):
    """False means inconclusive, never select a replacement ROI from B."""
    return (review.get("baseline_geometry_verified") is True and
            review.get("fixed_geometry_verified") is True and
            review.get("flat_screen_content_verified") is True and
            review.get("rois_xywh")==qualification["rois_xywh"] and
            review.get("baseline_fine_search_cycles_per_row")==
                qualification["baseline_fine_search_cycles_per_row"])

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("video", type=Path)
    parser.add_argument("--derived",type=Path,required=True)
    parser.add_argument("--source-bindings",type=Path,required=True)
    parser.add_argument("--no-concurrent-writers",action="store_true",required=True)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--review", type=Path)
    parser.add_argument("--profiles", type=Path)
    parser.add_argument("--stock-acquisition",type=Path)
    parser.add_argument("--optical-qualification",type=Path)
    parser.add_argument("--qualification-output",type=Path)
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
    fd=os.open(args.video,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        run=media.joined_view(raw,args.derived.read_bytes(),fd,
            expected_bindings=json.loads(args.source_bindings.read_text()),
            no_concurrent_writers=args.no_concurrent_writers)
        video_identity=media.identity(os.fstat(fd))
    finally:os.close(fd)
    stages = validate_run(run)  # BEFORE stat, ffprobe, decode or screenshot read.
    frozen=None
    if run["candidate_enabled"]:
        require(args.stock_acquisition is not None and args.optical_qualification is not None,
                "Candidate analysis requires same-version frozen stock optical qualification")
        frozen=validate_stock_qualification(json.loads(args.stock_acquisition.read_bytes()),
            json.loads(args.optical_qualification.read_bytes()),run)
    if args.qualification_output:
        require(not run["candidate_enabled"] and not args.plan and not args.qualification_output.exists(),
                "Only new completed stock analysis may freeze qualification")
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
    result = {"schema": SCHEMA, "scope": run["scope"], "mode": "window_plan" if args.plan else "analysis",
              "source_run_sha256": digest, "source_acquisition_sha256":run["source_acquisition_sha256"],
              "source_video_sha256":run["video_sha256"], "source_video_bytes": run["video_bytes"],
              "decoded_frame_count": len(pts), "stream": stream, "windows": windows,
              "timing_assumptions": {"snapshot_max_age_seconds": args.snapshot_age_seconds,
                                     "encoder_binding_ambiguity_frames": args.binding_frames,
                                     "minimum_edge_margin_seconds": .25},
              "stronger_timing_sensitivity": stronger,
              "c1_observations": c1_observations(stages),
              "middle_c1_measurement": "measured long3 in all three stages",
              "full_middle_wait_timing_validated": True,
              "observed_active_G_seconds": run["active_G_seconds"],
              "timed_window_limit": "Observed AA run only, not a future latency bound",
              "physical_pwm_hz": None, "stock_optics_restored": None,
              "sham_optics_unchanged": None, "lead_approved": False,
              "candidate_enabled": run["candidate_enabled"],
              "limits": ["One fixed AA contrast only; no hardware permission or physical PWM claim.",
                         "Timing envelopes are conditional, not per-exposure sensor/MP4 binding.",
                         "No physical Hz, modulation-depth, comfort, or general C1-count inference.",
                         "Encoded Y includes ISP, codec, black offset and nonlinearity.",
                         "Fine/6 is a spatial diagnostic; short ROI limits broad-component inference.",
                         "Neighbouring ROIs and frame blocks are not independent experiments."]}
    if args.plan:
        if args.preview_dir:
            common.inspect_frames(args.video, windows, args.preview_dir)
        result["review_template"] = {
            "schema": "aa-threshold-roi-review-v1", "run_sha256": digest,
            "video_bytes": run["video_bytes"], "decoded_frame_count": len(pts),
            "reviewed_frames": {w["stage"]: w["review_frames"] for w in windows},
            "native_y_noautorotate_inspected": False, "flat_screen_content_verified": False,
            "fixed_geometry_verified": False, "timestamp_margins_reviewed": False,
            "rois_xywh": None, "baseline_fine_search_cycles_per_row": None}
        if frozen is not None:
            result["review_template"].update(rois_xywh=frozen["rois_xywh"],
                baseline_fine_search_cycles_per_row=frozen["baseline_fine_search_cycles_per_row"],
                baseline_geometry_verified=False,
                geometry_rule=frozen["candidate_geometry_rule"])
    else:
        review = json.loads(args.review.read_text())
        if frozen is not None and not frozen_candidate_geometry(frozen,review):
            result.update(mode="inconclusive",reason="Frozen stock geometry/band not verified from candidate baseline; no reselection or optical inference")
        else:
            rois, band = validate_review(review, run_sha256=digest,
                video_bytes=run["video_bytes"], frame_count=len(pts), windows=windows)
            findings, arrays = common.analyze(args.video, windows, rois, band)
            result.update(findings, aa_contrasts=aa_contrasts(findings), rois_xywh=rois, full_spatial_spectrum_cycles_per_row=[0, .5],
                          normalization="RMS Y coefficient / (mean Y - 16), not optical modulation depth.",
                          q_selection="Baseline-only fine q, fixed in every stage.",
                          detrend="Spatial per frame, None/1/2/3; temporal mean never removed.")
            arrays["pts"] = pts
            with args.profiles.open("xb") as handle:
                np.savez_compressed(handle, **arrays)
    fd=os.open(args.video,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        size,video_digest=media.snapshot(fd,no_concurrent_writers=args.no_concurrent_writers)
        require(media.identity(os.fstat(fd))==video_identity and video_digest==run["video_sha256"],
                "Video identity/bytes changed during analysis")
    finally:os.close(fd)
    require(args.run.read_bytes() == raw and size == run["video_bytes"],
            "Completed run/video changed during analysis")
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    if args.qualification_output:
        qualification=stock_qualification(raw,args.output.read_bytes())
        with args.qualification_output.open("x") as handle:
            json.dump(qualification,handle,indent=2,allow_nan=False);handle.write("\n")
    print("Offline AA result written; physical PWM Hz unknown.")


if __name__ == "__main__":
    main()
