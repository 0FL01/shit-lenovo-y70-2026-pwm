"""Complete-cycle ternary grammar audit; no optics, wall clocks or devices."""
import json
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOOK = json.loads((ROOT / "codebook.json").read_text())


def check_word(w):
    if Counter(w) != {"0": 4, "1": 4, "2": 4} or any(
        a == b for a, b in zip(w, w[1:] + w[:1])
    ):
        raise ValueError("expected 12 balanced ternary levels and distinct neighbours")


@lru_cache(maxsize=4)
def catalog(w):
    """Rotate retained indices *after* removing a slot; all exact explanations."""
    check_word(w)
    table = defaultdict(list)
    for missing in (None, *range(len(w))):
        indices = [i for i in range(len(w)) if i != missing]
        for sign in (1, -1):
            ix = indices[::sign]
            for k, first in enumerate(ix):
                s = "".join(w[i] for i in ix[k:] + ix[:k])
                table[s].append((sign, first, missing))
    return table


def decode(rows, word):
    """Use both axes, reject any non-stripe pixel, abstain for ties/no match."""
    n = len(rows)
    if n not in (11, 12) or any(len(row) != n for row in rows):
        return None
    hits = []
    for axis, lines in (("x", rows), ("y", list(zip(*rows)))):
        p = tuple(lines[0])
        if all(tuple(row) == p for row in lines):
            hits.extend((axis, *hit) for hit in catalog(word).get("".join(p), ()))
    return hits[0] if len(hits) == 1 else None


def render(axis, profile):
    n = len(profile)
    return ["".join(profile[x if axis == "x" else y] for x in range(n))
            for y in range(n)]


def audit():
    a, b = BOOK["primary"], BOOK["reserve"]
    shared = len(catalog(a).keys() & catalog(b).keys())
    counts = Counter()
    rejected = 0
    for axis in ("x", "y"):
        for sign in (1, -1):
            for start in range(len(a)):
                # Independently generate a full cycle from physical phase, then
                # remove any position, including the first observed position.
                for skip in (None, *range(len(a))):
                    ix = [(start + t * sign) % len(a) for t in range(len(a)) if t != skip]
                    profile = "".join(a[i] for i in ix)
                    missing = None if skip is None else (start + skip * sign) % len(a)
                    want = (axis, sign, ix[0], missing)
                    if decode(render(axis, profile), a) != want:
                        rejected += 1
                    counts["one_deletion" if skip is not None else "full"] += 1
    return {"acquired_device_frames": 0, "physical_time_unit": None,
            "trials": dict(counts), "wrong_or_unresolved": rejected,
            "distinct_primary_profiles": len(catalog(a)),
            "reserve_overlap": shared}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
