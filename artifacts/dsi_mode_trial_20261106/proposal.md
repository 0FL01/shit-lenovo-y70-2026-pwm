# One-byte mode-selector experiment — completed

Status: completed once at19:44–19:45UTC after [authorization](authorization.json).
[Native execution](run.json) and [optical analysis](analysis.json) confirm the
isolated value changes the image but does not establish a higher-frequency profile.
The original full OFF program and target settings were restored. No flash occurred.

The first preparation failed before any debugfs callback (`dd` rejected `nocreat`
despite advertising it in help); [failure evidence](run_dd_option_failure.json)
records zero candidate attempts and successful ordinary reboot. The corrected
attempt applied the candidate exactly once. Do not repeat either run.

## Exact change

- Target only: XT2611-1 / W3WWS36.65-64-4-1 / BOE ILI97701A cmd_v4.
- Base: full live [DC OFF program](../device_tree/selected_boe_v4/qcom,mdss-dsi-dc-off-command),875bytes/75packets.
- [Candidate](dc_off_mode90.bin): only byte offset126, packet12 (zero-based),
  page23/opcode80 data **50→90**.90 comes from the same panel's live DC ON program.
- All other bytes, page transitions, ordering, HS mode, delays and batch flags
  are unchanged; [offline validation](validation.json). The isolated combination
  was unverified before this test; it is still not an approved daily-use preset.
- Do not alter thresholds23:A9/AA,24:9D/9E, init24:80/81,53/63 or OD tables.

## Bounded trial

1. Re-identify both phones; verify build/panel/current module, root/Enforcing,
   awake/dismissed keyguard, DC0, stable DBV3600, software120Hz. Camera720p,
   actual100µs/ISO6400, AE/AF off, fixed focus; no automatic exposure.
2. First replay the unmodified full DC OFF program through the native guarded
   transport, verify packets/native results and record7seconds of optical baseline.
   Only if the native transport check succeeds, apply the one-byte candidate once,
   record7seconds, then replay the unmodified full DC OFF program and record its
   return. Compare the three optical segments after acquiring the complete clip;
   native success alone will not be reported as optical success.
3. Restore target settings/logging/tracing. No flash, DTBO/module/table replacement,
   persistent profile, AVB/slot/security changes, register sweep or alternate byte.

## Transport invariants

- [Read-only discovery](../dsi_tx_readonly_recon_20261106.json) located
  `dri/9800000.qcom,mdss_mdp/DSI-1/tx_cmd`; use a private mount namespace, not a
  permanent global debugfs mount. `panel_parse_para` is not used.
- Native writer accepts at most255 decoded bytes per write; shell write count
  does **not** prove successful transfer. Source pinfa008c43c070ff20faa33853649f5dfd4c427e99:
  `msm/sde/sde_connector.c:3232–3337`, `msm/dsi/dsi_display.c:1527–1623`.
- Original first74packets have BATCH0x40; final page00 packet has0x00. Keep whole
  packets in chunks253/247/254/110/11bytes, final non-batched packet separately.
  This queues875bytes, then native code sends the group under panel_lock.
- Observe native entry pending-count and returns before allowing the next chunk;
  expected pre-write counts0/253/500/754/864. In the captured current module,
  `dsi_display_cmd_transfer` copies arg2 to x19 at0x1a1774 and accesses the count
  at`display+0x694`; it clears it at0x1a197c before transmission. This is a
  binary-specific trace layout, not a stable ABI or permission to write memory.
- Require matching module evidence, complete trace, original native payloads
  for baseline/return and exactly one changed payload for the candidate. Stop on
  unexpected pending data, negative results, dropped trace or changed screen state.

## Return and interpretation

Return is the full unmodified DC OFF program, not a cached UI0 request that may
be skipped. If partial staging or a failed transfer makes the buffer/state
uncertain, do not append/flush more data blindly: ordinary reboot restores stock
initialization and clears this volatile buffer. No image write is part of return.
If ADB is lost, stop remote writes; physical restart remains available from the
previously demonstrated access path. A temporarily black display is a real risk.

A changed optical pattern would identify an effect of this field in this context;
no change would reject it as a sufficient isolated selector. Neither result alone
certifies Hz, eliminates all modulation, or approves a permanent Android preset.
