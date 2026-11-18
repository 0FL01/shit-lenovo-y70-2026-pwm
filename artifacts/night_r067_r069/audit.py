"""Replay sanitized archive fields. No hardware, private inputs or network."""
import json
import re
import struct
from pathlib import Path
from statistics import median

A = Path(__file__).resolve().parents[1]


def need(ok, message):
    if not ok:
        raise ValueError(message)


def obj(path):
    return json.loads((A / path).read_text())


def dc(trial, trace):
    phases = trial["phases"]
    names = [p["name"] for p in phases]
    markers = trace["markers"]
    need(len(phases) == len(set(names)) == 6 and
         [m["phase"] for m in markers] == names, "incomplete phase markers")
    times = [m["timestamp"] for m in markers]
    need(all(x < y for x, y in zip(times, times[1:])), "marker order")
    need(trial["six_stock_phases_completed"] and trial["cleanup_verified"]
         and trace["cleanup_verified"] and not trace["trace_reports_lost_events"],
         "incomplete source or restore")
    rows = []
    matches = trace["exact_dc_set_matches"]
    for m in matches:
        need(m["payload_and_dtype_match_live_dt"] and
             (m["packets"], m["bytes"]) == (75, 875), "not a complete DC set")
        i = names.index(m["phase"])
        need(times[i] <= m["timestamp"] and
             (i == len(times)-1 or m["timestamp"] < times[i+1]), "misassigned set")
    for p in phases:
        obs = p["observed"]
        provider = int(re.fullmatch(r"Result: Bundle\[\{value=([01])\}\]", obs["requested_dc"])[1])
        state = int(obs["panel_dc"])
        need(provider == state == p["requested_dc"], "provider/panel state mismatch")
        sets = sorted((m for m in matches if m["phase"] == p["name"]), key=lambda m:m["timestamp"])
        rows.append([p["name"], provider, state, int(obs["brightness"]), [m["dc"] for m in sets]])
    return rows


def extra(doc, locked):
    states = doc["target_snapshots"]
    base = states["transaction_pre"]["fields"]
    rows = []
    for phase in ("transaction_pre", "on1_pre", "restore_independent", "final"):
        f = states[phase]["fields"]
        diff = sorted(k for k in set(f) | set(base) if f.get(k) != base.get(k))
        need(diff == (["activated", "activated_key", "color_matrix", "rbc"] if phase == "on1_pre" else []),
             "not an isolated recorded software contrast")
        matrix = f["color_matrix"]
        diag = matrix[0][0]
        expected = [[(diag if i < 3 else 1) if i == j else 0 for j in range(4)] for i in range(4)]
        need(matrix == expected, "not a common RGB scalar")
        rows.append([phase, f["activated_key"], diag, f["strength"], f["panel_brightness"],
                     f["panel_actual_brightness"], f["vsync_hz"]])
    photos = locked["photos"]
    labels = [p["label"] for p in photos]
    need(labels == [f"{s}{i}" for s in ("off","on","return") for i in (1,2,3)],
         "missing or reordered raster frames")
    return {"states": rows, "auto_accepted": doc["on_contrast_admitted"],
            "auto_photos": len(doc["photos"]),
            "locked_raster_medians": [median(p["bright_red_pixel_fraction"] for p in photos
                                              if p["label"].startswith(s)) for s in ("off","on","return")]}


def apl():
    dt = A / "device_tree/selected_boe_v4"
    def u32(name):
        return struct.unpack(">I", (dt / name).read_bytes())[0]
    threshold = u32("qcom,mdss-dsi-panel-APL-THRESHOLD-BL")
    maximum = u32("qcom,mdss-dsi-bl-max-level")
    need((dt/"qcom,apl-enabled").is_file(), "no APL enable property")
    code = (A/"brightness_policy_recon_20261107/evidence/dsi_panel_set_apl.txt").read_text()
    for line in (r"1b5a6c:\s+6b01013f\s+cmp\s+w9, w1",r"1b5a70:\s+54000262\s+b.cs\s+1b5abc"):
        need(re.search(line,code), "unverified threshold comparison")
    pre = (A/"stock_apl_reachability_20261118/result.md").read_text()
    cap, mapped = map(float, re.search(r"framework (\d+\.\d+) → нормализованный backlight (\d+\.\d+)",pre).groups())
    native = int(re.search(r"native brightness (\d+) \(в начале и в конце\)",pre)[1])
    need(f"max_brightness {maximum}" in pre and 0 < cap < 1 and 0 < mapped < 1, "preflight model")
    return {"threshold": threshold,"first_on_candidate": threshold+1,"max_class": maximum,
            "framework_cap":cap, "mapped_normalized_backlight":mapped,
            "estimated_native_at_cap":round(maximum*mapped),"pre_and_post_native":native}


def audit():
    return {"dc_phase_rows":dc(obj("stock_dc_trial_20261106.json"),obj("stock_dc_trace_analysis_20261106.json")),
            "extra_dim":extra(obj("STOCK_EXTRA_DIM_20261118_data.json"),
                              obj("stock_extra_dim_locked_20261118/observations.json")),
            "apl":apl()}


if __name__ == "__main__":
    print(json.dumps(audit(),indent=2))
