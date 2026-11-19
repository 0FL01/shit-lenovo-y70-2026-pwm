# Causal DDIC Round 8: Which `dc-on` Field Returns Camera Signal `~7 DN → ~2.4 DN` at `DBV 2048` (`0.6×` DNG, `2026-11-19`)

## 1. Purpose and Setup

Round 7 left a gap: at `DBV 2048`, isolated `23:A9 = 0x8e` (+ `53:A2 = DC ON` in Round 6) raised uncalibrated camera signal to `7.0574 DN` all-frame while suppressing `[±2, ∓1]`, whereas stock active `panelDC = 1` kept it at `2.4349 DN`. Round 8 sequentially accumulated the remaining stock `cmd_v4` `dc-on` differences on top of `23:A9 = 0x8e + 53:A2 = DC ON` to find the compensating field, with an addressed A-B-A control at the first transition and a live-snapshot restore.

- **Target & Observer:** Lenovo XT2611-1/PVT (`W3WWS36.65-64-4-1`, BOE `ILI97701A cmd_v4`), Nothing A001 (`Camera ID: 2`, `EXPERT 0.6×`, `RAW ON`, `ISO 6400`, fixed `625 µs`, reference `IMG_20260502_083009182.DNG`), `#FFFFFF` (`HTMLViewer` via `content://media/external/file`), `panelDC = 0` (sysfs + `GET_global`) throughout, `120 Hz`, guarded `unshare -m` debugfs transactions (`esd_sw_sim_success` → per-write page select / write / page-0 return / readback → `reg_read` verified in `trap EXIT`).
- **Baseline snapshot:** before the first write, all fields to be modified were read live (`23:A9/24:9D/23:80/23:85/53:95/53:A2(30B)/51:A1/51:A2/52:81/52:82`, bank-wrapped `63:F2/F3(16B)`, all 23 PAM registers `0x5A/0x5B/0x5C ×3B`). Live PAM equaled the stock `dc-off` table 23/23 (`make_r8_ret.py` gate); live `63:F2 = 10×5 00×11` again differed from the vendor `dc-off` `00×16` (as in Round 3), so the restore used the snapshot, not table values.
- **Reproducible spec & summary (33 DNGs, 3 per phase):** [spec_round8_20261119.json](spec_round8_20261119.json) and [summary_round8_20261119.json](summary_round8_20261119.json), verified via `analyze_2d_modulation.py --evidence-dir <private> --spec-json spec_round8_20261119.json --out-json summary_round8_20261119.json` (`EXIT=0`). No `frac_lt_065` filtering (stock DC frames legitimately sit at `0.05–0.39`); per-frame values below.
- **Session incidents (both recovered in-session):** (a) one read-only bank probe hung once on `63:F2` and was retried successfully minutes later with no state change; (b) the framework reasserted `screen_brightness 105` (DIM curve, `00:52 = 0x03 0x3c` = 828) between two phases — the affected `r8_addf23` shots were discarded and the phase re-run at `00:52 = 0x08 0x00`; from then on every phase re-asserted `BL = 2048` and verified `00:52` in its own readback (held `2048` through all shooting windows); (c) the first `r8_ret` attempt failed before any write (double `0x`-prefix bug in the generated cmdfile); its 3 shots (same register state as `r8_addpam`) were discarded. Discarded frames are listed in the spec.

## 2. Phases (cumulative writes; every write verified by readback in its phase output, except `63:F2/F3` whose confirmation read happened in the next phase's `r8_addpam` transaction)

| # | Phase | Added on top of previous | Readback confirms |
|---|---|---|---|
| 1 | `r8_base` | — (stock `dc-off`, `00:52 = 0x08 0x00`, `23:C1 = 00 02 26`) | all fields = `dc-off` |
| 2 | `r8_a9a2` | `23:A9 = 0x8e`, `53:A2 = DC ON 30B` | `C1 → 00 00 10`, A2 tail `74 7b b4` |
| 3 | `r8_add9d` | `24:9D = 0x8e` | `9D = 0x8e` |
| 4 | `r8_add80` | `23:80 = 0x90` | `80 = 0x90` |
| 5 | `r8_add95` | `53:95 = 0x44 0x50` | `95 = 44 50` |
| 6 | `r8_add5152` | `51:A1/A2`, `52:81/82` → stock `dc-on` values | all four |
| 7 | `r8_ctl_80off` → `r8_ctl_80on` | addressed control: only `23:80` reverted `0x90 → 0x50`, shots, then re-applied `0x90`, shots | `80 = 0x50` / `0x90`, `A9 = 0x8e` kept |
| 8 | `r8_addf23` | `63:F2/F3` stock `dc-on` swap inside `53:F0 01 … 00` | writes `W_OK`; F2/F3 values confirmed by the read in `r8_addpam` |
| 9 | `r8_addpam` | full PAM block `dc-on` (23 regs, `0x5A/0x5B/0x5C`) — completes the register-level `dc-on` replica | spot reads `5A:8A = 32 38 18`, `5A:BF = 00 f8 fe` |
| 10 | `r8_ret` | **snapshot restore** (36 writes from `r8_base` live values) | all 37 readback fields identical to `r8_base` (0 mismatches), `C1 = 00 02 26` |

## 3. Optical Results (`625 µs`, all frames, no filtering)

| Phase | `raw_mean_dn` (all-frame mean) | Mean `F(-2,+1)` | Mean `frac_lt_065` | Per-frame `raw / F(-2,+1) / peak 2D k` |
|---|---:|---:|---:|---|
| `r8_base` | 2.7797 | 0.6446 | 0.3924 | 2.9197/0.611/[2,-1] · 2.4976/0.706/[2,-1] · 2.9217/0.617/[2,-1] |
| `r8_a9a2` | **7.1826** | **0.0095** | 0.0069 | 7.2246/0.012/[0,7] · 7.1925/0.009/[6,-3] · 7.1308/0.007/[0,3] |
| `r8_add9d` | 7.8468 | 0.1215 | 0.1701 | 7.5216/0.141/[1,0] · 8.0163/0.111/[1,0] · 8.0024/0.113/[1,0] |
| **`r8_add80`** | **2.6139** | 0.0237 | 0.0695 | 2.6109/0.036/[6,4] · 2.6439/0.015/[4,4] · 2.5868/0.020/[8,-2] |
| `r8_add95` | 2.3204 | 0.0367 | 0.1239 | 2.5879/0.015/[6,-6] · 2.2761/0.017/[1,0] · 2.0972/0.079/[1,0] |
| `r8_add5152` | 2.6345 | 0.0288 | 0.0521 | 2.6768/0.012/[6,7] · 2.6750/0.040/[9,4] · 2.5518/0.035/[9,4] |
| `r8_ctl_80off` | **9.3885** | 0.0278 | 0.0301 | 9.1671/0.051/[-1,0] · 9.4622/0.025/[1,0] · 9.5363/0.007/[0,7] |
| `r8_ctl_80on` | **1.1572** | 0.1360 | 0.3090 | 1.9261/0.178/[1,0] · 0.7406/0.142/[1,0] · 0.8049/0.088/[1,0] |
| `r8_addf23` | 2.6266 | 0.0189 | 0.0556 | 2.5938/0.015/[8,5] · 2.6222/0.025/[9,5] · 2.6637/0.016/[9,3] |
| `r8_addpam` | 2.4296 | 0.0343 | 0.1018 | 2.3210/0.061/[1,0] · 2.5441/0.011/[-1,-1] · 2.4236/0.031/[6,-6] |
| `r8_ret` | 2.6415 | 0.6760 | 0.4097 | 2.5437/0.669/[2,-1] · 2.4699/0.721/[-2,1] · 2.9109/0.638/[2,-1] |

## 4. Key Findings

1. **The `23:80: 0x50 ↔ 0x90` switch is the brightness-compensating lever of the `dc-on` set (confirmed-on-target, causal, attributed to the `23:80` block within this combination):** In the cumulative sequence, writing `23:80 = 0x90` on top of `23:A9 = 0x8e + 53:A2 ON + 24:9D = 0x8e` collapsed all-frame camera signal from `7.8468` to `2.6139 DN` (`3.0×`) while keeping `[±2, ∓1]` suppressed (`F = 0.0237`). The addressed control on the accumulated state (only `23:80` toggled) reproduced the effect in both directions: `80 = 0x50` → `9.3885 DN` (`F = 0.0278`, wave still suppressed), `80 = 0x90` again → `1.1572 DN` with `[1, 0]` dips (`lt065 = 0.26–0.38`, peak amplitudes `0.41–0.65`) — the same dip signature as stock `panelDC = 1` at `DBV 1024` in Round 7. `0x50 XOR 0x90 = 0xc0`, so this transition changes **both bits 7 and 6**; the individual roles of the bits were not isolated (and R2 showed `0x90` written alone at `23:A9 = 0x0e`/`DBV 3600` does nothing). The compensated level also differed between entry paths at the same programmed field values: `r8_add5152` (`2.6345 DN`, cumulative entry) vs `r8_ctl_80on` (`1.1572 DN`, after the `0x50` excursion) — five fields (`95`, `51/52 ×4`) plus the path differed between `r8_add80` and `r8_ctl_80on`, while the `add5152`/`ctl_80on` pair matches on all programmed fields, though the control phases re-read only `00:52`, `23:80`, `23:A9`, `23:C1` (not the full set). Any internal `23:80`-triggered recalculation mechanism remains a **hypothesis**.
2. **Direct DDIC writes at `panelDC = 0` reached the stock active `panelDC = 1` signal level of Round 7 without enabling the stock setting (confirmed-on-target, cross-session comparison):** `r8_addpam` — every live-read `dc-on` difference applied (`A9`, `9D`, `80`, `95`, `A2`, `51/52`, `F2/F3`, PAM block) — measured `2.4296 DN` all-frame mean (`F(-2,+1) = 0.0343`) vs Round 7's stock `2.4349 DN` (`F = 0.0726`, `-0.2%`) at the same `00:52 = 0x08 0x00`, each side being 3 frames in separate sessions. Manually sending the untouched same-prefix commit packets (`00:00`, `08:98`, `4F:81/88/8B`, `23:AA/24:9E/23:A6/A7`) was not required to reach this level; absence of any other framework/HWC contribution to the stock behavior is **not established** by this comparison.
3. **`24:9D = 0x8e` raises the uncompensated DC signal on its own (`7.18 → 7.85 DN`) and brings back `[1, 0]` dip frames (`lt065 = 0.16–0.18`); the separate effect of `53:95 = 44 50` on the uncompensated state is not isolated:** in the control phase `+95 +51/52` (and the different entry path) were present together with `80 = 0x50`, giving `9.39 DN`, so `95`'s individual contribution cannot be separated from `51/52` and path history. After `23:80 = 0x90` compensation, the `95` and `51/52` additions stayed in the `2.3–2.6 DN` band.
4. **The final phases (`add5152`, `addf23`, `addpam`) all measured `2.3–2.7 DN` with `F(-2,+1) = 0.019–0.037`**, i.e. adding `F2/F3` and the PAM `dc-on` tables did not move the compensated level beyond that band; independent neutrality of these blocks is **not established** by this sequence (single accumulation path, `addf23` re-run after a framework brightness reset, `[1, 0]` dip frames appearing in some `95`/PAM frames).
5. **Full reversibility:** the snapshot restore returned all 37 readback fields to `r8_base` values (including live `F2 = 10×5 00×11`, PAM `dc-off`), and the `[±2, ∓1]` wave plus signal level returned immediately (`F = 0.6760` vs `0.6446` base; `2.6415 DN` vs `2.7797 DN` base, `-5.0%` all-frame). The cleanest optical state of the session remains `A9 = 0x8e + A2 ON` alone (`F = 0.0095`, `lt065 = 0.0069`) — at the cost of `2.6×` brightness.

## 5. Verification and Next Step

- **Both phones restored and verified:** `Lenovo` (`BL = 6873` via `screen_brightness 104→105`, `panelDC = 0` sysfs, `GET_global display_dc_mode_enabled = 0`, `120 Hz`, `ZRamSettingsActivity`, `esd_check_mode = reg_read` in every phase output, temp HTML/cmdfiles/script removed incl. MediaStore row) and `A001` (Nothing camera returned to `PHOTO`, `1×`, RAW off — screencap-verified; `OpenCamera Device 0`, `exposureTime = 100000 ns`, `ISO 6400` foreground baseline).
- **Verification commands after final edits:** `analyze_2d_modulation.py` CLI check on `spec_round8_20261119.json` (`EXIT=0`) and `python3 -B` / `python3 -OB -m unittest discover -v` in [pwm_06x_dng_bench_20261119](../pwm_06x_dng_bench_20261119/) (`7/7` pass).
- **Next step:** the owner-facing lever candidates are now two register switches (`23:A9: 0x0e ↔ 0x8e` PWM↔DC, `23:80: 0x50 ↔ 0x90` compensation; individual bit roles unknown). Round 9 should (a) resolve the entry-path difference of the compensated level (`r8_add5152` vs `r8_ctl_80on` at identical programmed fields), reading the full register set (`23:C1`, PAM, `51/52`) after each path, and (b) test whether `53:95` / PAM values intermediate between `dc-off` and `dc-on` yield a compensated DC state at lower brightness without `[1, 0]` dips at `DBV ≤ 1024`, toward reduced modulation depth without the `2.6×` brightness rise.
