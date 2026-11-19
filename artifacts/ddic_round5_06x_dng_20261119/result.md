# Causal DDIC Round 5: `23:A9` `0x88..0x8f` `A-B-A` Probe, DBV Persistence, and `DBV 512–1024` Behavior (`0.6×` DNG, `2026-11-19`)

## 1. Purpose and Setup

Building on Round 4, this round tested:
1. `A-B-A` readback probing of `23:A9 = 0x88..0x8f` (varying `[2:0]` with `bit 7 = 1, bit 3 = 1, [6:4] = 0`) against `23:C1` at `DBV 3600`, testing `0x8a` vs `0x8e`.
2. Whether sysfs `DBV` writes (`1500 → 1024 → 800 → 512`) reset `23:A9 = 0x8e`, and whether `53:A2` (`30B`) differs between `DBV 3600` and `DBV 2048` under `panelDC = 0`.
3. Whether lowering `DBV` (`1024 / 680 / 512`) under `23:A9 = 0x8e` brings uncalibrated camera signal down to `DBV 2048` (`0x0e`) baseline (`2.3311 DN` at `625 µs`) without restoring `[±2, ∓1]`.

- **Target & Observer:** Lenovo XT2611-1/PVT (`W3WWS36.65-64-4-1`, BOE `ILI97701A cmd_v4`), Nothing A001 (`Camera ID: 2`, `EXPERT 0.6×`, `RAW ON`, `ISO 6400`, fixed `625 µs` exposure, reference `IMG_20260502_083009182.DNG`), `#FFFFFF` (`HTMLViewer`), `panelDC = 0`, `120 Hz`, `esd_check_mode = reg_read`.
- **Reproducible spec & summary (`18` DNGs, 3 per phase):** [spec_round5_20261119.json](spec_round5_20261119.json) and [summary_round5_20261119.json](summary_round5_20261119.json), verified via `analyze_2d_modulation.py --evidence-dir <dir> --spec-json spec_round5_20261119.json --out-json summary_round5_20261119.json` (`EXIT=0`).
- **Frame classification rule & scope:** Low-dip frames are `frac_lt_065 < 0.05`. At `DBV 2048` (`0x0e`) and `DBV 1024` (`0x0e`), `[±2, ∓1]` modulation crosses below `0.65` in all frames (`frac_lt_065 = 0.3507–0.4688`), so `0/3` pass `< 0.05`. All Round 5 DNGs were acquired at a single exposure (`625 µs`), so frequency vs depth cannot be separated from exposure scaling in this dataset alone.

## 2. DDIC Readback Probes (`23:A9` `A-B-A`, `DBV` Write Persistence, `53:A2`)

1. **Probed `23:A9 = 0x88..0x8f` (`A-B-A` with `0x0e` between every step, `250 ms` initial settle after `BL 6873 → 3600`, `100 ms` per write):**
   - Writing `23:A9 = 0x88 / 0x89 / 0x8a / 0x8b / 0x8c / 0x8d` latched each byte on readback while keeping `23:C1 = 0x00 0x00 0x60` (`96`).
   - Writing `23:A9 = 0x8e / 0x8f` switched `23:C1` to `0x00 0x00 0x10` (`16`), and returning to `0x0e` restored `0x00 0x00 0x60`. Thus in `0x88..0x8f` (`bit 7 = 1`, `bit 3 = 1`, `[6:4] = 0`), `23:C1 = 16` occurred only for `0x8e` and `0x8f`, and bit 0 did not affect the outcome. Combined with Round 4 (`0x80 / 0x86` stayed `96`, while `0x8e / 0x9e / 0xae / 0xbe` flipped to `16`), among all combinations tested so far with `[6:4] = 0` only `[3:1] == 0b111` + `bit 7 = 1` triggered `16`; combinations with `[6:4] != 0` and `[3:1] != 0b111` (e.g., `0xa8..0xad`) were not tested.
   - An earlier un-settled burst started right after `6873 → 3600` (`40 ms` step without `0x0e` resets between `0x8a..0x8e`) read stale `23:C1 = 00 00 10` across all writes; because both settle delay and `0x0e` resets changed together in the clean `A-B-A` run, those two factors are not separately isolated.
2. **Persistence across `DBV` writes & `53:A2` (`panelDC = 0`):**
   - After setting `23:A9 = 0x8e` at `DBV 2048`, subsequent sysfs writes `1500 → 1024 → 800 → 512` to `brightness` did not reset `23:A9` (`0x8e` retained, `23:C1 = 00 00 10`). Immediate pre-shot readbacks at `DBV 1024`, `680`, and `512` also all confirmed `R_A9 = 0x8e` and `R_C1 = 0x00 0x00 0x10`.
   - Readback of `53:A2 (30B)` was identical at `DBV 3600` and `DBV 2048` (`0x10 0x10 0x10 0x10 0x48 0x10 0x10 0x10 0x4b 0x4b` repeated ×3).

## 3. Optical DNG Results at `625 µs` (`DBV 512–2048`)

| Phase (`DBV`, `23:A9`) | `23:C1` | Frames (`frac_lt_065 < 0.05`) | `F(-2,+1)` (all frames) | `F(-2,+1)` (`< 0.05`) | Mean `raw_mean_dn` (all) | Mean `DN / µs` (all) | Mean `raw_mean_dn` (`< 0.05`) | Mean `DN / µs` (`< 0.05`) |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `dbv2048_0e_base` (`2048`, `0x0e`) | `00 02 26` | `0/3` | `0.6370–0.7157` (mean `0.6825`) | `—` | `2.3311` | `0.00373` | `—` | `—` |
| `dbv1024_8e` (`1024`, `0x8e`) | `00 00 10` | `2/3` | `0.0208–0.1322` (mean `0.0593`) | `0.0208–0.0250` | `4.5882` | `0.00734` | `4.9537` | `0.00793` |
| `dbv680_8e` (`680`, `0x8e`) | `00 00 10` | `2/3` | `0.0136–0.1490` (mean `0.0628`) | `0.0136–0.0259` | `3.9617` | `0.00634` | `4.2810` | `0.00685` |
| `dbv512_8e` (`512`, `0x8e`) | `00 00 10` | `2/3` | `0.0329–0.1470` (mean `0.0755`) | `0.0329–0.0465` | `3.7438` | `0.00599` | `3.9978` | `0.00640` |
| `dbv1024_0e_base` (`1024`, `0x0e`) | `00 02 ac` | `0/3` | `0.6294–0.6792` (mean `0.6565`) | `—` | `0.9707` | `0.00155` | `—` | `—` |
| `dbv2048_0e_ret` (`2048`, `0x0e`) | `00 02 26` | `0/3` | `0.6158–0.6458` (mean `0.6259`) | `—` | `2.5249` | `0.00404` | `—` | `—` |

In `dbv1024_8e`, `dbv680_8e`, and `dbv512_8e`, exactly `1/3` frame per phase (`IMG_20260502_112141073.DNG`, `112150386.DNG`, `112159734.DNG`) intersected the narrow dark dip (`frac_lt_065 = 0.2083 / 0.2188 / 0.2431`).

Key findings:

1. **Low `[±2, ∓1]` under `23:A9 = 0x8e` at `DBV 1024 / 680 / 512`:** At matched `DBV 1024` (`625 µs`), switching `0x0e → 0x8e` reduced all-frame mean `F(-2,+1)` by `11.1×` (`0.6565 → 0.0593`; `< 0.05` frames `0.0208–0.0250`). Low `[±2, ∓1]` persisted under `23:A9 = 0x8e` at `DBV 680` (all-frame mean `0.0628`, `< 0.05` `0.0136–0.0259`) and `DBV 512` (all-frame mean `0.0755`, `< 0.05` `0.0329–0.0465`); paired `0x0e` baselines were not acquired at `680` or `512`.
2. **Gentle DBV-driven signal drop (`-18.4%` all-frame, `-19.3%` `< 0.05`) without reaching `DBV 2048` `0x0e`:** While `DBV 2048 → 1024` under `0x0e` reduced all-frame camera signal by `58.4%` (`2.3311 → 0.9707 DN`), halving DBV from `1024` to `512` under `23:A9 = 0x8e` decreased signal at every step (`4.5882 → 3.9617 → 3.7438 DN` all-frame, `-18.4%`; `4.9537 → 4.2810 → 3.9978 DN` `< 0.05`, `-19.3%`). A lower brightness floor is not established because signal kept falling down to `DBV 512`, though even `DBV 512` (`0x8e`, `3.7438 DN`) stayed `1.61×` brighter than `DBV 2048` `0x0e` (`2.3311 DN`) and `3.86×` brighter than `DBV 1024` `0x0e` (`0.9707 DN`), while at matched `DBV 1024` (`0x8e` vs `0x0e`) signal was `4.73×` higher (`4.5882 / 0.9707`). Compression of an analog/PAM curve below `DBV 1024` under `panelDC = 0` remains a hypothesis (internal PAM current was not measured).
3. **Reversibility:** Returning to `DBV 2048`, `23:A9 = 0x0e` restored `23:C1 = 00 02 26`, strong `[±2, ∓1]` (`0.6158–0.6458`, mean `0.6259`), and `2.5249 DN` all-frame camera signal (`0.00404 DN/µs`).

## 4. Verification and Next Step

- **Both phones restored and verified:** `Lenovo` (`BL = 6873`, `screen_brightness = 105`, `panelDC = 0`, `120 Hz`, `ZRamSettingsActivity`, `esd_check_mode = reg_read`, `23:A9 = 0x0e` / `23:C1 = 00 00 60` at `3600` before restore `105`) and `A001` (`1×`, `RAW OFF`, `OpenCamera Device 0`, `exposureTime = 100000 ns`, `sensitivity = 6400`, `focusDistance = 0.58822089`).
- **Verification commands after final edits:** `analyze_2d_modulation.py` CLI check on `spec_round5_20261119.json` (`EXIT=0`) and `python3 -B` / `python3 -OB -m unittest discover -v` in [pwm_06x_dng_bench_20261119](../pwm_06x_dng_bench_20261119/) (`7/7` pass).
- **Next step:** Test `DBV < 512` (`256 / 128`) and/or applying `53:A2` (`DC ON` LUT) + `23:A9 = 0x8e` vs stock `panelDC = 1` at `DBV 2048` (accounting for the 2–3 minute `panelDC` off-hysteresis at cleanup) to determine how `DC ON` achieves low brightness, alongside measuring `23:A9 = 0x8e` time-domain modulation depth on a DC-coupled photodiode.
