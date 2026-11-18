#!/usr/bin/env python3
"""Digitize a single rectified XY scope trace; never infer time from camera FPS."""
import argparse
import json
import math
from dataclasses import asdict, dataclass
from bisect import bisect_right

import numpy as np
from PIL import Image


class Unresolved(ValueError):
    """The image/calibration does not support a measurement."""


@dataclass(frozen=True)
class Calibration:
    seconds_per_div: float
    x_px_per_div: float
    volts_per_div: float
    y_px_per_div: float
    polarity: str = "unknown"  # voltage response to increasing light
    dark_y: float | None = None  # global image row with detector dark
    linear_dc_unclipped: bool = False
    level_error_v: float | None = None  # independent absolute bound per corrected level

    def check(self):
        scales = (self.seconds_per_div, self.x_px_per_div,
                  self.volts_per_div, self.y_px_per_div)
        if not all(math.isfinite(v) and v > 0 for v in scales):
            raise Unresolved("calibration scales must be finite and positive")
        if self.dark_y is not None and not math.isfinite(self.dark_y):
            raise Unresolved("invalid dark reference row")
        if self.level_error_v is not None and not (math.isfinite(self.level_error_v)
                                                     and self.level_error_v > 0):
            raise Unresolved("level error bound must be finite and positive")
        if self.polarity not in ("positive", "negative", "unknown"):
            raise Unresolved("invalid detector polarity")
        scales = (self.seconds_per_div / self.x_px_per_div,
                  self.volts_per_div / self.y_px_per_div)
        if not all(math.isfinite(v) and v > 0 for v in scales):
            raise Unresolved("derived calibration scales out of numeric range")
        return scales


def extract(image, roi, rgb, tolerance):
    """Return global y at each x; refuse gaps, clipped or non-single-valued traces."""
    left, top, right, bottom = roi
    if not (0 <= left < right <= image.width and 0 <= top < bottom <= image.height):
        raise Unresolved("ROI outside image; bounds are left top right bottom (exclusive)")
    if not 0 <= tolerance <= 255 or not all(0 <= c <= 255 for c in rgb):
        raise Unresolved("RGB values and tolerance must be in [0,255]")
    a = np.asarray(image.crop(roi).convert("RGB"), dtype=np.int16)
    mask = np.all(np.abs(a - np.array(rgb)) <= tolerance, axis=2)
    if mask[[0, -1]].any():
        raise Unresolved("trace touches vertical ROI limit: clipping or unwanted overlay")
    y, thickness = [], []
    for x, column in enumerate(mask.T):
        rows = np.flatnonzero(column)
        if not len(rows):
            raise Unresolved(f"trace gap at image x={x + left}; revise color/ROI")
        if np.any(np.diff(rows) > 1):
            raise Unresolved(f"multiple trace segments at image x={x + left}")
        y.append(top + (int(rows[0]) + int(rows[-1])) / 2)
        thickness.append(int(rows[-1] - rows[0]))
    y = np.asarray(y)
    lo, hi = np.percentile(y, (2, 98))
    # Steep edges can legitimately occupy tall runs in occasional columns.
    # A sustained vertical band has no identifiable centreline (fills,
    # persistence or same-colour grid). Do not report a synthetic midpoint.
    if np.mean(np.asarray(thickness) >= max(3., .25 * (hi - lo))) > .20:
        raise Unresolved("trace too thick over sustained columns: filled or ambiguous band")
    return y


def crossings(signal):
    """Interpolate 50% edges; arm/rearm at 30%/70% against threshold noise."""
    state = None
    pending = None
    up, down = [], []
    for i, value in enumerate(signal):
        if i and signal[i - 1] < .5 <= value:
            pending = (1, i - 1 + (.5 - signal[i - 1]) / (value - signal[i - 1]))
        elif i and signal[i - 1] >= .5 > value:
            pending = (-1, i - 1 + (.5 - signal[i - 1]) / (value - signal[i - 1]))
        level = 1 if value >= .7 else -1 if value <= .3 else None
        if level is None:
            continue
        if state is not None and level != state and pending and pending[0] == level:
            (up if level == 1 else down).append(float(pending[1]))
        state = level
    return up, down


def measure(image, roi, rgb, tolerance, cal):
    seconds_per_pixel, volts_per_pixel = cal.check()
    if cal.dark_y is not None and not 0 <= cal.dark_y < image.height:
        raise Unresolved("dark reference must be a row in original image coordinates")
    y = extract(image, roi, rgb, tolerance)
    if len(y) < 48:
        raise Unresolved("insufficient trace width")
    # Increasing z means increasing light when polarity is known; otherwise higher voltage.
    sign = -1 if cal.polarity == "negative" else 1
    z = -sign * y
    # Resist isolated hot pixels. These are resolved extrema, not subpixel spikes.
    low, high = np.percentile(z, (2, 98))
    span = float(high - low)
    if span < 6:
        raise Unresolved("vertical swing below 6 pixels or flat/unresolved")
    s = (z - low) / span
    up, down = crossings(s)
    if len(up) < 4:
        raise Unresolved("need at least three complete rising-edge periods")
    periods = np.diff(up)
    period = float(np.median(periods))
    if min(periods) < 12:
        raise Unresolved("under-resolved period (<12 pixels); zoom timebase")
    if max(abs(periods - period)) > max(2, .10 * period):
        raise Unresolved("irregular/multiple periods; no unique repetition rate")
    # Each end can be an incomplete cycle, but not a full cycle with no new
    # rising edge. A burst followed/preceded by DC is not periodic over this ROI.
    if max(up[0], (len(s) - 1) - up[-1]) >= period:
        raise Unresolved("a full period without rising edges at an ROI end; "
                         "possible burst or pause, no ROI-wide rate")
    widths = []
    for a, b in zip(up, up[1:]):
        j = bisect_right(down, a)
        if j == len(down) or down[j] >= b or (j + 1 < len(down) and down[j + 1] < b):
            raise Unresolved("ambiguous falling edge within a cycle")
        widths.append(down[j] - a)
    period_s = seconds_per_pixel * period
    if not math.isfinite(period_s) or period_s <= 0:
        raise Unresolved("period out of numeric range")
    frequency, vpp = 1 / period_s, span * volts_per_pixel
    if not all(math.isfinite(v) and v > 0 for v in (frequency, vpp)):
        raise Unresolved("frequency or voltage out of numeric range")
    # Judge two-level occupancy independently in every complete cycle.
    plateaus = [s[math.ceil(a):math.ceil(b)] for a, b in zip(up, up[1:])]
    def has_two_levels(c):
        upper = c >= .5
        near_low = abs(c) <= .10
        near_high = abs(c - 1) <= .10
        # A long flat baseline with narrow triangular peaks is not two-level.
        return (np.any(upper) and np.any(~upper)
                and np.mean(near_low | near_high) >= .80
                and np.mean(near_low[~upper]) >= .65
                and np.mean(near_high[upper]) >= .65)

    two_level = all(has_two_levels(c) for c in plateaus)
    duties = np.array(widths) / periods
    warnings = ["Edge repetition rate is not necessarily the waveform fundamental. "
                "Alternating pulse shapes or additional modulation may repeat more slowly.",
                "Raster repetition rate only: display decimation, acquisition aliasing, "
                "sensor bandwidth and faster pulses cannot be excluded from one image.",
                "This short window cannot exclude a slower optical envelope."]
    raster_upper_duty = duty = depth = v_min = v_max = None
    varying_width = np.ptp(duties) > max(.05, 2 / period)
    # Compare the typical level on each side of the crossing, not instantaneous
    # extrema. This is a variability screen, not a proof of cycle identity.
    sides = [[np.median(c[c >= .5]), np.median(c[c < .5])] for c in plateaus
             if np.any(c >= .5) and np.any(c < .5)]
    varying_levels = bool(sides and np.max(np.ptp(sides, axis=0)) > max(.10, 2 / span))
    if varying_width or varying_levels:
        warnings.append("Cycles differ in width or level: the edge rate does not describe "
                        "the repeating full pattern or exclude a lower fundamental.")
    if not two_level:
        warnings.append("Not a resolved two-level waveform; no PWM duty inferred.")
    elif min(min(widths), min(periods - widths)) < 3:
        warnings.append("A pulse or gap spans <3 pixels; duty unresolved.")
    elif varying_width:
        warnings.append("Duty varies among cycles; no single duty reported.")
    else:
        selected_high_duty = 100 * float(np.median(duties))
        raster_upper_duty = selected_high_duty if sign > 0 else 100 - selected_high_duty
        if cal.polarity != "unknown" and cal.linear_dc_unclipped:
            duty = selected_high_duty
        else:
            warnings.append("Only a raster threshold duty: optical duty needs known polarity "
                            "and verified bandwidth/linear, DC-coupled, unclipped chain.")
    z_min, z_max = float(z.min()), float(z.max())
    outliers = max(low - z_min, z_max - high) > max(1., .05 * span)
    if outliers:
        warnings.append("Excursions beyond P02/P98: robust range omits significant extrema; "
                        "optical modulation withheld, inspect the original trace.")
    if cal.dark_y is not None and cal.linear_dc_unclipped and cal.polarity != "unknown":
        dark = -sign * cal.dark_y
        if z_min < dark:
            warnings.append("Trace below dark baseline; invalid optical depth.")
        elif not outliers:
            v_min = (float(low) - dark) * volts_per_pixel
            v_max = (float(high) - dark) * volts_per_pixel
            if not math.isfinite(v_max) or v_max <= 0:
                raise Unresolved("dark-referenced voltage out of numeric range")
            u = cal.level_error_v
            if u is None:
                warnings.append("No independent level error bound; optical depth withheld.")
            # Equivalent to max + min <= 2*u, without overflowing either sum.
            elif v_max <= u or (v_min <= u and v_max - u <= u - v_min):
                warnings.append("Dark-corrected level sum does not exceed its uncertainty; "
                                "optical depth withheld.")
            else:
                ratio = v_min / v_max
                depth = 100 * (1 - ratio) / (1 + ratio)
    else:
        warnings.append("No calibrated optical depth: need dark row, known polarity "
                        "and verified linear, DC-coupled, unclipped optical chain.")
    return {
        "status": "resolved_raster", "confidence": "conditional_on_calibration",
        "frequency_hz": frequency,
        "frequency_kind": "rising_edge_repetition_rate",
        "frequency_basis": "median same-direction 50% edge spacing on horizontal timebase",
        "waveform_fundamental_hz": None, "cycle_variation_detected": bool(varying_width or varying_levels),
        "complete_periods": len(periods), "period_px": period,
        "period_px_range": [float(min(periods)), float(max(periods))],
        "resolved_two_level_shape": two_level, "raster_upper_duty_pct": raster_upper_duty,
        "optical_high_duty_pct": duty,
        "trace_vpp_p02_p98": vpp, "out_of_quantile_excursion": bool(outliers),
        "dark_referenced_min_v": v_min, "dark_referenced_max_v": v_max,
        "percent_modulation": depth, "modulation_estimator": "dark-referenced raster P02/P98",
        "calibration": asdict(cal),
        "roi_ltrb": list(roi), "trace_rgb": list(rgb), "color_tolerance": tolerance,
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--roi", required=True, nargs=4, type=int,
                        metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))
    parser.add_argument("--rgb", required=True, nargs=3, type=int)
    parser.add_argument("--tolerance", default=30, type=int)
    for name in ("seconds-per-div", "x-px-per-div", "volts-per-div", "y-px-per-div"):
        parser.add_argument("--" + name, required=True, type=float)
    parser.add_argument("--polarity", choices=("positive", "negative", "unknown"),
                        default="unknown")
    parser.add_argument("--dark-y", type=float, help="global image row of dark detector output")
    parser.add_argument("--linear-dc-unclipped", action="store_true",
                        help="attest calibrated linear DC, adequate bandwidth and no clipping")
    parser.add_argument("--level-error-v", type=float,
                        help="independent absolute uncertainty bound (V) per dark-corrected "
                             "level, including noise, dark offset and raster uncertainty")
    args = parser.parse_args()
    cal = Calibration(args.seconds_per_div, args.x_px_per_div, args.volts_per_div,
                      args.y_px_per_div, args.polarity, args.dark_y, args.linear_dc_unclipped,
                      args.level_error_v)
    try:
        with Image.open(args.image) as im:
            result = measure(im, tuple(args.roi), args.rgb, args.tolerance, cal)
        print(json.dumps(result, indent=2, allow_nan=False))
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "unresolved", "confidence": "none", "reason": str(exc)}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
