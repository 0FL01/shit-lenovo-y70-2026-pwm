#!/usr/bin/env python3
"""Read-only structural audit of the supplied PWM context pack. No device I/O."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_packets(blob: bytes) -> list[dict]:
    result = []
    offset = 0
    page = None
    while offset < len(blob):
        if offset + 7 > len(blob):
            raise ValueError(f"Truncated packet header at {offset}")
        header = blob[offset:offset + 7]
        size = int.from_bytes(header[5:7], "big")
        end = offset + 7 + size
        if end > len(blob) or size == 0:
            raise ValueError(f"Invalid packet length at {offset}")
        payload = blob[offset + 7:end]
        is_page = len(payload) == 4 and payload[:3] == bytes.fromhex("ff 5a a5")
        if is_page:
            page = payload[3]
        result.append({
            "index": len(result), "offset": offset,
            "header": header.hex(" "), "page": page,
            "opcode": payload[0], "is_page_selector": is_page,
            "payload": payload.hex(" "), "data": payload[1:].hex(" "),
        })
        offset = end
    return result


def writes(packets: list[dict], page: int, opcode: int) -> list[dict]:
    return [p for p in packets if not p["is_page_selector"]
            and p["page"] == page and p["opcode"] == opcode]


def audit(root: Path) -> dict:
    panel = root / "artifacts/device_tree/selected_boe_v4"
    off_path = panel / "qcom,mdss-dsi-dc-off-command"
    on_path = panel / "qcom,mdss-dsi-dc-on-command"
    off, on = off_path.read_bytes(), on_path.read_bytes()
    off_packets, on_packets = parse_packets(off), parse_packets(on)
    if len(off) != 875 or len(on) != 875 or len(off_packets) != 75 or len(on_packets) != 75:
        raise ValueError("Not the archived 875-byte / 75-packet v4 DC pair")
    if [p["header"] for p in off_packets] != [p["header"] for p in on_packets]:
        raise ValueError("DC ON/OFF header mismatch")
    diffs = []
    for a, b in zip(off_packets, on_packets):
        if (a["page"], a["opcode"], a["offset"]) != (b["page"], b["opcode"], b["offset"]):
            raise ValueError("Packet alignment mismatch")
        if a["payload"] != b["payload"]:
            diffs.append({"packet_index": a["index"], "page": f"{a['page']:02X}",
                          "opcode": f"{a['opcode']:02X}", "off_data": a["data"],
                          "on_data": b["data"]})

    candidate_checks = []
    for name, expected_offset, page, opcode in (("a9_only", 68, 0x23, 0xA9),
                                               ("9d_only", 97, 0x24, 0x9D)):
        path = root / f"artifacts/dsi_selector_split_20261107/{name}.bin"
        candidate = path.read_bytes()
        deltas = [i for i, (a, b) in enumerate(zip(off, candidate)) if a != b]
        if len(candidate) != len(off) or deltas != [expected_offset]:
            raise ValueError(f"Unexpected byte changes in {name}")
        if off[expected_offset] != 0x0E or candidate[expected_offset] != 0x8E:
            raise ValueError(f"Unexpected candidate value in {name}")
        parsed = parse_packets(candidate)
        if [p["header"] for p in parsed] != [p["header"] for p in off_packets]:
            raise ValueError(f"Changed packet headers in {name}")
        match = writes(parsed, page, opcode)
        if len(match) != 1 or match[0]["data"] != "8e":
            raise ValueError(f"Wrong page/opcode in {name}")
        candidate_checks.append({"name": name, "offset": expected_offset,
                                 "page_opcode": f"{page:02X}:{opcode:02X}",
                                 "from": "0e", "to": "8e", "packets": len(parsed),
                                 "scope": "offline validation; no Hz semantics established"})

    modes = []
    for directory in sorted((panel / "qcom,mdss-dsi-display-timings").glob("timing@*")):
        nominal = int.from_bytes((directory / "qcom,mdss-dsi-panel-framerate").read_bytes(), "big")
        groups = sorted(p.name for p in directory.iterdir() if "framerate-group" in p.name)
        packets = parse_packets((directory / "qcom,mdss-dsi-timing-switch-command").read_bytes())
        selected = [p for p in packets if p["page"] == 0x2D and p["opcode"] in (0x83, 0x84, 0x85)]
        effective = (10 if any("idle-10hz" in x for x in groups) else
                     1 if any("idle-1hz" in x for x in groups) else nominal)
        mode = {"timing": directory.name, "nominal_fps_property": nominal,
                "effective_mode_from_labels": effective, "groups": groups,
                "page_2d_payloads": [p["payload"] for p in selected],
                "packet_count": len(packets)}
        if len(selected) == 1 and selected[0]["opcode"] == 0x83:
            code = bytes.fromhex(selected[0]["data"])[0]
            predicted = 120 / (code + 1)
            mode.update({"formula": "120 / (first_data_byte + 1)",
                         "formula_fps": predicted, "matches_mode_label": predicted == effective,
                         "interpretation": "frame-division hypothesis; not a PWM setter"})
        modes.append(mode)

    history_path = root / "artifacts/ddic_regdump_20261107/stock_timing_history_analysis.json"
    history = json.loads(history_path.read_text())
    stock_history = [{"label": p["label"], "software_refresh": p["software_refresh"],
                      "read_4f81": p["read_4f81"],
                      "archived_autocorrelation_lags_px": [a["lag_px"] for a in p["preview_autocorrelation"]]}
                     for p in history["phases"]]

    referenced = ["artifacts/optical", "sources", "extracted", "05-safety",
                  "artifacts/dsi_selector_split_20261107/proposal.md",
                  "artifacts/kernel/gki_r59/kernelsu_next/persistent/install.json"]
    reader = (root / "06-tools/run_ddic_regdump.py").read_text()
    optical = (root / "06-tools/analyze_dsi_redraw.py").read_text()
    return {
        "scope": "Independent offline byte/code audit of the attached archive",
        "device_io": False, "source_files_modified": False,
        "dc_program": {"bytes_each": len(off), "packets_each": len(off_packets),
                       "changed_packets": len(diffs), "packet_differences": diffs},
        "selector_candidates": candidate_checks,
        "timing_programs": modes,
        "stock_4f81_history": stock_history,
        "optical_evidence_status": "Reported analysis only: original optical directory absent"
            if not (root / "artifacts/optical").exists() else "Directory present; pixels not audited by this tool",
        "known_code_hazards": {
            "temporal_mean_subtraction_removes_stationary_bands":
                "signal = selected - selected.mean(axis=0)" in optical,
            "legacy_keyguard_assertion_disabled": "or True" in reader,
        },
        "missing_referenced_paths": [p for p in referenced if not (root / p).exists()],
        "conclusion": {
            "target_2000hz_profile_verified": False,
            "known_frequency_register": None,
            "next_information_gain": [
                "Reanalyse original clips using total/coherent/incoherent spatial power",
                "Use a controlled stock 120-144-120-90-120 sequence to test the base time model",
                "Select a bounded causal register experiment only after stating its prediction",
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive_root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = json.dumps(audit(args.archive_root), indent=2, ensure_ascii=False) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(output)
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
