"""Offline 2D spatiotemporal modulation and exposure-sinc analyzer for native 0.6x DNGs.

Analyzes linear Bayer green-averaged patches (two CFA green sites with per-site
black-level subtraction) relative to a flat DC-mode reference frame, quantifying
diagonal PWM wave-vector amplitudes (F(-2, +1)), blanking-notch fractions,
narrow-strip 1D projections, and |sinc(f * T_exp)| carrier-frequency fits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

R113_DIR = Path(__file__).resolve().parent.parent / "night_r113_camera_notch"
if str(R113_DIR) not in sys.path:
    sys.path.insert(0, str(R113_DIR))

import dng_qualify  # noqa: E402

# Interior uniform white ROI in 2x2-averaged coordinates (raw y=90..270, x=1860..2020)
DEFAULT_B2_ROI = (45, 135, 930, 1010)
DEFAULT_BIN = 5
DEFAULT_WAVE_KY = -2
DEFAULT_WAVE_KX = 1
DEFAULT_REFERENCE_MIN_DN = 3.0


def load_bayer2x2_green(path: Path) -> tuple[np.ndarray, dict[int, Any]]:
    """Decode a linear DNG and return per-site black-subtracted 2x2 green mean and tags."""
    raw, tags = dng_qualify.decode_dng_bytes(path.read_bytes())
    meta = dng_qualify.extract_metadata(tags)
    cfa = meta["cfa_pattern_2x2"]
    blacks = meta["black_levels"]
    green_indices = [idx for idx, color in enumerate(cfa) if color == 1]
    if len(green_indices) != 2:
        raise ValueError(f"Expected 2 green CFA sites, got {cfa}")

    green_sum = np.zeros((raw.shape[0] // 2, raw.shape[1] // 2), dtype=np.float64)
    for idx in green_indices:
        dy, dx = divmod(idx, 2)
        plane = raw[dy::2, dx::2].astype(np.float64) - float(blacks[idx])
        green_sum += plane
    return 0.5 * green_sum, tags


def analyze_patch_2d(
    cur_b2: np.ndarray,
    ref_b2: np.ndarray,
    *,
    b2_roi: tuple[int, int, int, int] = DEFAULT_B2_ROI,
    bin_size: int = DEFAULT_BIN,
    target_k: tuple[int, int] = (DEFAULT_WAVE_KY, DEFAULT_WAVE_KX),
    narrow_col_slice: tuple[int, int] = (940, 950),
) -> dict[str, Any]:
    """Compute normalized 2D DFT modulation and blanking-notch metrics on a white patch."""
    if cur_b2.ndim != 2 or ref_b2.ndim != 2 or cur_b2.shape != ref_b2.shape:
        raise ValueError(f"Mismatched or non-2D array shapes: cur={cur_b2.shape}, ref={ref_b2.shape}")

    arr_h, arr_w = ref_b2.shape
    y0, y1, x0, x1 = b2_roi
    if not (0 <= y0 < y1 <= arr_h and 0 <= x0 < x1 <= arr_w):
        raise ValueError(f"b2_roi {b2_roi} out of bounds for shape {(arr_h, arr_w)}")

    nc0, nc1 = narrow_col_slice
    if not (x0 <= nc0 < nc1 <= x1):
        raise ValueError(f"narrow_col_slice {narrow_col_slice} must be non-empty and inside x=[{x0}, {x1}]")

    cur_sub = cur_b2[y0:y1, x0:x1]
    ref_sub = ref_b2[y0:y1, x0:x1]
    h, w = cur_sub.shape
    if bin_size <= 0 or h % bin_size != 0 or w % bin_size != 0:
        raise ValueError(f"Patch shape {(h, w)} incompatible with bin_size={bin_size}")
    gh, gw = h // bin_size, w // bin_size

    # Bin before flat-field division so single-pixel dark noise never crosses zero.
    cur_blk = cur_sub.reshape(gh, bin_size, gw, bin_size).mean(axis=(1, 3))
    ref_blk = ref_sub.reshape(gh, bin_size, gw, bin_size).mean(axis=(1, 3))
    if float(ref_blk.min()) < DEFAULT_REFERENCE_MIN_DN:
        raise ValueError(f"Reference binned block below {DEFAULT_REFERENCE_MIN_DN} DN")

    ratio = cur_blk / ref_blk
    ratio_mean = float(ratio.mean())
    if not np.isfinite(ratio_mean) or ratio_mean <= 0.0:
        raise ValueError("Non-positive or non-finite normalized ratio mean")
    binned = ratio / ratio_mean

    # Cosine amplitude is |F| / N for self-conjugate bins (DC and Nyquist), 2|F| / N otherwise.
    f2_raw = np.abs(np.fft.fft2(binned - 1.0)) / float(binned.size)
    mult_2d = np.full((gh, gw), 2.0, dtype=np.float64)
    for sy in ({0, gh // 2} if gh % 2 == 0 else {0}):
        for sx in ({0, gw // 2} if gw % 2 == 0 else {0}):
            mult_2d[sy, sx] = 1.0
    f2 = f2_raw * mult_2d
    f2_dc_zero = f2.copy()
    f2_dc_zero[0, 0] = 0.0
    ky, kx = target_k
    target_amp = float(f2[ky % gh, kx % gw])

    peak_idx = np.unravel_index(int(np.argmax(f2_dc_zero)), f2_dc_zero.shape)
    pky = int(peak_idx[0]) if peak_idx[0] <= gh // 2 else int(peak_idx[0]) - gh
    pkx = int(peak_idx[1]) if peak_idx[1] <= gw // 2 else int(peak_idx[1]) - gw

    ref_narrow = ref_b2[y0:y1, nc0:nc1].mean(axis=1)
    if float(ref_narrow.min()) < DEFAULT_REFERENCE_MIN_DN:
        raise ValueError("Narrow strip reference mean below minimum threshold")
    p1 = cur_b2[y0:y1, nc0:nc1].mean(axis=1) / ref_narrow
    p1_mean = float(p1.mean())
    if not np.isfinite(p1_mean) or p1_mean <= 0.0:
        raise ValueError("Non-positive or non-finite narrow strip ratio mean")
    p1 /= p1_mean
    fft1 = np.abs(np.fft.rfft(p1 - 1.0)) / float(len(p1))
    mult_1d = np.full(len(fft1), 2.0, dtype=np.float64)
    mult_1d[0] = 1.0
    if len(p1) % 2 == 0:
        mult_1d[-1] = 1.0
    fft1 = fft1 * mult_1d

    return {
        "raw_mean_dn": float(cur_sub.mean()),
        "binned_std": float(binned.std()),
        "binned_min": float(binned.min()),
        "binned_max": float(binned.max()),
        "frac_lt_065": float((binned < 0.65).mean()),
        "frac_065_to_088": float(((binned >= 0.65) & (binned < 0.88)).mean()),
        "target_wave_amp": target_amp,
        "peak_2d_k": [pky, pkx],
        "peak_2d_amp": float(f2_dc_zero[peak_idx]),
        "narrow_1d_k2_amp": float(fft1[2]) if len(fft1) > 2 else 0.0,
    }


def fit_sinc_frequency(
    samples: list[tuple[float, float]],
    freq_min_hz: int = 100,
    freq_max_hz: int = 2500,
    step_hz: int = 2,
) -> dict[str, Any]:
    """Fit A(T) = A0 * |sinc(f * T)| across (exposure_s, amplitude) pairs."""
    if len(samples) < 3:
        raise ValueError("Need at least 3 exposure samples for frequency fit")
    exps = np.array([float(t) for t, _ in samples], dtype=np.float64)
    amps = np.array([float(a) for _, a in samples], dtype=np.float64)

    best: tuple[float, int, float] | None = None
    for f_hz in range(freq_min_hz, freq_max_hz + 1, step_hz):
        sinc_vals = np.abs(np.sinc(f_hz * exps))
        denom = float(np.dot(sinc_vals, sinc_vals))
        if denom <= 0.0:
            continue
        a0 = float(np.dot(sinc_vals, amps) / denom)
        rmse = float(np.sqrt(np.mean((amps - a0 * sinc_vals) ** 2)))
        if best is None or rmse < best[0]:
            best = (rmse, f_hz, a0)

    if best is None:
        raise RuntimeError("Frequency fit failed")

    candidates = {}
    for f_hz in (360, 480, 600, 720, 840, 1080, 1440, 2160):
        sinc_vals = np.abs(np.sinc(f_hz * exps))
        a0 = float(np.dot(sinc_vals, amps) / np.dot(sinc_vals, sinc_vals))
        rmse = float(np.sqrt(np.mean((amps - a0 * sinc_vals) ** 2)))
        candidates[f"{f_hz}_hz"] = {"a0": round(a0, 4), "rmse": round(rmse, 4)}

    return {
        "best_freq_hz": best[1],
        "best_a0": round(best[2], 4),
        "best_rmse": round(best[0], 4),
        "candidates": candidates,
    }


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_bench_summary(evidence_dir: Path, ref_name: str, phases: dict[str, list[str]], sinc_files: list[str]) -> dict[str, Any]:
    """Analyze all recorded bench DNG phases and exposure sinc sweep from disk."""
    ref_b2, ref_tags = load_bayer2x2_green(evidence_dir / ref_name)
    phase_results: dict[str, list[dict[str, Any]]] = {}
    hashes: dict[str, str] = {ref_name: sha256_file(evidence_dir / ref_name)}

    for phase, names in phases.items():
        rows = []
        for name in names:
            p = evidence_dir / name
            hashes[name] = sha256_file(p)
            cur_b2, tags = load_bayer2x2_green(p)
            metrics = analyze_patch_2d(cur_b2, ref_b2)
            exp_us = float(tags[33434][0]) * 1e6 if 33434 in tags else None
            iso = int(tags[34855][0]) if 34855 in tags else None
            rows.append({
                "file": name,
                "exposure_us": exp_us,
                "iso": iso,
                **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in metrics.items()},
            })
        phase_results[phase] = rows

    sinc_samples: list[tuple[float, float]] = []
    sinc_rows = []
    for name in sinc_files:
        p = evidence_dir / name
        hashes[name] = sha256_file(p)
        cur_b2, tags = load_bayer2x2_green(p)
        exp_s = float(tags[33434][0])
        metrics = analyze_patch_2d(cur_b2, ref_b2)
        sinc_samples.append((exp_s, metrics["target_wave_amp"]))
        sinc_rows.append({
            "file": name,
            "exposure_us": round(exp_s * 1e6, 2),
            "target_wave_amp": round(metrics["target_wave_amp"], 4),
            "sinc720": round(float(abs(np.sinc(720.0 * exp_s))), 4),
        })

    return {
        "reference_dng": ref_name,
        "reference_exposure_us": round(float(ref_tags[33434][0]) * 1e6, 2),
        "green_planes_only": True,
        "b2_roi": list(DEFAULT_B2_ROI),
        "target_wave_vector_k": [DEFAULT_WAVE_KY, DEFAULT_WAVE_KX],
        "phases": phase_results,
        "sinc_sweep_samples": sinc_rows,
        "sinc_fit": fit_sinc_frequency(sinc_samples),
        "file_sha256": hashes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze native 0.6x bench DNG phases and sinc sweep.")
    parser.add_argument("--evidence-dir", type=Path, required=True, help="Directory holding private raw DNG files.")
    parser.add_argument("--spec-json", type=Path, required=True, help="JSON file defining reference_dng, phases, sinc_files.")
    parser.add_argument("--out-json", type=Path, required=True, help="Output summary JSON path.")
    args = parser.parse_args(argv)

    spec = json.loads(args.spec_json.read_text(encoding="utf-8"))
    summary = run_bench_summary(
        args.evidence_dir,
        spec["reference_dng"],
        spec["phases"],
        spec["sinc_files"],
    )
    args.out_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
