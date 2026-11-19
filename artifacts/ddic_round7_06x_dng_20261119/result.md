# Causal DDIC Round 7: Stock `panelDC = 1` (`display_dc_mode_enabled`) Transition & `DBV 2048 / 1024` Behavior (`0.6×` DNG, `2026-11-19`)

## 1. Purpose and Setup

In Rounds 4–6, forcing `23:A9 = 0x8e` (`+ 53:A2 DC ON` in Round 6) at `DBV 2048` (`panelDC = 0`) suppressed `[±2, ∓1]` while raising camera signal (`7.0574 DN` all-frame / `7.3066 DN` `< 0.05` vs `2.4800 DN` baseline). Round 7 tested stock Android/Motorola `panelDC = 1` (`content call --uri content://com.motorola.android.providers.settings/global --method PUT_global --arg display_dc_mode_enabled --extra value:s:1`) at `DBV 2048` and `DBV 1024`, reading `00:52`, `23:A9`, `24:9D`, `23:C1`, `23:80`, `23:85`, `53:95`, `53:A2`, `51:A1/A2`, `52:81/82`, and restoring `PUT_global ... 0`.

- **Target & Observer:** Lenovo XT2611-1/PVT (`W3WWS36.65-64-4-1`, BOE `ILI97701A cmd_v4`), Nothing A001 (`Camera ID: 2`, `EXPERT 0.6×`, `RAW ON`, `ISO 6400`, fixed `625 µs` exposure, reference `IMG_20260502_083009182.DNG`), `#FFFFFF` (`HTMLViewer`), `120 Hz`, `esd_check_mode = reg_read`.
- **Reproducible spec & summary (`15` DNGs, 3 per phase):** [spec_round7_20261119.json](spec_round7_20261119.json) and [summary_round7_20261119.json](summary_round7_20261119.json), verified via `analyze_2d_modulation.py --evidence-dir <dir> --spec-json spec_round7_20261119.json --out-json summary_round7_20261119.json` (`EXIT=0`).
- **Frame classification note:** Low-dip threshold `frac_lt_065 < 0.05` is noted, but in both active `panelDC = 1` phases (`min frac_lt_065 = 0.0660` at `DBV 2048`, `0.2292` at `DBV 1024`) and both `DC = 0` phases (`0.3681–0.4410`), `0/3` frames fell below `0.05`, so all-frame summaries and per-frame values are reported directly. All Round 7 DNGs used a single `625 µs` exposure.

## 2. Observed `panelDC` Dispatch Sequence & DDIC Register Diff

1. **Sequence of `dc-on` / `dc-off` commits (`dbv2048_dc1_pending` → `dbv1024_dc1_active` → `dbv2048_dc1_active` → `dbv2048_dc0_ret`):**
   - After calling `PUT_global display_dc_mode_enabled 1` and writing `echo 2048 > brightness` (`sysfs panelDC = 1`), readback showed `51:A1` (`...79 7b` → `...79 79`), `51:A2` (`7e 7e 85 85` → `78 78 78 78`), `52:81` (`...48 4b` → `...49 48`), and `52:82` (`4e 4e 50 50` → `4a 4a 4b 4b`) changed (not read before `echo 2048`), while `23:A9 = 0x0e`, `24:9D = 0x0e`, `23:C1 = 00 02 26`, `23:80 = 0x50`, `53:95 = 00 a0`, and `53:A2 = ...10 4b 4b` stayed at `DC OFF` values (`dbv2048_dc1_pending`).
   - On the subsequent change `echo 1024 > brightness`, readback showed the full `dc-on` register set committed (`23:A9 = 0x8e`, `24:9D = 0x8e`, `23:C1 = 00 00 10`, `23:80 = 0x90`, `53:95 = 44 50`, `53:A2 = ...74 7b b4`, `51/52` at the shifted values above, `00:52 = 0x04 0x00`), which stayed active after rewriting `echo 2048 > brightness` (`00:52 = 0x08 0x00`, `dbv2048_dc1_active`).
   - After `PUT_global display_dc_mode_enabled 0` and rewriting `echo 2048 > brightness`, `dc-off` committed immediately (`23:A9 = 0x0e`, `24:9D = 0x0e`, `23:C1 = 00 02 26`, `23:80 = 0x50`, `53:95 = 00 a0`, `53:A2 = ...10 4b 4b`, and pre-DC `51/52` bytes). This shows `PUT_global 1` + unchanged `2048` left the main `dc-on` table pending until `1024`, whereas `PUT_global 0` + `2048` flushed `dc-off` at once; it does not establish what caused Round 0's `~2–3 min` delay (where `brightness` was not rewritten).

## 3. Optical DNG Results (`625 µs`)

| Phase (`BL`, `panelDC`, state) | `23:A9` / `23:C1` / `53:A2[-3:]` | `F(-2,+1)` (all frames) | Mean `F(-2,+1)` | `raw_mean_dn` (all frames) | Mean `raw_mean_dn` | Mean `DN / µs` | `frac_lt_065` |
| --- | --- | --- | ---: | --- | ---: | ---: | --- |
| `dbv2048_dc0_base` (`2048`, `0`, off) | `0x0e` / `00 02 26` / `10 4b 4b` | `0.6075–0.7612` | `0.6666` | `1.8531–2.9861` | `2.4603` | `0.00394` | `0.3681–0.4236` |
| `dbv2048_dc1_pending` (`2048`, `1`, pending) | `0x0e` / `00 02 26` / `10 4b 4b` | `0.5865–0.7247` | `0.6351` | `1.8340–2.6598` | `2.2692` | `0.00363` | `0.3924–0.4410` |
| `dbv1024_dc1_active` (`1024`, `1`, active) | `0x8e` / `00 00 10` / `74 7b b4` | `0.0376–0.1096` | `0.0681` | `0.6241–1.1285` | `0.8051` | `0.00129` | `0.2292–0.3854` |
| `dbv2048_dc1_active` (`2048`, `1`, active) | `0x8e` / `00 00 10` / `74 7b b4` | `0.0172–0.1685` | `0.0726` | `1.8571–2.7747` | `2.4349` | `0.00390` | `0.0660–0.2778` |
| `dbv2048_dc0_ret` (`2048`, `0`, off) | `0x0e` / `00 02 26` / `10 4b 4b` | `0.5725–0.7057` | `0.6466` | `2.2204–2.6901` | `2.4635` | `0.00394` | `0.3924–0.4340` |

Per-frame highlights in active `panelDC = 1`:
- `dbv2048_dc1_active`: two frames avoided the deep `[1, 0]` dip (`IMG_20260502_121210191.DNG`: `raw = 2.7747`, `F(-2,+1) = 0.0321`, `lt065 = 0.0660`; `121214497.DNG`: `raw = 2.6729`, `F = 0.0172`, `lt065 = 0.0938`), while `121212352.DNG` hit the dip (`raw = 1.8571`, `lt065 = 0.2778`, `peak = [1, 0] (0.4930)`, `F(-2,+1) = 0.1685`).
- `dbv1024_dc1_active`: all 3 frames showed prominent low-frequency/dip structure (`peak = [1, 0]` of `0.4736` and `0.6558` on `121121722` and `121126025`, `peak = [3, 2]` of `0.1509` on `121123891`, `lt065 = 0.2292–0.3854`).

Key findings:

1. **Stock active `panelDC = 1` keeps `DBV 2048` camera signal at `2.4349` vs `2.4603 DN` (`-1.0%`) while suppressing `[±2, ∓1]` `9.18×`:** At identical `00:52 = 0x08 0x00` (`DBV 2048`), active `panelDC = 1` reduced all-frame mean `F(-2,+1)` from `0.6666` to `0.0726` (`9.18×`) without raising mean camera signal at `625 µs` (contrasting with `7.0574 DN` in Round 6 when only `23:A9 = 0x8e` + `53:A2 = on` were written at `DBV 2048`). Pending `panelDC = 1` (`dbv2048_dc1_pending`, before `23:A9/24:9D/23:80/53:95/53:A2` committed) retained strong `[±2, ∓1]` (`0.6351`).
2. **Low-brightness `panelDC = 1` (`DBV 1024`) lowers camera signal to `0.8051 DN`:** At `BL = 1024`, active `panelDC = 1` kept `[±2, ∓1]` suppressed (`mean 0.0681`) while giving `0.8051 DN` mean camera signal (`-17.1%` vs Round 5 `DBV 1024 0x0e` `0.9707 DN`, cross-session comparison, rather than `4.5882 DN` with isolated `23:A9 = 0x8e` in Round 5), accompanied by larger `[1, 0]` / `lt065 = 0.2292–0.3854` dips.
3. **Full return on `PUT_global 0` + `BL = 2048`:** Register state (`23:A9 = 0x0e`, `23:C1 = 00 02 26`, `53:A2`, `51/52`) and optical metrics (`mean F = 0.6466` vs `0.6666` base, `mean raw_mean_dn = 2.4635 DN` vs `2.4603 DN` base, `+0.13%`) returned immediately.

## 4. Verification and Next Step

- **Both phones restored and verified:** `Lenovo` (`BL = 6873`, `screen_brightness = 105`, `panelDC = 0`, `GET_global display_dc_mode_enabled = 0`, `120 Hz`, `ZRamSettingsActivity`, `esd_check_mode = reg_read`) and `A001` (`1×`, `RAW OFF`, `OpenCamera Device 0`, `exposureTime = 100000 ns`, `sensitivity = 6400`, `focusDistance = 0.58822089`).
- **Verification commands after final edits:** `analyze_2d_modulation.py` CLI check on `spec_round7_20261119.json` (`EXIT=0`) and `python3 -B` / `python3 -OB -m unittest discover -v` in [pwm_06x_dng_bench_20261119](../pwm_06x_dng_bench_20261119/) (`7/7` pass).
- **Next step:** At fixed `DBV 2048` (`panelDC = 0`), test which of the remaining `dc-on` fields that differed between Round 6 (`7.06 DN`) and Round 7 (`2.43 DN`) — namely `23:80 = 0x90`, `53:95 = 0x44 0x50`, `24:9D = 0x8e`, and `51:A1/A2` / `52:81/82` (or HWC/framework dimming under `panelDC = 1`) — drops camera signal back from `~7.1 DN` to `~2.4 DN` when added to `23:A9 = 0x8e` (and check whether widening `[1, 0]` at `1024` is hardware-side or frame-level).
