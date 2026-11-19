# Causal DDIC Round 6: `DBV 128–256` Floor Check & `53:A2` + `23:A9 = 0x8e` Combination (`0.6×` DNG, `2026-11-19`)

## 1. Purpose and Setup

Building on Round 5 (`DBV 512–1024` under `23:A9 = 0x8e`), this round tested:
1. Whether dropping `DBV` all the way down to `256` and `128` under `23:A9 = 0x8e` (`panelDC = 0`) breaks below `3.74 DN` toward `DBV 2048` (`0x0e`) signal (`2.4800 DN`), or plateaus.
2. What paired `DBV 256` (`23:A9 = 0x0e`) reads in `23:C1` and `0.6×` DNG.
3. Whether adding the `30B` `53:A2` `DC ON` LUT (`...74 7b b4`) alongside `23:A9 = 0x8e` at `DBV 2048` lowers camera signal relative to `23:A9 = 0x8e` alone (`7.2879 DN` `< 0.05` in Round 4).

- **Target & Observer:** Lenovo XT2611-1/PVT (`W3WWS36.65-64-4-1`, BOE `ILI97701A cmd_v4`), Nothing A001 (`Camera ID: 2`, `EXPERT 0.6×`, `RAW ON`, `ISO 6400`, fixed `625 µs` exposure, reference `IMG_20260502_083009182.DNG`), `#FFFFFF` (`HTMLViewer`), `panelDC = 0`, `120 Hz`, `esd_check_mode = reg_read`.
- **Reproducible spec & summary (`18` DNGs, 3 per phase):** [spec_round6_20261119.json](spec_round6_20261119.json) and [summary_round6_20261119.json](summary_round6_20261119.json), verified via `analyze_2d_modulation.py --evidence-dir <dir> --spec-json spec_round6_20261119.json --out-json summary_round6_20261119.json` (`EXIT=0`).
- **Frame classification rule & scope:** Low-dip frames are `frac_lt_065 < 0.05`. All Round 6 DNGs were acquired at a single `625 µs` exposure, so frequency vs depth cannot be separated from exposure scaling in this dataset alone.

## 2. Pre-Shot DDIC Readbacks & Optical Results (`625 µs`)

| Phase (`DBV`, `23:A9`, `53:A2`) | Read `23:A9` / `23:C1` / `53:A2[-3:]` | Frames (`< 0.05`) | `F(-2,+1)` (all frames) | `F(-2,+1)` (`< 0.05`) | Mean `raw_mean_dn` (all) | Mean `DN / µs` (all) | Mean `raw_mean_dn` (`< 0.05`) | Mean `DN / µs` (`< 0.05`) |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `dbv2048_0e_off_base` (`2048`, `0x0e`, `off`) | `0x0e` / `00 02 26 (550)` / `10 4b 4b` | `0/3` | `0.6310–0.6971` (mean `0.6701`) | `—` | `2.4800` | `0.00397` | `—` | `—` |
| `dbv256_8e_off` (`256`, `0x8e`, `off`) | `0x8e` / `00 00 10 (16)` / `10 4b 4b` | `2/3` | `0.0130–0.0264` (mean `0.0197`) | `0.0130–0.0264` | `3.9233` | `0.00628` | `4.0440` | `0.00647` |
| `dbv128_8e_off` (`128`, `0x8e`, `off`) | `0x8e` / `00 00 10 (16)` / `10 4b 4b` | `3/3` | `0.0208–0.0256` (mean `0.0237`) | `0.0208–0.0256` | `3.8606` | `0.00618` | `3.8606` | `0.00618` |
| `dbv256_0e_off_base` (`256`, `0x0e`, `off`) | `0x0e` / `00 02 c0 (704)` / `10 4b 4b` | `0/3` | `0.4035–0.6112` (mean `0.5376`) | `—` | `0.6730` | `0.00108` | `—` | `—` |
| `dbv2048_8e_a2on` (`2048`, `0x8e`, `on`) | `0x8e` / `00 00 10 (16)` / `74 7b b4` | `2/3` | `0.0051–0.0698` (mean `0.0321`) | `0.0051–0.0213` | `7.0574` | `0.01129` | `7.3066` | `0.01169` |
| `dbv2048_0e_off_ret` (`2048`, `0x0e`, `off`) | `0x0e` / `00 02 26 (550)` / `10 4b 4b` | `0/3` | `0.6682–0.7063` (mean `0.6850`) | `—` | `2.5902` | `0.00414` | `—` | `—` |

Outliers/dips: in `dbv256_8e_off`, `IMG_20260502_115615378.DNG` had `frac_lt_065 = 0.0660` (`binned_min = 0.2328`, `raw_mean_dn = 3.6819`, `F(-2,+1) = 0.0197`); in `dbv128_8e_off`, `IMG_20260502_115625368.DNG` passed `< 0.05` (`frac_lt_065 = 0.0486`, `F(-2,+1) = 0.0247`) yet showed `binned_min = 0.1952` and slightly reduced `raw_mean_dn = 3.6358` (vs `0.4325–0.5038` and `3.9441–4.0019` in the other two frames); and in `dbv2048_8e_a2on`, `115653364.DNG` had `frac_lt_065 = 0.0833` (`binned_min = 0.3574`, `raw_mean_dn = 6.5590`, `F(-2,+1) = 0.0698`). Note also at `DBV 256` (`0x0e`), `115643605.DNG` reached `raw_mean_dn = 0.4072` (`peak_2d_k = [1, 0]`, `F(-2,+1) = 0.4035`), lowering the phase mean of `F(-2,+1)` relative to `DBV 2048`.

Key findings:

1. **Signal remains in the `3.86–4.04 DN` band at `DBV 256` and `128` under `23:A9 = 0x8e`, `panelDC = 0`:** Extending Round 5 (`DBV 512`: `3.7438 DN` all-frame, `3.9978 DN` `< 0.05`, separate session with `1/3` deep dip `lt065 = 0.2431`) to `DBV 256` and `128` (`max lt065 = 0.0660` here) kept camera signal nearly flat in the `3.86–4.04 DN` band: `3.9233 DN` all-frame (`4.0440 DN` `< 0.05`) at `DBV 256`, and `3.8606 DN` (`3/3` `< 0.05`) at `DBV 128`, remaining `1.56×` (`DBV 128`) above `dbv2048_0e_off_base` (`2.4800 DN`) and `5.83×` above paired `dbv256_0e_off_base` (`3.9233 / 0.6730`), without dropping toward `2.48 DN` (`DBV < 128` was not tested). At matched `DBV 256` (`0x0e → 0x8e`), `23:C1` dropped `704 → 16` and all-frame mean `F(-2,+1)` fell `27.3×` (`0.5376 → 0.0197`).
2. **Adding `53:A2` (`DC ON` LUT) alongside `23:A9 = 0x8e` did not reduce `DBV 2048` camera signal toward `2.48 DN`:** In this write order at `DBV 2048`, adding `53:A2 = DC ON` (`...74 7b b4`) yielded `7.3066 DN` (`0.01169 DN/µs`) on `< 0.05` frames (`2/3`, `F(-2,+1) = 0.0051–0.0213`) vs `7.2879 DN` in Round 4 (`0.26%` cross-session difference), and `7.0574 DN` all-frame vs `6.3793 DN` in Round 4 (reflecting `1/3` vs `2/3` dip-frame counts). Whether `53:A2` interacts with another register or a subsequent `DBV` rewrite was not tested.
3. **Full reversibility:** Returning to `DBV 2048`, `23:A9 = 0x0e`, `53:A2 = off` restored `23:C1 = 00 02 26`, `53:A2[-3:] = 10 4b 4b`, strong `[±2, ∓1]` (`0.6682–0.7063`, mean `0.6850`), and `2.5902 DN` (`0.00414 DN/µs`).

## 3. Verification and Next Step

- **Both phones restored and verified:** `Lenovo` (`BL = 6873`, `screen_brightness = 105`, `panelDC = 0`, `120 Hz`, `ZRamSettingsActivity`, `esd_check_mode = reg_read`, `23:A9 = 0x0e` / `23:C1 = 00 00 60` / `53:A2[-3:] = 10 4b 4b` at `3600` before restore `105`) and `A001` (`1×`, `RAW OFF`, `OpenCamera Device 0`, `exposureTime = 100000 ns`, `sensitivity = 6400`, `focusDistance = 0.58822089`).
- **Verification commands after final edits:** `analyze_2d_modulation.py` CLI check on `spec_round6_20261119.json` (`EXIT=0`) and `python3 -B` / `python3 -OB -m unittest discover -v` in [pwm_06x_dng_bench_20261119](../pwm_06x_dng_bench_20261119/) (`7/7` pass).
- **Next step:** Inspect `DBV 2048` under stock Android `panelDC = 1` (plus `51:A1/A2`, `52:81/82`, `23:80`, `53:95` readbacks and `0.6×` DNGs, allowing for the 2–3 minute `panelDC` off-hysteresis at cleanup) to see whether stock `DC ON` achieves low brightness via remaining `dc-on` registers (`51:A1/A2`, `52:81/82`, `23:80`, `53:95`) or framework/PAM LUT scaling.
