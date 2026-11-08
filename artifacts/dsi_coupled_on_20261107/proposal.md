# Large coupled-block control S0C1 — completed; owner rejected the profile

Owner confirmed the exact series and emergency ordinary reboot on2026-11-07;
see `authorization.json`. Series and separate requested manual viewing are now
complete; stock returned09:58UTC. See `result.md` and `owner_view/return/run.json`.
The pre-approval wording below records the original proposal, not current status
or permission to repeat. No emergency reboot was needed.

Target: XT2611-1/PVT, W3WWS36.65-64-4-1, selected BOE ILI97701A cmd_v4/IDd2.
R3 active. This is **one coarse interaction experiment**, not a daily-use profile
and not a claimed2–3× frequency setter. Owner accepts panel destruction and
requires large frequency-increase attempts; no tiny register sweep is proposed.
Exact operation approval remains required before sending this new combination.

## New variable and falsifiable question

Already measured: stock S0C0 retains the fine train; selector-pair S1C0 and
full native ON S1C1 suppress it; isolated A9 is sufficient for suppression.
Isolated mode90/page53/page63 replacements did not remove the train with the
corrected redraw method. These observations do not test simultaneous effects
of the remaining ON program while the causal selector remains OFF.

**S0C1:** start from the complete native75-packet ON table, but keep23:A9 and
24:9D at their stock OFF value0E. All other values/order/header/batching are
native ON. This changes32 packets/83bytes versus stock OFF, but only two bytes
versus native ON. The packet count is not a frequency multiplier.

`hypothesis`: the coupled non-selector program may change emission timing when
the fine-train branch is retained, although its isolated parts did not. It may
instead change only gamma/OD/brightness or cause faults. A large new optical
train/fundamental shift would select further reverse-engineering targets;
an unchanged train would show no detected large optical effect in this state
and method, not prove unchanged physicalHz or rule out high-frequency support.
A positive result belongs to the entire residual block, not specifically to
synergy between mode90/page53/page63: other fields also change. No numeric2–3× prediction is justified
until an actual period/count field is decoded. Do not multiply unknown bytes
and label the result2–3× PWM.

The preserved best experimental panel baseline is A9-only, normalized q93 total
ratio0.2264067 to adjacent stock (same DBV3600/120/100us/ISO6400 nominal conditions;
`artifacts/dsi_selector_split_20261107/analysis_spatial_v2.json`). This diagnostic
stock bracket does not replace that baseline. Compare the new normalized image
component/full spectra with the saved A9 result, explicitly as a historical
comparison, not a simultaneous head-to-head or physical-Hz ranking. No repeat of
the consumed A9 experiment is included. Promote a new baseline only for supported
panel improvement; retain both original evidence sets and any geometry/scene limits.

## Exact finite operation, if separately approved

One sequence **stock OFF → S0C1 → stock OFF**, once per state, fixed native
DBV3600/software120/DC provider0. Full875-byte75-packet writes use the already
verified5-chunk batching/last-flush route under native locking. Reapply the same
standard DBV and verified chooser-open/cancel redraw after each table. Short
readback of23:A9,24:9D and00:52 must give0E/0E/0E10 for all three states; this
checks selectors/DBV, not every changed register. Capture7s holds with prepared
Pacman100us/ISO6400/AE-AF OFF, fixed focus/crop/stabilization. Analyse original
pixels, full spatial spectra and frame-wise phase, including possible stationary
components; no single harmonic or disappearance of q93 certifies>=2000Hz.

Expected new evidence: complete native payload/type/order/return checks,
readback, before/after optical return, and one camera file. No second candidate,
repeat, persistence, kernel/DTBO/AVB/slot change or flash is included.

## Preconditions and return

Re-identify transports; verify exact build/kernel/panel/root/Enforcing and module
identity. Require screen awake/manual state, DC0, logger0, ESDreg_read, no pending
raw batch/own probes. Save actual Android policy and native DBV, including dimmed
initial values. Refuse existing run/consumed authorization. Native timeout and
independent page0/ESD recovery protect short reads; do not reuse the broad reader.

Stop on unexpected trace, negative return/lost event, readback mismatch, camera
change, visual fault or owner discomfort. Restore full stock OFF plus same DBV
and redraw, verify optical return, page0/ESDreg_read, logger0 and own probe/file
cleanup; restore captured native DBV and Android policy. If a raw batch is
uncertain, do not append another batch: the proposed emergency return is an
ordinary reboot to unchanged stock display initialization, then identity/root/
Enforcing checks. This reboot must be included in the exact approval; no flash
fallback. Permanent panel damage cannot be undone by software and is an accepted
risk, not a promised recoverable failure.

`compile_candidate.py` generates the exact candidate and image-identification
hashes in `validation.json` from saved live tables. These files are offline only;
there is intentionally no authorization record and no device execution here.

## Prepared executor — offline checked, still not authorized

Existing `06-tools/run_dsi_mode_trial.py` now supports `--coupled-on`; its matching
offline consumer is `06-tools/analyze_dsi_redraw.py --coupled-on`. The runner
refuses before subprocess/device calls or chunk-directory creation without a
separate `authorization.json`. Do not synthesize approval from HORIZON or risk
acceptance. After actual owner confirmation only, the record must bind:

- `proposal`: `artifacts/dsi_coupled_on_20261107/proposal.md`;
- `candidates`: `["s0c1"]`; `sequence`: `["stock", "s0c1", "stock"]`;
- `program_sha256.stock`: `b5ed66ba69e6221de5fdeaf4d003c9628602d743880acd1c8e2cf7198facd193`;
- `program_sha256.s0c1`: `dbe3e4cddda896b6c6864cbab6ff9271cff6745913afb3ccfa43a4f786c4b3b9`;
- `emergency_reboot_approved`: explicit boolean true;
- actual `owner_confirmation` and timezone-aware `approved_at_utc`.

This is a provenance record, not a cryptographic proof of permission. The agent
must never create it without the actual operation-specific owner confirmation.
Python `-O` is refused; existing one-shot run/private-directory guards remain.
Expected successful trace shape is225 table packets,3 same-DBV writes,9 short
reads,37 tx callbacks including final page0/ESD restore. These are **expected**
counts, not new observations. Byte/unit/CLI and synthetic decoder checks are
offline only; no live cleanup/recovery qualification is claimed for S0C1.
