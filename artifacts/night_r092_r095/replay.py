"""Offline, deterministic AC counterexample and calls to the repository raster tool."""
import json
import statistics
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "06-tools" / "scope_pwm"))
from test_scope_pwm import CAL, Unresolved, draw, run, square


def checked(name, im, cal):
    try:
        r = run(im, cal)
        return dict(case=name, status=r["status"], M=r["percent_modulation"],
                    warnings=[w for w in r["warnings"] if "depth" in w.lower()
                              or "uncertainty" in w.lower()])
    except Unresolved as e:
        return dict(case=name, status="unresolved", M=None, reason=str(e))


def main():
    samples = [[base + (1 if i % 4 < 2 else -1) for i in range(32)] for base in (2, 5)]
    ac = [[x - statistics.mean(s) for x in s] for s in samples]
    delta = max(abs(x-y) for x, y in zip(*ac))
    ms = [100 * (max(s)-min(s)) / (max(s)+min(s)) for s in samples]
    if delta != 0 or ms != [50., 20.]:
        raise ValueError("AC counterexample did not reproduce")
    q = 2.0**-34
    cal = replace(CAL, volts_per_div=20*q)
    checks = [checked("dark", draw(lambda x: 90), CAL),
              checked("negative", draw(square), replace(CAL, dark_y=68))]
    checks += [checked(name, draw(square), replace(cal, level_error_v=u)) for name, u in
               (("bound_missing", None), ("below_resolution", 41*q),
                ("at_resolution", 40*q), ("resolved_same_levels", q))]
    if ([r["M"] for r in checks[:5]] != [None]*5 or abs(checks[-1]["M"] - 50) > 1.e-10
            or checks[0]["status"] != "unresolved"
            or any(r["status"] != "resolved_raster" for r in checks[1:])):
        raise ValueError("unexpected raster acceptance or depth")
    print(json.dumps(dict(ac=dict(count=len(ac[0]), max_difference=delta, true_M=ms),
                          uncertainty_units_v=q, raster=checks), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
