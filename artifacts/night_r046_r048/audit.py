"""Retrospective archive eligibility audit. No device or private frame access."""
import csv
import json
import math
from pathlib import Path

ART = Path(__file__).resolve().parent.parent


def reverse_windows(labels, medians):
    if len(labels) != len(medians) or set(labels) != {"A", "B"}:
        raise ValueError("phase mismatch")
    if not all(math.isfinite(v) for v in medians):
        raise ValueError("non-finite metric")
    windows = []
    for i in range(len(labels) - 2):
        s = labels[i:i+3]
        if s not in ("ABA", "BAB"):
            continue
        x, y, z = medians[i:i+3]
        sign = 1 if s == "ABA" else -1
        windows.append(dict(phases=s, index=i+1,
                            B_minus_A=[round(sign * (y-x), 8), round(sign * (y-z), 8)]))
    aba = [v["index"] for v in windows if v["phases"] == "ABA"]
    bab = [v["index"] for v in windows if v["phases"] == "BAB"]
    return dict(windows=windows,
                disjoint_ABA_BAB_pairs=sum(abs(a-b) >= 3 for a in aba for b in bab),
                AAA_windows=sum(labels[i:i+3] == "AAA" for i in range(len(labels)-2)))


def audit(rows, context, gate):
    if [row["phase"] for row in rows] != ["1A", "2B", "3A", "4B", "5A"]:
        raise ValueError("unexpected phase order")
    if context["included"].get("spatial") != len(rows) * 3:
        raise ValueError("wrong archive size")
    triples = context["context"]["spatial"]["phase_log_center_right_min_median_max"]
    if len(triples) != len(rows) or not all(len(v) == 3 and all(map(math.isfinite, v))
                                             and v[0] <= v[1] <= v[2] for v in triples):
        raise ValueError("invalid phase summary")
    labels = "".join(r["phase"][1] for r in rows)
    means = [float(r["full_mean_rgb"]) for r in rows]
    bounds = [(int(r["white_content_px_min_per_row"]), int(r["white_content_px_max_per_row"]))
              for r in rows]
    central = [int(r["center_luma_code"]) for r in rows]
    if not all(map(math.isfinite, means)):
        raise ValueError("nonfinite full-screen mean")
    return dict(archive_phases=labels, camera_slots=context["included"]["spatial"],
                archived_sequences=1, **reverse_windows(labels, [v[1] for v in triples]),
                target_center_code=central, target_white_row_bounds=bounds,
                all_test_rows_720_white=all(pair == (720, 720) for pair in bounds),
                full_screenshot_mean_span_DN=round(max(means)-min(means), 6),
                qualified_sham_triplets_in_parent_input=gate["matched_sham_triplets_available_in_input"],
                new_camera_slots=0)


def main():
    with (ART/"scope_spatial_stock_20261118"/"spatial"/"target_patterns.csv").open() as f:
        rows = list(csv.DictReader(f))
    result = audit(rows, json.loads((ART/"r8_raster_context_20261118"/"results.json").read_text()),
                   json.loads((ART/"night_r043_r045"/"outcome.json").read_text()))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
