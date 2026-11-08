#!/usr/bin/env python3
"""Spatial band spectra that retain stationary camera stripes.

Input is a finite float-compatible array with shape (frames, rows), usually a
column average of a flat screen patch from ONE controlled state. Select the
baseline/candidate intervals separately; do not pool a whole multi-state video.
The output is in cycles per camera row,
NOT hertz. Encoded image values are not calibrated optical luminance.

Only a low-order spatial trend is removed from each frame. For each spatial
frequency, the complex coefficients C obey the energy decomposition

    mean(abs(C)**2) = abs(mean(C))**2 + mean(abs(C - mean(C))**2).

These are the total, coherent, and incoherent powers. Removing the temporal
mean before computing the spectrum retains only the last term and can erase
real stationary PWM stripes. The coherent term can also contain static screen
content or spatial artefacts, so use a flat patch and retain the original image.

The Hann amplitude normalization is a window-corrected Fourier coefficient,
not a power spectral density or a calibrated modulation depth. Spatial
detrending itself suppresses broad spatial components; set detrend_degree=None
when investigating that effect and inspect the separate raw means.

Requires only NumPy and the Python standard library.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np


def _local_peaks(
    frequencies: np.ndarray,
    power: np.ndarray,
    count: int,
    min_separation: float,
) -> list[int]:
    """Return strongest separated local maxima; retain boundary flags later."""
    if count == 0 or not np.any(power > 0):
        return []
    if len(power) == 1:
        return [0]
    candidates = []
    if power[0] > power[1]:
        candidates.append(0)
    candidates.extend(
        i
        for i in range(1, len(power) - 1)
        if power[i] >= power[i - 1]
        and power[i] >= power[i + 1]
        and (power[i] > power[i - 1] or power[i] > power[i + 1])
    )
    if power[-1] > power[-2]:
        candidates.append(len(power) - 1)
    selected: list[int] = []
    for index in sorted(candidates, key=lambda i: float(power[i]), reverse=True):
        if all(
            abs(float(frequencies[index] - frequencies[other])) >= min_separation
            for other in selected
        ):
            selected.append(index)
            if len(selected) == count:
                break
    return selected


def analyze_profiles(
    profiles: np.ndarray,
    *,
    frequencies: np.ndarray | Sequence[float] | None = None,
    n_fft: int | None = None,
    frequency_min: float = 0.0,
    frequency_max: float = 0.5,
    detrend_degree: int | None = 2,
    window: str = "hann",
    peak_count: int = 8,
    peak_min_separation: float | None = None,
) -> dict[str, Any]:
    """Analyze spatial spectra without subtracting a temporal mean.

    ``profiles`` has shape (frames, rows); it is never modified. The default
    frequency grid spans DC through spatial Nyquist, using a fourfold-or-more
    zero-padded real FFT. Zero padding interpolates the spectrum; it does not
    improve the physical resolution 1 / number_of_rows.

    ``frequencies`` optionally supplies an increasing grid in cycles per row,
    including a singleton such as [1 / 93.43]. Otherwise ``n_fft`` chooses the
    FFT size. ``frequency_min`` and ``frequency_max`` restrict either grid.

    Arrays in the returned dictionary share the same frequency axis. Powers
    have squared input-value units. Their square roots are RMS coefficient
    amplitudes. ``raw_mean`` and ``raw_mean_per_frame`` precede detrending and
    preserve any camera black-level offset. No conversion to optical Hz,
    luminous flux, duty cycle, or modulation depth is performed.

    Coherence here means phase coherence across the sampled frames. It does
    not distinguish physical flicker from static spatial structure by itself.
    """
    values = np.asarray(profiles, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] < 1 or values.shape[1] < 4:
        raise ValueError("profiles must have shape (at least 1 frame, at least 4 rows)")
    if not np.all(np.isfinite(values)):
        raise ValueError("profiles must contain only finite values")
    if not 0 <= frequency_min <= frequency_max <= 0.5:
        raise ValueError("frequency bounds must satisfy 0 <= min <= max <= 0.5 cycles/row")
    frames, rows = values.shape
    if detrend_degree is not None and (
        not isinstance(detrend_degree, (int, np.integer))
        or not 0 <= detrend_degree <= min(3, rows - 1)
    ):
        raise ValueError("detrend_degree must be None or an integer from 0 through 3")
    if not isinstance(peak_count, (int, np.integer)) or peak_count < 0:
        raise ValueError("peak_count must be a nonnegative integer")
    if window == "hann":
        weights = np.hanning(rows)
    elif window in ("rectangular", "boxcar"):
        weights = np.ones(rows)
        window = "rectangular"
    else:
        raise ValueError("window must be 'hann' or 'rectangular'")
    if peak_min_separation is None:
        peak_min_separation = (2.0 if window == "hann" else 1.0) / rows
    if not np.isfinite(peak_min_separation) or peak_min_separation < 0:
        raise ValueError("peak_min_separation must be finite and nonnegative")

    raw_means = values.mean(axis=1)
    signal = values.copy()
    if detrend_degree is not None:
        x = np.linspace(-1.0, 1.0, rows)
        design = np.polynomial.legendre.legvander(x, int(detrend_degree))
        trend_coefficients = np.linalg.lstsq(design, values.T, rcond=None)[0]
        signal -= (design @ trend_coefficients).T
    weighted = signal * weights

    if frequencies is None:
        if n_fft is None:
            n_fft = 1 << (4 * rows - 1).bit_length()
        if not isinstance(n_fft, (int, np.integer)) or n_fft < rows:
            raise ValueError("n_fft must be an integer at least as large as number_of_rows")
        grid = np.fft.rfftfreq(int(n_fft), d=1.0)
        use = (grid >= frequency_min) & (grid <= frequency_max)
        frequencies_array = grid[use]
        coefficients = np.fft.rfft(weighted, n=int(n_fft), axis=1)[:, use]
        method = "real_fft"
    else:
        if n_fft is not None:
            raise ValueError("choose either an explicit frequency grid or n_fft")
        grid = np.asarray(frequencies, dtype=np.float64)
        if (
            grid.ndim != 1
            or len(grid) == 0
            or not np.all(np.isfinite(grid))
            or np.any(grid < 0)
            or np.any(grid > 0.5)
            or np.any(np.diff(grid) <= 0)
        ):
            raise ValueError("frequencies must be finite, strictly increasing, and within [0, 0.5]")
        frequencies_array = grid[(grid >= frequency_min) & (grid <= frequency_max)]
        coefficients = np.empty((frames, len(frequencies_array)), dtype=np.complex128)
        position = np.arange(rows, dtype=np.float64)
        # Bound the temporary basis to roughly 16 MiB, including tall profiles.
        chunk_size = max(1, min(512, 1_048_576 // rows))
        for start in range(0, len(frequencies_array), chunk_size):
            stop = start + chunk_size
            basis = np.exp(-2j * np.pi * np.outer(position, frequencies_array[start:stop]))
            coefficients[:, start:stop] = weighted @ basis
        method = "explicit_fourier_grid"
    if len(frequencies_array) == 0:
        raise ValueError("the requested frequency interval contains no sampled frequencies")

    scale = np.full(len(frequencies_array), 2.0 / weights.sum())
    scale[(frequencies_array == 0) | (frequencies_array == 0.5)] *= 0.5
    coefficients *= scale
    coherent_coefficients = coefficients.mean(axis=0)
    total_power = np.mean(np.abs(coefficients) ** 2, axis=0)
    coherent_power = np.abs(coherent_coefficients) ** 2
    incoherent_power = np.mean(
        np.abs(coefficients - coherent_coefficients[None, :]) ** 2, axis=0
    )
    total_amplitude = np.sqrt(total_power)
    coherent_amplitude = np.sqrt(coherent_power)
    incoherent_amplitude = np.sqrt(incoherent_power)
    peak_indices = _local_peaks(
        frequencies_array, total_power, int(peak_count), float(peak_min_separation)
    )
    maximum_index = int(np.argmax(total_power))
    peaks = []
    for index in peak_indices:
        frequency = float(frequencies_array[index])
        peaks.append(
            {
                "index": index,
                "frequency_cycles_per_row": frequency,
                "period_rows": 1.0 / frequency if frequency > 0 else None,
                "total_rms_amplitude": float(total_amplitude[index]),
                "coherent_amplitude": float(coherent_amplitude[index]),
                "incoherent_rms_amplitude": float(incoherent_amplitude[index]),
                "amplitude_relative_to_maximum": float(
                    total_amplitude[index] / total_amplitude[maximum_index]
                ),
                "at_frequency_boundary": index in (0, len(frequencies_array) - 1),
            }
        )
    return {
        "frequencies_cycles_per_row": frequencies_array,
        "total_power": total_power,
        "coherent_power": coherent_power,
        "incoherent_power": incoherent_power,
        "total_rms_amplitude": total_amplitude,
        "coherent_amplitude": coherent_amplitude,
        "incoherent_rms_amplitude": incoherent_amplitude,
        "raw_mean_per_frame": raw_means,
        "raw_mean": float(raw_means.mean()),
        "frames": frames,
        "rows": rows,
        "method": method,
        "n_fft": int(n_fft) if n_fft is not None else None,
        "detrend_degree": int(detrend_degree) if detrend_degree is not None else None,
        "window": window,
        "nominal_record_bin_width_cycles_per_row": 1.0 / rows,
        "peak_min_separation_cycles_per_row": float(peak_min_separation),
        "peaks": peaks,
        "maximum_at_frequency_boundary": maximum_index in (0, len(frequencies_array) - 1),
        "power_partition_max_abs_error": float(
            np.max(np.abs(total_power - coherent_power - incoherent_power))
        ),
        "units": {
            "frequency": "cycles_per_camera_row",
            "amplitude": "input_value_units",
            "power": "squared_input_value_units_not_PSD",
            "raw_mean": "input_value_units_including_any_black_level",
        },
        "interpretation": (
            "Total retains stationary and moving spatial bands; coherent/incoherent "
            "partition them by frame-to-frame phase consistency. Static content may "
            "also create peaks. No physical frequency or modulation calibration."
        ),
    }


def json_ready(value: Any) -> Any:
    """Convert the result's NumPy arrays/scalars for strict JSON serialization."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help=".npy array or .npz containing frame x row profiles")
    parser.add_argument("--key", default="profiles", help="array key in .npz (default: profiles)")
    parser.add_argument("--output", type=Path, help="write new JSON here; existing evidence is not overwritten")
    parser.add_argument("--min-frequency", type=float, default=0.0, help="cycles/row, default 0")
    parser.add_argument("--max-frequency", type=float, default=0.5, help="cycles/row, default 0.5")
    parser.add_argument("--n-fft", type=int, help="FFT size >= rows; zero padding only interpolates")
    parser.add_argument("--detrend-degree", choices=("none", "0", "1", "2", "3"), default="2")
    parser.add_argument("--window", choices=("hann", "rectangular"), default="hann")
    parser.add_argument("--peaks", type=int, default=8, help="number of separated local peaks")
    args = parser.parse_args(argv)
    loaded = np.load(args.input, allow_pickle=False)
    if isinstance(loaded, np.lib.npyio.NpzFile):
        try:
            if args.key not in loaded:
                parser.error(f"NPZ key {args.key!r} not present; available keys: {', '.join(loaded.files)}")
            profiles = loaded[args.key]
        finally:
            loaded.close()
    else:
        profiles = loaded
    result = analyze_profiles(
        profiles,
        frequency_min=args.min_frequency,
        frequency_max=args.max_frequency,
        n_fft=args.n_fft,
        detrend_degree=None if args.detrend_degree == "none" else int(args.detrend_degree),
        window=args.window,
        peak_count=args.peaks,
    )
    text = json.dumps(json_ready(result), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
