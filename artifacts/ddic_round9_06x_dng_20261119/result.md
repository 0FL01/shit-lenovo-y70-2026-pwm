# Causal DDIC Round 9: Entry-Path Dependence of the Compensated DC Level & Low-Brightness Dip Structure (`0.6×` DNG, `2026-11-19`)

## 1. Purpose and Setup

Round 8 left two open questions: (a) the compensated DC level reached by the cumulative register sequence (`2.63 DN`, the `r8_add5152` landing) differed from the level after a `23:80: 0x50` excursion (`1.16 DN`, `r8_ctl_80on`) at identical programmed fields — unresolved because the control phases re-read only 4 fields; (b) whether a DDIC register state exists that gives low brightness without the deep `[1, 0]` dips that stock `panelDC = 1` shows at `DBV 1024` (Round 7). Round 9 closes both: the compared end states are closed by **full 37-field readbacks** (standard set + all 23 PAM registers + bank-wrapped `63:F2/F3`; the short `exc80off` phases read 4 fields), and the cumulative-entry DC replica is measured against fresh PWM baselines at `DBV 2048 / 1024 / 512`.

- **Target & Observer:** Lenovo XT2611-1/PVT (`W3WWS36.65-64-4-1`, BOE `ILI97701A cmd_v4`), Nothing A001 (`Camera ID: 2`, `EXPERT 0.6×`, `RAW ON`, `ISO 6400`, fixed `625 µs`, reference `IMG_20260502_083009182.DNG`), `#FFFFFF` (`HTMLViewer`), `panelDC = 0` (sysfs + `GET_global`) throughout, `120 Hz`, guarded `unshare -m` debugfs transactions with `esd_sw_sim_success → … → reg_read` verified in `trap EXIT`.
- **Baseline snapshot & restore:** same discipline as Round 8 — live snapshot before the first write (`make_r8_ret.py` gate re-run: live PAM again matched the stock `dc-off` table 23/23, live `63:F2 = 10×5 00×11`), snapshot-based restore after each DBV series, `00:52` verified inside every phase output and `BL` re-asserted before every phase (no brightness reassert hit any shooting window this round; `00:52` read `08 00 / 04 00 / 02 00` for the `2048 / 1024 / 512` series).
- **Reproducible spec & summary (39 DNGs, 13 phases, 3 frames each):** [spec_round9_20261119.json](spec_round9_20261119.json) and [summary_round9_20261119.json](summary_round9_20261119.json), verified via `analyze_2d_modulation.py --evidence-dir <private> --spec-json spec_round9_20261119.json --out-json summary_round9_20261119.json` (`EXIT=0`); no frame filtering, per-frame values below.
- **Session incident:** the first `DBV 512` sequence started while the `DBV 1024` DC replica was still latched (`23:A9 = 0x8e` read back in the intended "base"), so its first 3 frames are kept as a **separate unplanned observation** `r9_dv512_carryover` — excursion-latched DC carried to `512`, with **no readback in that state** (the register map in the spec is explicitly inherited from `r9_dv1024_exc80on`, captured at `00:52 = 0x04 0x00`; `BL = 512` was verified only in the later planned phases) — and its re-written duplicate 3 frames are discarded; the proper `512` series then ran from a verified `dc-off` restore (`23:C1 = 00 02 be`). The carryover phase is neither a paired control nor a test of stock DC at `512`.

## 2. Phases

| # | Phase | State | `00:52` |
|---|---|---|---|
| 1 | `r9_base` | stock `dc-off`, snapshot | `08 00` |
| 2 | `r9_cumul` | full `dc-on` replica, cumulative writes in one session (R8 sequence) | `08 00` |
| 3–4 | `r9_exc80off` → `r9_exc80on` | only `23:80: 0x90 → 0x50` (shots), then `0x50 → 0x90` + full readback | `08 00` |
| 5 | `r9_ret` | snapshot restore | `08 00` |
| 6–9 | `r9_dv1024_base / _cumul / _exc80off / _exc80on` | same design at `DBV 1024` from a fresh `dc-off` base | `04 00` |
| 10 | `r9_dv512_carryover` | excursion-latched DC carried `1024 → 512` (unplanned, kept) | `02 00` |
| 11–13 | `r9_dv512_base / _cumul / _ret` | PWM base, fresh cumulative replica, snapshot restore at `512` | `02 00` |

## 3. Optical Results (`625 µs`, all frames, no filtering)

| Phase | `raw_mean_dn` | Mean `F(-2,+1)` | Mean `frac_lt_065` | Per-frame `raw / F / peak k / binned_min` |
|---|---:|---:|---:|---|
| `r9_base` | 2.5974 | 0.6614 | 0.4190 | 2.78/0.613/[−2,1]/−0.19 · 2.50/0.678/[2,−1]/−0.18 · 2.51/0.693/[2,−1]/−0.31 |
| `r9_cumul` | 2.4777 | 0.0389 | 0.0891 | 2.62/0.028/[−7,−3]/0.40 · 2.48/0.033/[6,1]/0.18 · 2.33/0.056/[0,1]/0.01 |
| `r9_exc80off` | 9.2315 | 0.0106 | 0.0000 | 9.27/0.008/[3,2]/0.66 · 9.23/0.009/[6,−1]/0.68 · 9.19/0.015/[6,−1]/0.68 |
| `r9_exc80on` | 1.9434 | 0.1412 | 0.2639 | 1.87/0.165/[−1,0]/−0.38 · 1.85/0.131/[1,0]/−0.26 · 2.11/0.128/[−1,0]/−0.13 |
| `r9_ret` | 2.1557 | 0.6254 | 0.4167 | 2.39/0.665/[2,−1]/−0.28 · 1.83/0.679/[2,−1]/−0.44 · 2.25/0.532/[2,−1]/−0.40 |
| `r9_dv1024_base` | 0.6106 | 0.5651 | 0.4421 | 0.53/0.543/[2,0]/−2.46 · 0.53/0.479/[1,0]/−2.09 · 0.78/0.674/[1,0]/−1.43 |
| **`r9_dv1024_cumul`** | **1.1292** | **0.0410** | 0.2211 | 1.04/0.070/[1,0]/−0.43 · 1.15/0.015/[1,7]/−0.40 · 1.20/0.038/[−2,−4]/−0.33 |
| `r9_dv1024_exc80off` | 9.7696 | 0.0149 | 0.0023 | 9.88/0.008/[0,1]/0.73 · 9.79/0.020/[−6,5]/0.74 · 9.63/0.016/[0,7]/0.64 |
| `r9_dv1024_exc80on` | 0.6344 | 0.1348 | 0.3669 | 0.67/0.127/[1,0]/−1.29 · 0.61/0.108/[1,0]/−1.75 · 0.62/0.169/[1,0]/−1.18 |
| `r9_dv512_carryover` | 0.4724 | 0.1153 | 0.3715 | 0.52/0.092/[−1,0]/−2.46 · 0.35/0.111/[1,0]/−2.70 · 0.55/0.143/[−1,0]/−2.10 |
| `r9_dv512_base` | 0.7694 | 0.6126 | 0.3935 | 0.77/0.540/[2,−1]/−0.97 · 0.81/0.653/[2,−1]/−1.06 · 0.73/0.644/[2,−1]/−1.27 |
| **`r9_dv512_cumul`** | **0.6974** | **0.0792** | 0.3206 | 0.69/0.091/[−7,−6]/−1.25 · 0.69/0.058/[4,8]/−1.06 · 0.71/0.089/[2,1]/−1.48 |
| `r9_dv512_ret` | 0.8388 | 0.5138 | 0.3761 | 0.81/0.570/[2,−1]/−1.33 · 0.83/0.456/[2,−1]/−1.03 · 0.87/0.515/[2,−1]/−0.98 |

Register-state verification: `r9_cumul` and `r9_exc80on` readbacks are **identical in all 37 readable fields** (programmed values, `23:C1 = 00 00 10` both, PAM/F-bank equal), as are `r9_dv1024_cumul` and `r9_dv1024_exc80on`.

## 4. Key Findings

1. **The entry-path difference is real, reproduced, and not explained by the measured register map (confirmed-on-target):** in the same session, the cumulative `dc-on` replica measured `2.4777 DN` (`F = 0.0389`, mild dips `lt065 = 0.089`) while the `23:80: 0x50 → 0x90` excursion on a state identical in all **37 measured fields** (programmed values, `23:C1 = 00 00 10` both, PAM/F-bank equal) measured `1.9434 DN` with `[1, 0]` structure (`F = 0.1412`, `lt065 = 0.264`) at `DBV 2048`; the same 37/37 match holds between `r9_dv1024_cumul` and `r9_dv1024_exc80on`. Since no readable field differs, the measured map cannot explain the dimming-level difference; that it lives in a hidden DDIC-internal state latched by the `0x50↔0x90` transition history remains a **hypothesis**, and the cumulative path is a **candidate recipe** for reproducing the shallower-dip landing, not a proven necessary sequence.
2. **The excursion-latched state resembles the stock low-brightness DC signature; the cumulative-landed state shows weaker `[1, 0]` dominance (confirmed-on-target; the stock side is a cross-session comparison, not an equivalence proof):** at `DBV 1024`, excursion-latched DC gave `0.6344 DN` with `[1, 0]` peaks in 3/3 frames and `binned_min` down to `−1.75`, resembling Round 7's stock `panelDC = 1` behavior (`0.8051 DN`, `[1, 0]` dominant in 2/3 frames at `0.47/0.66`, `lt065 = 0.23–0.39`); the cumulative-landed DC at the same `00:52` measured `1.1292 DN` with `[1, 0]` dominant in only 1/3 frames and shallower dips (`binned_min −0.33…−0.43`, `lt065 = 0.221` vs PWM base `0.442`).
3. **At `DBV 512` the cumulative-landed DC shows the smallest wave amplitude and dip-block fraction among this round's `512` phases, at a measured brightness tradeoff (confirmed-on-target):** `raw_mean_dn = 0.6974` vs the in-session PWM base `0.7694` (`−9.4%`; vs the later `r9_dv512_ret` mean `0.8388` it is `−16.9%`), `F(-2,+1) = 0.0792` vs `0.6126` (**7.7× suppression** of the established spatial `~720 Hz` carrier signature), and a smaller dip-block fraction than PWM (`lt065 = 0.321` vs `0.394`), with a slightly deeper single-block minimum (`binned_min −1.48` vs `−1.27`). This is the best low-brightness tradeoff measured on this panel so far — a spatial-metric statement; the temporal modulation depth of the residual dip structure was not measured here. The unplanned carryover observation (excursion-latched DC at `512`) was worse on both counts: `0.4724 DN` with deep dips (`binned_min −2.10…−2.70`).
4. **The cleanest overall state remains the uncompensated DC set** (`exc80off`, `80 = 0x50`): `9.23–9.77 DN` with `F = 0.011–0.015` and `lt065 ≤ 0.007` at `DBV 2048/1024` — but its `>3×` brightness rise is unusable directly; its value is as a research reference (an optical floor for modulation).
5. **Reversibility verified at `2048` and `512`; at `1024` the restore is inferred, not separately read:** snapshot restores at `2048` and `512` returned all 37 readback fields to base values and the dominant `[±2, ∓1]` wave immediately (`F = 0.6254 / 0.5138` vs base `0.6614 / 0.6126`); the `1024` series ended in the unplanned carryover transition, and the `00 02 ac` reading is from its `base` phase — no separate post-restore readback exists at `1024`. At `2048` the restore's all-frame mean was `2.1557 DN` vs `2.5974` base (`−17.0%`, all three return frames below all three base frames, with one dip-heavy `1.83 DN`); wave amplitude stayed within `5.4%` of base. At `512` the restore mean was `0.8388 DN` vs `0.7694` base (`+9.0%`).

## 5. Interpretation for the Owner's Goal

The spatial `~720 Hz` carrier signature (`[±2, ∓1]` wave) can be suppressed `7.7×` at `DBV 512` with a `−9.4%` camera-signal shift against the in-session PWM base, and with a weaker `[1, 0]` dip dominance than the excursion-latched (stock-like) landing at `DBV 1024` — provided the DDIC is driven through the **cumulative entry path** (all `dc-on` fields written in one fresh sequence from `dc-off` at the target DBV, never through a `23:80` toggle excursion), which in this round's two DBV series produced the shallower-dip landing every time it was used fresh. The same readable register state entered the excursion way showed deep `[1, 0]` dips. The entry path is therefore an observed control knob distinct from register values; whether the cumulative sequence is *necessary*, or merely one of several non-excursion paths that work, is untested, and the temporal modulation depth of the best state is not yet measured — an Android-side implementation should treat the fresh cumulative sequence as the current reproduction recipe, not a proven requirement.

## 6. Verification and Next Step

- **Both phones restored and verified:** `Lenovo` (`BL = 6873` via `screen_brightness 104→105`, `panelDC = 0` sysfs, `GET_global = 0`, `120 Hz`, `ZRamSettingsActivity`, `esd_check_mode = reg_read` in every phase output, temp HTML/cmdfiles/MediaStore row removed) and `A001` (Nothing camera screencap-verified `PHOTO`, `1×`, RAW off; `OpenCamera Device 0`, `exposureTime = 100000 ns`, `ISO 6400` foreground).
- **Verification commands after final edits:** `analyze_2d_modulation.py` CLI check on `spec_round9_20261119.json` (`EXIT=0`) and `python3 -B` / `python3 -OB -m unittest discover -v` in [pwm_06x_dng_bench_20261119](../pwm_06x_dng_bench_20261119/) (`7/7` pass).
- **Next step:** (a) test the cumulative path at the lowest usable DBVs (`256/128`) to find where the shallow-dip property and the brightness penalty degrade, and whether a `DBV` exists whose cumulative-DC brightness matches the owner's evening level; (b) quantify the residual low-frequency dip of the cumulative-landed state directly (multi-exposure `|sinc|` sweep or photodiode) instead of relying on the spatial `[1, 0]` proxy; (c) with a DC-qualified photodiode, measure the true temporal waveform and modulation `%` of the cumulative-landed state vs stock PWM at matched brightness.
