# `panelCellId`: bounded page/lock check for the proposed panel trial

**Status:** `confirmed-on-target` for the *stored current* `msm_drm.ko` code and
selected BOE v4 DT bytes; **unknown** for a concurrent invocation on the phone.
Offline only; no cell ID content was read, no ADB/DSI/sensor/setting operation.
This is an interference check, **not** a PWM-register decoder or a Hz result.

## Testable hypothesis and result

Hypothesis: the selected-DT `panelCellId` page-change/read/reset sequence is
atomic under the same panel mutex used by the stock DC-command sender.
**Rejected for this bounded target-code path:** page-select and reset sit
*outside* that mutex. This establishes a possible interleaving boundary, not
that a cell-ID read, panel glitch or frequency change actually occurred.

Selected `artifacts/device_tree/selected_boe_v4/` has empty boolean properties
`qcom,cellid-read-enabled` and
`qcom,mdss-dsi-panel-cellid-send-command-enabled`. Its cell-ID command bytes:

| Property suffix | Bytes | Meaning within the command stream |
|---|---|---|
| `panel-cellid-send-command` | `39 00 00 00 00 00 04 ff 5a a5 1d` | page `1D` |
| `panel-cellid-command` | `06 01 00 01 00 00 01 80` | DCS read `80`, configured read length 23 |
| `panel-cellid-send-back-command` | `39 00 00 00 00 00 04 ff 5a a5 00` | page `00` |

Ghidra 12.1.4 on `artifacts/kernel/gki_r59/target_vendor/msm_drm.ko`, SHA256
`1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804`,
via `06-tools/ghidra_decompile.py`. Offsets below are **ELF `.text` offsets**,
not live VAs. Only `brief` manifests and `decompile --lines` excerpts were read;
full C stays unread in approved external cache under
`/home/stfu/.cache/opencode-tmp/opencode/ghidra-toolkit-20261107/cellid-atomicity-20261108/`.

- `dsi_panel_tx_cellid_cmd` `.text+0x1c5280` (120 instructions):
  `target-cellid-excerpt/excerpt.c:26–55` calls
  `dsi_panel_tx_send_mot_cmd` **before** `mutex_lock(param_1+0x82)`;
  `target-cellid-tail/excerpt.c:9–13` releases the mutex **before**
  the second send. `target-cellid-excerpt/manifest.json` also orders
  call instructions: `0x1c52c8` send, `0x1c5340` lock,
  `0x1c53b4` host read, `0x1c53fc` unlock, `0x1c5414` send-back.
- `dsi_panel_tx_send_mot_cmd` `.text+0x1c5460` (66 instructions):
  `target-send-excerpt/excerpt.c:22–43` calls `dsi_host_transfer_sub`
  per descriptor; its `brief` lists **no mutex callee/direct call**. These two page sends
  do not acquire the panel mutex internally in the verified function.
- Stock DC sender `dsi_panel_send_param_cmd` `.text+0x1c456c`
  (`target-dc-sender-head/excerpt.c:18–29`,
  `target-dc-sender-loop/excerpt.c:2–19,38–40`) acquires **the same**
  `param_1+0x82` mutex before its descriptor loop and releases it afterward.
  `panelCellId_show` `.text+0x1af058` has a direct call to the cell-ID
  function, and its `brief` has no outer mutex call. This checks only these
  concrete caller/helper functions; other shared transport serialization and
  unknown external invocations are not excluded.

No `ff 5a a5 1d` DSI transfer was found in the three saved historical S0C1
stage logs (`baseline`, `s0c1`, `return_s0c1`) under the approved private cache
`dsi-coupled-on-20261107/`; these logs also previously showed no extra writes
during redraw/hold. This is **not** a trace of the unapproved A0D1C1 trial.
`06-tools/run_dsi_mode_trial.py` does not call `panelCellId_show`; do not read
that sysfs node as an allegedly passive check during any DSI experiment. The
existing exact transmitted-packet checks and short A9/9D readbacks remain
necessary, but do not prove all future page transitions impossible.

**Next boundary:** neither panel-cell-ID bytes nor external concurrent
readers were measured. Do not infer physical panel revision, DDIC period,
PWM depth or frequency. A0D1C1 remains NOT AUTHORIZED / NOT SENT and its
one-series operation confirmation remains separate.
