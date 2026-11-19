# Recipe bug-hunt protocol (fast path)

`recipe_bug_hunt.sh` re-runs the R21 stability/defect regression against the
3-write DC recipe (`23:A9=0x8e`, `24:9D=0x8e`, `23:80=0x90`) on a live
bench phone and prints a PASS/DEFECT table. One command covers the known
matrix; new system actions plug in as one-line cases (template below).

## Preconditions

- Remote ADB per `03-investigation/adb-remote.md` (no `kill/start-server`),
  both devices re-identified; target must be the XT2611-1 with the audited
  `msm_drm.ko` (`1bec69fa…`) and `esd_check_mode=reg_read` at rest.
- Files staged on target (`/data/local/tmp/`): `rbd_ddic.sh` (guarded
  runner, identical mechanics to `ddic_regdump.sh`: `unshare -m`, debugfs
  `tx_cmd/rx_cmd`, page select `FF 5A A5 <page>`, page-0 return, ESD
  `esd_sw_sim_success → reg_read` in `trap EXIT`), plus two cmdfiles:
  - `probe_state.cmd`: `R 23 1 0xA9`, `R 24 1 0x9D`, `R 23 1 0x80`,
    `R 23 3 0xC1`, `R 00 2 0x52` (read-only, ESD-safe).
  - `recipe_on.cmd`: `W 23 0xA9 0x8e`, `W 24 0x9D 0x8e`, `W 23 0x80 0x90`
    + the five reads above (apply + verify in one transaction).

## State probe interpretation

| Readback | Meaning |
|---|---|
| `A9=0x8e, 9D=0x8e, 80=0x90, C1=00 00 10` | recipe alive (DC mode, shallow-landing core) |
| `A9=0x0e, 9D=0x0e, 80=0x50, C1=00 02 xx (DBV-scaled)` | stock PWM (recipe killed or never applied) |
| `A9=0x8e, 9D=0x8e, 80=0x90` but the state was reached via the **stock** dc-on dispatch | internal landing is the stock DEEP one — the registers alone cannot tell; the optical signature ([1,0] dip depth at 625 µs) or the entry history must decide |
| `00:52` | telemetry only — sysfs BL value actually on the panel (watch for framework re-asserts) |

## The matrix (each case = action → probe → expect)

| ID | Action | Expected (R21 result) |
|---|---|---|
| T1 | sysfs sweep `256 680 1024 2048 3600 6873 1024 512` | PASS — registers intact at every step |
| T2 | adaptive brightness ON + setting moves | PASS — registers intact under framework writes |
| T3 | refresh forcing `60/90/144/120` (`min/peak_refresh_rate`) | PASS — DSI mode-sets do not touch the recipe |
| T4 | screen OFF → ON (power button) | **DEFECT №1 — stock re-init; heal = re-apply** |
| T5 | stock Flicker prevention `PUT_global 0` (root only) | **DEFECT №2 — driver dc-off kills the recipe; heal = fresh 3-write entry** |
| T5b | stock Flicker prevention `PUT_global 1` | core registers read the same, internal state becomes the stock deep landing — treat as contamination, re-apply after |
| T6 | *new system action template*: run the action, probe, compare against the interpretation table, restore state, record PASS/DEFECT |

Heal after any DEFECT: run `recipe_on.cmd` once (idempotent; verified for both
kill paths and the prepared deep case in R20/R21), then re-probe; finish by
restoring the owner's preferred sysfs BL. Save every probe output to the
evidence dir with a tag; the hunt itself changes no camera state.

## Known-defect ledger (2026-11-19, R21)

1. Screen off/on kills the recipe → applier must re-apply on every `SCREEN_ON`.
2. Stock `display_dc_mode_enabled` dispatch kills (PUT 0) or re-lands (PUT 1) →
   applier must re-apply on every change of that setting; keep the stock
   toggle off.
3. Reboot kills (session-only by design; not tested live).

Re-run cadence: after any driver/OTA update, after any recipe change, or
whenever the owner reports a regression — the whole matrix is ~5 minutes.

Reference: [R21 result](../artifacts/ddic_round21_stability_20261119/result.md);
recipe provenance: [R18–R20](../artifacts/ddic_round18_20_recipe_20261119/result.md).
