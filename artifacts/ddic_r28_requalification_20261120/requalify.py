"""Print a per-frame signal-floor overlay for the archived R22–R31 summary."""

import csv
import json
import math
import sys
from pathlib import Path


SUMMARY = (Path(__file__).resolve().parents[1] / "ddic_round22_31_9dladder_20261120"
           / "summary_round22_31.json")
MIN_DN = 20


def main():
    phases = json.loads(SUMMARY.read_text(encoding="utf-8"))["phases"]
    out = csv.writer(sys.stdout, lineterminator="\n")
    out.writerow(("phase", "frame_index", "raw_mean_dn", "banding_signal_gate", "archive_error"))
    for phase, frames in phases.items():
        for index, frame in enumerate(frames):
            if "error" in frame:
                out.writerow((phase, index, "", "unusable_archive_error", frame["error"]))
                continue
            dn = frame["raw_mean_dn"]
            if not math.isfinite(dn):
                raise ValueError(f"{phase}/{index}: non-finite raw_mean_dn")
            gate = "unusable_below_20_dn" if dn < MIN_DN else "signal_floor_met_only"
            out.writerow((phase, index, dn, gate, ""))


if __name__ == "__main__":
    main()
