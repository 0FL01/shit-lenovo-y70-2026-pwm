"""Synthetic profiles only. Stdlib. No archived images or device calls."""
import cmath
import json
import math

TAU = math.tau
TRAINS = ((1,), (1, .65), (1, .65, .65))
A = ((720, .22), (2160, .06))
B = ((2160, .28),)


def sinc(x):
    return math.sin(math.pi*x)/(math.pi*x) if x else 1.


def amp(n, duty, weights):
    # Disjoint equal-width rectangles starting at j/k; factor 2 for real sinusoid.
    k = len(weights)
    w = duty/k
    return 2*w*abs(sinc(n*w)*sum(a*cmath.exp(-1j*TAU*n*j/k)
                                   for j, a in enumerate(weights)))


def rows(terms, fs, exposure=0., phase=0., count=64):
    # Centered rectangular exposure; phase is a time offset in seconds.
    return [.5 + sum(a*sinc(f*exposure)*math.cos(TAU*f*(i/fs + phase))
                     for f, a in terms) for i in range(count)]


def rms(a, b):
    return math.sqrt(sum((x-y)**2 for x, y in zip(a, b))/len(a))


def result():
    scans = []
    for weights in TRAINS:
        hits = {2: [], 3: []}
        for p in range(1, 100):
            v = [amp(n, p/100, weights) for n in (1, 2, 3)]
            for n in (2, 3):
                if v[n-1] > v[0]+1e-12:
                    hits[n].append(p)
        scans.append({'weights': weights, 'percent_strictly_above_fundamental':
                      {n: [min(v), max(v), len(v)] if v else [] for n, v in hits.items()}})
    cases = []
    for fs, exp, shift in ((2880, 0., 0.), (2880, .0001, 0.),
                           (11520, .0001, 0.), (2880, 0., 1/11520)):
        x, y = (rows(t, fs, exp, shift) for t in (A, B))
        err = rms(x, y)
        cases.append({'fs': fs, 'exposure_us': round(1e6*exp),
                      'offset_rows': shift*fs, 'first4_A': [round(z,6) for z in x[:4]],
                      'first4_B': [round(z,6) for z in y[:4]],
                      'rms': round(err,9), 'similar': err <= .015})
    # Second pair with no alias: a weak true fundamental is below the
    # profile-distance tolerance but has a coherent 720-Hz component.
    c, d = (rows(t, 11520) for t in (((720,.015),(2160,.23)), ((2160,.23),)))
    def projection(v):
        return 2*sum((y-.5)*math.cos(TAU*720*i/11520) for i,y in enumerate(v))/len(v)
    second = {'fs': 11520, 'rms': round(rms(c,d),9), 'similar': rms(c,d) <= .015,
              '720_projection': [round(projection(v),9) for v in (c,d)]}
    return {'R083': scans, 'R084': cases, 'R084_weak_fundamental': second}


if __name__ == '__main__':
    print(json.dumps(result(), indent=2))
