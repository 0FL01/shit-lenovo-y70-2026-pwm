# Rounds 18–20: Entry-Path Bisection → the Minimal 3-Write DC Recipe (`0.6×` DNG, `2026-11-19`)

## 1. Purpose and Setup

R9 showed the landing quality depends on the entry path (cumulative fresh entry: shallow dips; `23:80` excursion: deep). R12–R17 showed no compensation knob tunes the events. Rounds 18–20 asked what exactly in the entry sequence carries the shallow landing and searched for the shortest variant that still lands shallow. Every phase entered from a **verified dc-off snapshot restore** (`23:A9=0x0e`, `23:C1` back to the DBV-appropriate PWM telemetry) at sysfs BL `1024` (`00:52=0x04 0x00`) or `256` (`0x01 0xcc`=460); `120 Hz`, `#FFFFFF`, `625 µs` (camera UI set to manual ISO 6400; all campaign DNGs carry EXIF ISO 3200 — see §3.4), guarded `unshare -m` debugfs transactions. All phases except `r20_core3_reapply_from_core2` entered fresh from the dc-off restore; that one phase re-applied on top of the prepared core2 state.

- **Reproducible spec & summary (35 DNGs, 9 phases):** [spec_round18_20.json](spec_round18_20.json) and [summary_round18_20.json](summary_round18_20.json), verified via `analyze_2d_modulation.py --evidence-dir <private> --spec-json spec_round18_20.json --out-json summary_round18_20.json` (`EXIT=0`). The entry-variant generator is [gen_r18_cmdfiles.py](../ddic_round18_entry_20261119/gen_r18_cmdfiles.py); the core-minimization cmdfiles are three inline writes each (below).

## 2. Results (all frames, no filtering; fresh dc-off entry each phase)

| Phase (sysfs BL) | Writes | Mean `raw` | Mean `F(-2,+1)` | Mean `lt065` | `binned_min` |
|---|---|---:|---:|---:|---:|
| `r18_minus_pam` (1024) | cumulative w/o the 23 PAM writes | 0.911 | 0.079 | 0.287 | −1.86 |
| `r18_minus_f2f3` (1024) | cumulative w/o `63:F2/F3` swap | 0.932 | 0.138 | 0.269 | −2.62 |
| `r18_minus_5152` (1024) | cumulative w/o `51/52` | 0.929 | 0.087 | 0.271 | −1.41 |
| `r19_core5` (1024) | `A9=8e, A2=ON, 9D=8e, 80=90, 95=44 50` | 0.892 | 0.113 | 0.301 | −1.53 |
| **`r19_core3` (1024)** | **`A9=8e, 9D=8e, 80=90`** | **0.896** | 0.058 | 0.284 | −1.60 |
| `r19_core2` (1024) | `A9=8e, 80=90` (no `9D`) | **0.323** | 0.186 | **0.411** | **−4.99** |
| `r20_core3_460` (256) | `A9=8e, 9D=8e, 80=90` | 0.638 | 0.089 | 0.319 | −3.67 |
| `r20_core3_reapply_from_core2` (256) | same 3 writes **on top of the deep core2 state, no restore** | 0.634 | 0.107 | 0.342 | −2.53 |
| `r20_ret3_pwm` (256) | `A9=0e, 9D=0e, 80=50` (3-write restore) | 0.716 | **0.601** | 0.394 | −1.99 |

## 3. The Recipe Candidate (confirmed-on-target; shortest successfully tested variant)

1. **`24:9D = 0x8e` is the deciding write of the shallow landing:** the cumulative sequence minus PAM, minus `F2/F3`, and minus `51/52` all land shallow (`0.91–0.93 DN` at 1024); dropping only `9D` (core2) collapses the landing to the deep excursion-like regime (`0.323 DN`, `lt065 0.411`, `bmin −4.99`) — the core3/core2 contrast holds per-frame without overlap (`0.569–1.077` vs `0.176–0.437 DN`). Neither the `53:A2` LUT nor `53:95` is required (core5 ≈ core3), and neither are the PAM block, `F2/F3`, or `51/52`.
2. **Apply = 3 register writes, in order — the shortest variant tested:** `W 23:A9=0x8e` (PWM→DC), `W 24:9D=0x8e` (landing quality), `W 23:80=0x90` (brightness compensation). Verified fresh from dc-off at sysfs `1024` (mean `0.896 DN`, `F = 0.058`) and at sysfs `256`/readback 460 (mean `0.638 DN`, `F = 0.089`); at 460 the landing is "shallow **relative to core2**" but the intrinsic deep-event regime of that BL (R12–R17) remains. One reapply test: the same 3 writes **on top of the prepared deep core2 state without a restore** restored the fresh signal level (`0.634` vs `0.638 DN`) with dip statistics comparable to fresh core3 at 460 (`lt065 0.342` vs `0.319`; `bmin −2.53` vs `−3.67`) — i.e. it re-landed like a fresh entry in that one prepared case; no claim is made for arbitrary DC-side states.
3. **Restore = the 3 mirrored writes (verified once, at sysfs 256/460):** `W 23:A9=0x0e`, `W 24:9D=0x0e`, `W 23:80=0x50` — the `[±2, ∓1]` wave returned immediately (`F = 0.601`, `23:C1 = 00 02 c0`) at a somewhat higher mean signal (`0.716` vs `0.638/0.634 DN`, `≈+12%`; same exposure and actual ISO within the campaign). In-session, same-ISO suppression ratio at 460: core3 `F = 0.089/0.107` vs the 3-write restore `F = 0.601` (`≈6×`); the larger `5.6×/7.7×/13.8×` ratios belong to the full 36-write recipe rounds (R9/R10, ISO 6400), not to core3 across the range.
4. **Scope and caveats:** the recipe was verified with 4 frames per point at two sysfs levels plus one reapply; the R18 full readbacks carry the `23:85=0x14` leftover of the R16 probe (below the optical noise floor for these metrics, reverted at campaign end — see R12–R17); ISO note: the camera UI was set to manual 6400 but **all campaign DNGs carry EXIF ISO 3200** — every campaign-internal comparison shares that actual ISO, while cross-references to the R9/R10 baselines (ISO 6400) are qualitative. No claim of equal time-averaged brightness, no "all metrics better" claim (R9 full recipe at 512: worst-block `−1.48` vs PWM `−1.27`), and no frequency/depth/comfort claim — the `≥2000 Hz` goal is not established by these spatial metrics.

## 4. Consequences for the Owner

The control surface is now **three two-byte writes plus the sysfs brightness** — no kernel patch, no 36-write table. The DC state it produces suppresses the diagonal `~720 Hz` carrier signature in every measurement (`≈6×` in-session at 460 vs the 3-write restore; `5.6×/7.7×/13.8×` for the full recipe vs PWM in R9/R10), with the caveat from R11–R17: below readback DBV ~2048 the DDIC dims by sporadic deep dark events (`0.5–0.8 ms`), so the perceptual verdict at the lowest brightness still awaits the DC-coupled photodiode or the owner's trial. The dip-block fraction is lower than PWM at every probed BL; the worst-block depth is mixed at 512 (`−1.48` vs `−1.27`, R9 full recipe). The owner's first direct comfort trial of the 3-write recipe (enabled at sysfs 512 on 2026-11-19) was reported positive in direction; a stability/defect hunt under real usage (brightness moves, adaptive brightness, refresh-rate changes, screen off/on, stock Flicker-prevention toggles) is the next round.

## 5. Verification

- Both phones restored and verified (Lenovo: `BL=6873`, `panelDC=0`, `GET_global=0`, `120 Hz`, `ZRamSettingsActivity`, `esd_check_mode=reg_read`; A001: `PHOTO 1×` RAW off, `OpenCamera` baseline); the full snapshot restore before the final teardown returned all 37 readable fields (the `23:85=0x14` leftover from the R16 probe was caught by the diff and reverted to `0x15`).
- Analyzer CLI `EXIT=0` on `spec_round18_20.json`; `python3 -B` / `python3 -OB -m unittest discover -v` in [pwm_06x_dng_bench_20261119](../pwm_06x_dng_bench_20261119/): `7/7`.
- **Next step:** hand the 3-write recipe to the owner for a direct comfort trial at their evening brightness (it is session-only and fully reversible), and in parallel obtain the DC-coupled photodiode measurement of the residual events (frequency/duty/percent depth at 460 and 512) — the two remaining unknowns before declaring the ≥2000 Hz-equivalent goal met or moving to intermediate-PAM/value search in the DC drive itself.
