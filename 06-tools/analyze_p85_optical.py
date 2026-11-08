#!/usr/bin/env python3
"""Offline P85 video qualification. No device imports, transport, or approval.

--plan writes timing evidence and optional PRIVATE native-Y review frames.
--review consumes an explicit fresh ROI review, then writes JSON and NPZ.
All outputs are new files. No automatic stock review/lead approval is produced.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np

from optical_spectrum import analyze_profiles

SCHEMA = "p85-optical-analysis-v1"
PROFILE = {"exposure_ns": 100000, "iso": 6400, "focus_diopters": 2.03874850,
           "crop": [0, 0, 4080, 3072], "zoom": 1.0, "ae_mode": "OFF",
           "af_mode": "OFF", "eis_mode": "OFF", "ois_mode": "OFF",
           "capture_intent": "VIDEO_RECORD"}
CLEAN_FLAGS = ("camera_stopped_verified", "original_settings_dbv_logger_restored",
               "watchdog_disarmed", "mutex_released",
               "explicit15_readback_and_stock_c1_return")
BANDS = {"broad": (.002, .006), "higher": (.025, .1), "tail": (.1, .5)}


class OpticalError(ValueError):
    """Unqualified input; never silently fall back to a guessed window."""


def require(condition, message):
    if not condition:
        raise OpticalError(message)


def utc(value):
    require(isinstance(value, str), "Missing UTC timestamp")
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OpticalError("Malformed UTC timestamp") from exc
    require(date.tzinfo is not None, "Naive host timestamp")
    return date.timestamp()


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_run(run):
    """Validate finalized, successful runner evidence BEFORE opening the video."""
    require(isinstance(run, dict), "Run must be an object")
    utc(run.get("finished_at_utc"))
    require(run.get("status") == "awaiting_optical_review", "Run not complete/clean")
    require(all(run.get(key) is True for key in CLEAN_FLAGS), "Cleanup or explicit return not verified")
    require(not any(run.get(key) for key in
                    ("error", "error_type", "cleanup_error_type", "camera_cleanup_error_type",
                     "camera_ui_cleanup_pending", "recovery_reboot_attempted",
                     "physical_ddic_recovery_unverified")), "Failure/recovery invalidates optical qualification")
    require(run.get("cleanup_errors", []) == [], "Cleanup errors present")
    candidate = run.get("scope") == "p85-candidate14"
    require(candidate or run.get("scope") == "p85-stock-only", "Wrong experiment scope")
    labels = ["baseline", "sham15"] + (["candidate14"] if candidate else []) + ["return15"]
    stages = run.get("stages", [])
    require([s.get("label") for s in stages] == labels, "Incomplete or reordered stages")
    if candidate:
        require(run.get("candidate_attempts") == 1 and
                run.get("candidate_watchdog") == "disarmed_after_verified_return_or_boot",
                "Candidate/return watchdog evidence missing")
    else:
        require(run.get("candidate_attempts") == 0 and
                run.get("unknown_value_write_attempted") is False,
                "Stock-only report contains an unknown write")
    for stage in stages:
        require(stage.get("qualified") is True and stage.get("observed_sensor_frames", 0) >= 120,
                "Stage continuity/control checks not qualified")
        require(stage.get("p85", {}).get("data") ==
                ([20, 0, 0] if stage["label"] == "candidate14" else [21, 0, 0]),
                "Unexpected P85 observation")
        for register in ("p85", "c1"):
            capture = stage.get(register, {})
            require(capture.get("framing_qualified") is True and
                    capture.get("cleanup_verified") is True and capture.get("native_dbv") == 3600,
                    "Missing qualified read/DBV evidence")
        if stage["label"] != "candidate14":
            require(stage["c1"].get("data") == [0, 0, 96], "Stock C1 did not return")
        markers = stage.get("hold_markers", {})
        require(isinstance(markers.get("begin"), str) and isinstance(markers.get("end"), str) and
                markers["begin"] != markers["end"], "Missing distinct hold markers")
        require(utc(stage.get("hold_end_utc")) > utc(stage.get("hold_start_utc")),
                "Invalid host hold bounds")
    require(isinstance(run.get("video_bytes"), int) and run["video_bytes"] > 0,
            "Missing finalized video size")
    profile = run.get("video_profile", {})
    require(profile.get("codec") == "h264" and profile.get("size") == [1280, 720] and
            profile.get("audio_streams") == 0, "Runner video profile not qualified")
    return stages


def validate_snapshot(snapshot):
    require(snapshot.get("recording_verified") is True and snapshot.get("session_token"),
            "Unqualified recording snapshot")
    for which in ("request", "result"):
        values = snapshot.get(which, {})
        for key, expected in PROFILE.items():
            require(values.get(key) == expected, "Camera profile changed: " + which + "." + key)
    result = snapshot["result"]
    require(snapshot.get("rolling_shutter_skew_ns") == 15047630 and
            result.get("rolling_shutter_skew_ns") == 15047630, "Recording geometry/skew changed")
    require(result.get("frame_count") == snapshot.get("frame_count") and
            result.get("timestamp_ns") == snapshot.get("timestamp_ns"), "Inconsistent snapshot counters")
    require(snapshot["request"].get("request_id") == result.get("request_id"),
            "Request/result mismatch")
    for key in ("frame_count", "timestamp_ns"):
        require(isinstance(snapshot.get(key), int) and snapshot[key] > 0, "Invalid camera counter")
    for which in ("request", "result"):
        duration = snapshot[which].get("frame_duration_ns")
        require(finite(duration) and 32_000_000 <= duration <= 35_000_000, "Non-30 fps camera settings")
    encoders = [s for s in snapshot.get("streams", [])
                if s.get("id") == snapshot.get("encoder_stream_id")]
    require(len(encoders) == 1, "Missing/ambiguous encoder stream")
    encoder = encoders[0]
    require((encoder.get("width"), encoder.get("height")) == (1280, 720) and
            encoder.get("consumer_kind") == "GraphicBufferSource" and
            encoder.get("requested") is True and encoder.get("state") == 4,
            "Inactive or changed encoder")
    require(all(isinstance(encoder.get(k), int) and encoder[k] > 0
                for k in ("frames_produced", "last_timestamp_ns")), "Empty encoder snapshot")
    begin, end = utc(snapshot.get("host_call_start_utc")), utc(snapshot.get("host_call_end_utc"))
    elapsed = snapshot.get("host_call_elapsed_seconds")
    require(finite(elapsed) and 0 <= elapsed <= 3 and 0 <= end - begin <= 3 and
            abs(end - begin - elapsed) < .05, "Host clock jump or missing call envelope")
    return encoder


def validate_pts(probe):
    """Accept original native video and original decoded frame presentation times."""
    streams = probe.get("streams", [])
    require(len(streams) == 1, "Exactly one video stream required, no audio")
    stream = streams[0]
    require((stream.get("codec_type"), stream.get("codec_name"), stream.get("width"),
             stream.get("height"), stream.get("pix_fmt"), stream.get("color_range")) ==
            ("video", "h264", 1280, 720, "yuv420p", "tv"), "Original video geometry/range changed")
    try:
        pts = np.asarray([float(f["best_effort_timestamp_time"]) for f in probe["frames"]], dtype=float)
        count = int(stream["nb_frames"])
    except (KeyError, ValueError, TypeError) as exc:
        raise OpticalError("Missing original PTS/frame count") from exc
    require(len(pts) == count and count >= 60 and np.all(np.isfinite(pts)),
            "Decoded frame count/PTS mismatch")
    diffs = np.diff(pts)
    require(np.all((diffs >= .025) & (diffs <= .042)), "PTS gap, duplicate or non-30 fps stream")
    require(abs(float(np.median(diffs)) - 1 / 30) < .001, "Unexpected PTS cadence")
    return pts, {key: stream[key] for key in
                 ("codec_name", "width", "height", "pix_fmt", "color_range", "nb_frames")}


def select_windows(run, pts, *, frames=60, edge_seconds=.25,
                   snapshot_age_seconds=.25, binding_frames=2):
    """Original protocol entry point: always validate its complete run first."""
    stages = validate_run(run)
    return select_windows_from_stages(
        stages, run.get("recording_preflight", []), pts, frames=frames,
        edge_seconds=edge_seconds, snapshot_age_seconds=snapshot_age_seconds,
        binding_frames=binding_frames)


def select_windows_from_stages(stages, recording_preflight, pts, *, frames=60,
                              edge_seconds=.25, snapshot_age_seconds=.25, binding_frames=2):
    """Conditional worst-case envelope, never a sensor-to-file calibration.

    Pure timing calculation. Caller must first validate its exact run protocol;
    this helper does not validate hardware actions or authorize any experiment.
    A result is assumed no older than snapshot_age_seconds before call start.
    Each matched encoder production count is mapped to decoded index count-1.
    binding_frames allows a bounded origin/queue ambiguity, not arbitrary drops.
    PTS gaps and unstable matched offsets are rejected separately.
    Every selected frame must fit BOTH anchor envelopes inside the host hold.
    """
    pts = np.asarray(pts, dtype=float)
    require(pts.ndim == 1 and len(pts) >= 60 and np.all(np.isfinite(pts)) and
            np.all((np.diff(pts) >= .025) & (np.diff(pts) <= .042)), "Invalid PTS")
    require(isinstance(frames, int) and frames >= 60, "At least 60 encoded frames required")
    require(finite(edge_seconds) and edge_seconds >= .25 and
            finite(snapshot_age_seconds) and snapshot_age_seconds >= .25 and
            isinstance(binding_frames, int) and binding_frames >= 2,
            "Do not silently weaken timing uncertainty budgets")
    snapshots = recording_preflight
    require(isinstance(snapshots, list) and len(snapshots) >= 2, "Missing recording preflight")
    snapshots = snapshots + [s[side] for s in stages for side in ("camera_start", "camera_end")]
    encoders = [validate_snapshot(s) for s in snapshots]
    require(len({s["session_token"] for s in snapshots}) == 1 and
            len({s["encoder_stream_id"] for s in snapshots}) == 1, "Recording session changed")
    offsets = [s["frame_count"] - e["frames_produced"] for s, e in zip(snapshots, encoders)
               if s["timestamp_ns"] == e["last_timestamp_ns"]]
    require(len(offsets) >= 3 and len(set(offsets)) == 1,
            "No unique timestamp-matched camera/encoder count offset")
    offset = offsets[0]
    for previous, current in zip(snapshots, snapshots[1:]):
        require(current["frame_count"] > previous["frame_count"] and
                current["timestamp_ns"] > previous["timestamp_ns"], "Camera snapshots did not advance")
        require(utc(current["host_call_start_utc"]) >= utc(previous["host_call_end_utc"]),
                "Overlapping/reordered host snapshot calls")
        fps = (current["frame_count"] - previous["frame_count"]) * 1e9 / (
            current["timestamp_ns"] - previous["timestamp_ns"])
        require(29.5 < fps < 30.5, "Sensor counter/timestamp cadence changed")
    for snapshot, encoder in zip(snapshots, encoders):
        require(abs(snapshot["frame_count"] - offset - encoder["frames_produced"]) <= binding_frames and
                abs(snapshot["timestamp_ns"] - encoder["last_timestamp_ns"]) <= binding_frames * 35_000_000,
                "Encoder/result discrepancy exceeds declared binding budget")
    windows = []
    pad = binding_frames * float(np.max(np.diff(pts)))
    for stage in stages:
        start, end = stage["camera_start"], stage["camera_end"]
        require(end["frame_count"] - start["frame_count"] == stage["observed_sensor_frames"],
                "Stage continuity count disagrees")
        hold_start, hold_end = utc(stage["hold_start_utc"]), utc(stage["hold_end_utc"])
        require(hold_start <= utc(start["host_call_start_utc"]) <
                utc(start["host_call_end_utc"]) <= utc(end["host_call_start_utc"]) <
                utc(end["host_call_end_utc"]) <= hold_end, "Camera anchors outside hold")
        lower, upper = [], []
        anchors = []
        for snapshot in (start, end):
            index = snapshot["frame_count"] - offset - 1
            require(0 <= index < len(pts), "Encoder-derived anchor outside original video")
            lower.append(utc(snapshot["host_call_start_utc"]) - snapshot_age_seconds +
                         (pts - pts[index]) - pad)
            upper.append(utc(snapshot["host_call_end_utc"]) + (pts - pts[index]) + pad)
            anchors.append(index)
        # Union is deliberately more conservative than intersecting two bounds.
        lower = np.minimum.reduce(lower)
        upper = np.maximum.reduce(upper)
        eligible = np.flatnonzero((lower >= hold_start + edge_seconds) &
                                  (upper <= hold_end - edge_seconds))
        require(len(eligible) >= frames and np.all(np.diff(eligible) == 1),
                "Fewer than requested stable encoded frames after timing margins")
        first = int(eligible[(len(eligible) - frames) // 2])
        last = first + frames
        require(not windows or first >= windows[-1]["end_exclusive"], "Stage windows overlap")
        windows.append({"stage": stage["label"], "start_inclusive": first,
                        "end_exclusive": last, "encoded_frames": frames,
                        "review_frames": [first, first + frames // 2, last - 1],
                        "pts_first_seconds": float(pts[first]),
                        "pts_last_seconds": float(pts[last - 1]),
                        "eligible_encoded_frames": len(eligible),
                        "anchor_encoded_indices": anchors,
                        "conditional_leading_margin_seconds": float(lower[first] - hold_start),
                        "conditional_trailing_margin_seconds": float(hold_end - upper[last - 1]),
                        "host_hold_seconds": hold_end - hold_start})
    return windows


def validate_review(review, *, run_sha256, video_bytes, frame_count, windows):
    require(review.get("schema") == "p85-optical-roi-review-v1" and
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
    require(isinstance(band, list) and len(band) == 2 and all(finite(x) for x in band) and
            .006 < band[0] < band[1] < .1, "Explicit baseline-only fine search band required")
    return rois, band


def probe_video(video):
    return json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries",
        "stream=codec_type,codec_name,width,height,pix_fmt,color_range,nb_frames:"
        "frame=best_effort_timestamp_time", "-of", "json", str(video)], text=True))


def select_expression(indices):
    require(indices and sorted(set(indices)) == indices, "Frame indices not unique/increasing")
    ranges = []
    first = last = indices[0]
    for index in indices[1:]:
        if index == last + 1:
            last = index
        else:
            ranges.append((first, last))
            first = last = index
    ranges.append((first, last))
    # Long chains of single-frame eq terms exceed libavutil expression depth.
    # Compress contiguous windows without changing any selected frame.
    require(len(ranges) <= 64, "Too many disjoint frame groups for one bounded decode")
    return "+".join(f"eq(n\\,{a})" if a == b else f"between(n\\,{a}\\,{b})"
                    for a, b in ranges)


def decode_y(video, indices, rect=(0, 0, 1280, 720)):
    selection = select_expression(indices)
    x, y, width, height = rect
    command = ["ffmpeg", "-v", "error", "-noautorotate", "-i", str(video), "-vf",
               f"select={selection},extractplanes=y,crop={width}:{height}:{x}:{y}",
               "-fps_mode", "passthrough", "-enc_time_base", "demux",
               "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    raw = subprocess.check_output(command)
    require(len(raw) == len(indices) * height * width, "Native-Y decode size mismatch")
    return np.frombuffer(raw, dtype=np.uint8).reshape(len(indices), height, width)


def inspect_frames(video, windows, directory):
    """Private original native-Y PNGs only; no inferred ROI or review approval."""
    directory = directory.resolve()
    require(directory.parent == video.resolve().parent and not directory.exists(),
            "Preview directory must be a NEW direct child of the private video directory")
    indices = sorted(n for w in windows for n in w["review_frames"])
    pixels = decode_y(video, indices)
    from PIL import Image
    directory.mkdir(mode=0o700)
    for index, frame in zip(indices, pixels):
        target = directory / f"native-y-frame-{index}.png"
        Image.fromarray(frame).save(target)
        target.chmod(0o600)


def fixed_metrics(profile, frequencies, degree=2):
    measurement = analyze_profiles(profile, frequencies=frequencies, detrend_degree=degree)
    mean = float(profile.mean())
    require(mean > 20, "Mean Y too close to black floor for requested normalization")
    return {"mean_y": mean,
            "total_rms_y": measurement["total_rms_amplitude"].tolist(),
            "coherent_y": measurement["coherent_amplitude"].tolist(),
            "incoherent_rms_y": measurement["incoherent_rms_amplitude"].tolist(),
            "normalized_rms": (measurement["total_rms_amplitude"] / (mean - 16)).tolist()}


def ratio(numerator, denominator):
    a, b = np.asarray(numerator), np.asarray(denominator)
    return [float(x / y) if y > 1e-9 else None for x, y in zip(a, b)]


def analyze(video, windows, rois, search_band):
    all_indices = [i for w in windows for i in range(w["start_inclusive"], w["end_exclusive"])]
    x = min(r[0] for r in rois.values())
    right = max(r[0] + r[2] for r in rois.values())
    y, height = rois["main"][1], rois["main"][3]
    pixels = decode_y(video, all_indices, (x, y, right - x, height))
    count = windows[0]["encoded_frames"]
    pixels = pixels.reshape(len(windows), count, height, right - x)
    profiles = {name: pixels[:, :, :, r[0]-x:r[0]-x+r[2]].mean(axis=3)
                for name, r in rois.items()}
    baseline = analyze_profiles(profiles["main"][0], n_fft=8192, frequency_max=.5)
    grid = baseline["frequencies_cycles_per_row"]
    search = np.flatnonzero((grid >= search_band[0]) & (grid <= search_band[1]))
    selected = int(search[np.argmax(baseline["total_power"][search])])
    require(selected not in (search[0], search[-1]), "Baseline fine peak is at search edge")
    fine = float(grid[selected])
    qs = [fine / 6, fine / 2, fine, fine * 2, fine * 3]
    arrays = {"q": grid, **{"profiles_" + k: v for k, v in profiles.items()}}
    measurements, ratios = [], []
    for name, stages in profiles.items():
        for n, profile in enumerate(stages):
            pix = pixels[n, :, :, rois[name][0]-x:rois[name][0]-x+rois[name][2]]
            item = {"stage": windows[n]["stage"], "roi": name,
                    "mean_y": float(profile.mean()), "min_y": int(pix.min()), "max_y": int(pix.max()),
                    "fraction_y_ge_235": float(np.mean(pix >= 235)),
                    "fraction_y_le_16": float(np.mean(pix <= 16)), "degrees": {}, "blocks": []}
            for degree in (None, 1, 2, 3):
                full = analyze_profiles(profile, n_fft=8192, frequency_max=.5,
                                        detrend_degree=degree, peak_count=12)
                require(full["power_partition_max_abs_error"] < 1e-8, "Power decomposition failed")
                item["degrees"][str(degree)] = fixed_metrics(profile, qs, degree)
                item["degrees"][str(degree)]["peaks"] = full["peaks"]
                item["degrees"][str(degree)]["band_maxima"] = {}
                for band, (lo, hi) in {**BANDS, "fine_search": search_band}.items():
                    use = np.flatnonzero((grid >= lo) & (grid <= hi))
                    peak = int(use[np.argmax(full["total_power"][use])])
                    item["degrees"][str(degree)]["band_maxima"][band] = {
                        "q": float(grid[peak]), "rms_y": float(full["total_rms_amplitude"][peak]),
                        "at_band_edge": bool(peak in (use[0], use[-1]))}
                if degree == 2:
                    for field in ("total_power", "coherent_power", "incoherent_power"):
                        arrays[f"{name}_{windows[n]['stage']}_{field}"] = full[field]
            for indices in np.array_split(np.arange(count), 3):
                item["blocks"].append({"offset_first": int(indices[0]), "frames": len(indices),
                                       **fixed_metrics(profile[indices], qs)})
            measurements.append(item)
        chosen = [m for m in measurements if m["roi"] == name]
        for degree in ("None", "1", "2", "3"):
            values = [m["degrees"][degree]["normalized_rms"] for m in chosen]
            for n in range(1, len(values)):
                entry = {"roi": name, "stage": windows[n]["stage"], "degree": degree,
                         "over_baseline": ratio(values[n], values[0])}
                if windows[n]["stage"] == "candidate14":
                    entry["over_adjacent_stock_mean"] = ratio(values[n], (
                        np.asarray(values[n-1]) + np.asarray(values[n+1])) / 2)
                ratios.append(entry)
    return {"fixed_q_cycles_per_row": qs, "fixed_fine_period_rows": 1 / fine,
            "baseline_fine_search_cycles_per_row": search_band,
            "measurements": measurements, "ratios": ratios}, arrays


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
            "Analysis requires NEW profile output")
    require(not (args.review and args.preview_dir), "Preview is a separate plan/review step")
    raw = args.run.read_bytes()
    run = json.loads(raw)
    validate_run(run)  # Must precede stat, ffprobe, decode, or preview of the video.
    require(args.video.stat().st_size == run["video_bytes"], "Finalized video size mismatch")
    pts, stream = validate_pts(probe_video(args.video))
    windows = select_windows(run, pts, frames=args.frames,
                             snapshot_age_seconds=args.snapshot_age_seconds,
                             binding_frames=args.binding_frames)
    sensitivity = None
    try:
        sensitivity = {"snapshot_max_age_seconds": max(.5, args.snapshot_age_seconds),
                       "encoder_binding_ambiguity_frames": max(3, args.binding_frames),
                       "windows": select_windows(run, pts, frames=args.frames,
                           snapshot_age_seconds=max(.5, args.snapshot_age_seconds),
                           binding_frames=max(3, args.binding_frames))}
    except OpticalError:
        sensitivity = {"qualified": False,
                       "reason": "Stronger timing uncertainty leaves insufficient qualified window"}
    digest = hashlib.sha256(raw).hexdigest()  # Bind fresh review to this exact run.
    result = {"schema": SCHEMA, "mode": "window_plan" if args.plan else "analysis",
              "source_run_sha256": digest, "source_video_bytes": run["video_bytes"],
              "decoded_frame_count": len(pts), "stream": stream, "windows": windows,
              "timing_assumptions": {"snapshot_max_age_seconds": args.snapshot_age_seconds,
                                     "encoder_binding_ambiguity_frames": args.binding_frames,
                                     "minimum_edge_margin_seconds": .25},
              "stronger_timing_sensitivity": sensitivity,
              "alignment": "Conditional union of host call envelopes at both camera anchors, "
                           "with actual MP4 PTS. Matched encoder/result counts establish a consistent "
                           "count offset, not calibrated per-frame sensor-to-file binding.",
              "scope": run["scope"], "physical_pwm_hz": None,
              "stock_optics_restored": None, "sham_optics_unchanged": None,
              "lead_approved": False,
              "limits": ["No physical Hz, modulation-depth, comfort, or general C1-count inference.",
                         "Camera Y includes ISP, black offset, codec and nonlinearity.",
                         "Fine/6 is a spatial diagnostic, not a physical fundamental.",
                         "Adjacent ROI strips and frame blocks are not independent experiments.",
                         "No video can be called unchanged solely from a single scalar ratio."]}
    if args.plan:
        if args.preview_dir:
            inspect_frames(args.video, windows, args.preview_dir)
        result["review_template"] = {
            "schema": "p85-optical-roi-review-v1", "run_sha256": digest,
            "video_bytes": run["video_bytes"], "decoded_frame_count": len(pts),
            "reviewed_frames": {w["stage"]: w["review_frames"] for w in windows},
            "native_y_noautorotate_inspected": False, "flat_screen_content_verified": False,
            "fixed_geometry_verified": False, "timestamp_margins_reviewed": False,
            "rois_xywh": None, "baseline_fine_search_cycles_per_row": None}
    else:
        review = json.loads(args.review.read_text())
        rois, band = validate_review(review, run_sha256=digest, video_bytes=run["video_bytes"],
                                    frame_count=len(pts), windows=windows)
        findings, arrays = analyze(args.video, windows, rois, band)
        result.update(findings, rois_xywh=rois,
                      full_spatial_spectrum_cycles_per_row=[0, .5],
                      normalization="RMS Y Fourier coefficient / (mean Y - 16); image-code metric only.",
                      q_selection="Fine q selected from baseline main ROI alone and held fixed in all stages.",
                      detrend="Spatial per frame only, degrees None/1/2/3. Temporal mean never removed.")
        arrays["pts"] = pts
        with args.profiles.open("xb") as handle:
            np.savez_compressed(handle, **arrays)
    require(args.video.stat().st_size == run["video_bytes"] and args.run.read_bytes() == raw,
            "Run/video changed during offline analysis; discard outputs and review source")
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print("Offline output written. Lead optical qualification remains required; physical_pwm_hz=null.")


if __name__ == "__main__":
    main()
