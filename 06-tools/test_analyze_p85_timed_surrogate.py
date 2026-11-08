"""Offline synthetic and saved-artifact regressions; no device/video access."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import analyze_p85_optical as old
import analyze_p85_timed_surrogate as timed
from test_analyze_p85_optical import fixture as old_fixture, snapshot, stamp


def fixture():
    run, pts = old_fixture()
    run.update(scope=timed.SCOPE, candidate_enabled=False,
               unknown_register_writes=False, timed_stock_exploratory=True,
               active_limit_seconds=37, host_limit_seconds=45, recovery_reserve_seconds=8,
               timed_watchdog_seconds=60, timed_watchdog_renewals=0,
               host_alarm_restored_before_cleanup=True,
               explicit15_readback_and_stock_c1_verified=True,
               active_start_monotonic=18., arm_seconds=.2,
               return_qualified_monotonic=27., disarm_seconds=.4, active_G_seconds=9.4,
               register85_writes_attempted=["sham15", "return15"],
               writes=[{"stage": label, "standalone_callbacks": 3, "native_and_wire_gates": True}
                       for label in ("sham15", "return15")])
    for n, stage in enumerate(run["stages"]):
        index = 300 + n * 300
        stage.update(camera_start=snapshot(index), camera_end=snapshot(index+150),
                     observed_sensor_frames=150, hold_seconds=4.5,
                     phase_seconds={"p85": 1., "c1": 1.},
                     hold_start_utc=stamp(index/30-.1),
                     hold_end_utc=stamp((index+150)/30+.3),
                     hold_start_monotonic=index/30-.1,
                     hold_end_monotonic=(index+150)/30+.3)
    for snap in run["recording_preflight"] + [
            s[k] for s in run["stages"] for k in ("camera_start", "camera_end")]:
        index = snap["frame_count"]-101
        snap["host_capture_bounds"] = {"begin_monotonic": index/30+.05,
                                       "end_monotonic": index/30+.25}
    middle = run["stages"][1]
    middle["c1"] = timed.C1_NOT_MEASURED.copy()
    del middle["phase_seconds"]["c1"]
    begin = middle["camera_start"]["host_capture_bounds"]["end_monotonic"]
    middle["return_prequiet"] = {
        "started_monotonic": begin+.01, "ended_monotonic": begin+3,
        "wait_seconds": 1.5, "overlap_seconds": 2.99, "overshoot_seconds": 0.,
        "quiet_evidence": {"quiet_seconds": 2, "begin_marker": "quiet_BEGIN", "end_marker": "quiet_END",
                           "kernel_marker_bounds": {"begin_seconds": 100., "end_seconds": 102.01,
                               "clock": "target kernel printk monotonic; not host/camera clock"},
                           "native_state": {"native_actual_hz": 120, "native_group": 3}}}
    middle["hold_verified_monotonic"] = middle["hold_end_monotonic"]+.3
    run["writes"][1]["started_monotonic"] = middle["hold_verified_monotonic"]+.1
    run["writes"][0].update(started_monotonic=19.,dispatch_monotonic=19.1,validated_monotonic=19.2)
    run["writes"][1].update(dispatch_monotonic=26.,validated_monotonic=26.2)
    return run, pts


class TimedSurrogateOpticalTests(unittest.TestCase):
    def setUp(self):
        self.run, self.pts = fixture()

    def test_explicit_unmeasured_middle_accepted_only_by_new_protocol(self):
        self.assertEqual(len(timed.select_windows(self.run, self.pts)), 3)
        with self.assertRaises(old.OpticalError):
            old.select_windows(self.run, self.pts)

    def test_old_scope_not_accepted_by_adapter(self):
        old_run, _ = old_fixture()
        with self.assertRaises(old.OpticalError):
            timed.validate_run(old_run)

    def test_old_missing_c1_still_rejected_before_timing_helper(self):
        for value in (None, timed.C1_NOT_MEASURED.copy()):
            old_run, pts = old_fixture()
            if value is None:
                del old_run["stages"][1]["c1"]
            else:
                old_run["stages"][1]["c1"] = value
            with patch.object(old, "select_windows_from_stages") as helper:
                with self.assertRaises(old.OpticalError):
                    old.select_windows(old_run, pts)
                helper.assert_not_called()

    def test_no_invented_c1_or_zero_duration(self):
        for mutate in (
            lambda r: r["stages"][1].pop("c1"),
            lambda r: r["stages"][1]["c1"].update(data=[0, 0, 96]),
            lambda r: r["stages"][1]["c1"].update(status="measured"),
            lambda r: r["stages"][1]["c1"].update(reason="unknown"),
            lambda r: r["stages"][1]["phase_seconds"].update(c1=0),
        ):
            run = deepcopy(self.run)
            mutate(run)
            with self.assertRaises(old.OpticalError):
                timed.validate_run(run)

    def test_baseline_and_return_c1_remain_required(self):
        for index in (0, 2):
            for mutate in (lambda c: c.clear(), lambda c: c.update(data=[0, 0, 16]),
                           lambda c: c.update(framing_qualified=False)):
                run = deepcopy(self.run)
                mutate(run["stages"][index]["c1"])
                with self.assertRaises(old.OpticalError):
                    timed.validate_run(run)

    def test_unknown14_or_wrong_attempts_rejected(self):
        for key, value in (("candidate_enabled", True), ("candidate_attempts", 1),
                           ("unknown_value_write_attempted", True), ("unknown_register_writes", True),
                           ("register85_writes_attempted", ["sham15", "candidate14", "return15"])):
            run = deepcopy(self.run)
            run[key] = value
            with self.subTest(key=key), self.assertRaises(old.OpticalError):
                timed.validate_run(run)
        self.run["stages"][1]["p85"]["data"] = [20, 0, 0]
        with self.assertRaises(old.OpticalError):
            timed.validate_run(self.run)

    def test_old_cleanup_and_failure_guards_preserved(self):
        for key in old.CLEAN_FLAGS:
            run = deepcopy(self.run)
            run[key] = False
            with self.subTest(key=key), self.assertRaises(old.OpticalError):
                timed.validate_run(run)
        for key, value in (("error_type", "Error"), ("status", "active"),
                           ("recovery_reboot_attempted", True), ("cleanup_errors", ["error"])):
            run = deepcopy(self.run)
            run[key] = value
            with self.assertRaises(old.OpticalError):
                timed.validate_run(run)

    def test_full_hold_and_sensor_progress_not_shortened(self):
        for key, value in (("hold_seconds", 4.49), ("observed_sensor_frames", 119)):
            run = deepcopy(self.run)
            run["stages"][1][key] = value
            with self.assertRaises(old.OpticalError):
                timed.validate_run(run)
        run = deepcopy(self.run)
        end = run["stages"][1]["camera_end"]
        end["host_capture_bounds"]["begin_monotonic"] -= 1
        end["host_capture_bounds"]["end_monotonic"] -= 1
        end["host_call_start_utc"] = stamp(24.05)
        end["host_call_end_utc"] = stamp(24.25)
        with self.assertRaises(old.OpticalError):
            timed.validate_run(run)

    def test_wrong_prequiet_timing_rejected(self):
        for key, value in (("started_monotonic", 0), ("ended_monotonic", 999),
                           ("wait_seconds", 0), ("overlap_seconds", 4.5), ("overshoot_seconds", 1)):
            run = deepcopy(self.run)
            run["stages"][1]["return_prequiet"][key] = value
            with self.subTest(key=key), self.assertRaises(old.OpticalError):
                timed.validate_run(run)

    def test_individual_call_duration_cannot_hide_between_call_clock_jump(self):
        end = self.run["stages"][1]["camera_end"]
        end["host_call_start_utc"] = stamp(24.05)
        end["host_call_end_utc"] = stamp(24.25)
        with self.assertRaises(old.OpticalError):
            timed.validate_run(self.run)
        with self.assertRaises(old.OpticalError):
            timed.select_windows(self.run, self.pts)

    def test_claimed_two_second_quiet_cannot_fit_in_point_one_seconds(self):
        quiet = self.run["stages"][1]["return_prequiet"]
        quiet.update(started_monotonic=22.25,ended_monotonic=22.35,
                     wait_seconds=2.4,overlap_seconds=.1,overshoot_seconds=0.)
        with self.assertRaises(old.OpticalError):
            timed.validate_run(self.run)

    def test_timed_watchdog_evidence_required_and_not_inferred(self):
        for key, value in (("timed_watchdog_seconds", 90), ("timed_watchdog_renewals", 1),
                           ("active_G_seconds", 38.), ("disarm_seconds", 0.),
                           ("host_alarm_restored_before_cleanup", False),
                           ("candidate_watchdog", "armed60s_no_renewal"),
                           ("return_qualified_monotonic", 23.)):
            run = deepcopy(self.run)
            run[key] = value
            with self.subTest(key=key), self.assertRaises(old.OpticalError):
                timed.validate_run(run)

    def test_prequiet_overshoot_never_shortens_wait(self):
        # A longer read-only prequiet may extend hold, not reduce its 4.5 s.
        run = deepcopy(self.run)
        middle = run["stages"][1]
        start = middle["camera_start"]["host_capture_bounds"]["end_monotonic"]
        middle["return_prequiet"].update(ended_monotonic=start+4.6, wait_seconds=0.,
                                          overlap_seconds=4.49, overshoot_seconds=.1)
        self.assertEqual(len(timed.validate_run(run)), 3)

    def test_missing_quiet_native_state_rejected(self):
        for key, value in (("native_actual_hz", 90), ("native_group", 5)):
            run = deepcopy(self.run)
            run["stages"][1]["return_prequiet"]["quiet_evidence"]["native_state"][key] = value
            with self.assertRaises(old.OpticalError):
                timed.validate_run(run)

    def test_target_quiet_marker_interval_checked_without_clock_mixing(self):
        marker = self.run["stages"][1]["return_prequiet"]["quiet_evidence"]["kernel_marker_bounds"]
        marker["end_seconds"] = marker["begin_seconds"]+1.9
        with self.assertRaises(old.OpticalError):
            timed.validate_run(self.run)
        marker["end_seconds"] = marker["begin_seconds"]+2.01
        self.assertEqual(len(timed.validate_run(self.run)), 3)
        marker["clock"] = "host"
        with self.assertRaises(old.OpticalError):
            timed.validate_run(self.run)

    def test_return_cannot_start_before_hold_verification(self):
        run = deepcopy(self.run)
        run["writes"][1]["started_monotonic"] = run["stages"][1]["hold_end_monotonic"]
        with self.assertRaises(old.OpticalError):
            timed.validate_run(run)
        run = deepcopy(self.run)
        run["stages"][1]["hold_verified_monotonic"] = run["stages"][1]["hold_end_monotonic"]-.01
        with self.assertRaises(old.OpticalError):
            timed.validate_run(run)

    def test_c1_output_never_fills_middle_data(self):
        result = timed.c1_observations(timed.validate_run(self.run))
        self.assertEqual(result[0]["data"], [0, 0, 96])
        self.assertEqual(result[2]["data"], [0, 0, 96])
        self.assertEqual(result[1]["status"], "not_measured")
        self.assertNotIn("data", result[1])

    def test_timing_still_rejects_small_windows_gaps_and_changed_camera(self):
        with self.assertRaises(old.OpticalError):
            timed.select_windows(self.run, self.pts, frames=59)
        pts = self.pts.copy()
        pts[100] = pts[99]
        with self.assertRaises(old.OpticalError):
            timed.select_windows(self.run, pts)
        self.run["stages"][1]["camera_end"]["result"]["exposure_ns"] = 500000
        with self.assertRaises(old.OpticalError):
            timed.select_windows(self.run, self.pts)

    def test_cli_unfinished_rejected_before_video_access(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            run = deepcopy(self.run)
            run.pop("finished_at_utc")
            source = directory/"run.json"
            source.write_text(json.dumps(run))
            with patch.object(old, "probe_video") as probe:
                with self.assertRaises(old.OpticalError):
                    timed.main([str(source), str(directory/"missing.mp4"), "--plan",
                                "--output", str(directory/"out.json")])
                probe.assert_not_called()

    def test_plan_output_honestly_marks_omission_and_no_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source, video, output = directory/"run.json", directory/"video.mp4", directory/"out.json"
            source.write_text(json.dumps(self.run));video.write_bytes(bytes(123))
            probe = {"streams": [{"codec_type": "video", "codec_name": "h264", "width": 1280,
                                  "height": 720, "pix_fmt": "yuv420p", "color_range": "tv",
                                  "nb_frames": str(len(self.pts))}],
                     "frames": [{"best_effort_timestamp_time": str(x)} for x in self.pts]}
            with patch.object(old, "probe_video", return_value=probe):
                timed.main([str(source), str(video), "--plan", "--output", str(output)])
            result = json.loads(output.read_text())
            self.assertEqual(result["c1_observations"][1]["status"], "not_measured")
            self.assertNotIn("data", result["c1_observations"][1])
            self.assertIsNone(result["physical_pwm_hz"])
            self.assertIsNone(result["stock_optics_restored"])
            self.assertFalse(result["lead_approved"])
            self.assertFalse(result["candidate_enabled"])
            self.assertFalse(result["review_template"]["native_y_noautorotate_inspected"])

    def test_no_overwrite_under_optimized_python(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/"out.json";output.write_text("sentinel")
            process = subprocess.run([sys.executable, "-O", timed.__file__,
                                      "missing.json", "missing.mp4", "--plan", "--output", str(output)],
                                     capture_output=True, text=True)
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("Refusing to overwrite JSON", process.stderr)
            self.assertEqual(output.read_text(), "sentinel")

    def test_completed_legacy_timing_plans_identical(self):
        root = Path(__file__).resolve().parents[1]
        for folder in ("p85_stock_a001_20261108_04", "p85_batch_stock_a001_20261108_01"):
            path = root/"artifacts"/folder
            if not (path/"optical_profiles.npz").is_file():
                self.skipTest("Saved legacy numerical fixture unavailable")
            run = json.loads((path/"run.json").read_text())
            plan = json.loads((path/"optical_plan.json").read_text())
            with np.load(path/"optical_profiles.npz", allow_pickle=False) as profiles:
                pts = profiles["pts"]
            with self.subTest(folder=folder):
                self.assertEqual(old.select_windows(run, pts), plan["windows"])
                self.assertEqual(old.select_windows(run, pts, snapshot_age_seconds=.5,
                                                    binding_frames=3),
                                 plan["stronger_timing_sensitivity"]["windows"])


if __name__ == "__main__":
    unittest.main()
