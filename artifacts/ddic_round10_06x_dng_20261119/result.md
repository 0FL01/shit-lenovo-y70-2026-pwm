# Causal DDIC Round 10: Minimum-Brightness Floor Probe (sysfs `BL=256` → DDIC `460`) & Exposure Sweep of the Cumulative-Landed DC State (`0.6×` DNG, `2026-11-19`)

## 1. Purpose and Setup

Round 9 established the cumulative-entry `dc-on` replica as the best low-brightness spatial tradeoff (`DBV 512`: `7.7×` wave suppression at `−9.4%` signal). Round 10 answers two follow-ups at the lowest sysfs brightness: (a) does the recipe hold at `sysfs BL = 256` (DDIC readback `00:52 = 0x01 0xcc` = **460**, the documented minimum of the selected DT), and (b) what temporal structure remains in the cumulative-landed state — probed with a `125 µs – 12.5 ms` exposure sweep with the **sysfs** backlight verified `256` immediately before **and after** every shot pair.

- **Target & Observer:** Lenovo XT2611-1/PVT (`W3WWS36.65-64-4-1`, BOE `ILI97701A cmd_v4`), Nothing A001 (`Camera ID: 2`, `EXPERT 0.6×`, `RAW ON`, `ISO 6400`, reference `IMG_20260502_083009182.DNG`), `#FFFFFF` (`HTMLViewer`), `panelDC = 0`, `120 Hz`, guarded `unshare -m` debugfs transactions (`esd_sw_sim_success → … → reg_read` in `trap EXIT`), snapshot restore from the R9 baseline gate (live PAM matched stock `dc-off` 23/23).
- **Reproducible spec & summary (21 DNGs in 9 phases — `3×3 + 6×2` — plus the reference):** [spec_round10_20261119.json](spec_round10_20261119.json) and [summary_round10_20261119.json](summary_round10_20261119.json), verified via `analyze_2d_modulation.py --evidence-dir <private> --spec-json spec_round10_20261119.json --out-json summary_round10_20261119.json` (`EXIT=0`); no frame filtering.
- **Register readback scope:** the three floor-probe phases carry their own full readbacks; the six sweep phases share **one** readback inherited from the state-entry transaction (`r10_out_sweep2_cumul.txt`, `00:52 = 0x01 0xcc` = 460) — no re-read was taken at the individual pairs, whose light-level control was the per-pair **sysfs** check only. A final post-sweep snapshot restore re-read `00:52 = 0x01 0xcc`, `23:A9 = 0x0e`, `23:C1 = 00 02 c0`.
- **Incidents (both excluded from the accepted sample):** the *first* sweep attempt lost slider control after shots reset the EXPERT shutter slider (its x-mapping re-renders), produced unintended `1 s`/`20 s` saturated frames, and drifted without any DDIC write (13 frames discarded). An *intermediate* second series (10 frames: `625/500/800/1562.5/2500 µs × 2`, taken with `dumpsys`-verified exposures but **without** per-pair BL checks) showed pair-level inconsistencies against the final series (e.g. `800 µs` pair consistent at `1.01/1.02` there vs `0.52/1.03` in the final run) and was discarded in full as superseded; the *final* series ("v3") re-entered the fresh cumulative state and verified sysfs `BL = 256` before and after every pair — all pairs held `256` on both checks.

## 2. Phases

| # | Phase | State | Frames |
|---|---|---|---|
| 1 | `r10_dv256_base` | stock `dc-off` (`23:C1 = 00 02 c0` = 704) | 3 |
| 2 | `r10_dv256_cumul` | fresh cumulative `dc-on` replica (`23:C1 = 00 00 10`) | 3 |
| 3 | `r10_dv256_ret` | snapshot restore | 3 |
| 4 | `r10_sweep125/500/625/800/1562/12500` | cumulative-landed replica, exposure sweep (`125/500/625/800/1562.5/12500 µs`) | 2 each |

## 3. Optical Results (sysfs `BL = 256`, DDIC readback `00:52 = 0x01 0xcc` = 460; all frames, no filtering)

| Phase | `raw_mean_dn` | `F(-2,+1)` | `frac_lt_065` |
|---|---|---|---|
| `r10_dv256_base` | 0.7458 (0.5387–0.8681) | 0.5349 | 0.4039 |
| `r10_dv256_cumul` | **0.7579** (0.6238–0.8315) | **0.0953** | 0.3114 |
| `r10_dv256_ret` | 0.8231 (0.7756–0.9026) | 0.5627 | 0.3796 |
| `r10_sweep125` | 0.2324 / 0.2962 | 0.1607 / 0.0941 | 0.4549 / 0.3993 |
| `r10_sweep500` | 0.6503 / 0.7064 | 0.0935 / 0.0104 | 0.3160 / 0.3056 |
| `r10_sweep625` | **0.3837 / 0.7601** | 0.0976 / 0.0730 | 0.4062 / 0.2951 |
| `r10_sweep800` | **0.5214 / 1.0283** | 0.1378 / 0.0978 | 0.4097 / 0.2674 |
| `r10_sweep1562` | 1.8157 / 1.9136 | 0.0342 / 0.0840 | 0.1319 / 0.1389 (`binned_min` `+0.08/+0.14`) |
| `r10_sweep12500` | 11.4058 / 12.2347 | 0.0030 / 0.0047 | 0.0000 / 0.0000 |

## 4. Key Findings

1. **At the panel's minimum DBV (sysfs `BL = 256` → DDIC readback `00:52 = 0x01 0xcc` = 460) the cumulative-entry recipe keeps the diagonal wave suppressed while the mean `625 µs` signal stays at the measured PWM base level (confirmed-on-target):** `raw_mean_dn = 0.7579` vs PWM base `0.7458` (`+1.6%`, per-frame ranges overlapping: `0.6238–0.8315` vs `0.5387–0.8681`; the post-restore PWM mean read `0.8231`, `+10.4%` vs base, so equality of time-averaged brightness is not claimed), `F(-2,+1) = 0.0953` vs `0.5349` (**5.6× suppression** of the `[±2, ∓1]` carrier signature), dip-block fraction `0.3114` vs `0.4039`; snapshot restore returned `23:A9 = 0x0e`, `23:C1 = 00 02 c0` and the wave (`F = 0.5627`). Combined with R9 the measured recipe range spans readback DBV `460`–`2048` (`460: +1.6%`, `512: −9.4%`, `1024: +85%`, `2048: stock-level`).
2. **Same-exposure pairs diverge ~2× at short exposures with sysfs `BL` verified `256` on both sides (confirmed-on-target observation; interpretation is a hypothesis):** `625 µs`: `0.3837` vs `0.7601` (`1.98×`); `800 µs`: `0.5214` vs `1.0283` (`1.97×`). This is compatible with a phase lottery between a brighter (`≈1.2 DN/ms`) and a dimmer (`≈0.6 DN/ms`) emission phase, but two frames per point cannot distinguish phase sampling from an optical-state change invisible to the sysfs check (R9 already showed same-readback states with different emission). The dip-block fraction falls at `1562.5 µs` (`0.1319/0.1389`, `binned_min` positive `+0.08/+0.14`) relative to `≤800 µs` (`0.27–0.45`), and the `12.5 ms` pair is internally consistent with `lt065 = 0.0000` — consistent with averaging of a chop, but **no frequency fit was performed** (`sinc_fit: null`), and two clean long frames cannot exclude a slow envelope (integration can hide it).
3. **Character change, not elimination (spatial-metric statement):** the DC replica removes the diagonal `~720 Hz` wave (the metric at `0.53–0.66` in every PWM baseline since Round 0) while the worst block minima at `125 µs` reach `binned_min −5.7…−5.8`. The comparison to PWM's `−1.0…−1.4` is cross-exposure (different `T_exp` normalizations) and does not by itself rank modulation depth; whether the replica state is perceptually better for the owner is not decidable from these spatial metrics. Round 9's conclusion (best *measured spatial* tradeoff at `DBV 512`) is not overturned by this round — no frequency, depth, or comfort ranking is claimed.
4. **The `12.5 ms` pair of the replica state is dip-free on the block metric** (`lt065 = 0.0000`, `F(-2,+1) = 0.0030/0.0047`); this bounds nothing stronger than the absence of block-level dips in those two frames.

## 5. Verification and Next Step

- **Both phones restored and verified:** `Lenovo` (`BL = 6873` via `screen_brightness 104→105`, `panelDC = 0` sysfs, `GET_global = 0`, `120 Hz`, `ZRamSettingsActivity`, `esd_check_mode = reg_read` in every phase output, temp HTML/cmdfiles/MediaStore rows removed) and `A001` (Nothing camera returned to `PHOTO`, `1×`, RAW off; `OpenCamera` foreground baseline).
- **Verification commands after final edits:** `analyze_2d_modulation.py` CLI check on `spec_round10_20261119.json` (`EXIT=0`) and `python3 -B` / `python3 -OB -m unittest discover -v` in [pwm_06x_dng_bench_20261119](../pwm_06x_dng_bench_20261119/) (`7/7` pass).
- **Next step:** the recipe now spans readback DBV `460–2048` and its remaining unknown is temporal, not spatial: measure the cumulative-landed state with a DC-coupled photodiode (chop frequency/duty/percent depth at readback `460` and `512`) and compare with stock PWM at matched brightness — this decides whether the register recipe is owner-usable or whether the search must move to intermediate `53:95`/PAM values that could soften the chop while keeping the diagonal wave suppressed.
