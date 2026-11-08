#!/usr/bin/env python3
"""Constructive optical identifiability counterexamples, OFFLINE ONLY.

This does not fit the archived movie, simulate the real DDIC, or identify PWM.
Only committed JSON summaries are read. No camera/device/network/subprocess I/O.
"""

import argparse
from fractions import Fraction
import json
import math
from pathlib import Path


def sinc(x):
    return math.sin(math.pi * x) / (math.pi * x) if x else 1.0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    names = {
        "selector": "artifacts/dsi_selector_split_20261107/analysis_spatial_v2.json",
        "exposure": "artifacts/exposure_notch_20261107/supported/analysis.json",
        "run": "artifacts/exposure_notch_20261107/supported/run.json",
        "phase": "artifacts/temporal_alias_20261108/analysis.json",
    }
    data = {k: json.loads((repo / p).read_text()) for k, p in names.items()}
    rows = data["selector"]["roi_xywh"][3]
    frames = data["selector"]["stages"][0]["frames"]
    period = data["exposure"]["stages"][0]["reference_period_rows"]
    exposure = data["exposure"]["stages"][0]["exposure_ns"] * 1e-9
    skew_ns = int(data["run"]["phases"][0]["camera_start"]
                  ["android.sensor.rollingShutterSkew"][0])
    beat = data["phase"]["controls"][0]["frame_index_phase_beat_hz_not_physical_pwm"]
    fps, video_height = 30, 720
    tau = skew_ns * 1e-9 / video_height  # hypothetical full-window mapping
    q = 1.0 / period
    image_amplitude = 0.2  # freely chosen SYNTHETIC amplitude, not observed Y
    phi0 = 0.37

    # E(y,t)=1+A*cos(2*pi*(f*t+beta*y)+phi).
    # A=B/sinc(f*T), beta=q-f*tau, phi=phi0-pi*f*T.
    # The exposure average is exactly 1+B*cos(2*pi*(f*n/F+q*y)+phi0).
    def component(f, spatial_q, amplitude):
        return dict(f=f, beta=spatial_q-f*tau,
                    A=amplitude/sinc(f*exposure),
                    phi=phi0-math.pi*f*exposure)

    def optical(c, y, t):
        return c["A"] * math.cos(2*math.pi*(c["f"]*t+c["beta"]*y)+c["phi"])

    def integrated(c, n, y):
        t_mid = n/fps + tau*y + exposure/2
        return c["A"]*sinc(c["f"]*exposure)*math.cos(
            2*math.pi*(c["f"]*t_mid+c["beta"]*y)+c["phi"])

    models = [component(720*m+beat, q, image_amplitude) for m in (1, 2, 3)]
    exact_alias_cycles = []
    beat_rational = Fraction(str(beat))
    for m in (1, 2, 3):
        f = Fraction(720*m) + beat_rational
        f0 = Fraction(720) + beat_rational
        cycle = (f-f0) / fps
        if cycle.denominator != 1:
            raise ValueError("Counterexample frame-alias identity failed")
        exact_alias_cycles.append(int(cycle))
    image_error = max(abs(integrated(c, n, y)-integrated(models[0], n, y))
                      for c in models for n in range(frames) for y in range(rows))

    # Independently integrate the optical field by composite Simpson quadrature;
    # this path does not call sinc or the analytic exposure formula.
    quadrature_error = 0.0
    intervals = 512
    for c in models:
        for n in (0, 7, frames-1):
            for y in (0, 42, rows-1):
                t0 = n/fps + tau*y
                samples = [optical(c, y, t0+k*exposure/intervals)
                           for k in range(intervals+1)]
                avg = (samples[0]+samples[-1]
                       +4*sum(samples[1:-1:2])+2*sum(samples[2:-1:2])) / (3*intervals)
                quadrature_error = max(quadrature_error, abs(avg-integrated(c,n,y)))

    # A broad spatial image term does not force a separate low temporal frequency.
    # Model S: both spatial terms have the SAME local temporal frequency.
    # Model L: second term has a lower frequency, differing by 480=16*30 Hz.
    fine = component(720+beat, q, 0.2)
    broad_same = component(720+beat, q/3, 0.1)
    broad_low = component(240+beat, q/3, 0.1)
    broad_error = max(abs(integrated(broad_same,n,y)-integrated(broad_low,n,y))
                      for n in range(frames) for y in range(rows))
    positivity_bound = min(1-abs(c["A"]) for c in models)
    two_term_positivity_bound = min(1-abs(fine["A"])-abs(c["A"])
                                  for c in (broad_same,broad_low))
    if max(image_error, quadrature_error, broad_error) > 5e-9:
        raise ValueError("Numerical verification did not satisfy tolerance")
    if min(positivity_bound, two_term_positivity_bound) <= 0:
        raise ValueError("Constructed irradiance is not positive")

    result = {
        "scope": "Formal synthetic counterexample, not a fit or target measurement",
        "source_summaries": names,
        "archive_values_used_only_to_set_an_illustrative_grid": {
            "frames": frames, "rows": rows, "reference_period_rows": period,
            "exposure_seconds": exposure, "reported_skew_ns": skew_ns,
            "reported_camera_phase_alias_cycles_per_second": beat,
        },
        "additional_model_assumptions": {
            "uniform_sensor_fps": fps, "output_height": video_height,
            "hypothetical_known_seconds_per_output_row": tau,
            "sensor": "linear rectangular exposure, identity ISP",
            "spatial_emission_phase": "unknown linear phase gradient per term",
            "synthetic_mean_irradiance": 1, "synthetic_image_amplitude": image_amplitude,
        },
        "frequency_exchange_models": [
            {"local_temporal_frequency_hz_hypothetical": c["f"],
             "optical_amplitude": c["A"],
             "optical_spatial_phase_cycles_per_output_row": c["beta"],
             "equivalent_propagation_delay_over_roi_seconds": -c["beta"]*(rows-1)/c["f"],
             "phase_offset_radians": c["phi"]}
            for c in models
        ],
        "verification": {
            "exact_alias_cycles_per_frame_from_rational_arithmetic": exact_alias_cycles,
            "samples_per_model": frames*rows,
            "max_abs_image_difference": image_error,
            "independent_simpson_cases": 27,
            "simpson_intervals_per_exposure": intervals,
            "max_abs_simpson_analytic_difference": quadrature_error,
            "minimum_irradiance_lower_bound": positivity_bound,
        },
        "broad_component_exchange": {
            "same_temporal_frequency_model_hz": [fine["f"], broad_same["f"]],
            "separate_lower_frequency_model_hz": [fine["f"], broad_low["f"]],
            "spatial_cycles_per_row": [q,q/3],
            "exact_alias_difference_cycles_per_frame": 16,
            "max_abs_image_difference": broad_error,
            "minimum_irradiance_lower_bound": two_term_positivity_bound,
            "claim": "same movie in this model; not a model fit to measured broad phase",
        },
        "limits": [
            "Does not reproduce the real video, real DDIC timing or all exposure-sweep stages.",
            "The 30 fps grid and skew/output mapping are deliberately granted, not established on target.",
            "Strict common linear/phase assumptions across multiple exposures can reject particular models.",
            "This does not assert that the ILI97701A can implement the constructed optical fields.",
            "No numeric frequency, low envelope or PWM improvement on the target is established.",
        ],
    }
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(result, out, ensure_ascii=False, indent=2, sort_keys=True)
        out.write("\n")


if __name__ == "__main__":
    main()
