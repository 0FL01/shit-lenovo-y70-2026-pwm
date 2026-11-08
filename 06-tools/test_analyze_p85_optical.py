"""Synthetic/offline tests only. No device APIs or real capture required."""
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import analyze_p85_optical as optical

EPOCH = 1_800_000_000


def stamp(seconds):
    return datetime.fromtimestamp(EPOCH + seconds, timezone.utc).isoformat()


def snapshot(index):
    settings = {**optical.PROFILE, "request_id": 7, "frame_duration_ns": 33333333}
    timestamp = 1_000_000_000 + round(index * 1e9 / 30)
    return {"recording_verified": True, "session_token": "synthetic-session",
            "encoder_stream_id": 3, "frame_count": index + 101,
            "timestamp_ns": timestamp, "rolling_shutter_skew_ns": 15047630,
            "request": settings.copy(),
            "result": {**settings, "frame_count": index + 101,
                       "timestamp_ns": timestamp, "rolling_shutter_skew_ns": 15047630},
            "streams": [{"id": 3, "width": 1280, "height": 720,
                         "consumer_kind": "GraphicBufferSource", "state": 4, "requested": True,
                         "frames_produced": index + 1, "last_timestamp_ns": timestamp}],
            "host_call_start_utc": stamp(index / 30 + .05),
            "host_call_end_utc": stamp(index / 30 + .25),
            "host_call_elapsed_seconds": .2}


def fixture(candidate=False):
    capture = {"framing_qualified": True, "cleanup_verified": True, "native_dbv": 3600}
    labels = ["baseline", "sham15"] + (["candidate14"] if candidate else []) + ["return15"]
    stages = []
    for n, label in enumerate(labels):
        index = 300 + 300 * n
        stages.append({"label": label, "qualified": True, "observed_sensor_frames": 135,
                       "p85": {**capture, "data": [20 if label == "candidate14" else 21, 0, 0]},
                       "c1": {**capture, "data": [0, 0, 96]},
                       "camera_start": snapshot(index), "camera_end": snapshot(index + 135),
                       "hold_markers": {"begin": label + "_BEGIN", "end": label + "_END"},
                       "hold_start_utc": stamp(index / 30 - .1),
                       "hold_end_utc": stamp((index + 135) / 30 + .3)})
    run = {"scope": "p85-candidate14" if candidate else "p85-stock-only",
           "status": "awaiting_optical_review", "finished_at_utc": stamp(60),
           **{key: True for key in optical.CLEAN_FLAGS}, "candidate_attempts": int(candidate),
           "unknown_value_write_attempted": candidate,
           "candidate_watchdog": "disarmed_after_verified_return_or_boot",
           "stages": stages, "recording_preflight": [snapshot(60), snapshot(90)],
           "video_bytes": 123,
           "video_profile": {"codec": "h264", "size": [1280, 720], "audio_streams": 0}}
    return run, np.arange(1800, dtype=float) / 30


def review(windows):
    return {"schema": "p85-optical-roi-review-v1", "run_sha256": "synthetic-sha",
            "video_bytes": 123, "decoded_frame_count": 1800,
            "native_y_noautorotate_inspected": True, "flat_screen_content_verified": True,
            "fixed_geometry_verified": True, "timestamp_margins_reviewed": True,
            "reviewed_frames": {w["stage"]: w["review_frames"] for w in windows},
            "rois_xywh": {"left": [220, 70, 40, 540], "main": [260, 70, 40, 540],
                         "right": [320, 70, 40, 540]},
            "baseline_fine_search_cycles_per_row": [.015, .025]}


class P85OpticalTests(unittest.TestCase):
    def setUp(self):
        self.run, self.pts = fixture()

    def test_stock_and_candidate_window_orders(self):
        for candidate in (False, True):
            run, pts = fixture(candidate)
            windows = optical.select_windows(run, pts)
            self.assertEqual([w["stage"] for w in windows], [s["label"] for s in run["stages"]])
            for w in windows:
                self.assertEqual(w["end_exclusive"] - w["start_inclusive"], 60)
                self.assertGreaterEqual(w["conditional_leading_margin_seconds"], .25)
                self.assertGreaterEqual(w["conditional_trailing_margin_seconds"], .25)

    def test_all_cleanup_flags_fail_closed(self):
        for key in optical.CLEAN_FLAGS:
            run = deepcopy(self.run)
            del run[key]
            with self.subTest(key=key), self.assertRaises(optical.OpticalError):
                optical.validate_run(run)

    def test_unfinished_run_rejected_before_video_access(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            self.run.pop("finished_at_utc")
            path = directory / "run.json"
            path.write_text(json.dumps(self.run))
            with patch.object(optical, "probe_video") as probe:
                with self.assertRaises(optical.OpticalError):
                    optical.main([str(path), str(directory / "DOES_NOT_EXIST.mp4"), "--plan",
                                  "--output", str(directory / "out.json")])
                probe.assert_not_called()
                self.assertFalse((directory / "out.json").exists())

    def test_failed_or_recovered_run_rejected(self):
        for key, value in (("status", "active"), ("error_type", "TimeoutError"),
                           ("camera_cleanup_error_type", "Error"),
                           ("recovery_reboot_attempted", True), ("cleanup_errors", ["error"])):
            run = deepcopy(self.run)
            run[key] = value
            with self.subTest(key=key), self.assertRaises(optical.OpticalError):
                optical.validate_run(run)

    def test_stock_unknown_write_and_wrong_stage_rejected(self):
        self.run["unknown_value_write_attempted"] = True
        with self.assertRaises(optical.OpticalError):
            optical.validate_run(self.run)
        self.run["unknown_value_write_attempted"] = False
        self.run["stages"].reverse()
        with self.assertRaises(optical.OpticalError):
            optical.validate_run(self.run)

    def test_bad_p85_or_stock_c1_rejected(self):
        for register in ("p85", "c1"):
            run = deepcopy(self.run)
            run["stages"][1][register]["data"] = [0, 0, 0]
            with self.subTest(register=register), self.assertRaises(optical.OpticalError):
                optical.validate_run(run)

    def test_missing_qualification_or_dbv_rejected(self):
        for field, value in (("framing_qualified", False), ("cleanup_verified", False),
                             ("native_dbv", 828)):
            run = deepcopy(self.run)
            run["stages"][1]["p85"][field] = value
            with self.subTest(field=field), self.assertRaises(optical.OpticalError):
                optical.validate_run(run)

    def test_naive_and_reversed_host_times_rejected(self):
        self.run["stages"][0]["hold_start_utc"] = "2027-01-01T00:00:00"
        with self.assertRaises(optical.OpticalError):
            optical.select_windows(self.run, self.pts)
        self.run, _ = fixture()
        snap = self.run["stages"][0]["camera_start"]
        snap["host_call_start_utc"], snap["host_call_end_utc"] = (
            snap["host_call_end_utc"], snap["host_call_start_utc"])
        with self.assertRaises(optical.OpticalError):
            optical.select_windows(self.run, self.pts)

    def test_missing_call_envelope_no_guess(self):
        del self.run["stages"][0]["camera_start"]["host_call_start_utc"]
        with self.assertRaises(optical.OpticalError):
            optical.select_windows(self.run, self.pts)

    def test_host_clock_step_rejected(self):
        self.run["stages"][0]["camera_start"]["host_call_elapsed_seconds"] = 1.0
        with self.assertRaises(optical.OpticalError):
            optical.select_windows(self.run, self.pts)

    def test_profile_or_session_changes_rejected(self):
        for mutate in (
            lambda s: s["result"].update(exposure_ns=500000),
            lambda s: s.update(session_token="different"),
            lambda s: s.update(encoder_stream_id=99),
            lambda s: s.update(rolling_shutter_skew_ns=15596307),
        ):
            run = deepcopy(self.run)
            mutate(run["stages"][1]["camera_start"])
            with self.assertRaises(optical.OpticalError):
                optical.select_windows(run, self.pts)

    def test_inconsistent_matched_offsets_rejected(self):
        self.run["stages"][1]["camera_start"]["streams"][0]["frames_produced"] += 1
        with self.assertRaises(optical.OpticalError):
            optical.select_windows(self.run, self.pts)

    def test_async_one_frame_encoder_snapshot_allowed_without_polluting_offset(self):
        snapshot = self.run["stages"][1]["camera_end"]
        snapshot["streams"][0]["frames_produced"] += 1
        snapshot["streams"][0]["last_timestamp_ns"] += 33333333
        windows = optical.select_windows(self.run, self.pts)
        self.assertEqual(len(windows), 3)

    def test_async_large_encoder_error_rejected(self):
        snapshot = self.run["stages"][1]["camera_end"]
        snapshot["streams"][0]["frames_produced"] += 5
        snapshot["streams"][0]["last_timestamp_ns"] += 166666667
        with self.assertRaises(optical.OpticalError):
            optical.select_windows(self.run, self.pts)

    def test_too_few_matched_offsets_rejected(self):
        for stage in self.run["stages"]:
            for key in ("camera_start", "camera_end"):
                stage[key]["streams"][0]["last_timestamp_ns"] += 1
        with self.assertRaises(optical.OpticalError):
            optical.select_windows(self.run, self.pts)

    def test_sensor_count_is_not_stable_encoded_frame_count(self):
        # 135 observed sensor frames, but 90 central encoded frames do not fit
        # under a larger declared snapshot-age budget.
        with self.assertRaises(optical.OpticalError):
            optical.select_windows(self.run, self.pts, frames=90, snapshot_age_seconds=1.5)
        self.assertTrue(optical.select_windows(self.run, self.pts, frames=60,
                                             snapshot_age_seconds=.5, binding_frames=3))

    def test_insufficient_window_no_shrink(self):
        with self.assertRaises(optical.OpticalError):
            optical.select_windows(self.run, self.pts, frames=150)

    def test_weak_budgets_rejected(self):
        for kwargs in ({"frames": 59}, {"edge_seconds": .1},
                       {"snapshot_age_seconds": 0}, {"binding_frames": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(optical.OpticalError):
                optical.select_windows(self.run, self.pts, **kwargs)

    def test_pts_gap_duplicate_or_nan_rejected(self):
        for replacement in (self.pts[50], np.nan, self.pts[51] + .1):
            pts = self.pts.copy()
            pts[51] = replacement
            with self.assertRaises(optical.OpticalError):
                optical.select_windows(self.run, pts)

    def test_continuity_count_mismatch_rejected(self):
        self.run["stages"][0]["observed_sensor_frames"] += 1
        with self.assertRaises(optical.OpticalError):
            optical.select_windows(self.run, self.pts)

    def test_original_video_probe(self):
        probe = {"streams": [{"codec_type": "video", "codec_name": "h264", "width": 1280,
                              "height": 720, "pix_fmt": "yuv420p", "color_range": "tv",
                              "nb_frames": "1800"}],
                 "frames": [{"best_effort_timestamp_time": str(x)} for x in self.pts]}
        pts, stream = optical.validate_pts(probe)
        np.testing.assert_array_equal(pts, self.pts)
        for field, value in (("width", 720), ("color_range", "pc"), ("nb_frames", "1799")):
            bad = deepcopy(probe)
            bad["streams"][0][field] = value
            with self.subTest(field=field), self.assertRaises(optical.OpticalError):
                optical.validate_pts(bad)

    def test_fresh_roi_review_and_failures(self):
        windows = optical.select_windows(self.run, self.pts)
        data = review(windows)
        kwargs = dict(run_sha256="synthetic-sha", video_bytes=123,
                      frame_count=1800, windows=windows)
        self.assertEqual(len(optical.validate_review(data, **kwargs)[0]), 3)
        for mutate in (
            lambda r: r.update(run_sha256="old"),
            lambda r: r.update(native_y_noautorotate_inspected=False),
            lambda r: r["reviewed_frames"]["baseline"].pop(),
            lambda r: r["rois_xywh"].update(right=[260, 70, 40, 540]),
            lambda r: r["rois_xywh"].update(right=[1260, 70, 40, 540]),
            lambda r: r.update(baseline_fine_search_cycles_per_row=[.02, .02]),
        ):
            changed = deepcopy(data)
            mutate(changed)
            with self.assertRaises(optical.OpticalError):
                optical.validate_review(changed, **kwargs)

    def test_temporal_stationary_bands_retained_and_no_black_floor_division(self):
        rows = np.arange(540)
        profile = np.repeat((35 + 5 * np.cos(2 * np.pi * rows / 50))[None], 60, axis=0)
        result = optical.fixed_metrics(profile, [1 / 50])
        self.assertGreater(result["coherent_y"][0], 4.9)
        self.assertLess(result["incoherent_rms_y"][0], 1e-10)
        with self.assertRaises(optical.OpticalError):
            optical.fixed_metrics(profile - 18, [1 / 50])

    def test_full_spectrum_baseline_fixed_q_and_candidate_ratio(self):
        run, pts = fixture(True)
        windows = optical.select_windows(run, pts)
        rows = np.arange(540)
        amplitudes = [6, 6, 1.5, 6]
        wave = np.cos(2 * np.pi * rows / 50)
        wave -= wave.mean()
        pixels = np.stack([np.broadcast_to(
            (35 + amp * wave)[None, :, None],
            (60, 540, 140)) for amp in amplitudes]).astype(np.float64)
        rois = review(windows)["rois_xywh"]
        with patch.object(optical, "decode_y", return_value=pixels.reshape(-1, 540, 140)):
            result, arrays = optical.analyze(Path("unused.mp4"), windows, rois, [.015, .025])
        self.assertEqual(arrays["q"][-1], .5)
        self.assertAlmostEqual(result["fixed_fine_period_rows"], 50, delta=.2)
        item = next(r for r in result["ratios"] if r["roi"] == "main" and
                    r["stage"] == "candidate14" and r["degree"] == "2")
        self.assertAlmostEqual(item["over_adjacent_stock_mean"][2], .25, places=10)

    def test_decode_flags_native_y_no_resampling(self):
        with patch.object(optical.subprocess, "check_output", return_value=bytes(2*4*6)) as call:
            out = optical.decode_y(Path("private.mp4"), [4, 7], (10, 20, 6, 4))
        args = call.call_args.args[0]
        self.assertIn("-noautorotate", args)
        self.assertIn("extractplanes=y,crop=6:4:10:20", args[args.index("-vf") + 1])
        self.assertNotIn("-r", args)
        self.assertEqual(out.shape, (2, 4, 6))

    def test_select_expression_compresses_exact_contiguous_ranges(self):
        indices = list(range(845, 905)) + list(range(2390, 2450)) + list(range(3819, 3879))
        self.assertEqual(optical.select_expression(indices),
                         r"between(n\,845\,904)+between(n\,2390\,2449)+between(n\,3819\,3878)")
        self.assertEqual(optical.select_expression([1, 3, 4, 5, 9]),
                         r"eq(n\,1)+between(n\,3\,5)+eq(n\,9)")
        with self.assertRaises(optical.OpticalError):
            optical.select_expression(list(range(0, 200, 2)))

    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg unavailable')
    def test_real_ffmpeg_180_frames_expression_regression(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / 'synthetic.mkv'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                            'color=c=gray:size=64x64:rate=30', '-frames:v', '240',
                            '-c:v', 'ffv1', str(video)], check=True, capture_output=True)
            indices = list(range(0, 60)) + list(range(80, 140)) + list(range(160, 220))
            decoded = optical.decode_y(video, indices, (0, 0, 64, 64))
            self.assertEqual(decoded.shape, (180, 64, 64))
            self.assertEqual(int(decoded.max()), int(decoded.min()))

    def test_no_overwrite_under_optimized_python(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "already.json"
            output.write_text("sentinel")
            command = [sys.executable, "-O", str(Path(optical.__file__)),
                       "missing-run.json", "missing-video.mp4", "--plan", "--output", str(output)]
            completed = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Refusing to overwrite JSON", completed.stderr)
            self.assertEqual(output.read_text(), "sentinel")


if __name__ == "__main__":
    unittest.main()
