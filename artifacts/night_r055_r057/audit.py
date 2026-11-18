"""Dimensionless synthetic scale stress test; no device, media or clock input."""
import json
import math
from fractions import Fraction as F

A = tuple(map(int, '012021201021'))
DENSITIES = (F(3, 4), F(5, 4), F(23, 10), F(47, 10))
BLURS = (F(0), F(1, 2), F(1), F(2), F(12))


def area(t, q):
    """Integral of A from slot 0 to t/q, in integer ticks, incl. negative t."""
    n, pos = divmod(t, q * len(A))
    k, rem = divmod(pos, q)
    return (n * sum(A) + sum(A[:k])) * q + rem * A[k]


def profile(density, blur, phase, width=174):
    period = 1 / F(density)
    phase, half = F(phase), F(blur) / 2
    q = math.lcm(period.denominator, phase.denominator, half.denominator)
    step, left, h = (int(q * v) for v in (period, phase, half))
    if not h:
        return [A[((left + x * step) // q) % len(A)] >= 1.5 for x in range(width)]
    # Exact integration and threshold, including exact equality to 1.5.
    return [area(t+h, q) - area(t-h, q) >= 3*h
            for t in range(left, left + width * step, step)]


def fit(high):
    e = [x - .5 for x in range(1, len(high)) if high[x] and not high[x-1]]
    if len(e) < 8:
        return None, 'few_edges'
    # Rising crossings into level 2 in the unblurred cycle.
    events = [i for i, v in enumerate(A) if A[i-1] < 2 and v == 2]
    n, k = len(e), len(events)
    candidates = []
    for shift in range(k):
        s = [events[(j+shift) % k] + len(A) * ((j+shift)//k) for j in range(n)]
        sm, em = sum(s)/n, sum(e)/n
        slope = sum((a-sm)*(b-em) for a, b in zip(s,e))/sum((a-sm)**2 for a in s)
        err = max(abs(b-em-slope*(a-sm)) for a, b in zip(s,e))
        if err <= 1 + 1e-10:
            candidates.append((err, slope))
    if not candidates:
        return None, 'shape'
    slopes = [s for _, s in candidates]
    if max(slopes) > min(slopes) * 1.01:
        return None, 'ambiguous'
    return min(candidates)[1], 'accepted'


def trial(density, blur):
    reasons, errors = {}, []
    for i in range(96):
        est, reason = fit(profile(density, blur, F(i, 8)))
        reasons[reason] = reasons.get(reason, 0) + 1
        if est is not None:
            errors.append((100*(float(density)/est - 1), i))
    worst = max(errors, key=lambda pair: abs(pair[0])) if errors else None
    return dict(density_px_per_slot=float(density), blur_slots=float(blur),
                counts=reasons, over_5pct=sum(abs(e) > 5 for e, _ in errors),
                worst_abs_percent=round(abs(worst[0]), 5) if worst else None,
                signed_range_pct=[round(v,5) for v in (min(x for x,_ in errors),
                                    max(x for x,_ in errors))] if worst else None,
                worst_phase_eighths=worst[1] if worst else None)


def crop_case(height, origin):
    # R12 nominal row time; 153-column synthetic strip after rotation.
    width, row_us, exposure = 153, 13, 156
    dt = height*row_us//width
    slot = 3*dt
    phase_origin = origin * row_us
    values = []
    for x in range(width):
        # Times doubled to keep centres of exposure and integrals exact.
        center = 2*origin*row_us + (2*x+1)*dt
        l, r = center-exposure-2*phase_origin, center+exposure-2*phase_origin
        values.append(F(area(r, 2*slot)-area(l, 2*slot), 2*exposure))
    return dict(height=height, origin_rows=origin, modeled_us_per_px=dt,
                source_slot_us=slot, exposure_us=exposure), values


def outcome():
    rows = [trial(d,b) for d in DENSITIES for b in BLURS]
    full, a = crop_case(2448,0)
    crop, b = crop_case(1836,306)
    return dict(code_a=''.join(map(str,A)), synthetic_traces=len(rows)*96, cells=rows,
                worst_fraction_over_5pct_all_planned=max(r['over_5pct']/96 for r in rows),
                crop_example=dict(models=[full,crop], ui_positions=len(a),
                                  unequal=sum(x != y for x,y in zip(a,b)),
                                  levels=sorted(float(v) for v in set(a))))


if __name__ == '__main__':
    print(json.dumps(outcome(), indent=2, allow_nan=False))
