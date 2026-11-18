"""Deterministic models; no images, device I/O, external libraries or arguments."""
import cmath
import json
import math


def sinc(x):
    return math.sin(math.pi * x) / (math.pi * x) if x else 1.0


def rows(freq, amplitude, spatial_cycles, start, exposure=0.0001):
    """Row-centred rectangular exposure of a travelling cosine on a flat field."""
    return [0.5 + amplitude * sinc(freq * exposure) * math.cos(
        math.tau * (freq * (start + row / 300000) + spatial_cycles * row / 500)
    ) for row in range(500)]


def stripes():
    amplitude = 0.3 * sinc(720 * 0.0001) / sinc(120 * 0.0001)
    out = {}
    for key, delay, direction in [('same', 0, 1), ('delayed', .001, 1),
                                  ('mirrored', 0, -1)]:
        a = rows(720, .3, 0, delay)
        b = rows(120, amplitude, direction, delay)
        out[key] = max(abs(x-y) for x, y in zip(a, b))
    return out


def tone(f, n):
    return [cmath.exp(1j*math.tau*f*i/24000) for i in range(n)]


def residual(samples, model):
    """Relative RMS after unconstrained complex amplitude fit, unit model."""
    gain = sum(y*x.conjugate() for y, x in zip(samples, model)) / len(samples)
    return (sum(abs(y-gain*x)**2 for y, x in zip(samples, model))
            / sum(abs(y)**2 for y in samples))**0.5


def windows():
    result = []
    for n, mix in [(100, False), (400, False), (800, False), (1600, False), (800, True)]:
        a, b = tone(720, n), tone(750, n)
        y = [x+z for x, z in zip(a, b)] if mix else a
        r = [residual(y, x) for x in [a, b]]
        ok = [f for f, e in zip([720, 750], r) if e <= .05]
        result.append(dict(n=n, mixture=mix, bin_hz=24000/n, cycles720=n*720//24000,
                           residual720=r[0], residual750=r[1],
                           candidate=ok[0] if n >= 800 and len(ok) == 1 else None))
    return result


def edge_checks(edges):
    gaps = [b-a for a, b in zip(edges, edges[1:])]
    fits = [p for p in range(1, 17) if all(d % p == 0 for d in gaps)
            and sum(d//p - 1 for d in gaps) <= 1]
    seen = set(edges)
    pairs = {p: sum(t+p in seen for t in edges) for p in range(1, 17)}
    high = max(pairs.values())
    return dict(gaps=gaps, candidates=fits, acf_max_pairs=high,
                acf_lags=[p for p, v in pairs.items() if v == high and v],
                pair_counts={p: n for p, n in pairs.items() if n})


def run():
    full = list(range(0, 65, 8))
    return dict(stripes_max_abs=stripes(), windows=windows(), edges={
        'full': edge_checks(full),
        'missing_one': edge_checks([t for t in full if t != 32]),
        'short': edge_checks([0, 16])})


if __name__ == '__main__':
    print(json.dumps(run(), indent=2, sort_keys=True))
