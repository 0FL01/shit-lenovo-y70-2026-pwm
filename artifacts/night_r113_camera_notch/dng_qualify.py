#!/usr/bin/env python3
"""Offline 0.6x native Bayer DNG qualification and bracket builder for R113.

Reads strict uncompressed uint16 CFA DNG files (either single-IFD CFA or IFD0
EXIF/thumbnail + one full-res CFA SubIFD) without demosaicing, verifies
lens/geometry/exposure/clipping/dark-noise gates, and evaluates the two
preselected spatial-frequency hypotheses (2160 Hz and 1/52us - 2160 Hz) on the
two green CFA phases separately. Does not touch devices or calibrate time.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
from typing import Any

import numpy as np

ROW_PITCH_US_DEFAULT = 13.0
BASE_STEP_US = 52.0
PRESELECTED_HYPOTHESES_HZ = (
    ("h_2160hz", 2160.0),
    ("h_17071hz_alias", 1e6 / BASE_STEP_US - 2160.0),
)
DEFAULT_WIDTH = 3264
DEFAULT_HEIGHT = 2448
DEFAULT_FOCAL_RANGE_MM = (1.35, 1.95)  # GC08A8 0.6x ~1.64 mm; rejects 1x ~5.56 mm.
VALID_BAYER_CFAS = ([0, 1, 1, 2], [1, 0, 2, 1], [1, 2, 0, 1], [2, 1, 1, 0])

REQUIRED_RAW_TAGS = (
    256, 257, 258, 259, 262, 273, 277, 278, 279,
    33421, 33422, 50714, 50717,
)
REQUIRED_EXIF_TAGS = (33434, 34855)
SHARED_META_TAGS = {271, 272, 274, 33434, 34855, 37386, 50706}
RAW_KEEP_TAGS = set(REQUIRED_RAW_TAGS) | SHARED_META_TAGS | {
    254, 284, 339, 50710, 50711, 50712, 50713, 50715, 50716, 50719, 50720, 50829,
}
IFD0_KEEP_TAGS = SHARED_META_TAGS | {254, 262, 330, 34665} | RAW_KEEP_TAGS
EXIF_KEEP_TAGS = {33434, 34855, 37386}
TIFF_TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8, 11: 4, 12: 8}


class DNGQualificationError(ValueError):
    """Raised when a DNG fails format, geometry, lens, or signal-headroom gates."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DNGQualificationError(message)


def _unpack(data: bytes, endian: str, fmt: str, offset: int) -> tuple[Any, ...]:
    size = struct.calcsize(endian + fmt)
    _require(0 <= offset <= len(data) - size, "Truncated TIFF structure")
    return struct.unpack_from(endian + fmt, data, offset)


def _decode_tag_value(
    data: bytes, endian: str, typ: int, count: int, pos: int
) -> Any:
    _require(typ in TIFF_TYPE_SIZES and 0 < count <= 100_000, f"Invalid TIFF field type/count ({typ}, {count})")
    byte_len = TIFF_TYPE_SIZES[typ] * count
    _require(0 <= pos <= len(data) - byte_len, "Truncated TIFF tag payload")
    if typ in (1, 3, 4, 7):
        fmt_char = {1: "B", 3: "H", 4: "I", 7: "B"}[typ]
        return list(_unpack(data, endian, f"{count}{fmt_char}", pos))
    if typ == 2:
        raw_bytes = data[pos : pos + count]
        return raw_bytes.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()
    if typ == 5:
        nums = _unpack(data, endian, f"{2 * count}I", pos)
        _require(all(nums[1::2]), "Zero rational denominator")
        return [num / den for num, den in zip(nums[::2], nums[1::2])]
    if typ == 10:
        nums = _unpack(data, endian, f"{2 * count}i", pos)
        _require(all(nums[1::2]), "Zero signed rational denominator")
        return [num / den for num, den in zip(nums[::2], nums[1::2])]
    raise DNGQualificationError(f"Unsupported TIFF tag type {typ}")


def _read_ifd(data: bytes, endian: str, ifd_offset: int, keep: set[int]) -> tuple[dict[int, Any], int]:
    field_count = _unpack(data, endian, "H", ifd_offset)[0]
    _require(field_count <= 512, "Too many IFD fields")
    tags: dict[int, Any] = {}
    for index in range(field_count):
        entry = ifd_offset + 2 + index * 12
        tag, typ, count = _unpack(data, endian, "HHI", entry)
        if tag not in keep:
            continue
        _require(tag not in tags, f"Duplicate TIFF tag {tag}")
        _require(typ in TIFF_TYPE_SIZES and 0 < count <= 100_000, f"Invalid tag {tag} type/count")
        size = TIFF_TYPE_SIZES[typ] * count
        pos = entry + 8 if size <= 4 else _unpack(data, endian, "I", entry + 8)[0]
        tags[tag] = _decode_tag_value(data, endian, typ, count, pos)
    next_ifd = _unpack(data, endian, "I", ifd_offset + 2 + field_count * 12)[0]
    return tags, next_ifd


def _is_full_res_cfa_ifd(ifd_tags: dict[int, Any]) -> bool:
    return ifd_tags.get(262) == [32803] and ifd_tags.get(254, [0]) == [0]


def decode_dng_bytes(data: bytes) -> tuple[np.ndarray, dict[int, Any]]:
    """Decode strict uncompressed uint16 CFA DNG bytes into (raw, validated_tags)."""
    _require(len(data) >= 8 and data[:2] in (b"II", b"MM"), "Invalid TIFF header")
    endian = "<" if data[:2] == b"II" else ">"
    _require(_unpack(data, endian, "H", 2)[0] == 42, "Not classic TIFF (magic != 42)")
    ifd0_offset = _unpack(data, endian, "I", 4)[0]
    ifd0, next_ifd = _read_ifd(data, endian, ifd0_offset, IFD0_KEEP_TAGS)
    _require(next_ifd == 0, "Chained top-level IFDs unsupported")

    exif_tags: dict[int, Any] = {}
    if 34665 in ifd0:
        _require(len(ifd0[34665]) == 1, "Multiple ExifIFD pointers unsupported")
        exif_tags, _ = _read_ifd(data, endian, int(ifd0[34665][0]), EXIF_KEEP_TAGS)

    candidates: list[dict[int, Any]] = []
    if _is_full_res_cfa_ifd(ifd0):
        candidates.append({k: v for k, v in ifd0.items() if k in RAW_KEEP_TAGS})
    for sub_off in ifd0.get(330, []):
        sub_tags, sub_next = _read_ifd(data, endian, int(sub_off), RAW_KEEP_TAGS)
        _require(sub_next == 0, "Chained SubIFDs unsupported")
        if _is_full_res_cfa_ifd(sub_tags):
            candidates.append(sub_tags)

    _require(len(candidates) == 1, f"Expected exactly 1 full-res CFA IFD, found {len(candidates)}")
    raw_tags = candidates[0]

    for required in REQUIRED_RAW_TAGS:
        _require(required in raw_tags, f"Missing required RAW IFD tag {required}")

    width, height = int(raw_tags[256][0]), int(raw_tags[257][0])
    _require(0 < width <= 20_000 and 0 < height <= 20_000, "Invalid image dimensions")
    _require(width % 2 == 0 and height % 2 == 0, "Odd CFA image dimensions unsupported")
    _require(raw_tags[258] == [16], f"Expected 16-bit samples, got {raw_tags[258]}")
    _require(raw_tags.get(339, [1]) == [1], f"Expected unsigned integer SampleFormat (1), got {raw_tags.get(339)}")
    _require(raw_tags[259] == [1], f"Expected uncompressed TIFF (1), got {raw_tags[259]}")
    _require(raw_tags[262] == [32803], f"Expected CFA photometric (32803), got {raw_tags[262]}")
    _require(raw_tags[277] == [1], f"Expected 1 sample/pixel, got {raw_tags[277]}")
    _require(raw_tags.get(284, [1]) == [1], "Unsupported planar configuration")
    _require(raw_tags[33421] == [2, 2] and raw_tags[33422] in VALID_BAYER_CFAS, "Unsupported 2x2 Bayer CFA layout")
    _require(raw_tags.get(50711, [1]) == [1], f"Unsupported non-rectangular CFALayout {raw_tags.get(50711)}")

    black_dim = raw_tags.get(50713, [1, 1])
    if black_dim == [1, 1] and len(raw_tags[50714]) == 1:
        raw_tags[50713] = [2, 2]
        raw_tags[50714] = raw_tags[50714] * 4
    else:
        _require(black_dim == [2, 2] and len(raw_tags[50714]) == 4, "Need 1x1 or 2x2 per-CFA BlackLevel")
    _require(min(raw_tags[50714]) >= 0.0, "Negative BlackLevel unsupported")
    _require(not any(t in raw_tags for t in (50712, 50715, 50716)), "Linearization/black-delta tags unsupported")
    _require(raw_tags.get(50710, [0, 1, 2]) == [0, 1, 2], "Non-RGB CFA planes unsupported")
    _require(raw_tags.get(50829, [0, 0, height, width]) == [0, 0, height, width], "Non-full ActiveArea unsupported")
    _require(
        len(raw_tags[50717]) == 1 and max(raw_tags[50714]) < raw_tags[50717][0] <= 65535,
        "Invalid WhiteLevel for uint16 SamplesPerPixel=1",
    )

    shared_meta = {
        k: raw_tags[k] if k in raw_tags else (exif_tags[k] if k in exif_tags else ifd0[k])
        for k in SHARED_META_TAGS
        if k in raw_tags or k in exif_tags or k in ifd0
    }
    tags = {**raw_tags, **shared_meta}
    for required in REQUIRED_EXIF_TAGS:
        _require(required in tags, f"Missing required capture metadata tag {required}")
    _require(len(tags[33434]) == 1 and tags[33434][0] > 0, "Invalid ExposureTime")
    _require(len(tags[34855]) == 1 and tags[34855][0] > 0, "Invalid ISO")

    rows_per_strip = int(raw_tags[278][0])
    _require(rows_per_strip > 0, "Invalid RowsPerStrip")
    offsets, counts = raw_tags[273], raw_tags[279]
    expected_strips = (height + rows_per_strip - 1) // rows_per_strip
    _require(len(offsets) == len(counts) == expected_strips, "Strip count mismatch")

    raw = np.empty((height, width), dtype=np.uint16)
    for idx, (offset, byte_count) in enumerate(zip(offsets, counts)):
        y0 = idx * rows_per_strip
        rows = min(rows_per_strip, height - y0)
        _require(byte_count == rows * width * 2, "Unexpected strip byte count")
        _require(0 <= offset <= len(data) - byte_count, "Truncated strip bytes")
        raw[y0 : y0 + rows] = np.frombuffer(
            data, dtype=endian + "u2", count=rows * width, offset=offset
        ).reshape(rows, width)
    return raw, tags


def extract_metadata(tags: dict[int, Any]) -> dict[str, Any]:
    """Build sanitized numeric/text DNG metadata summary."""
    width, height = int(tags[256][0]), int(tags[257][0])
    exposure_s = float(tags[33434][0])
    focal = float(tags[37386][0]) if 37386 in tags and tags[37386] else None
    return {
        "make": tags.get(271),
        "model": tags.get(272),
        "width": width,
        "height": height,
        "orientation": int(tags[274][0]) if 274 in tags else None,
        "cfa_pattern_2x2": [int(v) for v in tags[33422]],
        "exposure_seconds": exposure_s,
        "exposure_us": exposure_s * 1e6,
        "iso": int(tags[34855][0]),
        "focal_length_mm": focal,
        "black_levels": [float(v) for v in tags[50714]],
        "white_level": float(tags[50717][0]),
        "default_crop_origin": [float(v) for v in tags[50719]] if 50719 in tags else None,
        "default_crop_size": [float(v) for v in tags[50720]] if 50720 in tags else None,
    }


def _validate_roi(roi: tuple[int, int, int, int], width: int, height: int, min_rows: int) -> None:
    if len(roi) != 4:
        raise DNGQualificationError("ROI must have 4 integer bounds [x0, y0, x1, y1]")
    x0, y0, x1, y1 = roi
    _require(all(isinstance(v, int) and v % 2 == 0 for v in roi), "ROI coordinates must be even integers")
    _require(0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height, "ROI out of image bounds")
    _require(y1 - y0 >= min_rows, f"ROI height {y1 - y0} below minimum {min_rows} physical rows")


def _fit_preselected_component(
    profile: np.ndarray,
    phys_rows: np.ndarray,
    freq_hz: float,
    row_pitch_us: float,
    *,
    dc_override_dn: float | None = None,
) -> dict[str, float]:
    """Linearly detrended OLS sinusoid fit at one preselected frequency (no peak fishing)."""
    q_phys = freq_hz * row_pitch_us * 1e-6
    _require(0.0 < q_phys < 0.25, f"Frequency {freq_hz} Hz is at or above single-phase green Nyquist")
    times_s = phys_rows * (row_pitch_us * 1e-6)
    r_centered = phys_rows - phys_rows.mean()
    design = np.column_stack((
        np.ones(len(phys_rows)),
        r_centered,
        np.sin(2.0 * math.pi * freq_hz * times_s),
        np.cos(2.0 * math.pi * freq_hz * times_s),
    ))
    coef, _, rank, _ = np.linalg.lstsq(design, profile, rcond=None)
    _require(rank == 4, "Rank-deficient preselected frequency fit")
    dc_dn = float(coef[0]) if dc_override_dn is None else dc_override_dn
    _require(dc_dn > 0.0, f"Non-positive DC intercept {dc_dn}")
    amp_dn = float(math.hypot(coef[2], coef[3]))
    residual = profile - design @ coef
    return {
        "q_cycles_per_physical_row": q_phys,
        "physical_rows_per_cycle": 1.0 / q_phys,
        "dc_dn": dc_dn,
        "amplitude_dn": amp_dn,
        "fractional_amplitude": amp_dn / dc_dn,
        "residual_std_dn": float(residual.std()),
        "phase_radians": float(math.atan2(coef[3], coef[2])),
    }


def _phase_stats(
    raw: np.ndarray,
    roi: tuple[int, int, int, int],
    cfa_index: int,
    black: float,
    white: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    x0, y0, x1, y1 = roi
    dy, dx = divmod(cfa_index, 2)
    stored = raw[y0 + dy : y1 : 2, x0 + dx : x1 : 2]
    linear = stored.astype(np.float64) - black
    profile = linear.mean(axis=1)
    phys_rows = np.arange(y0 + dy, y1, 2, dtype=np.float64)
    p1_raw, p50_raw, p99_raw = np.percentile(stored, [1, 50, 99])
    span = white - black
    stats = {
        "cfa_position": [dy, dx],
        "sample_rows": int(stored.shape[0]),
        "sample_cols": int(stored.shape[1]),
        "black_dn": black,
        "white_dn": white,
        "mean_dn": float(linear.mean()),
        "median_dn": float(np.median(linear)),
        "min_dn": float(linear.min()),
        "max_dn": float(linear.max()),
        "std_dn": float(linear.std()),
        "raw_p1_p50_p99": [float(p1_raw), float(p50_raw), float(p99_raw)],
        "fraction_at_or_above_white": float((stored >= white).mean()),
        "fraction_at_storage_floor": float((stored == 0).mean()),
        "headroom_fraction": float((white - p99_raw) / span),
    }
    return profile, phys_rows, stats


def analyze_bayer_pair(
    raw: np.ndarray,
    tags: dict[int, Any],
    screen_roi: tuple[int, int, int, int],
    dark_roi: tuple[int, int, int, int],
    *,
    row_pitch_us: float = ROW_PITCH_US_DEFAULT,
    freq_rel_tol: float = 0.01,
    extra_amplitude_margin: float = 0.0,
    min_roi_rows: int = 72,
    max_clipping_fraction: float = 0.0,
    max_screen_floor_fraction: float = 0.0,
    min_signal_to_dark_ratio: float = 3.0,
    expected_width: int | None = DEFAULT_WIDTH,
    expected_height: int | None = DEFAULT_HEIGHT,
    expected_focal_range_mm: tuple[float, float] | None = DEFAULT_FOCAL_RANGE_MM,
    allow_rotated_orientation: bool = False,
) -> dict[str, Any]:
    """Qualify one native DNG and evaluate preselected bands on separated green phases."""
    meta = extract_metadata(tags)
    width, height = meta["width"], meta["height"]
    if expected_width is not None:
        _require(width == expected_width, f"Expected width {expected_width}, got {width}")
    if expected_height is not None:
        _require(height == expected_height, f"Expected height {expected_height}, got {height}")
    if expected_focal_range_mm is not None:
        focal = meta["focal_length_mm"]
        lo_f, hi_f = expected_focal_range_mm
        _require(
            focal is not None and lo_f <= focal <= hi_f,
            f"FocalLength {focal} mm outside expected 0.6x range [{lo_f}, {hi_f}]",
        )
    if not allow_rotated_orientation and meta["orientation"] is not None:
        _require(
            meta["orientation"] == 1,
            f"Orientation={meta['orientation']} != 1; verify readout row axis explicitly",
        )
    _require(0.0 <= freq_rel_tol <= 0.1, "Unsupported frequency_relative_tolerance")
    _require(extra_amplitude_margin >= 0.0, "Negative extra_amplitude_margin")

    _validate_roi(screen_roi, width, height, min_roi_rows)
    _validate_roi(dark_roi, width, height, min_roi_rows)

    cfa = meta["cfa_pattern_2x2"]
    green_indices = [idx for idx, color in enumerate(cfa) if color == 1]
    _require(len(green_indices) == 2, "Expected exactly 2 green sites in 2x2 CFA")

    white = meta["white_level"]
    blacks = meta["black_levels"]
    sx0, sy0, sx1, sy1 = screen_roi
    dx0, dy0, dx1, dy1 = dark_roi
    screen_clip_all = float((raw[sy0:sy1, sx0:sx1] >= white).mean())
    dark_clip_all = float((raw[dy0:dy1, dx0:dx1] >= white).mean())
    screen_floor_all = float((raw[sy0:sy1, sx0:sx1] == 0).mean())
    dark_floor_all = float((raw[dy0:dy1, dx0:dx1] == 0).mean())
    _require(screen_clip_all <= max_clipping_fraction, f"Upper clipping on screen ROI (all CFA): {screen_clip_all}")
    _require(dark_clip_all <= max_clipping_fraction, f"Upper clipping on dark ROI (all CFA): {dark_clip_all}")
    _require(screen_floor_all <= max_screen_floor_fraction, f"Lower storage-floor clipping on screen ROI: {screen_floor_all}")
    clipping_summary = {
        "screen_upper_clipping_fraction": screen_clip_all,
        "dark_upper_clipping_fraction": dark_clip_all,
        "screen_lower_floor_fraction": screen_floor_all,
        "dark_lower_floor_fraction": dark_floor_all,
        "within_clipping_tolerances": True,
        "zero_clipping_observed": (
            screen_clip_all == 0.0
            and dark_clip_all == 0.0
            and screen_floor_all == 0.0
            and dark_floor_all == 0.0
        ),
    }

    roi_span_s = (sy1 - sy0) * row_pitch_us * 1e-6
    green_phases: list[dict[str, Any]] = []
    combined: dict[str, dict[str, Any]] = {}

    for idx in green_indices:
        black = blacks[idx]
        s_prof, s_rows, s_stats = _phase_stats(raw, screen_roi, idx, black, white)
        d_prof, d_rows, d_stats = _phase_stats(raw, dark_roi, idx, black, white)

        _require(s_stats["mean_dn"] > 0.0, f"Non-positive black-corrected screen mean on CFA {s_stats['cfa_position']}")
        dark_abs_floor = max(abs(d_stats["mean_dn"]), d_stats["std_dn"], 1e-6)
        signal_ratio = s_stats["mean_dn"] / dark_abs_floor
        _require(
            signal_ratio >= min_signal_to_dark_ratio,
            f"Insufficient screen signal vs dark background ({signal_ratio:.2f} < {min_signal_to_dark_ratio})",
        )

        bands: dict[str, Any] = {}
        n_rows = s_stats["sample_rows"]
        for label, freq_hz in PRESELECTED_HYPOTHESES_HZ:
            delta_cycles = freq_hz * roi_span_s * freq_rel_tol
            s_fit = _fit_preselected_component(s_prof, s_rows, freq_hz, row_pitch_us)
            dc_dn = s_fit["dc_dn"]
            d_fit = _fit_preselected_component(
                d_prof, d_rows, freq_hz, row_pitch_us, dc_override_dn=dc_dn
            )
            noise_floor_frac = d_fit["amplitude_dn"] / dc_dn
            fit_se_frac = (3.0 * s_fit["residual_std_dn"] * math.sqrt(2.0 / n_rows)) / dc_dn
            dc_rel_err = (3.0 * s_fit["residual_std_dn"] / math.sqrt(n_rows) + 0.5) / dc_dn
            _require(dc_rel_err < 0.5, "Excessive DC relative uncertainty")
            noise_bound = max(noise_floor_frac, fit_se_frac) + 0.5 / dc_dn
            frac = s_fit["fractional_amplitude"]
            if delta_cycles < 0.5:
                detune_factor = (
                    math.sin(math.pi * delta_cycles) / (math.pi * delta_cycles) if delta_cycles > 0.0 else 1.0
                )
                lo = max(0.0, (frac - noise_bound) / (1.0 + dc_rel_err) - extra_amplitude_margin)
                hi = (frac / detune_factor + noise_bound) / (1.0 - dc_rel_err) + extra_amplitude_margin
                interval: list[float] | None = [lo, hi]
                detune_status = "WITHIN_HALF_CYCLE_TOLERANCE"
            else:
                detune_factor = None
                interval = None
                detune_status = "ROI_TOO_TALL_FOR_FIXED_TEMPLATE"
            bands[label] = {
                "freq_hz": freq_hz,
                "screen": s_fit,
                "dark_noise_floor_dn": d_fit["amplitude_dn"],
                "dark_noise_floor_fractional": noise_floor_frac,
                "detune_delta_cycles": delta_cycles,
                "detune_lower_factor": detune_factor,
                "detune_status": detune_status,
                "diagnostic_fractional_interval": interval,
            }
        green_phases.append({
            "cfa_index": idx,
            "screen_stats": s_stats,
            "dark_stats": d_stats,
            "signal_to_dark_ratio": signal_ratio,
            "preselected_bands": bands,
        })

    for label, freq_hz in PRESELECTED_HYPOTHESES_HZ:
        intervals = [p["preselected_bands"][label]["diagnostic_fractional_interval"] for p in green_phases]
        amps = [p["preselected_bands"][label]["screen"]["fractional_amplitude"] for p in green_phases]
        if all(iv is not None for iv in intervals):
            combined_iv: list[float] | None = [
                min(iv[0] for iv in intervals if iv is not None),
                max(iv[1] for iv in intervals if iv is not None),
            ]
        else:
            combined_iv = None
        combined[label] = {
            "freq_hz": freq_hz,
            "g1_g2_fractional_amplitudes": amps,
            "g1_g2_difference": abs(amps[0] - amps[1]),
            "diagnostic_combined_interval": combined_iv,
        }

    return {
        "status": "QUALIFIED_SINGLE_DNG",
        "metadata": meta,
        "clipping_summary": clipping_summary,
        "row_pitch_us_model": row_pitch_us,
        "freq_rel_tol": freq_rel_tol,
        "screen_roi": list(screen_roi),
        "dark_roi": list(dark_roi),
        "green_phases": green_phases,
        "combined_preselected": combined,
    }


def qualify_dng_file(
    path: Path,
    screen_roi: tuple[int, int, int, int],
    dark_roi: tuple[int, int, int, int],
    **kwargs: Any,
) -> dict[str, Any]:
    """Load and qualify a single DNG path from disk."""
    raw_bytes = path.read_bytes()
    raw, tags = decode_dng_bytes(raw_bytes)
    result = analyze_bayer_pair(raw, tags, screen_roi, dark_roi, **kwargs)
    result["file_name"] = path.name
    result["file_sha256"] = hashlib.sha256(raw_bytes).hexdigest()
    return result


def build_bracket_payload(manifest: dict[str, Any], *, base_dir: Path | None = None) -> dict[str, Any]:
    """Build verify.py-compatible payload plus provenance from a multi-block DNG manifest."""
    screen_roi = tuple(manifest["screen_roi"])
    dark_roi = tuple(manifest["dark_roi"])
    band_key = manifest.get("band_key", "h_2160hz")
    if band_key not in dict(PRESELECTED_HYPOTHESES_HZ):
        raise DNGQualificationError(f"Unknown preselected band_key: {band_key}")

    freq_rel_tol = float(manifest.get("frequency_relative_tolerance", 0.01))
    qual_opts = dict(manifest.get("qualification_options", {}))
    if "freq_rel_tol" in qual_opts:
        _require(
            math.isclose(float(qual_opts["freq_rel_tol"]), freq_rel_tol, rel_tol=0.0, abs_tol=1e-12),
            "Conflicting qualification_options.freq_rel_tol and frequency_relative_tolerance",
        )
    qual_opts["freq_rel_tol"] = freq_rel_tol
    max_exp_rel = float(manifest.get("max_exposure_mismatch_rel", 0.12))
    max_exp_abs_us = float(manifest.get("max_exposure_mismatch_us", 26.0))
    _require(
        math.isfinite(max_exp_rel) and max_exp_rel >= 0.0 and math.isfinite(max_exp_abs_us) and max_exp_abs_us >= 0.0,
        "Invalid or non-finite exposure mismatch tolerance",
    )

    expected_iso: int | None = manifest.get("expected_iso")
    expected_geom: tuple[int, int, list[int]] | None = None
    seen_files: set[Path] = set()
    seen_hashes: set[str] = set()
    blocks_out: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    used_diagnostic_only = False
    any_nonzero_clipping = False

    for block in manifest["blocks"]:
        samples_out: list[dict[str, Any]] = []
        for sample in block["samples"]:
            dng_path = Path(sample["dng_path"])
            if not dng_path.is_absolute() and base_dir is not None:
                dng_path = base_dir / dng_path
            resolved = dng_path.resolve()
            _require(resolved not in seen_files, f"Duplicate DNG path reused across samples/blocks: {dng_path.name}")
            seen_files.add(resolved)

            actual_t = sample["actual_time_us"]
            _require(
                isinstance(actual_t, list) and len(actual_t) == 2 and 0 < actual_t[0] <= actual_t[1],
                f"Invalid actual_time_us interval for {dng_path.name}",
            )
            q = qualify_dng_file(dng_path, screen_roi, dark_roi, **qual_opts)
            fhash = q["file_sha256"]
            _require(fhash not in seen_hashes, f"Byte-identical DNG reused across samples/blocks: {dng_path.name}")
            seen_hashes.add(fhash)

            meta = q["metadata"]
            if not q["clipping_summary"]["zero_clipping_observed"]:
                any_nonzero_clipping = True
            t_mid = 0.5 * (actual_t[0] + actual_t[1])
            exp_tol = max(max_exp_abs_us, max_exp_rel * t_mid)
            _require(
                abs(meta["exposure_us"] - t_mid) <= exp_tol,
                f"DNG ExposureTime {meta['exposure_us']:.1f} us disagrees with actual_time_us {actual_t} in {dng_path.name}",
            )
            if expected_iso is None:
                expected_iso = meta["iso"]
            _require(meta["iso"] == expected_iso, f"ISO drift in {dng_path.name}: {meta['iso']} != {expected_iso}")
            geom = (meta["width"], meta["height"], meta["cfa_pattern_2x2"])
            if expected_geom is None:
                expected_geom = geom
            _require(geom == expected_geom, f"Geometry/CFA mismatch in {dng_path.name}")

            band_summary = q["combined_preselected"][band_key]
            diag_interval = band_summary["diagnostic_combined_interval"]
            _require(
                diag_interval is not None,
                f"Screen ROI too tall for fixed-template tolerance on {band_key} in {dng_path.name}",
            )
            if "amplitude" in sample:
                ext_amp = sample["amplitude"]
                _require(
                    isinstance(ext_amp, list) and len(ext_amp) == 2 and 0.0 <= ext_amp[0] <= ext_amp[1],
                    f"Invalid externally supplied amplitude interval for {dng_path.name}",
                )
                g_amps = band_summary["g1_g2_fractional_amplitudes"]
                _require(
                    ext_amp[0] <= min(g_amps) and max(g_amps) <= ext_amp[1],
                    f"Externally supplied amplitude {ext_amp} excludes measured G1/G2 {g_amps} in {dng_path.name}",
                )
                amp_out = ext_amp
            else:
                used_diagnostic_only = True
                amp_out = diag_interval

            samples_out.append({
                "actual_time_us": actual_t,
                "amplitude": amp_out,
            })
            provenance.append({
                "block_id": block["id"],
                "file_name": dng_path.name,
                "file_sha256": fhash,
                "dng_exposure_us": meta["exposure_us"],
                "actual_time_us": actual_t,
                "iso": meta["iso"],
                "diagnostic_combined_interval": diag_interval,
                "amplitude_source": "diagnostic_only" if "amplitude" not in sample else "external_calibrated",
            })
        blocks_out.append({
            "id": block["id"],
            "order": block["order"],
            "samples": samples_out,
        })

    gates = dict(manifest.get("gates", {}))
    if any_nonzero_clipping:
        _require(
            gates.get("no_clipping") is not True,
            "Cannot claim gates.no_clipping=true when non-zero clipping or floor samples were observed",
        )
        gates["no_clipping"] = False
    if used_diagnostic_only:
        _require(
            gates.get("intervals_cover_noise_and_drift") is not True,
            "Cannot claim gates.intervals_cover_noise_and_drift=true without externally justified sample.amplitude bounds",
        )
        gates["intervals_cover_noise_and_drift"] = False

    return {
        "units": "black_corrected_linear_fractional_amplitude",
        "frequency_relative_tolerance": freq_rel_tol,
        "minimum_fractional_contrast": manifest.get("minimum_fractional_contrast", 0.002),
        "band_context": {
            "band_key": band_key,
            "spatial_band_hz": dict(PRESELECTED_HYPOTHESES_HZ)[band_key],
            "row_pitch_us_model": qual_opts.get("row_pitch_us", ROW_PITCH_US_DEFAULT),
            "intervals_bound_source": (
                "uncalibrated_dng_diagnostic_forced_hold" if used_diagnostic_only else "external_calibrated_and_dng_checked"
            ),
        },
        "provenance": provenance,
        "gates": gates,
        "blocks": blocks_out,
    }


def verify_bracket_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Run unified verify.verify() on a bracket payload."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import verify as r113_verify

    return r113_verify.verify(payload)


def _parse_roi_arg(text: str) -> tuple[int, int, int, int]:
    parts = [int(v.strip()) for v in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("ROI must be x0,y0,x1,y1")
    return (parts[0], parts[1], parts[2], parts[3])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Qualify 0.6x native Bayer DNGs for R113.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_one = sub.add_parser("qualify-one", help="Qualify a single 0.6x DNG with screen and dark ROIs.")
    p_one.add_argument("dng", type=Path)
    p_one.add_argument("--screen-roi", type=_parse_roi_arg, required=True)
    p_one.add_argument("--dark-roi", type=_parse_roi_arg, required=True)
    p_one.add_argument("--row-pitch-us", type=float, default=ROW_PITCH_US_DEFAULT)
    p_one.add_argument("--min-roi-rows", type=int, default=72)

    p_br = sub.add_parser("build-bracket", help="Build verify.py JSON from a bracket DNG manifest.")
    p_br.add_argument("manifest", type=Path)
    p_br.add_argument("--verify", action="store_true", help="Also run verify_bracket_payload() and exit 2 on HOLD.")

    args = parser.parse_args(argv)
    if args.cmd == "qualify-one":
        out = qualify_dng_file(
            args.dng,
            args.screen_roi,
            args.dark_roi,
            row_pitch_us=args.row_pitch_us,
            min_roi_rows=args.min_roi_rows,
        )
        print(json.dumps(out, indent=2))
        return 0

    manifest = json.loads(args.manifest.read_text(encoding="utf8"))
    payload = build_bracket_payload(manifest, base_dir=args.manifest.parent)
    if args.verify:
        res = verify_bracket_payload(payload)
        print(json.dumps({"payload": payload, "verify_result": res}, indent=2))
        return 0 if res["status"] in ("CONDITIONAL_COMPONENT_MATCH", "CONDITIONAL_ALIAS_COMPONENT_MATCH") else 2
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
