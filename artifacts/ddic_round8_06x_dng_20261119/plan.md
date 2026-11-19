# Round 8 Plan: Which `dc-on` field returns camera signal from ~7.06 DN to ~2.43 DN at `DBV 2048`? (`0.6×` DNG)

## Goal

At fixed `DBV 2048`, `panelDC = 0` (`00:52 = 0x08 0x00`), `120 Hz`, `#FFFFFF` (`HTMLViewer`), `625 µs`, `ISO 6400`, `0.6×` DNG (3 frames per phase), isolate which field of the stock `dc-on` set — applied on top of `23:A9 = 0x8e` + `53:A2 = DC ON` (Round 6 state, all-frame `7.0574 DN`) — restores the stock `panelDC = 1` camera signal level (`2.4349 DN`, Round 7), or establish that no tested DDIC register combination reproduces it (framework/HWC attenuation hypothesis).

Full stock `cmd_v4` `dc-on` minus `dc-off` diff (from `artifacts/cn_panel_commands.json`, panel `qcom,mdss_dsi_mot_boe_ili97701A_682_1440x3168_dsc_cmd_v4`; live `51/52` readbacks in Round 7 matched this table exactly):

1. `23:A9`: `0x0e → 0x8e`
2. `24:9D`: `0x0e → 0x8e`
3. `23:80`: `0x50 → 0x90`
4. `53:95`: `00 a0 → 44 50`
5. `53:A2` (30B LUT): `…48 10 10 10 4b 4b ×3 → …48 10 10 74 7b b4 ×3`
6. `63:F2`/`63:F3` swap (bank `53:F0 01`): five `0x20` bytes move from `F3` to `F2`
7. `51:A1`: `44 44 79 7b → 44 44 79 79`; `51:A2`: `7e 7e 85 85 → 78 78 78 78`
8. `52:81`: `46 47 48 4b → 46 47 49 48`; `52:82`: `4e 4e 50 50 → 4a 4a 4b 4b`
9. PAM block (never read/written live, prime suspect): `0x5A` regs `86/8a/8f/90/91/92/93/94/95/9b/9c/ae/b3/b9/bf/c0/d7/dd/e4`, `0x5B:dd`, `0x5C:c8/c9/ca` — 23 registers × 3 data bytes.

## Phases (single session, sequential accumulation, off/on/off)

| # | Phase | Writes (cumulative) |
|---|---|---|
| 1 | `r8_base` | none (stock dc-off readback + 3 DNG) |
| 2 | `r8_a9a2` | `23:A9=0x8e`, `53:A2=DC ON 30B` (R6 reproduction, expect ~7 DN) |
| 3 | `r8_add9d` | + `24:9D=0x8e` |
| 4 | `r8_add80` | + `23:80=0x90` |
| 5 | `r8_add95` | + `53:95=0x44 0x50` |
| 6 | `r8_add5152` | + `51:A1=44 44 79 79 22 22`, `51:A2=78 78 78 78 22 22`, `52:81=46 47 49 48 00 00`, `52:82=4a 4a 4b 4b 00 00` |
| 7 | `r8_addf23` | + `63:F2/F3` dc-on swap inside `53:F0=01 … 53:F0=00` bank wrapper (R3-proven route) |
| 8 | `r8_addpam` | + full PAM block dc-on values (23 regs, pages `0x5A/0x5B/0x5C`) — completes the register-level `dc-on` replica |
| 9 | `r8_ret` | **snapshot restore** (host-generated from `r8_base` live values by `make_r8_ret.py`): every written field returned to its live baseline, incl. PAM block and bank-wrapped F2/F3 — readback must equal the snapshot |

Readback set every phase: `00:52`, `23:A9`, `24:9D`, `23:C1(3B)`, `23:80`, `23:85`, `53:95`, `53:A2` (full 30B), `51:A1`, `51:A2`, `52:81`, `52:82`; `r8_base` and `r8_ret` additionally read all 23 PAM registers (3B each) and the bank-wrapped `63:F2`/`63:F3` (16B each). `r8_addpam` reads the full PAM set after its writes.

## Decision rules

- **Gate 0:** `r8_a9a2` must reproduce the high-signal state (all-frame mean well above base, `F(-2,+1)` suppressed); otherwise the attribution question is not posed for this session and the run stops after `r8_ret` restore.
- **PAM gate:** the live 23-register PAM snapshot at `r8_base` must equal the stock `cmd_v4` `dc-off` table before `r8_addpam` runs (`make_r8_ret.py` refuses otherwise); a mismatch stops the session before PAM writes.
- First phase whose all-frame mean camera signal drops toward the stock `≈2.4 DN` band marks the transition; it is attributed to the **last added block within this combination** (not to a single register). At the first convincing transition, run an **addressed control**: revert only that block to its pre-block value, take 3 control DNGs, re-apply the block, take 3 confirmation DNGs (other accumulated values unchanged, `[±2,∓1]` suppression checked in all of them).
- If `r8_addpam` (full replica) still shows the high-signal level, the conclusion is: **the tested combinations, at this order and write method, did not reproduce the stock `dc-on` camera signal** — this does not exclude the untested commit/wrapper packets (`00:00`, `08:98`, `4F:81/88/8B`, `23:AA/24:9E/23:A6/A7`) nor HWC/framework attenuation, which remains the next hypothesis (follow-up round).
- All writes verified by readback in the same guarded session; any readback mismatch aborts the session and triggers snapshot restore.
- **Restore is snapshot-based:** `r8_ret` is generated from the live `r8_base` snapshot (`make_r8_ret.py`), not from assumed table values; the post-restore readback must equal the snapshot field-for-field at `DBV 2048`.
- Per-frame `raw_mean_dn`, `F(-2,+1)`, `frac_lt_065` are published for all phases; no `frac_lt_065 < 0.05` filtering (stock DC frames legitimately sit at `0.066–0.385`); 3 frames per phase screen a large ~7 vs ~2.4 DN separation, tighter mean comparisons happen only at an addressed transition.

## Safety / discipline (unchanged from rounds 2–7)

- Guarded `unshare -m` debugfs session per phase: `esd_sw_sim_success\n` → page select `FF 5A A5 <page>` → single write → immediate page `0x00` return → readback → `reg_read\n` restore with verification, all in `trap EXIT`; no `adb kill/start-server`.
- `panelDC` stays `0` (sysfs + `GET_global`) throughout; `BL` stays `2048`; teardown restores `BL=6873` via `settings put system screen_brightness 104→105`, `120 Hz`, `ZRamSettingsActivity`, temp HTML removed; A001 returned to `1×`, `RAW OFF`, OpenCamera `Device 0`, `exposureTime=100000`, `sensitivity=6400`.
- New DNGs go to `<private evidence directory>` only (never committed); public artifacts carry filenames + metrics only.

## Verification

- `analyze_2d_modulation.py --evidence-dir <private> --spec-json spec_round8_20261119.json --out-json summary_round8_20261119.json` (`EXIT=0`), `python3 -B` / `python3 -OB -m unittest discover -v` in `artifacts/pwm_06x_dng_bench_20261119/` (7/7).
