"""Audit the coverage of the named archive summaries; never acquire or fit data."""
import hashlib
import json
from pathlib import Path

# Repository-relative published artifacts; no dependency on a Git object store.
ARTIFACTS = Path(__file__).resolve().parents[1]
PINS = {
    "night_r031_r033/outcome.json": "d70cb864ab9247c16e4b3f27211ffed0e143867ed160c632ca88e98929b045af",
    "night_r049_r051/outcome.json": "a169c56f600a6f56d65e609add4ec7ee9afecf2b9bc64a45340da24d0fbd4a57",
    "night_r052_r054/outcome.json": "743b5bb2be0d3537af4b97e69add596562d396cf0397867c3b46e32d4e9dd5d6",
    "night_r055_r057/results.json": "05bf59b8f63349970124f170a613d37975adb95e016de3861d8e9acae507c591",
}


def read(path, root=ARTIFACTS):
    data = (root / path).read_bytes()
    if hashlib.sha256(data).hexdigest() != PINS[path]:
        raise ValueError("published artifact differs from source pin: " + path)
    return json.loads(data)

def paired_slots(phases):
    count = 0
    for phase in phases:
        windows = phase["regions"]
        counts = [len(windows[k]["slot_counts_floor_ceiling_union"]) for k in ("C", "R")]
        if counts[0] != counts[1] or not counts[0]:
            raise ValueError("unpaired digital rail counts")
        count += counts[0]  # Two windows from one image are one slot.
    return count

def summary():
    r32 = read("night_r031_r033/outcome.json")["r11"]["frames"]
    r51 = read("night_r049_r051/outcome.json")
    r54 = read("night_r052_r054/outcome.json")
    r55 = read("night_r055_r057/results.json")
    return {
        "r11_paired_direct_background_slots": sum(
            f["direct"]["n"] == f["background"]["n"] == 1280 for f in r32.values()),
        "r51_processed_C_R_slots": {key: paired_slots(rows) for key, rows in r51.items()},
        "r54_new_device_frames": r54["acquired_device_frames"],
        "r54_physical_time_unit": r54["physical_time_unit"],
        "r55_synthetic_traces_by_outcome": {
            k: sum(row["counts"].get(k, 0) for row in r55["cells"])
            for k in sorted({k for row in r55["cells"] for k in row["counts"]})},
    }

if __name__ == "__main__":
    print(json.dumps(summary(), indent=2, sort_keys=True))
