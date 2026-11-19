# Causal DDIC Round 3 & `23:A9[7]` Multi-Exposure Sweep (`0.6×` DNG, `2026-11-19`)

## 1. Purpose and Setup

At fixed `DBV 3600`, `panelDC = 0`, `120 Hz`, `#FFFFFF` (`HTMLViewer`), this round tested three candidate register groups from `dc-off-command ↔ dc-on-command` / `s1 ↔ s2` (`selected_boe_v4` / `ddic_regdump_20261107`), followed by a `10×` exposure sweep (`250–2500 µs`) on `23:A9 = 0x8e` to check whether its suppression of `[±2, ∓1]` persists across exposure durations rather than being a single-exposure `625 µs` `sinc` null:

- **Panel / Target:** Lenovo XT2611-1/PVT (`W3WWS36.65-64-4-1`), BOE `ILI97701A cmd_v4` (`ID 0xd2`), guarded `unshare -m` debugfs DSI session with `esd_check_mode` restored to `reg_read` in the `EXIT` trap.
- **Observer:** Nothing A001 (`Camera ID: 2`, `EXPERT 0.6×`, `RAW ON`, `3264×2448` DNG, `ISO 6400`, reference DNG `IMG_20260502_083009182.DNG` at `DBV 6879`, `625 µs`).
- **Reproducible spec & output (`30` DNGs, 3 per phase):** [spec_round3_20261119.json](spec_round3_20261119.json) and [summary_round3_20261119.json](summary_round3_20261119.json), reproduced directly via `analyze_2d_modulation.py --evidence-dir <dir> --spec-json spec_round3_20261119.json --out-json summary_round3_20261119.json`.
- **Frame classification rule:** non-notch frames are defined as `frac_lt_065 < 0.05`, notch-intersecting frames as `frac_lt_065 >= 0.05`.

## 2. Live `DBV 3600` Readback & Candidate Probes

Under `DBV 3600`, `panelDC = 0`, `#FFFFFF`, `120 Hz` before any write:

- `23:C1 (3B)` = `0x00 0x00 0x60` (`96`)
- `23:C2 / C3 / C4 (3B)` = `0x00 0x03 0x84` (`900`; `1B` reads returned `0x00`)
- `4F:9D (1B)` = `0x3e`, `4F:9E (1B)` = `0x64`
- `4F:81 (1B)` = `0x10`, `23:A9 (1B)` = `0x0e`
- Under bank enable `53:F0 = 0x01` (then restored `53:F0 = 0x00`):
  - `63:F1` = `10 10 10 10 10 00 00 00 00 00 00 00 00 00 00 00`
  - `63:F2` = `10 10 10 10 10 00 00 00 00 00 00 00 00 00 00 00`
  - `63:F3` = `00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00`
  - `63:F4` = `00 00 00 00 00 f0 f0 f0 f0 f0 00 00 00 00 00 00`

Candidate outcomes (distinguishing register readback from optical behavior):

1. **`63:F2 / 63:F3` (`53:F0 01 → 00`) — register writes confirmed on readback; diagonal `[±2, ∓1]` wave persisted at `625 µs`:**
   - Wrote vendor `dc-on` pattern (`63:F2 = 00*5 20*5 00*6`, `63:F3 = 00*16`), then vendor `dc-off` pattern (`63:F2 = 00*16`, `63:F3 = 00*5 20*5 00*6`), then restored live `DBV 3600` baseline (`63:F2 = 10*5 00*11`, `63:F3 = 00*16`). Every write was verified on immediate DSI readback.
   - Non-notch `F(-2,+1)` at single exposure `625 µs`:
     - `base` (`2/3` non-notch): `0.0988–0.1005` (`raw_mean_dn` `8.6506–8.7047`)
     - `f2f3_dcon` (`2/3` non-notch): `0.0776–0.0795` (`raw_mean_dn` `8.5560–8.7008`)
     - `f2f3_dcoff` (`1/3` non-notch): `0.1174` (`raw_mean_dn` `8.4567`)
     - `f2f3_restore` (`3/3` non-notch): `0.0906–0.0982` (`raw_mean_dn` `8.2972–8.6558`)
   - Note: in `f2f3_dcon`, the non-notch `F(-2,+1)` range (`0.0776–0.0795`) lies below this round's `base` (`0.0988–0.1005`) and `f2f3_restore` (`0.0906–0.0982`), while overlapping the wider `DBV 3600 OFF` `625 µs` spread seen in Round 2 (`0.0772–0.1168`); frame 3 (`IMG_20260502_103041781.DNG`) still peaks at `[2, -1]` (`0.0795`). Because `63:F2/F3` was tested at a single exposure (`625 µs`), a single exposure cannot separate subtle frequency vs depth changes on its own, though it did not collapse the `[±2, ∓1]` mode. Notch-intersecting frames also persisted (`frac_lt_065` `0.1076–0.1493`).

2. **`23:C2` (`00 03 84`) and `4F:9D / 4F:9E` (`0x3e / 0x64`) — no DSI readback change observed:**
   - Writing `23:C2 = 0x00 0x07 0x08` (`1800`) produced no change on subsequent DSI readback under these conditions (`23:C2` stayed `0x00 0x03 0x84`, `23:C1` stayed `0x00 0x00 0x60`).
   - Writing `4F:9D = 0x3e` and `4F:9E = 0x7d` left DSI readback at `4F:9D = 0x3e`, `4F:9E = 0x64`. For `4F:9E`, the new value `0x7d` did not take effect on readback under these conditions; for `4F:9D`, the written byte `0x3e` matched its initial baseline, so `4F:9D` writability was not tested.

## 3. Coupled `23:C1` Telemetry & `10×` Exposure Sweep on `23:A9` (`0x0e → 0x8e → 0x0e`)

Writing `23:A9 = 0x8e` at `DBV 3600`, `panelDC = 0`, `120 Hz` immediately changed `23:C1` readback from `0x00 0x00 0x60` (`96`) to `0x00 0x00 0x10` (`16`), while `4F:9D/9E` (`0x3e/0x64`) and `63:F2/F3` stayed unchanged. Restoring `23:A9 = 0x0e` immediately restored `23:C1` back to `0x00 0x00 0x60`.

| Phase (`23:A9`) | `T_exp` (`µs`) | `23:C1` | Non-notch (`frac_lt_065 < 0.05`) | Non-notch `F(-2,+1)` | Phase-mean `raw_mean_dn` | Mean `DN / µs` | Phase-mean `binned_std` |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: |
| `base` (`0x0e`) | `625` | `00 00 60` | `2/3` | `0.0988–0.1005` | `8.6776` | `0.01388` | `0.1537` |
| `a9_8e_250us` (`0x8e`) | `250` | `00 00 10` | `2/3` | `0.0125–0.0147` | `3.7637` | `0.01505` | `0.1789` |
| `a9_8e_625us` (`0x8e`) | `625` | `00 00 10` | `1/3` | `0.0143` | `9.2534` | `0.01481` | `0.1106` |
| `a9_8e_800us` (`0x8e`) | `800` | `00 00 10` | `3/3` | `0.0093–0.0159` | `11.5050` | `0.01438` | `0.1181` |
| `a9_8e_1000us` (`0x8e`) | `1000` | `00 00 10` | `2/3` | `0.0060–0.0197` | `14.5234` | `0.01452` | `0.0975` |
| `a9_8e_2500us` (`0x8e`) | `2500` | `00 00 10` | `3/3` | `0.0088–0.0212` | `36.6517` | `0.01466` | `0.0913` |
| `a9_restore_625us` (`0x0e`) | `625` | `00 00 60` | `2/3` | `0.0801–0.1090` | `8.5533` | `0.01369` | `0.1578` |

Within `a9_8e_*` (`15` DNGs total), `11/15` frames were non-notch (`frac_lt_065` `0.0000–0.0278`) and `4/15` frames intersected the dark dip (`IMG_20260502_103434737.DNG`: `0.1875`, `103439042`: `0.1458`, `103521378`: `0.1250`, `103551616`: `0.0590`). All phase means and `DN / µs` values in the table above are computed over non-notch frames only (`frac_lt_065 < 0.05`).

Observed behavior from this sweep:

1. **Broad-exposure suppression of the `[±2, ∓1]` diagonal component:** Across all `11/15` non-notch frames spanning `250–2500 µs` (`10×` exposure span), `F(-2,+1)` remains `0.0060–0.0212`. This rules out suppression being caused by a single `sinc` zero near `625 µs`, and non-notch phase-mean `binned_std` generally decreases from `0.1789` (`250 µs`) to `0.0913` (`2500 µs`, with a slight rise from `0.1106` at `625 µs` to `0.1181` at `800 µs`; phase-mean product `mean(binned_std) * sqrt(mean(raw_mean_dn))` is `0.3364–0.4005` over `250–1000 µs` and `0.5529` at `2500 µs`). Because `250 µs` corresponds to a first `sinc` integration zero at `4 kHz` and no calibrated fast optical probe was attached, this rolling-shutter DNG set does not measure absolute modulation depth (%) in the time domain, prove waveform shape, or verify interaction with `panelDC = 1` (since `panelDC` was fixed at `0`).
2. **Dark refresh/EM dip persists and uncalibrated camera signal shifts slightly:** The `~120 Hz` narrow dark dip remains present (`4/15` frames in `a9_8e_*`, `frac_lt_065 = 0.0590–0.1875`). At matched `625 µs`, uncalibrated non-notch camera signal (`DN / µs`) is `+6.6%` higher under `23:A9 = 0x8e` (`0.01481`) than `base` (`0.01388`) and `+8.2%` higher than `a9_restore_625us` (`0.01369`).
3. **Full reversibility:** Restoring `23:A9 = 0x0e` immediately restores `23:C1 = 0x00 0x00 0x60` and the `[±2, ∓1]` diagonal wave (`F(-2,+1) = 0.0801–0.1090`).

## 4. Verification and Next Step

- **Bench restore verified after capture:** `Lenovo` (`BL = 6873`, `screen_brightness = 105`, `panelDC = 0`, `120 Hz`, `ZRamSettingsActivity`, `INIT_ESD = reg_read`, DDIC regs restored to baseline) and `A001` (`1×`, `RAW OFF`, `OpenCamera Device 0`, `exposureTime = 100000 ns`, `sensitivity = 6400`, `focusDistance = 0.58822089`).
- **Verification commands run after final edits:** CLI check of `analyze_2d_modulation.py` on `spec_round3_20261119.json` (`EXIT=0`) and `python3 -B` / `python3 -OB -m unittest discover -v` in [pwm_06x_dng_bench_20261119](../pwm_06x_dng_bench_20261119/) (`7/7` pass).
- **Next step:** Measure calibrated optical waveforms and absolute modulation depth (%) under `23:A9 = 0x8e ↔ 0x0e` at fixed `DBV 3600` (`panelDC = 0`) using a DC-coupled photodiode + oscilloscope, and check whether intermediate `23:A9` bit combinations modulate `23:C1` or emission duty between `0x60` and `0x10`.
