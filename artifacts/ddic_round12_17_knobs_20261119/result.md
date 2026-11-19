# Rounds 12–17: Compensation-Knob Probes at Low Brightness (`0.6×` DNG, `2026-11-19`)

## 1. Purpose and Setup

Round 11 mapped the cumulative-landed DC residual as deep dark events (`≈0.5–0.8 ms`) that fade with brightness and vanish near readback DBV 2048. Rounds 12–17 probed whether any writable register tunes that event structure (the "DC floor") at low brightness. All phases ran in the cumulative-landed replica state at `panelDC = 0`, `120 Hz`, `#FFFFFF`, `625 µs`, `ISO 6400`, guarded `unshare -m` debugfs transactions with per-probe readback and `esd_check_mode = reg_read` restored every time; sysfs BL was re-asserted and verified around every probe (`256 → 00:52 = 0x01 0xcc (460)`, `512`, `1024`, `2048` as noted).

- **Reproducible spec & summary (107 DNGs, 25 phases):** [spec_round12_17.json](spec_round12_17.json) and [summary_round12_17.json](summary_round12_17.json), verified via `analyze_2d_modulation.py --evidence-dir <private> --spec-json spec_round12_17.json --out-json summary_round12_17.json` (`EXIT=0`).
- Probe cmdfiles were ad-hoc single writes with readback (documented inline below); the PAM interpolation generator is [gen_r13_cmdfiles.py](../ddic_round13_pam_20261119/gen_r13_cmdfiles.py).

## 2. Probes and Results (all frames, no filtering)

| Round | Probe (state, sysfs BL) | Files | Mean `raw` | Mean `lt065` | `binned_min` |
|---|---|---:|---:|---:|---:|
| R12 | `53:95` ref `44 50` (cumulative, 256) | 4 | 0.612 | 0.352 | −2.64 |
| R12 | `95 = 33 58 / 22 70 / 11 88 / 00 a0 / 55 28` | 4×5 | 0.698 / 0.498 / 0.728 / 0.616 / 0.613 | 0.306–0.366 | −2.32…−3.51 |
| R13 | PAM block 25% / 50% / 75% / dc-on (256) | 4×4 | 0.652 / 0.645 / 0.799 / 0.590 | 0.282–0.347 | −1.51…−4.04 |
| R14 | cumulative at 2048 (latch) | 3 | 2.464 | 0.138 | −0.24 |
| R14 | then sysfs 2048→256, **no register writes** | 4 | 0.608 | 0.354 | −2.79 |
| R15 | sysfs 512 / 680 / 820 / 1024 / 1360 / 1700 | 4×6 | 0.664…1.729 | 0.345→0.181 monotone | −3.49…−0.89 |
| R16 | `23:85=0x14` (512) | 4 | 0.657 | 0.339 | −2.48 |
| R16 | `4F:81=0x06` (512) | 4 | 0.649 | 0.329 | −3.65 |
| R16 | `53:A2` tail mid `42 63 80` (512) | 4 | 0.717 | 0.322 | −3.40 |
| R16 | `51:A2 = 70 70 70 70` overshoot (512) | 4 | 0.602 | 0.349 | −2.87 |
| R16 | `24:9D = 0x0e` revert (512) | 4 | **0.246** | **0.416** | **−5.57** |
| R17 | PAM 75% vs dc-on, 8 frames each (256) | 8+8 | 0.662 / 0.713 | 0.332 / 0.311 | −3.09 / −3.33 |

## 3. Findings

1. **On the six probed compensation knobs no reproducible event improvement was found (confirmed-on-target, negative result):** across `53:95` interpolation (`00 a0 → 55 28`), full-block PAM interpolation (25/50/75/100% between `dc-off` and `dc-on`), `53:A2` tail interpolation, `51:A2` overshoot, `23:85` bit clear, and `4F:81` divider candidate, the event statistics stayed in the same band (`lt065 ≈ 0.28–0.37`, `binned_min ≈ −1.5…−4.0` at DBV 460/512) while the mean brightness also stayed constant — the internal feedback absorbs these tables at this operating point. The R13 `pam75` apparent improvement (`bmin −1.51` vs `−4.04`) did not reproduce in the 8-frame R17 statistics (`lt065 0.332` vs `0.311`, worst blocks `−3.09` vs `−3.33`): compatible with sampling noise, cause not established.
2. **`24:9D = 0x8e` is required for the compensated level (confirmed-on-target):** reverting it alone (R16 `9d0e`) collapsed the signal `≈0.65 → 0.246 DN` and deepened the events (`lt065 0.416`, `bmin −5.57`) — consistent with the R19 core2/core3 contrast at 1024 (`0.323` vs `0.896 DN`); removing `9D` only enlarges the deficit the chop must cover.
3. **On the single tested `2048 → 256` sysfs transition without register writes the optical dips returned (confirmed-on-target observation):** entering fresh at sysfs 2048 gave the clean regime (`lt065 0.138`, `bmin −0.24`); lowering sysfs to 256 with **no register writes** put the emission back in the deep-event regime (`0.608 DN`, `lt065 0.354`, `bmin −2.79`). This shows the clean 2048 regime does not survive that BL drop; it does **not** establish a general latch-reset law for every BL change (no readback was taken in the after-transition state; the register values themselves were not re-verified then).
4. **Mean dip fraction falls non-strictly with sysfs BL; worst-block depth is not monotone (confirmed-on-target):** mean `lt065` over `512 / 680 / 820 / 1024 / 1360 / 1700` reads `0.345 / 0.313 / 0.291 / 0.291 / 0.240 / 0.181`, while the worst `binned_min` is non-monotone (`−1.71` at 820 → `−3.46` at 1024); at sysfs 2048 (R14) the mean `lt065` was `0.138` — reduced, not zero. No sharp threshold below 2048 was found.

## 4. Interpretation

The DC-mode events below the floor appear intrinsic to this DDIC's DC-dimming architecture: on the six probed "brightness-scale" knobs no reproducible tuning of the events was found, and the regime follows the DBV-driven deficit. The practical consequence for the owner-facing recipe: the DC state suppresses the diagonal carrier signature in every measurement while the dip-block fraction is lower than PWM at every probed BL; at sysfs `512` the worst-block depth was slightly worse than PWM in R9 (full recipe: `binned_min −1.48` vs `−1.27`), and at the minimum (`460`) the recipe trades the `~720 Hz` wave for sporadic `0.5–0.8 ms` dark events. Whether that trade is perceptually acceptable requires the DC-coupled photodiode or the owner's direct trial (started 2026-11-19: the 3-write recipe was left enabled on the target at sysfs 512 for the owner's evaluation).

## 5. Verification

- Both phones restored and verified after the campaign (Lenovo: `BL=6873` via `screen_brightness 104→105`, `panelDC=0`, `GET_global=0`, `120 Hz`, `ZRamSettingsActivity`, `esd_check_mode=reg_read`, temp files and MediaStore rows removed; A001: `PHOTO 1×` RAW off, `OpenCamera` baseline). The end-of-campaign 37-field snapshot diff showed **36/37 fields matching** with one real leftover (`23:85=0x14` from the R16 probe, absent from the restore template); the corrective write `W 23:85=0x15` printed `W_OK` plus a readback `0x15` in the terminal — that control read is **reported**, not tee'd to the evidence dir. ISO note: the camera UI was set to manual ISO 6400, but all 107 campaign DNGs carry EXIF ISO 3200 (the UI setting did not take effect); every campaign-internal comparison shares the same actual ISO.
- Analyzer CLI `EXIT=0`; spec/summary regenerated from the saved session outputs; `python3 -B` / `python3 -OB -m unittest discover -v` in [pwm_06x_dng_bench_20261119](../pwm_06x_dng_bench_20261119/): `7/7`.
