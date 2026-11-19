# Causal DDIC Round 4: `23:C1` DBV Scaling, `23:A9` Probed Mask (`0x86` vs `0x8e`), and `DBV 2048` Causal Test (`0.6×` DNG, `2026-11-19`)

## 1. Purpose and Setup

Building on Round 3 (`23:A9 = 0x8e` switching `23:C1` from `00 00 60` to `00 00 10` at `DBV 3600`), this round investigated:
1. How `23:C1 (3B)` varies across `DBV 1024–4095` (`panelDC = 0`) and which probed combinations of `23:A9` (versus `24:9D`) trigger the `23:C1` transition.
2. Whether writing `23:A9 = 0x86` (`0x0e → 0x86`, toggling bit 7 `0→1` and bit 3 `1→0`) changes `[±2, ∓1]` at `DBV 3600`, `625 µs`.
3. What `23:A9 = 0x8e` does at `DBV 2048` (`panelDC = 0`, `120 Hz`, `#FFFFFF`), across `250 / 625 / 800 µs` with return to `23:A9 = 0x0e`.

- **Target:** Lenovo XT2611-1/PVT (`W3WWS36.65-64-4-1`), BOE `ILI97701A cmd_v4` (`ID 0xd2`), guarded `unshare -m` debugfs DSI session with `esd_check_mode` verified `reg_read`.
- **Observer:** Nothing A001 (`Camera ID: 2`, `EXPERT 0.6×`, `RAW ON`, `3264×2448` DNG, `ISO 6400`, reference `IMG_20260502_083009182.DNG`).
- **Reproducible spec & summary (`24` DNGs, 3 per phase):** [spec_round4_20261119.json](spec_round4_20261119.json) and [summary_round4_20261119.json](summary_round4_20261119.json), verified via `analyze_2d_modulation.py --evidence-dir <dir> --spec-json spec_round4_20261119.json --out-json summary_round4_20261119.json` (`EXIT=0`).
- **Spatial interpretation note & frame selection:** Throughout this report, `~720 Hz` (diagonal `[±2, ∓1]` component) and `~120 Hz` (broad dark dip) are used as physical interpretations of those spatial features from earlier rounds rather than frequency measurements made in Round 4. Low-dip frames are defined as `frac_lt_065 < 0.05`; at `DBV 2048` (`0x0e`), the `[±2, ∓1]` wave itself drives `frac_lt_065` to `0.3681–0.4236` in every frame, so `0/3` frames pass `< 0.05` in `dbv2048_a9_0e_base` and `dbv2048_a9_0e_ret`.

## 2. `23:C1` DBV Scaling & `23:A9` Readback Probes

1. **DBV sweep under `panelDC = 0`, `120 Hz` (`23:A9 = 0x0e`, `24:9D = 0x0e`):**
   - `DBV 1024`: `23:C1 = 0x00 0x02 0xac` (`[1:2]` as integer = `684`)
   - `DBV 2048`: `23:C1 = 0x00 0x02 0x26` (`550`)
   - `DBV 3584`: `23:C1 = 0x00 0x00 0x65` (`101`)
   - `DBV 3600`: `23:C1 = 0x00 0x00 0x60` (`96`)
   - `DBV 3601`: `23:C1 = 0x00 0x00 0x10` (`16`)
   - `DBV 4095`: `23:C1 = 0x00 0x00 0x10` (`16`)
   - Because `23:C1` spans `684` (`0x02ac`) at `DBV 1024` down to `16` at `DBV >= 3601`, byte 2 cannot be solely a sub-frame pulse-count nibble (`6` in `0x60`); bytes `[1:2]` vary monotonically across the threshold, though the hardware bit-width, timebase units, and exact internal field semantics of `23:C1` remain unverified.

2. **Probed `23:A9` combinations & `24:9D` split at `DBV 3600`:**
   - Bit 6 (`0x40`) of `23:A9` did not latch on readback (`W 0x4e → R 0x0e`, `W 0x6e → R 0x2e`, `W 0xce → R 0x8e`, `W 0xfe → R 0xbe`).
   - Writing `23:A9 = 0x00 / 0x02 / 0x06 / 0x0a / 0x0e / 0x1e / 0x2e / 0x80 / 0x86 / 0x88 / 0x8c` left `23:C1` at `0x00 0x00 0x60` (`96`).
   - Writing `23:A9 = 0x8e / 0x9e / 0xae / 0xbe` (and `0xce` reading `0x8e`, `0xfe` reading `0xbe`) switched `23:C1` to `0x00 0x00 0x10` (`16`). Among the probed values, neither setting bit 7 with `[3:1] != 0b111` (`0x80 / 0x86 / 0x88 / 0x8c`) nor `[3:1] = 0b111` with bit 7 = 0 (`0x0e / 0x1e / 0x2e`) switched `23:C1` (which remained `96`), whereas bit 7 combined with `[3:1] = 0b111` did; untested values such as `0x8a` (`[3:1] = 0b101`) mean individual necessity of bit 2 is not separately established.
   - Writing `24:9D = 0x8e` alone latched `24:9D = 0x8e` on readback without changing `23:A9` (`0x0e`) or `23:C1` (`0x00 0x00 0x60`).
   - Setting `23:A9 = 0x8e` at `DBV 2048` and `DBV 1024` also switched `23:C1` readback to `0x00 0x00 0x10` (`16`).

## 3. Optical DNG Results (`DBV 3600` `0x86` & `DBV 2048` `0x0e → 0x8e → 0x0e`)

| Phase (`DBV`, `23:A9`) | `T_exp` (`µs`) | `23:C1` | Frames (`frac_lt_065 < 0.05`) | `F(-2,+1)` (all frames) | `F(-2,+1)` (`< 0.05` only) | Mean `raw_mean_dn` (all) | Mean `DN / µs` (all) | Mean `DN / µs` (`< 0.05`) |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `dbv3600_a9_0e_base` (`3600`, `0x0e`) | `625` | `00 00 60` | `2/3` | `0.0862–0.1484` | `0.0862–0.1060` | `8.4083` | `0.01345` | `0.01380` |
| `dbv3600_a9_86` (`3600`, `0x86`) | `625` | `00 00 60` | `2/3` | `0.0976–0.1629` | `0.0976–0.1021` | `8.2813` | `0.01325` | `0.01362` |
| `dbv3600_a9_0e_ret` (`3600`, `0x0e`) | `625` | `00 00 60` | `2/3` | `0.0949–0.1769` | `0.0949–0.1097` | `8.4439` | `0.01351` | `0.01402` |
| `dbv2048_a9_0e_base` (`2048`, `0x0e`) | `625` | `00 02 26` | `0/3` | `0.5734–0.6291` | `—` | `2.4757` | `0.00396` | `—` |
| `dbv2048_a9_8e_625us` (`2048`, `0x8e`) | `625` | `00 00 10` | `1/3` | `0.0115–0.1646` | `0.0115` | `6.3793` | `0.01021` | `0.01166` |
| `dbv2048_a9_8e_250us` (`2048`, `0x8e`) | `250` | `00 00 10` | `1/3` | `0.0143–0.1930` | `0.0143` | `2.8116` | `0.01125` | `0.01177` |
| `dbv2048_a9_8e_800us` (`2048`, `0x8e`) | `800` | `00 00 10` | `2/3` | `0.0079–0.0844` | `0.0079–0.0185` | `8.5750` | `0.01072` | `0.01142` |
| `dbv2048_a9_0e_ret` (`2048`, `0x0e`) | `625` | `00 02 26` | `0/3` | `0.6538–0.6910` | `—` | `2.4759` | `0.00396` | `—` |

Within the 9 `DBV 2048`, `23:A9 = 0x8e` DNGs (`dbv2048_a9_8e_*`), `4/9` frames satisfied `frac_lt_065 < 0.05` (`IMG_20260502_105045356.DNG`, `105103054.DNG`, `105116265.DNG`, `105120565.DNG`: `0.01142–0.01177 DN/µs`, `F(-2,+1) = 0.0079–0.0185`), while `5/9` did not: `4/9` showed dark dips (`frac_lt_065 = 0.1111–0.1493`: `105043217`, `105047492`, `105100906`, `105118394`), and `1/9` was borderline (`IMG_20260502_105058742.DNG` at `250 µs`: `frac_lt_065 = 0.0694`, `binned_min = 0.4484`, `raw_mean_dn = 2.9588`, `0.01184 DN/µs`, `F(-2,+1) = 0.0240`).

Key experimental findings:

1. **`23:A9 = 0x86` at `DBV 3600` retains `[±2, ∓1]` at `625 µs`:** Transitioning `0x0e → 0x86` toggles both bit 7 (`0→1`) and bit 3 (`1→0`). `23:A9 = 0x86` latched on readback, kept `23:C1` at `0x00 0x00 0x60`, and preserved `[±2, ∓1]` at `625 µs` (`F(-2,+1) = 0.0976–0.1021` on `< 0.05` frames vs `0.0862–0.1060` base and `0.0949–0.1097` return).
2. **At `DBV 2048`, `23:A9 = 0x8e` strongly suppresses `[±2, ∓1]` while raising camera signal `2.58×`:**
   - At matched `625 µs` across all frames without selection, `DBV 2048` `0x0e → 0x8e` reduced mean `F(-2,+1)` from `0.5989` to `0.1023` (`5.86×` / `≈5.9×`; `0.5734–0.6291` to `0.0115` on the single `< 0.05` frame and `0.1307–0.1646` on the `2/3` dark-dip frames), while also keeping `F(-2,+1) = 0.0143` at `250 µs` (`< 0.05` frame; `0.0240` on `105058742`) and `0.0079–0.0185` at `800 µs` (`< 0.05` frames). Dark-dip frames (`frac_lt_065 = 0.1111–0.1493`) persisted across all three exposures (`4/9` frames).
   - Simultaneously, at matched `625 µs` across all frames without changing `DBV` or `panelDC`, uncalibrated camera signal jumped `2.58×`, from `0.00396 DN/µs` (`2.4757 DN`) to `0.01021 DN/µs` (`6.3793 DN`; `0.01142–0.01177 DN/µs` on `< 0.05` frames across `250–800 µs`). Because `53:A2` / PAM state was not read in this round, disabling an EM blanking window without PAM/gamma compensation remains a *hypothesis* consistent with the paired shift in `23:C1` (`550 → 16`), diagonal amplitude, and camera signal.
3. **Return behavior:** Restoring `23:A9 = 0x0e` at `DBV 2048` restored `23:C1 = 0x00 0x02 0x26` (`550`), returned strong `[±2, ∓1]` modulation (`F(-2,+1) = 0.6538–0.6910`, all-frame mean `0.6758`, higher than `0.5734–0.6291` pre-write), and brought all-frame mean signal back to `2.4759 DN` (`0.00396 DN/µs`, matching `2.4757 DN` baseline).

## 4. Verification and Next Step

- **Both phones restored and verified:** `Lenovo` (`BL = 6873`, `screen_brightness = 105`, `panelDC = 0`, `120 Hz`, `ZRamSettingsActivity`, `esd_check_mode = reg_read`, `23:A9 = 0x0e` / `23:C1 = 0x00 0x00 0x60` at `3600` prior to brightness `105`) and `A001` (`1×`, `RAW OFF`, `OpenCamera Device 0`, `exposureTime = 100000 ns`, `sensitivity = 6400`, `focusDistance = 0.58822089`).
- **Verification commands after final edits:** `analyze_2d_modulation.py` CLI check on `spec_round4_20261119.json` (`EXIT=0`) and `python3 -B` / `python3 -OB -m unittest discover -v` in [pwm_06x_dng_bench_20261119](../pwm_06x_dng_bench_20261119/) (`7/7` pass).
- **Next step:** Test whether combining `23:A9 = 0x8e` with lower DBV or `53:A2` LUT updates matches baseline `DBV 2048` camera signal without restoring the `[±2, ∓1]` wave, and probe `0x8a` as well as remaining writable timing/EM register candidates outside `23:A9`/`4F:81`.
