"""Replay selected PUBLIC outputs and fixtures only. No private paths or device APIs."""
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import subprocess
import sys

ART = Path(__file__).resolve().parents[1]
# Golden files are independent tracked inputs; missing files/errors fail, never skip.
CASES = [
    ("night_r076_r078", "audit.py", "outcome.json", "test_audit", 3),
    ("night_r079_r081", "audit.py", "outcome.json", "test_audit", 3),
    ("night_r088_r091", "audit.py", "inventory.json", "test_audit", 4),
    ("night_r082_r084", "models.py", "results.json", "test_models", 6),
    ("night_r085_r087", "audit.py", "results.json", "test_audit", 3),
    ("stock_blind_static_r12_20261118/analysis", None, None, "test_public_replay", 3),
    ("stock_blind_static_r12_20261118/analysis", None, None, "test_synthetic", 8),
]
SKIPS = {
    "R7 pixels -> phase D": "private ordinal PNGs and acquisition receipts not supplied",
    "3600/3601 scope photos -> D": "private original previews not supplied",
    "Extra Dim stills -> red fractions": "private original JPEGs not supplied",
    "R10/R11 original pixels -> cell decisions": "private preview sets not supplied",
    "R12b original pixels -> blind predictions": "18 private original PNGs not supplied",
}

def execute(directory, *args):
    p = subprocess.run([sys.executable, "-B", *args], cwd=directory, capture_output=True)
    if p.returncode:
        raise RuntimeError(f"{directory.name} {args}: {p.stderr.decode()[-1500:]}")
    return p

def main():
    results = []
    for folder, script, golden, suite, n in CASES:
        d = ART / folder
        row = dict(suite=f"{folder}/{suite}", tests=n)
        if script:
            if execute(d, script).stdout != (d/golden).read_bytes():
                raise ValueError(f"golden mismatch: {folder}/{golden}")
            row["byte_match"] = golden
        t = execute(d, "-m", "unittest", "-v", suite).stderr.decode()
        if not re.search(rf"^Ran {n} tests? in ", t, re.M) or t.strip().splitlines()[-1] != "OK":
            raise ValueError(f"test count, unexpected skip, or incomplete suite: {suite}: {t[-500:]}")
        results.append(row)
    print(json.dumps(dict(python=platform.python_version(),
        packages={p: importlib.metadata.version(p) for p in ("numpy", "Pillow")},
        public_pass=results, private_not_run=SKIPS), indent=2))

if __name__ == "__main__":
    main()
