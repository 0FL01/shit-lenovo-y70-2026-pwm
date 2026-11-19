"""Offline interval screen for ONE preselected optical component, not fundamental PWM.
Run: python3 verify.py measurements.json. Schema/example: test_verify.py (synthetic).
Intervals are simultaneous, predeclared bounds. No frames or metadata are authenticated.
"""
import json
import math
import sys

FREQ = (720, 1440, 2160)
GATES = ("capture_result_per_frame", "fixed_roi_band_geometry", "linear_black_corrected",
         "no_clipping", "fixed_panel_and_camera_mode", "dark_offscreen_noise_checked",
         "short_signal_and_return", "independent_blocks", "intervals_cover_noise_and_drift")
ORDERS = ("SMLS", "SLMS")
WINDOW = {"S": (100, 220), "M": (395, 550), "L": (595, 760)}  # µs: this bracket only


def number(x):
    if type(x) not in (float, int) or not math.isfinite(x):
        raise ValueError("expected a finite number")
    return x


def interval(pair):
    if not isinstance(pair, list) or len(pair) != 2:
        raise ValueError("expected [lower, upper]")
    lo, hi = map(number, pair)
    if not 0 <= lo <= hi:
        raise ValueError("negative or reversed bounds")
    return lo, hi


def response(cycles):
    return abs(math.sin(math.pi * cycles) / (math.pi * cycles)) if cycles else 1.


def envelope(f, rel, t):
    """Conservative over every f and time in supplied intervals, not point sampling.
    sinc(x)=integral_0^1 cos(pi*x*u)du, so |d sinc/dx| <= pi/2; abs is Lipschitz too.
    """
    left = f * (1-rel) * t[0] * 1e-6
    right = f * (1+rel) * t[1] * 1e-6
    step = (right-left)/32
    vals = [response(left+(i+.5)*step) for i in range(32)]
    err = math.pi*step/4 + 2e-14
    return max(0., min(vals)-err), min(1., max(vals)+err)


def common_scale(observations, response_bounds):
    # Necessary interval intersection over one shared unknown positive amplitude per block.
    lo, hi = 0., math.inf
    for (a, b), (h0, h1) in zip(observations, response_bounds):
        if h1 > 0:
            lo = max(lo, a/h1)
        elif a > 0:
            return False
        if h0 > 0:
            hi = min(hi, b/h0)
    return hi > 0 and math.isfinite(lo) and lo <= hi


def assess(d):
    def hold(why, **details):
        return dict(status="HOLD", reason=why, **details)
    if d["units"] != "black_corrected_linear_fractional_amplitude":
        return hold("wrong observable (not power, raw DN or processed video codes)")
    if not all(d["gates"].get(k) is True for k in GATES):
        return hold("one or more externally verified acquisition/analysis gates missing")
    rel = number(d["frequency_relative_tolerance"])
    margin = number(d["minimum_fractional_contrast"])
    if not 0 <= rel <= .1 or not 0 < margin < 1:
        raise ValueError("unsupported frequency tolerance or contrast margin")
    blocks, ids = [], set()
    for b in d["blocks"]:
        order = b["order"]
        if not isinstance(b["id"], str) or not b["id"] or b["id"] in ids:
            raise ValueError("duplicate or missing block ID")
        ids.add(b["id"])
        if order not in ORDERS or len(b["samples"]) != 4:
            raise ValueError("each four-phase block must be SMLS or SLMS")
        times, amps = [], []
        for label, s in zip(order, b["samples"]):
            t = interval(s["actual_time_us"])
            if not WINDOW[label][0] <= t[0] <= t[1] <= WINDOW[label][1]:
                return hold("out of bracket; verify microsecond units or preregister a new design")
            times.append(t)
            amps.append(interval(s["amplitude"]))
        if min(amps[0][0], amps[-1][0]) <= margin or max(amps[0][0], amps[-1][0]) > min(amps[0][1], amps[-1][1]):
            return hold("short baseline undetected or did not return")
        blocks.append((order, times, amps))
    if any(sum(o==q for o, _, _ in blocks)<2 for q in ORDERS):
        return hold("need at least two independent blocks per order; not a statistical confidence claim")
    survivors, witnessed, contrast = [], [], []
    for f in FREQ:
        viable = witness = separated = True
        for order, times, amps in blocks:
            viable &= common_scale(amps, [envelope(f, rel, t) for t in times])
            # Shared nominal frequency and central times give a constructive, joint witness.
            p = [response(f*sum(t)*.5e-6) for t in times]
            witness &= common_scale(amps, [(x, x) for x in p])
            # Both short endpoints must clear larger middle response; separate M/L despite noise.
            high, low = (order.index(c) for c in ("LM" if f==2160 else "ML"))
            separated &= (min(amps[0][0], amps[-1][0])-amps[high][1] > margin
                          and amps[high][0]-amps[low][1] > margin)
        if viable:
            survivors.append(f)
        if witness:
            witnessed.append(f)
        if separated:
            contrast.append(f)
    if len(survivors)!=1 or survivors[0] not in witnessed or survivors[0] not in contrast:
        return hold("no unique joint nominal fit with resolved contrasts in both orders",
                    possible_candidates_hz=survivors)
    return dict(status="CONDITIONAL_COMPONENT_MATCH", candidate_hz=survivors[0],
                scope="only among 720/1440/2160 Hz under the stated model and input gates")


def verify(data):
    try:
        return assess(data)
    except (AttributeError, KeyError, ValueError, TypeError, OverflowError) as e:
        return {"status": "HOLD", "reason": "invalid or incomplete input: " + str(e)}


if __name__ == "__main__":
    try:
        with open(sys.argv[1], encoding="utf8") as fh:
            result = verify(json.load(fh))
    except (IndexError, OSError, ValueError) as e:
        result = {"status": "HOLD", "reason": "input unavailable or invalid: " + str(e)}
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "CONDITIONAL_COMPONENT_MATCH" else 2)
