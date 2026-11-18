"""Default suite uses only committed output and synthetic metadata."""
import argparse
import json
from pathlib import Path
import sys
import unittest

import audit

ARCHIVE = SOURCE = None


def field(key, value):
    return f"    android.{key} (eeee): int32[1]\n      [{value} ]\n"


def driver_name(name):
    data = (name.encode("ascii") + b"\0").ljust(50, b"\0")
    return "    com.nothing.camera.moduleInfo.sensorname (901a0000): byte[50]\n" + "".join(
        "    [" + " ".join(map(str, data[i:i+16])) + " ]\n" for i in range(0, len(data), 16))


def sample():
    return ("== Camera device 2 dynamic info: ==\nDevice 2 is open.\nClient package: com.nothing.camera\n"
            "Latest received frame:\n" + field("sensor.exposureTime", 156000) +
            field("sensor.rollingShutterSkew", 31824000) + field("control.aeMode", "OFF") +
            "Device status:\nLast request sent:\n" + field("sensor.exposureTime", 200000) +
            "== Camera device 3 dynamic info: ==\n"
            "== Camera HAL device device@1.1/internal/1 (v1.2) static information: ==\n" +
            driver_name("SENSOR_DRVNAME_OTHER") + "dumpState:\n"
            "== Camera HAL device device@1.1/internal/2 (v1.2) static information: ==\n" +
            driver_name(audit.DRIVER) + field("sensor.info.activeArraySize", "0 0 3264 2448") + "dumpState:\n")


class Core(unittest.TestCase):
    def test_local_name_and_actual_not_request(self):
        v = audit.extract_dump(sample())
        self.assertEqual((v["driver"], v["exposure_ns"], v["request_exposure_ns"]),
                         (audit.DRIVER, 156000, 200000))

    def test_wrong_id(self):
        with self.assertRaises(ValueError):
            audit.extract_dump(sample().replace("internal/2", "internal/7"))

    def test_other_static_cannot_rescue_wrong_model(self):
        other = driver_name("SENSOR_DRVNAME_OTHER")
        s = sample().replace(other, "SWAP").replace(driver_name(audit.DRIVER), other).replace("SWAP", driver_name(audit.DRIVER))
        with self.assertRaises(ValueError):
            audit.extract_dump(s)

    def test_malformed_name(self):
        raw = driver_name(audit.DRIVER)
        for wrong in (raw + raw, raw.replace("[0 0 ]", "[0 ]"), raw.replace("[0 0 ]", "[0 7 ]")):
            with self.subTest(wrong=wrong[-20:]), self.assertRaises(ValueError):
                audit.sensor_name(wrong)

    def test_rejects_non_nothing_client(self):
        with self.assertRaises(ValueError):
            audit.extract_dump(sample().replace("com.nothing.camera\n", "elsewhere\n"))

    def test_does_not_substitute_request_for_missing_result(self):
        with self.assertRaises(ValueError):
            audit.extract_dump(sample().replace(field("sensor.exposureTime", 156000), ""))

    def test_report_claim_ceiling(self):
        v = json.loads((audit.HERE / "outcome.json").read_text())
        self.assertEqual(v["model_line_ns"], 13000)
        for s in v["samples"].values():
            self.assertEqual(s["exposure_ns"], s["exposure_in_model_lines"] * 13000)
            self.assertEqual(s["skew_ns"], s["active_rect"][3] * 13000)
        for k in ("installed_binary_source_match", "selected_sensor_scenario", "screenshot_readout_axis_and_sign",
                  "optical_preview_pixel_time_ns", "panel_pwm_hz"):
            self.assertIsNone(v[k])


class PinnedInputs(unittest.TestCase):
    def setUp(self):
        if ARCHIVE is None:
            self.skipTest("supply original archive and official C source for integration replay")

    def test_pinned_replay_matches_published(self):
        self.assertEqual(audit.audit(ARCHIVE, SOURCE), json.loads((audit.HERE/"outcome.json").read_text()))

    def test_wrong_source_rejected_before_reading_dumps(self):
        with self.assertRaisesRegex(ValueError, "wrong public source"):
            audit.audit(ARCHIVE, Path(__file__))

    def test_mode_table_does_not_accept_commented_template(self):
        text = SOURCE.read_text()
        with self.assertRaisesRegex(ValueError, "mode coverage changed"):
            audit.source_tables(text.replace(".frame_desc = frame_desc_vid,", "// .frame_desc = frame_desc_vid,"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_archive", nargs="?", type=Path)
    parser.add_argument("public_sensor_c", nargs="?", type=Path)
    args = parser.parse_args()
    ARCHIVE, SOURCE = args.private_archive, args.public_sensor_c
    if (ARCHIVE is None) != (SOURCE is None):
        parser.error("supply both originals or neither")
    unittest.main(argv=[sys.argv[0]])
