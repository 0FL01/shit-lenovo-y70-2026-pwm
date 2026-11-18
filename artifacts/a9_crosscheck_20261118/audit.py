"""Verify narrow facts about the saved target arrays and historical manual return."""
import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "06-tools"))
from audit_pwm_archive import parse_packets


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def eq(actual, expected, message):
    # JSON booleans compare equal to 0/1 in Python. Preserve JSON types.
    require(json.dumps(actual, sort_keys=True, allow_nan=False) ==
            json.dumps(expected, sort_keys=True, allow_nan=False), message)


PROGRAMS = {"stock": "b5ed66ba69e6221de5fdeaf4d003c9628602d743880acd1c8e2cf7198facd193",
            "a0d1c1": "8604d62cb74646105413c94105a5d66273e865bda2be0e0225f5dc3f69eac62e"}


def check_history(sent, ret):
    for rec, attempted, active, labels in (
        (sent, 1, True, ["baseline", "a0d1c1"]),
        (ret, 0, False, ["return_a0d1c1"]),
    ):
        auth = rec["authorization"]
        eq(auth["candidates"], ["a0d1c1"], "candidate name")
        eq(auth["program_sha256"], PROGRAMS, "program identities")
        eq(rec["candidate_attempts"], attempted, "attempt total")
        eq(rec["candidate_attempts_by_name"], {"a0d1c1": attempted}, "attempts by name")
        eq([s["label"] for s in rec["stages"]], labels, "stage order")
        eq(rec["pending_bytes_may_exist"], False, "pending bytes")
        eq(rec["cleanup_errors"], [], "cleanup errors")
        for key in ["owner_view_active", "candidate_may_be_active"]:
            eq(rec[key], active, key)
        for key in ["stock_return_verified", "target_restored"]:
            eq(rec[key], not active, key)
        eq(rec["esd_restored"], True, "ESD restore")
        for stage in rec["stages"]:
            eq(stage["native_packets_matched"], 75, "native match count")
            eq(stage["chunks_verified"], 5, "chunk count")
            eq(stage["redraw_completed"], True, "redraw")
            eq(stage["same_dbv_replay"]["dbv"], 3600, "DBV replay")
            eq(stage["same_dbv_replay"]["observed_writes"],
               [{"length": 3, "type": 57, "mode": "hs", "payload": "51 0e 10"}],
               "native brightness write")
            d9 = 142 if stage["label"] == "a0d1c1" else 14
            eq(stage["readback"]["values"],
               {"23:A9": [14], "24:9D": [d9], "00:52": [14, 16]}, "selector/DBV readback")
            eq(stage["readback"]["esd"], "reg_read", "stage ESD")
            eq(stage["readback"]["page_callbacks_verified"], 7, "page callbacks")


def main():
    panel = root / "artifacts/device_tree/selected_boe_v4"
    files = sorted(panel.rglob("*-command"))
    scalar = panel / "qcom,mdss-dsi-te-dcs-command"
    require(scalar in files and scalar.read_bytes() == bytes.fromhex("00000001"), "TE scalar")
    packets = [(p.relative_to(panel).as_posix(), z) for p in files if p != scalar
               for z in parse_packets(p.read_bytes())]
    require((len(files)-1, len(packets)) == (52, 1101), "corpus")
    def hits(page, cmd):
        return [(n,p["data"]) for n,p in packets if not p["is_page_selector"]
                and (p["page"], p["opcode"]) == (page, cmd)]
    dc = "qcom,mdss-dsi-dc-{}-command"
    require(hits(0x23, 0xa9) == [(dc.format("off"), "0e"), (dc.format("on"), "8e")], "A9")
    require(hits(0x23, 0xaa) == [(dc.format("off"), "11"), (dc.format("on"), "11")], "AA")
    require(not hits(0x23, 0xc1) and not hits(0x53, 0x86) and
            not any(hits(0x4f,i) for i in range(0xa1,0xa6)), "unexpected field")
    h = hits(0x23,0x85)
    require(len(h) == 8 and all(a.endswith("/qcom,mdss-dsi-on-command") and b=="15"
                                for a,b in h), "P85")
    view = root / "artifacts/dsi_coupled_9d_20261107/owner_view"
    sent = json.loads((view/"run.json").read_text())
    ret = json.loads((view/"return/run.json").read_text())
    stock = (panel / dc.format("off")).read_bytes()
    on = (panel / dc.format("on")).read_bytes()
    candidate = (view.parent / "on_keep_a9_off.bin").read_bytes()
    require(len(on) == len(candidate) == 875 and
            [k for k,(a,b) in enumerate(zip(on, candidate)) if a != b] == [68] and
            on[68] == 0x8e and candidate[68] == 0x0e, "not full native ON except A9")
    eq({k:hashlib.sha256(v).hexdigest() for k,v in (("stock",stock),("a0d1c1",candidate))},
       PROGRAMS, "archived bytes")
    check_history(sent, ret)
    print("PASS: 52 arrays / 1101 packets; checked fields and recorded reverse A9 return")


if __name__ == "__main__":
    main()
