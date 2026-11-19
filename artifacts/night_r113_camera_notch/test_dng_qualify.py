#!/usr/bin/env python3
"""Synthetic unit tests for dng_qualify.py (no real camera frames or device I/O)."""
from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np

import dng_qualify as dq
import verify as r113_verify


def _pack_ifd(entries: list[tuple[int, int, int, bytes]], base_offset: int, endian: str = "<") -> tuple[bytes, int]:
    """Build one classic TIFF IFD and trailing out-of-line data starting at base_offset."""
    count = len(entries)
    ifd_size = 2 + count * 12 + 4
    data_cursor = base_offset + ifd_size
    ifd_buf = bytearray(struct.pack(endian + "H", count))
    extra_buf = bytearray()
    for tag, typ, cnt, raw_val in sorted(entries, key=lambda x: x[0]):
        if len(raw_val) <= 4:
            padded = raw_val + b"\x00" * (4 - len(raw_val))
            ifd_buf += struct.pack(endian + "HHI", tag, typ, cnt) + padded
        else:
            ifd_buf += struct.pack(endian + "HHII", tag, typ, cnt, data_cursor)
            extra_buf += raw_val
            if len(raw_val) % 2:
                extra_buf += b"\x00"
            data_cursor = base_offset + ifd_size + len(extra_buf)
    ifd_buf += struct.pack(endian + "I", 0)
    return bytes(ifd_buf + extra_buf), data_cursor


def build_synthetic_dng(
    raw: np.ndarray,
    *,
    focal_mm: float = 1.64,
    exposure_us: float = 156.0,
    iso: int = 800,
    cfa: tuple[int, int, int, int] = (0, 1, 1, 2),
    black_levels: tuple[int, int, int, int] = (64, 64, 64, 64),
    white_level: int = 1023,
    orientation: int = 1,
    compression: int = 1,
    photometric: int = 32803,
    sample_format: int | None = None,
    cfa_layout: int | None = None,
    use_subifd: bool = False,
    ifd0_cfa_with_thumb_subifd: bool = False,
    omit_black_repeat_dim: bool = False,
    endian: str = "<",
) -> bytes:
    """Create an in-memory uncompressed uint16 CFA TIFF/DNG byte blob."""
    height, width = raw.shape
    pixel_bytes = raw.astype(endian + "u2").tobytes()
    row_bytes = width * 2
    pixel_offset = 4096
    strip_offsets = [pixel_offset + y * row_bytes for y in range(height)]
    strip_counts = [row_bytes] * height

    def rat(num: int, den: int) -> bytes:
        return struct.pack(endian + "II", num, den)

    exp_num = max(1, round(exposure_us))
    raw_entries = [
        (256, 4, 1, struct.pack(endian + "I", width)),
        (257, 4, 1, struct.pack(endian + "I", height)),
        (258, 3, 1, struct.pack(endian + "H", 16)),
        (259, 3, 1, struct.pack(endian + "H", compression)),
        (262, 3, 1, struct.pack(endian + "H", photometric)),
        (273, 4, height, struct.pack(endian + f"{height}I", *strip_offsets)),
        (277, 3, 1, struct.pack(endian + "H", 1)),
        (278, 4, 1, struct.pack(endian + "I", 1)),
        (279, 4, height, struct.pack(endian + f"{height}I", *strip_counts)),
        (284, 3, 1, struct.pack(endian + "H", 1)),
        (33421, 3, 2, struct.pack(endian + "2H", 2, 2)),
        (33422, 1, 4, bytes(cfa)),
        (50717, 4, 1, struct.pack(endian + "I", white_level)),
    ]
    if sample_format is not None:
        raw_entries.append((339, 3, 1, struct.pack(endian + "H", sample_format)))
    if cfa_layout is not None:
        raw_entries.append((50711, 3, 1, struct.pack(endian + "H", cfa_layout)))
    if omit_black_repeat_dim:
        raw_entries.append((50714, 5, 1, rat(black_levels[0], 1)))
    else:
        raw_entries.extend([
            (50713, 3, 2, struct.pack(endian + "2H", 2, 2)),
            (50714, 5, 4, b"".join(rat(b, 1) for b in black_levels)),
        ])

    exif_entries = [
        (33434, 5, 1, rat(exp_num, 1_000_000)),
        (34855, 3, 1, struct.pack(endian + "H", iso)),
        (37386, 5, 1, rat(round(focal_mm * 100), 100)),
    ]
    meta_start = pixel_offset + len(pixel_bytes)

    if ifd0_cfa_with_thumb_subifd:
        thumb_entries = [
            (254, 4, 1, struct.pack(endian + "I", 1)),
            (256, 4, 1, struct.pack(endian + "I", 160)),
            (257, 4, 1, struct.pack(endian + "I", 120)),
            (259, 3, 1, struct.pack(endian + "H", 7)),
            (262, 3, 1, struct.pack(endian + "H", 2)),
        ]
        thumb_bytes, ifd0_start = _pack_ifd(thumb_entries, meta_start, endian=endian)
        ifd0_entries = raw_entries + exif_entries + [
            (254, 4, 1, struct.pack(endian + "I", 0)),
            (271, 2, 8, b"Nothing\x00"),
            (272, 2, 5, b"A001\x00"),
            (274, 3, 1, struct.pack(endian + "H", orientation)),
            (330, 4, 1, struct.pack(endian + "I", meta_start)),
        ]
        ifd0_bytes, _ = _pack_ifd(ifd0_entries, ifd0_start, endian=endian)
        header = (b"II" if endian == "<" else b"MM") + struct.pack(endian + "HI", 42, ifd0_start)
        return header + b"\x00" * (pixel_offset - len(header)) + pixel_bytes + thumb_bytes + ifd0_bytes

    if not use_subifd:
        all_entries = raw_entries + exif_entries + [
            (271, 2, 8, b"Nothing\x00"),
            (272, 2, 5, b"A001\x00"),
            (274, 3, 1, struct.pack(endian + "H", orientation)),
        ]
        ifd0_bytes, _ = _pack_ifd(all_entries, meta_start, endian=endian)
        header = (b"II" if endian == "<" else b"MM") + struct.pack(endian + "HI", 42, meta_start)
        return header + b"\x00" * (pixel_offset - len(header)) + pixel_bytes + ifd0_bytes

    # SubIFD layout with realistic conflicting thumbnail storage tags in IFD0.
    sub_entries = raw_entries + [(254, 4, 1, struct.pack(endian + "I", 0))]
    sub_bytes, exif_start = _pack_ifd(sub_entries, meta_start, endian=endian)
    exif_bytes, ifd0_start = _pack_ifd(exif_entries, exif_start, endian=endian)
    ifd0_entries = [
        (254, 4, 1, struct.pack(endian + "I", 1)),
        (256, 4, 1, struct.pack(endian + "I", 256)),
        (257, 4, 1, struct.pack(endian + "I", 192)),
        (258, 3, 3, struct.pack(endian + "3H", 8, 8, 8)),
        (259, 3, 1, struct.pack(endian + "H", 7)),
        (262, 3, 1, struct.pack(endian + "H", 6)),
        (271, 2, 8, b"Nothing\x00"),
        (272, 2, 5, b"A001\x00"),
        (273, 4, 1, struct.pack(endian + "I", 128)),
        (274, 3, 1, struct.pack(endian + "H", orientation)),
        (279, 4, 1, struct.pack(endian + "I", 64)),
        (330, 4, 1, struct.pack(endian + "I", meta_start)),
        (34665, 4, 1, struct.pack(endian + "I", exif_start)),
    ]
    ifd0_bytes, _ = _pack_ifd(ifd0_entries, ifd0_start, endian=endian)
    header = (b"II" if endian == "<" else b"MM") + struct.pack(endian + "HI", 42, ifd0_start)
    return header + b"\x00" * (pixel_offset - len(header)) + pixel_bytes + sub_bytes + exif_bytes + ifd0_bytes


def synthesize_modulated_frame(
    width: int,
    height: int,
    screen_roi: tuple[int, int, int, int],
    *,
    freq_hz: float,
    mod_amp: float,
    exposure_us: float,
    dc_per_156us: float = 300.0,
    black: int = 64,
    row_pitch_us: float = 13.0,
    noise_std: float = 0.25,
    seed: int = 0,
) -> np.ndarray:
    """Synthesize uint16 CFA frame with rectangular-integrated sinusoid on screen ROI."""
    rng = np.random.default_rng(seed)
    raw = np.full((height, width), black, dtype=np.float64) + rng.normal(0.0, noise_std, (height, width))
    x0, y0, x1, y1 = screen_roi
    dc = dc_per_156us * (exposure_us / 156.0)
    t_s = exposure_us * 1e-6
    sinc_val = r113_verify.response(freq_hz * t_s)
    rows = np.arange(y0, y1, dtype=np.float64)[:, None]
    times_s = rows * (row_pitch_us * 1e-6)
    signal = dc * (1.0 + mod_amp * sinc_val * np.cos(2.0 * math.pi * freq_hz * times_s + 0.35))
    raw[y0:y1, x0:x1] = black + signal + rng.normal(0.0, noise_std, (y1 - y0, x1 - x0))
    return np.clip(np.rint(raw), 0, 1023).astype(np.uint16)


class TestDNGQualify(unittest.TestCase):
    def test_full_size_06x_layouts(self):
        screen_roi = (2200, 400, 2600, 1200)
        dark_roi = (100, 100, 400, 500)
        raw = synthesize_modulated_frame(
            3264, 2448, screen_roi, freq_hz=2160.0, mod_amp=0.25, exposure_us=156.0, seed=1
        )
        for mode, kw in (
            ("single_ifd", {}),
            ("subifd_with_thumb_ifd0", {"use_subifd": True}),
            ("ifd0_cfa_with_thumb_subifd", {"ifd0_cfa_with_thumb_subifd": True}),
        ):
            with self.subTest(mode=mode):
                blob = build_synthetic_dng(raw, focal_mm=1.64, exposure_us=156.0, iso=800, **kw)
                dec_raw, tags = dq.decode_dng_bytes(blob)
                res = dq.analyze_bayer_pair(dec_raw, tags, screen_roi, dark_roi)
                self.assertEqual(res["status"], "QUALIFIED_SINGLE_DNG")
                expected_frac = 0.25 * r113_verify.response(2160.0 * 156e-6)
                for amp in res["combined_preselected"]["h_2160hz"]["g1_g2_fractional_amplitudes"]:
                    self.assertAlmostEqual(amp, expected_frac, places=3)
                for amp in res["combined_preselected"]["h_17071hz_alias"]["g1_g2_fractional_amplitudes"]:
                    self.assertLess(amp, 0.005)

    def test_17071hz_alias_resolved_below_green_nyquist(self):
        screen_roi = (60, 40, 220, 200)
        dark_roi = (10, 40, 50, 200)
        f_alias = 1e6 / 52.0 - 2160.0
        raw = synthesize_modulated_frame(
            256, 256, screen_roi, freq_hz=f_alias, mod_amp=0.30, exposure_us=156.0, noise_std=0.1, seed=2
        )
        blob = build_synthetic_dng(raw, focal_mm=1.64)
        dec_raw, tags = dq.decode_dng_bytes(blob)
        res = dq.analyze_bayer_pair(
            dec_raw, tags, screen_roi, dark_roi, expected_width=256, expected_height=256
        )
        expected_frac = 0.30 * r113_verify.response(f_alias * 156e-6)
        for amp in res["combined_preselected"]["h_17071hz_alias"]["g1_g2_fractional_amplitudes"]:
            self.assertAlmostEqual(amp, expected_frac, places=3)
        for amp in res["combined_preselected"]["h_2160hz"]["g1_g2_fractional_amplitudes"]:
            self.assertLess(amp, 0.005)

    def test_rejects_bad_metadata_cfa_sample_format_and_clipping(self):
        screen_roi = (60, 20, 120, 120)
        dark_roi = (10, 20, 50, 120)
        raw = synthesize_modulated_frame(128, 128, screen_roi, freq_hz=2160.0, mod_amp=0.2, exposure_us=156.0)

        for kwargs in (
            {"focal_mm": 5.56},            # 1x main lens rejected
            {"orientation": 6},            # rotated scan axis rejected
            {"compression": 7},            # compressed DNG rejected
            {"photometric": 2},            # demosaiced RGB rejected
            {"sample_format": 2},          # signed SampleFormat rejected
            {"white_level": 70000},        # WhiteLevel > 65535 rejected
            {"cfa": (1, 1, 0, 2)},         # two greens on same row rejected
            {"cfa_layout": 2},             # non-rectangular CFALayout rejected
        ):
            blob = build_synthetic_dng(raw, **kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(dq.DNGQualificationError):
                r, t = dq.decode_dng_bytes(blob)
                dq.analyze_bayer_pair(r, t, screen_roi, dark_roi, expected_width=128, expected_height=128)

        for y, x, val in ((50, 80, 1023), (50, 81, 1023), (50, 80, 0)):
            bad = raw.copy()
            bad[y, x] = val
            blob = build_synthetic_dng(bad)
            r, t = dq.decode_dng_bytes(blob)
            with self.subTest(clip=(y, x, val)), self.assertRaises(dq.DNGQualificationError):
                dq.analyze_bayer_pair(r, t, screen_roi, dark_roi, expected_width=128, expected_height=128)

        # Oversized ROI for 17 kHz detuning tolerance must mark interval None and fail bracket build.
        tall_raw = synthesize_modulated_frame(128, 320, (60, 10, 120, 310), freq_hz=2160.0, mod_amp=0.2, exposure_us=156.0)
        r, t = dq.decode_dng_bytes(build_synthetic_dng(tall_raw))
        tall_res = dq.analyze_bayer_pair(r, t, (60, 10, 120, 310), (10, 10, 50, 310), expected_width=128, expected_height=320)
        self.assertIsNone(tall_res["combined_preselected"]["h_17071hz_alias"]["diagnostic_combined_interval"])
        self.assertIsNotNone(tall_res["combined_preselected"]["h_2160hz"]["diagnostic_combined_interval"])

    def test_end_to_end_bracket_cli_and_provenance_guards(self):
        screen_roi = (120, 20, 220, 200)
        dark_roi = (10, 20, 90, 200)
        times = {"S": 156.0, "M": 468.0, "L": 676.0}
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            blocks = []
            diag_blocks = []
            for idx, order in enumerate(("SMLS", "SMLS", "SLMS", "SLMS")):
                samples = []
                diag_samples = []
                for step_idx, label in enumerate(order):
                    t_us = times[label]
                    raw = synthesize_modulated_frame(
                        256, 256, screen_roi,
                        freq_hz=2160.0, mod_amp=0.22, exposure_us=t_us,
                        dc_per_156us=150.0, noise_std=0.2, seed=100 + idx * 10 + step_idx,
                    )
                    fname = f"b{idx}_{step_idx}_{label}.dng"
                    fpath = tmp_path / fname
                    fpath.write_bytes(build_synthetic_dng(raw, focal_mm=1.64, exposure_us=t_us, iso=800))
                    q_one = dq.qualify_dng_file(
                        fpath, screen_roi, dark_roi, expected_width=256, expected_height=256
                    )
                    self.assertTrue(q_one["clipping_summary"]["zero_clipping_observed"])
                    iv = q_one["combined_preselected"]["h_2160hz"]["diagnostic_combined_interval"]
                    samples.append({"dng_path": fname, "actual_time_us": [t_us - 0.5, t_us + 0.5], "amplitude": iv})
                    diag_samples.append({"dng_path": fname, "actual_time_us": [t_us - 0.5, t_us + 0.5]})
                blocks.append({"id": f"b{idx}", "order": order, "samples": samples})
                diag_blocks.append({"id": f"b{idx}", "order": order, "samples": diag_samples})

            manifest = {
                "screen_roi": list(screen_roi),
                "dark_roi": list(dark_roi),
                "band_key": "h_2160hz",
                "expected_iso": 800,
                "minimum_fractional_contrast": 0.002,
                "qualification_options": {"expected_width": 256, "expected_height": 256},
                "gates": dict.fromkeys(r113_verify.GATES, True),
                "blocks": blocks,
            }
            mpath = tmp_path / "manifest.json"
            mpath.write_text(json.dumps(manifest), encoding="utf8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = dq.main(["build-bracket", str(mpath), "--verify"])
            self.assertEqual(rc, 0)
            out = json.loads(buf.getvalue())
            self.assertEqual(out["verify_result"]["status"], "CONDITIONAL_COMPONENT_MATCH")
            self.assertEqual(out["verify_result"]["candidate_hz"], 2160)

            # Without externally supplied amplitude bounds, claiming intervals_cover_noise_and_drift=True must fail.
            with self.assertRaises(dq.DNGQualificationError):
                dq.build_bracket_payload({**manifest, "blocks": diag_blocks}, base_dir=tmp_path)

            # Diagnostic-only manifest (gates unverified) must force HOLD and exit code 2.
            diag_gates = {**dict.fromkeys(r113_verify.GATES, True), "intervals_cover_noise_and_drift": False}
            mpath_diag = tmp_path / "manifest_diag.json"
            mpath_diag.write_text(json.dumps({**manifest, "gates": diag_gates, "blocks": diag_blocks}), encoding="utf8")
            buf_diag = io.StringIO()
            with redirect_stdout(buf_diag):
                rc_diag = dq.main(["build-bracket", str(mpath_diag), "--verify"])
            self.assertEqual(rc_diag, 2)
            self.assertEqual(json.loads(buf_diag.getvalue())["verify_result"]["status"], "HOLD")

            # Empty gates must return HOLD and CLI exit code 2.
            mpath_hold = tmp_path / "manifest_hold.json"
            mpath_hold.write_text(json.dumps({**manifest, "gates": {}}), encoding="utf8")
            buf_hold = io.StringIO()
            with redirect_stdout(buf_hold):
                rc_hold = dq.main(["build-bracket", str(mpath_hold), "--verify"])
            self.assertEqual(rc_hold, 2)
            self.assertEqual(json.loads(buf_hold.getvalue())["verify_result"]["status"], "HOLD")

            # Conflicting freq_rel_tol must be rejected.
            bad_tol = json.loads(json.dumps(manifest))
            bad_tol["qualification_options"]["freq_rel_tol"] = 0.0
            with self.assertRaises(dq.DNGQualificationError):
                dq.build_bracket_payload(bad_tol, base_dir=tmp_path)

            # Alias spatial band must report CONDITIONAL_ALIAS_COMPONENT_MATCH, never bare candidate_hz=2160.
            alias_blocks = []
            f_alias = 1e6 / 52.0 - 2160.0
            for idx, order in enumerate(("SMLS", "SMLS", "SLMS", "SLMS")):
                samples = []
                for step_idx, label in enumerate(order):
                    t_us = times[label]
                    raw = synthesize_modulated_frame(
                        256, 256, screen_roi,
                        freq_hz=f_alias, mod_amp=0.45, exposure_us=t_us,
                        dc_per_156us=150.0, noise_std=0.2, seed=200 + idx * 10 + step_idx,
                    )
                    fname = f"alias_b{idx}_{step_idx}_{label}.dng"
                    fpath = tmp_path / fname
                    fpath.write_bytes(build_synthetic_dng(raw, focal_mm=1.64, exposure_us=t_us, iso=800))
                    q_alias = dq.qualify_dng_file(
                        fpath, screen_roi, dark_roi, expected_width=256, expected_height=256
                    )
                    iv_a = q_alias["combined_preselected"]["h_17071hz_alias"]["diagnostic_combined_interval"]
                    samples.append({"dng_path": fname, "actual_time_us": [t_us - 0.5, t_us + 0.5], "amplitude": iv_a})
                alias_blocks.append({"id": f"ab{idx}", "order": order, "samples": samples})
            alias_payload = dq.build_bracket_payload(
                {**manifest, "band_key": "h_17071hz_alias", "blocks": alias_blocks},
                base_dir=tmp_path,
            )
            alias_res = dq.verify_bracket_payload(alias_payload)
            self.assertEqual(alias_res["status"], "CONDITIONAL_ALIAS_COMPONENT_MATCH")
            self.assertNotIn("candidate_hz", alias_res)

            # Duplicate DNG path reuse across blocks must fail qualification.
            dup_manifest = json.loads(json.dumps(manifest))
            dup_manifest["blocks"][1]["samples"][0]["dng_path"] = dup_manifest["blocks"][0]["samples"][0]["dng_path"]
            with self.assertRaises(dq.DNGQualificationError):
                dq.build_bracket_payload(dup_manifest, base_dir=tmp_path)

            # Byte-identical DNG copy under a different filename must fail qualification.
            copy_name = "copy_of_b0_0_S.dng"
            (tmp_path / copy_name).write_bytes((tmp_path / manifest["blocks"][0]["samples"][0]["dng_path"]).read_bytes())
            copy_manifest = json.loads(json.dumps(manifest))
            copy_manifest["blocks"][1]["samples"][0]["dng_path"] = copy_name
            with self.assertRaises(dq.DNGQualificationError):
                dq.build_bracket_payload(copy_manifest, base_dir=tmp_path)

            # Swapped exposure time (unique M=468 us DNG paired as L=676 us) must fail on ExposureTime.
            swap_ml_manifest = json.loads(json.dumps(manifest))
            l_idx = swap_ml_manifest["blocks"][0]["order"].index("L")
            m_unique_raw = synthesize_modulated_frame(
                256, 256, screen_roi, freq_hz=2160.0, mod_amp=0.22, exposure_us=468.0, dc_per_156us=150.0, seed=999
            )
            m_unique = "m_unique_for_l.dng"
            (tmp_path / m_unique).write_bytes(build_synthetic_dng(m_unique_raw, focal_mm=1.64, exposure_us=468.0, iso=800))
            swap_ml_manifest["blocks"][0]["samples"][l_idx]["dng_path"] = m_unique
            with self.assertRaisesRegex(dq.DNGQualificationError, "ExposureTime"):
                dq.build_bracket_payload(swap_ml_manifest, base_dir=tmp_path)

            # Explicit zero exposure tolerance must not be overridden by a hidden floor.
            zero_tol_manifest = json.loads(json.dumps(manifest))
            s_180_raw = synthesize_modulated_frame(
                256, 256, screen_roi, freq_hz=2160.0, mod_amp=0.22, exposure_us=180.0, dc_per_156us=150.0, seed=998
            )
            (tmp_path / "s_180.dng").write_bytes(build_synthetic_dng(s_180_raw, focal_mm=1.64, exposure_us=180.0, iso=800))
            zero_tol_manifest["blocks"][0]["samples"][0]["dng_path"] = "s_180.dng"
            zero_tol_manifest["max_exposure_mismatch_us"] = 0.0
            zero_tol_manifest["max_exposure_mismatch_rel"] = 0.0
            with self.assertRaisesRegex(dq.DNGQualificationError, "ExposureTime"):
                dq.build_bracket_payload(zero_tol_manifest, base_dir=tmp_path)

            # Non-finite exposure tolerance must fail closed before comparing frames.
            for bad_field in ("max_exposure_mismatch_us", "max_exposure_mismatch_rel"):
                inf_manifest = json.loads(json.dumps(manifest))
                inf_manifest[bad_field] = float("inf")
                with self.assertRaisesRegex(dq.DNGQualificationError, "non-finite"):
                    dq.build_bracket_payload(inf_manifest, base_dir=tmp_path)

            # ISO drift in one frame must fail qualification.
            bad_raw = synthesize_modulated_frame(256, 256, screen_roi, freq_hz=2160.0, mod_amp=0.22, exposure_us=156.0)
            (tmp_path / "b0_0_S.dng").write_bytes(build_synthetic_dng(bad_raw, focal_mm=1.64, exposure_us=156.0, iso=1600))
            with self.assertRaises(dq.DNGQualificationError):
                dq.build_bracket_payload(manifest, base_dir=tmp_path)

    def test_scalar_black_level_and_cli(self):
        screen_roi = (2200, 400, 2600, 1200)
        dark_roi = (100, 100, 400, 500)
        raw = synthesize_modulated_frame(3264, 2448, screen_roi, freq_hz=2160.0, mod_amp=0.20, exposure_us=156.0)
        blob = build_synthetic_dng(raw, focal_mm=1.64, exposure_us=156.0, iso=800, omit_black_repeat_dim=True)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "scalar.dng"
            p.write_bytes(blob)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = dq.main([
                    "qualify-one", str(p),
                    "--screen-roi", "2200,400,2600,1200",
                    "--dark-roi", "100,100,400,500",
                ])
            self.assertEqual(rc, 0)
            out = json.loads(buf.getvalue())
            self.assertEqual(out["status"], "QUALIFIED_SINGLE_DNG")
            self.assertEqual(out["metadata"]["black_levels"], [64.0, 64.0, 64.0, 64.0])


if __name__ == "__main__":
    unittest.main()
