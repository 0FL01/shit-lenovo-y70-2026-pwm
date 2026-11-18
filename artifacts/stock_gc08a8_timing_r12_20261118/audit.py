"""Compare pinned public driver data with archived camera reports. Offline, no ADB."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
R11 = HERE.parent / "stock_expert_direct_r11_20261118"
SHA = "65ef638c5c49dddf78f5b48edddd44786d705197"
PUBLIC_HASH = "31642addc37af0b7c370b80805ffe731a9f8074fa50e8d8114f6daef6a7a6e05"
DRIVER = "SENSOR_DRVNAME_GC08A8_MIPI_RAW"
SAMPLES = ("expert_wide", "short_drag", "short2", "short3", "short4", "wide_auto_return")


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def section(text, begin, end):
    require(text.count(begin) == 1, "ambiguous/missing " + begin)
    tail = text.split(begin, 1)[1]
    require(end in tail, "missing terminator " + end)
    return tail.split(end, 1)[0]


def unique(pattern, text):
    hits = re.findall(pattern, text, re.M)
    require(len(hits) == 1, "ambiguous/missing field: " + pattern)
    return hits[0]


def sensor_name(static):
    raw = unique(r"^\s*com\.nothing\.camera\.moduleInfo\.sensorname \([0-9a-f]+\): byte\[50\]\n((?:[ \t]*\[(?:\d+[ \t]*)+\][ \t]*\n)+)", static)
    data = bytes(map(int, re.findall(r"\d+", raw)))
    require(len(data) == 50, "incomplete driver name")
    name, nul, pad = data.partition(b"\0")
    require(nul and not any(pad), "invalid driver-name padding")
    return name.decode("ascii")


def field(text, key):
    return unique(r"^[ \t]*android\." + re.escape(key) + r" \([0-9a-f]+\): [^\n]+\n[ \t]*\[([^\]\n]+)\]", text).strip()


def extract_dump(text):
    dynamic = section(text, "== Camera device 2 dynamic info: ==", "== Camera device 3 dynamic info: ==")
    static = section(text, "== Camera HAL device device@1.1/internal/2 (v1.2) static information: ==", "dumpState:")
    require("Device 2 is open." in dynamic and "Client package: com.nothing.camera" in dynamic, "camera/client mismatch")
    actual = section(dynamic, "Latest received frame:", "Device status:")
    request = dynamic.split("Last request sent:", 1)[1]
    name = sensor_name(static)
    require(name == DRIVER, "unexpected camera 2 driver")
    return dict(driver=name, active_rect=list(map(int, field(static, "sensor.info.activeArraySize").split())),
                ae=field(actual, "control.aeMode"), skew_ns=int(field(actual, "sensor.rollingShutterSkew")),
                exposure_ns=int(field(actual, "sensor.exposureTime")), request_exposure_ns=int(field(request, "sensor.exposureTime")))


def source_tables(text):
    # Ignore the commented-out high-speed template. Only designated entries in the
    # sensor-mode table count; do not accept a value copied from an unrelated sensor.
    text = re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)
    array = section(text, "static struct subdrv_mode_struct mode_struct[] = {", "\n};")
    ctx = section(text, "static struct subdrv_static_ctx static_ctx = {", "\n};")
    require(unique(r'^\s*\.name\s*=\s*"([^"]+)"\s*,', text) == "gc08a8_mipi_raw", "driver entry point")
    def decimal(record, key):
        return int(unique(r"^\s*\." + key + r"\s*=\s*([0-9]+)\s*,", record))
    matches = list(re.finditer(r"^\s*\.frame_desc\s*=\s*frame_desc_(\w+)\s*,", array, re.M))
    require([x[1] for x in matches] == ["prev", "cap", "vid"], "mode coverage changed")
    scenarios = {}
    for i, match in enumerate(matches):
        part = array[match.end():matches[i+1].start() if i+1 < len(matches) else len(array)]
        scenarios[match[1]] = {k: decimal(part, k) for k in ["pclk", "linelength", "framelength", "full_h", "y1_offset", "w2_tg_size", "h2_tg_size"]}
    return scenarios, decimal(ctx, "exposure_step")


def audit(archive, driver_file):
    src = driver_file.read_bytes()
    require(hashlib.sha256(src).hexdigest() == PUBLIC_HASH, "wrong public source")
    scenarios, step = source_tables(src.decode())
    line_times = {Fraction(10**9 * s["linelength"], s["pclk"]) for s in scenarios.values()}
    require(len(line_times) == 1, "different candidate mode timing")
    line = line_times.pop()
    require(line == 13000 and step == 4, "unexpected source line/step")
    pins = json.loads((R11 / "private_evidence_hashes.json").read_text())
    samples = {}
    for key in SAMPLES:
        filename = key + "_raw.txt"
        raw = (archive / filename).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == pins[filename], "unrecognized " + filename)
        v = extract_dump(raw.decode())
        require(v["active_rect"] == [0, 0, 3264, 2448], "active array changed")
        require(v["skew_ns"] == line * v["active_rect"][3], "skew/model disagreement")
        n = v["exposure_ns"] / line
        require(n.denominator == 1 and n.numerator % step == 0, "exposure not on declared grid")
        is_short = key.startswith("short")
        require((v["ae"], v["exposure_ns"], v["request_exposure_ns"]) == (
            ("OFF", 156000, 200000) if is_short else ("ON", 60008000, 0)), "unexpected mode")
        samples[key] = dict(**v, exposure_in_model_lines=n.numerator)
    return dict(public_driver_git_commit=SHA, public_source_sha256=PUBLIC_HASH,
                driver_declared_modes=scenarios, model_line_ns=int(line), declared_exposure_step_lines=step,
                samples=samples, installed_binary_source_match=None, selected_sensor_scenario=None,
                screenshot_readout_axis_and_sign=None, optical_preview_pixel_time_ns=None, panel_pwm_hz=None)


if __name__ == "__main__":
    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument("private_r11_archive", type=Path)
    arg.add_argument("public_sensor_c", type=Path)
    args = arg.parse_args()
    print(json.dumps(audit(args.private_r11_archive, args.public_sensor_c), indent=2))
