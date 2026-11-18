"""Сверка двух типов учётных таблиц, не фотометр и не автоматическое измерение."""
import csv
import json
from collections import Counter
from pathlib import Path

ARCHIVE = Path(__file__).resolve().parents[1]


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as fp:
        return list(csv.DictReader(fp))


def count_r7(rows):
    expected = {f"P{i:02}_s{j}" for i in range(17) for j in range(3)}
    if len(rows) != len(expected) or {r["slot"] for r in rows} != expected:
        raise ValueError("incomplete or duplicate slot ledger")
    states = Counter()
    labels = Counter()
    dc_review = []
    for r in rows:
        state, coupling = r["original_qc"], r["coupling"]
        if state not in {"missing", "rejected", "accepted"}:
            raise ValueError("unknown QC")
        if state == "missing" and any(r[k] for k in ("coupling","time_label","multiplier","source_sha256")):
            raise ValueError("metadata assigned to missing frame")
        states[state] += 1
        if state != "missing":
            labels[coupling or "unread"] += 1
            if coupling == "DC":
                dc_review.append(r["slot"])
    return {"planned": len(rows), "captured": len(rows)-states["missing"],
            "original_qc": dict(states), "coupling_label": dict(labels),
            "dc_labels_requiring_review_not_qualified_pairs": sorted(dc_review)}


def count_panel(rows):
    names = [r["capture"] for r in rows]
    if len(names) != len(set(names)):
        raise ValueError("duplicate capture")
    return {"frame_rows": len(rows), "raster_qc": dict(Counter(r["status"] for r in rows)),
            "per_phase": dict(Counter(r["phase"] for r in rows))}


def replay():
    data = {"R7": count_r7(read_rows(ARCHIVE/"night_r031_r033/legend_reads.csv"))}
    for key, dirname in (("panelDC_3600", "scope_dc_divergence_20261118"),
                         ("panelDC_3601", "scope_dc3601_divergence_20261118")):
        data[key] = count_panel(read_rows(ARCHIVE/dirname/"frames.csv"))
    return data


if __name__ == "__main__":
    print(json.dumps(replay(), indent=2, sort_keys=True))
