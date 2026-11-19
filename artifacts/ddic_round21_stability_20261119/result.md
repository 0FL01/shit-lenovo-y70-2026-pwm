# Round 21: Stability / Defect Hunt of the 3-Write Recipe Under Real Usage (`2026-11-19`)

> **Fast path:** the hunt process of this round is codified for reuse in [06-tools/RECIPE_BUG_HUNT.md](../../06-tools/RECIPE_BUG_HUNT.md) (protocol) and [06-tools/recipe_bug_hunt.sh](../../06-tools/recipe_bug_hunt.sh) (one-command regression; the required target files are staged under the protocol names).

## 1. Purpose and Method

The owner's live trial of the 3-write recipe (`23:A9=0x8e`, `24:9D=0x8e`, `23:80=0x90`) was positive in direction; this round hunts for defects under the real use-case: brightness moves (manual and adaptive), refresh-rate changes, screen off/on, and the stock Flicker-prevention toggle. Method: apply the action on the live phone, then read back `23:A9`, `24:9D`, `23:80`, `23:C1`, `00:52` through the guarded read-only debugfs probe (`unshare -m`, `esd_sw_sim_success → reg_read`). No camera frames; the persistence question is register-level, and the optical re-derivation per sysfs BL was already mapped in R15.

## 2. Results

| # | Test | Result | Registers after |
|---|---|---|---|
| 1 | **Brightness slider sweep** (sysfs `256 → 680 → 1024 → 2048 → 3600 → 6873 → 1024 → 512`, recipe ON) | **PASS — recipe survives the full range** | `A9=0x8e`, `9D=0x8e`, `80=0x90`, `C1=00 00 10` at every step; `00:52` tracked each sysfs value |
| 2 | **Adaptive brightness ON** (framework wrote its own sysfs values `911`, then `5321`) | **PASS** | recipe registers intact, `C1=16` |
| 3 | **Refresh-rate cycle** (`min/peak_refresh_rate` forcing `60 → 90 → 144 → 120`; actual FPS verified each step) | **PASS — DSI mode-sets do not touch the recipe** | recipe registers intact at every rate |
| 4 | **Screen OFF → ON** (power button; also an 8 s variant) | **DEFECT №1 — recipe killed** | after cycle: `A9=0x0e`, `9D=0x0e`, `80=0x50` (stock re-init); the framework also re-asserted its own brightness (`00:52 = 06 3f`) |
| 4b | Heal: re-apply the 3 writes after the screen cycle | **PASS — heal works** | `A9=0x8e`, `9D=0x8e`, `80=0x90` restored |
| 5 | **Stock Flicker prevention toggle** (`PUT_global display_dc_mode_enabled` as root; the shell-uid attempt correctly failed with `WRITE_SECURE_SETTINGS` denial) | `PUT 1`: core-3 register **values read the same** (`0x8e/0x8e/0x90` — the stock `dc-on` core equals ours) but the driver dispatches its full table and re-lands the internal state; **`PUT 0`: DEFECT №2 — driver's `dc-off` table kills the recipe** | after `PUT 0`: `A9=0x0e`, `9D=0x0e`, `80=0x50`, `C1` back to PWM telemetry |
| 5b | Heal: fresh 3-write entry after `PUT 0` (registers at stock `dc-off` = the canonical fresh-entry context) | **PASS** | recipe restored, `C1=16` |
| 6 | Reboot | **expected kill (not tested live)** — the recipe is session-only by design; stock re-init on boot |

## 3. Consequences for a Usable Android Implementation

1. **The recipe is robust against everything the user does with brightness and refresh rate** (manual slider, adaptive brightness, 60–144 Hz) — the registers persist through all of it.
2. **It is killed by screen off/on** (the most frequent event in real usage): an applier must re-apply the 3 writes on every screen-on (a root daemon listening for `ACTION_SCREEN_ON` / a display-state callback, re-sending the three packets idempotently — the heal is one guarded transaction, verified twice here and in R20).
3. **It is killed by the stock Flicker-prevention `OFF` dispatch** (and `ON` re-lands the internal state to the stock deep landing while the core registers read identically): the applier should also re-apply after any `display_dc_mode_enabled` change, and the stock toggle should be left off.
4. The re-apply after both kills used the same 3-write transaction and restored `C1=16` both times; no state divergence was observed between the two kill paths.

## 4. Verification and State

- The phone was returned to the owner-trial state after the hunt: recipe ON (`A9=0x8e`, `9D=0x8e`, `80=0x90`, `C1=16`), sysfs `512`, `screen_brightness=20`, launcher foreground; `esd_check_mode=reg_read` after every probe (guarded transactions).
- Known scope limits: register-level persistence only (the optical properties per sysfs BL follow the R15 map); one phone, one session; reboot kill untested live (by design session-only).
