"""R043 archive arithmetic + R044 prospective rule. Offline, public derivatives only."""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "r8_raster_context_20261118" / "results.json"


def ranked(triple):
    if len(triple) != 3 or not all(math.isfinite(x) for x in triple) or list(triple) != sorted(triple):
        raise ValueError("expected finite min/median/max of three slots")
    return triple


def archive(rows, sequence):
    if len(rows) != len(sequence):
        raise ValueError("phase count mismatch")
    ordered = [ranked(row) for row in rows]
    a = [row for row, label in zip(ordered, sequence) if label == "A"]
    b = [row for row, label in zip(ordered, sequence) if label == "B"]
    # Descriptive only. No time-order or cross-ROI errors recoverable from triples.
    return dict(phases=sequence, frames=3*len(rows),
                B_minus_A_median_range=[round(min(v[1] for v in b)-max(v[1] for v in a), 8),
                                        round(max(v[1] for v in b)-min(v[1] for v in a), 8)],
                B_minus_A_all_slot_range=[round(min(v[0] for v in b)-max(v[2] for v in a), 8),
                                          round(max(v[2] for v in b)-min(v[0] for v in a), 8)])


def difference(legs):
    if len(legs) != 3 or not all(math.isfinite(x) for x in legs):
        raise ValueError("expected three finite phase medians")
    x,y,z = legs
    return y-x,y-z,z-x


def screen(aba, aaa):
    """Numeric portion ONLY. One ABA plus three disjoint same-setup sham triplets."""
    if len(aaa) != 3:
        raise ValueError("need all three sham triplets")
    t = max(abs(v) for phases in aaa for v in difference(phases))
    ab, cb, ret = difference(aba)
    return ((min(ab,cb) > t or max(ab,cb) < -t) and abs(ret) <= t)


def main():
    d = json.loads(SOURCE.read_text())
    if d["included"] != dict(sham=51,r7=42,wbw=9,spatial=15):
        raise ValueError("unexpected source cohorts")
    c = d["context"]
    r7 = c["R7"]
    if len(r7["phase_median_rgb_DN"]) != 14:
        raise ValueError("incomplete R7")
    out = dict(metric="per-slot ln(center/right), as summarized in R8", archived={
        key:archive(c[key]["phase_log_center_right_min_median_max"], seq)
        for key,seq in (("WBW","ABA"),("spatial","ABABA"))},
        R7_42_slots_any_channel_zero_percent_min_max=r7["any_channel_zero_percent_min_max"],
        matched_sham_triplets_available_in_input=0, new_slots=0)
    print(json.dumps(out, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
