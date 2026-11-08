#!/usr/bin/env python3
"""Run the owner-approved XT2611-1 stock DC experiment; never send raw DSI.

Requires the Display Settings page scrolled to the English Flicker prevention
row, existing research-shell root, and the approved 2026-11-06 trial record.
Raw kernel/UI logs stay private; the public record contains commands/state only.
"""

import json
import re
import shlex
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "artifacts/stock_dc_trial_20261106.json"
PRIVATE = Path("/home/stfu/.cache/opencode-tmp/opencode/stock-dc-trial-20261106")
TRACE = "/sys/kernel/tracing/instances/pwm_dc"
LOGGER = "/sys/class/drm/card0-DSI-1/mipi_cmd_log_en"
PROBES = {
    "ctrl_return": "dsi_ctrl_cmd_transfer",
    "param_return": "dsi_panel_send_param_cmd",
}


def main():
    devices = subprocess.check_output(["adb", "devices"], text=True)
    targets = [line.split()[0] for line in devices.splitlines()[1:]
               if len(line.split()) >= 2 and line.split()[1] == "device"]
    assert len(targets) == 1, "Need one authorized target"
    serial = targets[0]
    report = json.loads(REPORT.read_text())
    assert "execution_started_at_utc" not in report, "Do not repeat the trial"
    assert PRIVATE.is_dir() and PRIVATE.stat().st_mode & 0o777 == 0o700
    events = report.setdefault("execution_events", [])
    created_probes = []
    instance_created = False
    settings_changed = False
    dc_touched = True  # The approved UI preparation already toggled the inline row ON.
    logger_changed = False

    def save():
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    def shell(command, *, root=False, check=True, private=None):
        remote = "su -c " + shlex.quote(command) if root else command
        result = subprocess.run(["adb", "-s", serial, "shell", remote],
                                capture_output=True, text=True, timeout=40)
        stdout = result.stdout.replace(serial, "<target>").strip()
        stderr = result.stderr.replace(serial, "<target>").strip()
        if private:
            path = PRIVATE / private
            path.write_text(result.stdout)
            path.chmod(0o600)
        events.append({"at_utc": datetime.now(timezone.utc).isoformat(),
                       "command": remote, "exit_code": result.returncode,
                       "stdout": "<private file: " + private + ">" if private else stdout,
                       "stderr": stderr})
        save()
        if check and result.returncode:
            raise RuntimeError(f"Command failed: {remote}: {stderr}")
        return stdout

    def state():
        return {
            "requested_dc": shell("content call --uri content://com.motorola.android.providers.settings/global --method GET_global --arg display_dc_mode_enabled"),
            "panel_dc": shell("cat /sys/class/drm/card0-DSI-1/panelDC", root=True),
            "brightness": shell("cat /sys/class/backlight/panel0-backlight/brightness", root=True),
            "bl_power": shell("cat /sys/class/backlight/panel0-backlight/bl_power", root=True),
            "selinux": shell("getenforce"),
        }

    def set_dc(enabled):
        nonlocal dc_touched
        shell("input keyevent 224; wm dismiss-keyguard; uiautomator dump /data/local/tmp/pwm-dc-settings.xml")
        text = shell("cat /data/local/tmp/pwm-dc-settings.xml", private="current-ui.xml")
        tree = ET.fromstring(text)
        parents = {child: parent for parent in tree.iter() for child in parent}
        labels = [node for node in tree.iter("node") if node.get("text") == "Flicker prevention"]
        assert len(labels) == 1, "Expected exact stock preference; never blind-tap"
        row = labels[0]
        while row.get("clickable") != "true":
            row = parents[row]
        switches = [node for node in row.iter("node") if node.get("checkable") == "true"]
        assert len(switches) == 1, "Ambiguous stock switch"
        current = switches[0].get("checked") == "true"
        if current != enabled:
            bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", row.get("bounds"))
            assert bounds
            x1, y1, x2, y2 = map(int, bounds.groups())
            dc_touched = True
            shell(f"input tap {(x1 + x2) // 2} {(y1 + y2) // 2}")
        observed = state()
        requested = re.search(r"\bvalue=(null|[01])\b", observed["requested_dc"])
        assert requested and requested.group(1) in (("1",) if enabled else ("0", "null")), observed
        assert observed["panel_dc"] == str(int(enabled)), observed
        assert observed["bl_power"] == "0", observed
        assert observed["selinux"] == "Enforcing", observed
        return observed

    identity = shell("printf '%s|%s|%s|' \"$(getprop ro.boot.hardware.sku)\" \"$(getprop ro.build.display.id)\" \"$(getprop ro.boot.slot_suffix)\"; uname -r; getenforce")
    assert identity.startswith("XT2611-1|W3WWS36.65-64-4-1|_b|")
    assert "-dirty-" in identity and "Enforcing" in identity
    assert shell("id", root=True).startswith("uid=0(")
    assert shell("cat " + LOGGER, root=True).endswith(": 0")
    assert shell("settings get system screen_brightness_mode") == "1"
    for name in ("peak_refresh_rate", "min_refresh_rate"):
        assert shell("settings get system " + name) == "null"
    shell(f"test ! -e {TRACE}", root=True)
    existing = shell("cat /sys/kernel/tracing/kprobe_events", root=True, private="preexisting-probes.txt")
    assert "pwm_dc/" not in existing
    report["execution_started_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["original_effective_dc"] = 0
    report["preparation_note"] = "Opening the inline stock row toggled it ON before tracing; execution returns OFF. This untraced preparation is not counted as captured evidence."
    save()
    error = None
    try:
        shell("mkdir " + TRACE, root=True)
        instance_created = True
        shell(f"printf '0\\n' > {TRACE}/tracing_on", root=True)
        shell(f"printf 'mono\\n' > {TRACE}/trace_clock", root=True)
        for name, symbol in PROBES.items():
            definition = f"r:pwm_dc/{name} msm_drm:{symbol} rc=$retval:s32"
            shell("printf '%s\\n' " + shlex.quote(definition) + " >> /sys/kernel/tracing/kprobe_events", root=True)
            created_probes.append(name)
            shell(f"printf '1\\n' > {TRACE}/events/pwm_dc/{name}/enable", root=True)
        shell(f"printf '1\\n' > {TRACE}/tracing_on", root=True)
        logger_changed = True
        shell(f"printf '1\\n' > {LOGGER}", root=True)
        assert shell("cat " + LOGGER, root=True).endswith(": 1")
        settings_changed = True
        shell("settings put system screen_brightness_mode 0; settings put system min_refresh_rate 120.0; settings put system peak_refresh_rate 120.0")
        assert shell("settings get system screen_brightness_mode") == "0"
        for name in ("min_refresh_rate", "peak_refresh_rate"):
            assert float(shell("settings get system " + name)) == 120.0
        report["phases"] = []
        for brightness in (78, 40):
            shell(f"input keyevent 224; settings put system screen_brightness {brightness}")
            assert shell("settings get system screen_brightness") == str(brightness)
            for enabled in (False, True, False):
                name = f"brightness{brightness}_dc{int(enabled)}_{len(report['phases'])}"
                shell("printf '%s\\n' " + shlex.quote("<6>PWM_DC_PHASE " + name) + " > /dev/kmsg", root=True)
                observed = set_dc(enabled)
                report["phases"].append({"name": name, "requested_brightness": brightness,
                                         "requested_dc": int(enabled), "observed": observed})
                save()
                returns = shell("cat " + TRACE + "/trace", root=True, private="returns-latest.txt")
                assert not re.search(r"\brc=-\d+\b", returns), "Negative native transfer/parameter return; stop"
        shell(f"printf '0\\n' > {TRACE}/tracing_on", root=True)
        shell("cat " + TRACE + "/trace", root=True, private="return-trace.txt")
        shell("cat /sys/kernel/tracing/kprobe_profile", root=True, private="probe-profile.txt")
        shell("dmesg", root=True, private="kernel-log.txt")
        shell("dumpsys display", private="display-state.txt")
        report["six_stock_phases_completed"] = True
    except Exception as caught:
        error = str(caught)
        report["execution_error"] = error
        shell("dmesg", root=True, private="kernel-log-on-error.txt", check=False)
    finally:
        failures = []
        if dc_touched:
            try:
                report["cleanup_dc"] = set_dc(False)
            except Exception as caught:
                failures.append("stock UI DC OFF: " + str(caught))
        if logger_changed:
            shell(f"printf '0\\n' > {LOGGER}", root=True, check=False)
        if instance_created:
            shell(f"printf '0\\n' > {TRACE}/tracing_on", root=True, check=False)
            for name in created_probes:
                shell(f"printf '0\\n' > {TRACE}/events/pwm_dc/{name}/enable", root=True, check=False)
            shell("rmdir " + TRACE, root=True, check=False)
        for name in reversed(created_probes):
            shell("printf '%s\\n' " + shlex.quote("-:pwm_dc/" + name) + " >> /sys/kernel/tracing/kprobe_events", root=True, check=False)
        if settings_changed:
            shell("settings put system screen_brightness 78; settings put system screen_brightness_mode 1; settings delete system min_refresh_rate; settings delete system peak_refresh_rate", check=False)
        report["cleanup_checks"] = {
            "logger": shell("cat " + LOGGER, root=True, check=False),
            "auto": shell("settings get system screen_brightness_mode", check=False),
            "peak": shell("settings get system peak_refresh_rate", check=False),
            "min": shell("settings get system min_refresh_rate", check=False),
            "own_instance_absent": shell(f"test ! -e {TRACE} && echo yes", root=True, check=False),
            "remaining_own_probes": "pwm_dc/" in shell("cat /sys/kernel/tracing/kprobe_events", root=True, private="remaining-probes.txt", check=False),
        }
        report["cleanup_errors"] = failures
        checks = report["cleanup_checks"]
        report["cleanup_verified"] = (
            checks["logger"].endswith(": 0") and checks["auto"] == "1"
            and checks["peak"] == checks["min"] == "null"
            and checks["own_instance_absent"] == "yes"
            and not checks["remaining_own_probes"]
            and report.get("cleanup_dc", {}).get("panel_dc") == "0"
        )
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        save()
    print(json.dumps({key: value for key, value in report.items()
                      if key not in ("execution_events", "visible_display_settings")},
                     ensure_ascii=False, indent=2), flush=True)
    if error or report["cleanup_errors"] or not report["cleanup_verified"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
