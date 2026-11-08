# Rate-switch interval multiplier: not an OLED PWM multiplier

2026-11-08. **R3 active.** `confirmed-on-target` for the saved current
`msm_drm.ko` code and selected BOE v4 DT; actual live transition, any boot
overlay, and physical OLED PWM Hz remain `unknown`. Offline only.

## Falsifiable hypothesis and evidence

Hypothesis: `qcom,mdss-dsi-rate-switch-interval-multiplier` could be the
requested ×2–3 physical emission-rate control. The pinned Motorola source
`/home/stfu/.cache/opencode-tmp/opencode/pwm-source-recon-20261106/msm/dsi/dsi_panel.c:5879–5915,8535–8648,8655–8673,8693–8745`
instead uses this value for the **minimum time between selected UI refresh
transitions**, `floor(1000 * multiplier / previous_refresh_hz) + 2` ms.
The neighboring source comment at line8606 gives a different formula; the
executable expression at8608 is the evidence. The delay is implemented with
sleep, not by scaling a DDIC register.

- All root and eight timing nodes in the saved
  [`selected_boe_v4/`](device_tree/selected_boe_v4/) lack the enabling
  `qcom,mdss-dsi-rate-switch-interval-enabled` boolean, the `-multiplier`
  property and `qcom,mdss-dsi-rate-switch-min-forced-delay`. Their ordinary
  timing-switch command arrays still exist; absence of this optional delay
  feature does not disable normal refresh switching.
- Current stored target [`msm_drm.ko`](kernel/gki_r59/target_vendor/msm_drm.ko),
  SHA256 `1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804`:
  Ghidra12.1.4 `dsi_panel_parse_rate_switch_config` `.text+0x1bcb40`
  `parser-excerpt/excerpt.c:19–45` sets the boolean bit in `panel+0xcd9`,
  defaults the multiplier to **2** in `panel+0xcdc` if absent, and defaults
  forced delay to0. Default2 is not proof that the feature is enabled.
- Target `dsi_panel_switch` `.text+0x1c3380`
  `switch-head/excerpt.c:22–109` skips the interval check when `panel+0xcd9`
  bit0 is clear; on an enabled 24/30/60→90/120 transition it uses the
  multiplier in the same *elapsed-milliseconds* threshold at lines38–57.
  If the threshold fails it can transmit the ordinary timing-switch set
  `0x15`, wait using `usleep_range_state`, then transmit that set again.
  With the interval check disabled it still sends the normal set once at
  line99. **Two timing-switch sends would not mean twice the OLED PWM Hz.**

The named excerpts/`brief` manifests are stored under the approved external
cache `/home/stfu/.cache/opencode-tmp/opencode/ghidra-toolkit-20261107/rate-switch-interval-20261108/`.
Only `brief`/`decompile --lines` excerpts were read, not the full generated C;
ELF `.text` offsets are not live kernel addresses. Target module source-to-binary
identity is not assumed; the selected-DT absence and target code were checked
separately. This closes only the proposed *rate-switch delay multiplier* as a
ready physical PWM control in the selected path. It does not rule out other
DDIC writers, a dynamic overlay or a future profile, and does not identify Hz.
No phone/ADB, DSI, camera, settings, sensor, reboot or flash operation occurred.
A9-only remains the best intermediate optical baseline; A0D1C1 still needs
its separate exact approval and has not been sent.
