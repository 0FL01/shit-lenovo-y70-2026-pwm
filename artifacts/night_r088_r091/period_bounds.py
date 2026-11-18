"""Deterministic interval arithmetic, not an automated acquisition gate.

Same kind of oriented edge on the same identified cycle family, coordinates in
divisions, positive calibrated seconds/div. Caller must verify these physical
preconditions, independent captures and shared systematics separately.
"""
from fractions import Fraction as Q


def interval(bounds):
    a, b = map(Q, bounds)
    if a > b:
        raise ValueError('reversed interval')
    return a, b


def period(first, last, seconds_per_div, cycles):
    a, b = interval(first)
    c, d = interval(last)
    lo, hi = interval(seconds_per_div)
    if type(cycles) is not int or cycles < 1 or c <= b or lo <= 0:
        raise ValueError('invalid cycle count, endpoints or calibration')
    return (c-b)*lo/cycles, (d-a)*hi/cycles


def relation(p, q):
    a, b = interval(p)
    c, d = interval(q)
    if a <= 0 or c <= 0:
        raise ValueError('period must be positive')
    if b < c:
        return 'shorter'
    if d < a:
        return 'longer'
    return 'compatible_not_equal'
