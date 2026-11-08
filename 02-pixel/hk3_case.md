# Pixel 8 Pro HK3: exact mechanism and portable engineering insights

**Primary artifact:** https://github.com/updateing/android_kernel_google_zuma/commit/6f7795dcf7b6a5c6f1c344c9de05ca10489b7d4d

## Baseline

Google Pixel 8 Pro (Tensor/Exynos-based display path), Samsung HK3 OLED panel. User-facing PWM rate typically described as 240 Hz. A custom kernel built from modified driver enables changing the panel's dimming command sequence. Not a generic Android property.

## What the patch ACTUALLY does (verified by source diff)

- File: `google-devices/shusky/display/panel-google-hk3.c`.
- Adds a 4-byte mutable `u8 freq_cmd[4] = {0x00, 0x43, 0x43, 0x03};`.
- Exposes values through `module_param_array(freq_cmd, byte, NULL, 0644);`.
- Adds `hk3_send_dimming_freq_cmd(ctx, need_unlock, cmd)`.
- That function writes panel-specific DSI bytes via `EXYNOS_DCS_BUF_ADD(ctx, 0xBD, 0x21, ...);`.
- Uses the FIRST data byte as-is or with `| 0x80` depending on `FEAT_EARLY_EXIT`, and switches to known HBM-specific command variants if `FEAT_HBM` is set.
- Explicit unlock / update / relock when called outside an existing command batch. The command order and update/lock phases matter.
- Replaces the original hardcoded `0xBD, 0x21, 0x01/0x81, 0x83, 0x03, 0x03` branch with a runtime/default selection.
- In local HBM for fingerprint, resets to default on entry and restores override on exit. This is a required regression scenario to cover.
- Writes to sysfs update the parameter array. The changed values are transmitted when relevant driver paths call `hk3_set_override_dimming`; it is NOT a universal frequency register write. On that implementation screen off/on was used to make it take effect.

## Reported practical result (separate from code proof)

Android Central describes testing at 3840 Hz (five days), a reported upper level at 4800 Hz, some green tint and inconsistent color when LTPO refresh varies. See https://www.androidcentral.com/phones/google-pixel-8-pro-display-upgrade . Original commit author describes trial-and-error discovery and severe artifacts at higher values.

The byte value to optical Hz relationship is HK3-specific and must be remeasured; sources contain different upper-rate descriptions. Do not assume `0x05` or `0x07` means the same multiplier on any other panel.

## Transferable PATTERN, not transferable bytes

1. Locate exact panel-specific state machine and existing dimming/refresh/HBM command sequences.
2. Identify the native command altering OLED modulation with A/B empirical optical measurement.
3. Make default behavior identical to stock unless the override is intentionally enabled.
4. Guard override against exact panel identity and revision; accept only empirically known profiles, not unbounded raw bytes.
5. Integrate into the same lifecycle calls that stock drivers use: initialization/reinit, brightness transition, refresh switch, HDR/HBM, AOD/doze, fingerprint HBM and resume.
6. Track command order, unlock/update/lock and panel timing (vsync/TE), using the Qualcomm equivalent, not Exynos macros.
7. Expose temporary runtime control for research, logging selected profile and applied state. Support immediate reset to stock.
8. Measure actual optical response vs baseline at IDENTICAL brightness, refresh rate, content and environmental conditions.

## Specific mistakes to avoid on XT2611-1

- The path `/sys/module/panel_google_hk3/parameters/freq_cmd` and its semantics are Pixel-only; this interface does not exist on XT2611-1.
- The Pixel `0xBD,0x21,...` sequence is HK3-specific; on the BOE controller `0xBD` may select a different function or be unimplemented, so target sequences are derived from the target driver.
- Do not transplant `panel-google-hk3.c` to Snapdragon/Qualcomm, which uses different display frameworks and potentially different closed vendor paths.
- Do not assume higher frequency is better if duty cycle/modulation amplitude/color uniformity are severely altered.
- `module_param_array(...,0644)` on Pixel does not carry over as a production model: unbounded writes, implicit lifecycle refresh; prefer validated enum/preset, exact IDs and an explicit application/restore transaction on XT2611-1.

## Target-specific design sketch (PSEUDOCODE ONLY; DO NOT APPLY AS SOURCE)

```text
on_panel_detected(panel_id, revision):
    ensure(panel_id == IDENTIFIED_TARGET_ID && revision in TESTED_REVISIONS)

set_pwm_profile(profile):
    ensure(profile in {STOCK, VERIFIED_PROFILE_A, VERIFIED_PROFILE_B})
    ensure(panel_is_on && state_is_safe_for_change)
    lock(display_command_lock)
    wait_for_required_panel_te_or_safe_timing()
    send_vendor_specific_unlock_if_required()
    send_VERIFIED_TARGET_DSI_sequence(profile)
    commit_latch_if_required()
    send_vendor_specific_lock_if_required()
    record_applied_state()
    unlock(display_command_lock)

on_hbm_aod_fod_refresh_resume_transition():
    apply_correct_panel_profile_for_new_state_or_stock()

on_error_or_reboot():
    use_stock_panel_sequence()
```

Must be designed after the REAL target driver and register sequence are identified; no DSI bytes are provided or inferred in this sketch.

## Mini research questions for agent

- Where is Pixel's `hk3_set_panel_feat()` equivalent on avr?
- Which Qualcomm driver interfaces correspond to `EXYNOS_DCS_BUF_ADD` and vendor command batches?
- Is Motorola's Flicker prevention controlled via `vendor display HAL` or directly via kernel? Where are aliases, properties and state transitions?
- Which path holds `dimming` registers when screen is 1, 60, 120 or 144 Hz?
- Does fingerprint local-HBM reset DC dimming like Pixel's path?
