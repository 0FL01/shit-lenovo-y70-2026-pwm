# Partition refresh ioctl: bounded selected-BOE-v4 check

2026-11-08. **R3 active.** Offline hypothesis: the current DRM partition-refresh
ioctl is an already available way to send a different panel-specific command
profile on the selected BOE v4, potentially worth testing optically. **Rejected
for the saved selected-DT / current-module path:** the required enable property
and PRR command sets are absent. This is not a proof about all runtime writers,
boot-time overlays or physical PWM Hz.

## Evidence

- Selected target DT `device_tree/selected_boe_v4/` identifies
  `qcom,mdss_dsi_mot_boe_ili97701A_682_1440x3168_dsc_cmd_v4`. Search of its
  root and eight timing nodes: no filename containing `partition` or `prr`, in
  particular no `qcom,partition-refreshrate-enabled`,
  `qcom,mdss-dsi-partition-refreshrate-on-command` or
  `qcom,mdss-dsi-partition-refreshrate-off-command`. The eight timing groups
  contain ordinary/special idle modes, which are **not** this PRR configuration.
- Current saved target `kernel/gki_r59/target_vendor/msm_drm.ko`, SHA256
  `1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804`:
  Ghidra 12.1.4 `dsi_panel_parse_prr_config` at `.text+0x1bd45c` reads
  `qcom,partition-refreshrate-enabled` via its `read_bool` callback, masks bit0
  and writes the result to `panel+0x898`; further PRR settings are parsed only
  if enabled. See `parse-head/excerpt.c:16–26` in the approved external cache
  `.../ghidra-toolkit-20261107/partition-refreshrate-20261108/`.
- The same target module's `dsi_panel_set_partition_refreshrate` at
  `.text+0x1c3bc4` copies the 24-byte request into panel state *before* locking
  `panel+0x410`, but sends PRR DISABLE set `0x4b` or mutates/sends PRR ENABLE
  set `0x4a` only under `*(char *)(panel+0x898)==1` and a separate mode guard.
  Outside the guard it returns zero after unlocking; success of an ioctl alone
  would therefore **not** prove that a DSI command was sent. See
  `set-head/excerpt.c:16–43`, `set-tail/excerpt.c:12–34`,
  `set-end-correct/excerpt.c:2–26` in that cache. Offset addresses are ELF
  `.text` offsets, **not live kernel VAs**.
- Pinned Motorola source reference
  `/home/stfu/.cache/opencode-tmp/opencode/pwm-source-recon-20261106/msm/dsi/dsi_panel.c:6190–6210,8757–8806`
  independently expresses the same boolean/guard shape; it is not claimed
  byte-identical to the current target binary. No source-controlled frequency
  multiplier was established.

Only Ghidra `brief` manifests and `decompile --lines` excerpts were read; full
decompiled C remains stored but unread in the approved external cache. Missing
selected-DT enable plus target guard rules out this *ready PRR ioctl path* as a
panel-specific high-frequency profile under that configuration; it does not
exclude an unsaved boot overlay, other commands, indirect effects of storing
request state or future firmware. Neither UI refresh nor partition refresh is
physical emission frequency. No ADB, DSI, camera, settings, flash or reboot;
the A9-only intermediate optical baseline and separate A0D1C1 confirmation
boundary remain unchanged.
