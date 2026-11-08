# Corrected-method isolated-field series — COMPLETED

Owner instructed execution of the immediately preceding night plan at22:22UTC;
[authorization](authorization.json). This covers the finite scope below, not
arbitrary new values/combinations or permanent image changes.

Completed22:24–22:27UTC: all four candidates once, nine states, each with verified
DBV/redraw/7s hold. [Run](run.json), [analysis](analysis.json),
[conclusions](result.md). Stock/policy/logger/Enforcing returned, no recovery reboot.
This permission is consumed; no automatic rerun or additional combinations.

The [factory ON positive control](../../dsi_stock_on_control_20261106/with_redraw/analysis.json)
now works after a visible screen redraw without additional logged DSI writes.
Earlier isolated-field negatives lacked that application step. This proposal is
a materially changed method, not permission to repeat the consumed old approvals.

## Exact finite scope

Use the same live BOE ILI97701A cmd_v4 OFF base,875B/75packets, and only these
previously prepared independent variants; each once, **no combinations**:

| Variant | Existing candidate | Only changes from live OFF |
|---|---|---|
|mode90|[one-byte program](../../dsi_mode_trial_20261106/dc_off_mode90.bin)|packet12,page23:80,50→90;1byte|
|thresholds|[program](../thresholds.bin)|packet6/page23:A9 and9/page24:9D,0E→8E;2bytes|
|page53|[program](../page53.bin)|packets16/17,95/A2 payloads from native ON;11bytes|
|page63|[program](../page63.bin)|packets27/28,F2/F3 payloads from native ON;10bytes|

All untouched bytes, headers, HS mode, delays and F0 framing stay unchanged.
Sequence: stock → mode90 → stock → thresholds → stock → page53 → stock → page63
→ stock. After **every** table: standard DBV3600, open/cancel the same stock Screen
timeout chooser without selecting a preference, verify state, then7s observation.
Do not claim that the physical carrier frequency is unchanged merely because the
band spacing looks similar, or that a denser pattern proves >=2000Hz.

## Checks and return

- Existing native writer/chunk boundaries/pending-counter and return checks;
  payload/type/HS comparison, DMA-error check through holds, no probe misses.
- Software120Hz/manual brightness, fixed camera720p/100µs/ISO6400/AE-AF OFF,
  verified manual focus and stabilization. Recheck actual settings before recording.
- No new power/OTP/NVM command, image flash, DTBO/module replacement, persistent
  PWM preset, AVB/slot/security change or arbitrary register sweep.
- Stop on the first unexpected state/transfer. If pending data or applied state
  is uncertain, ordinary reboot to the unchanged stock display initialization;
  do not blindly append/flush. Existing physical bootloader return remains available.
- End with full stock OFF plus redraw, original target policy/logger/Enforcing,
  removal of own traces/files. Camera stays ready by the owner's request.

This is a causal field-identification experiment, **not** an established higher-PWM
profile. Exact-operation confirmation is recorded above; result belongs in run.json.
