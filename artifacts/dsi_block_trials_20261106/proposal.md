# Three isolated native blocks — offline proposal only

Status: completed once for each of the three variants; [run](run.json),
[analysis](analysis.json), [frames](../optical/pacman_dsi_blocks_comparison.png).
All retained the fine train atDBV3600; no >=2000Hz result. Stock/policy restored.
The manifest describes historical offline generation, not the current sent status.
Purpose: identify which native DC block changes the fine optical train after
isolated23:80=90 changed image signal but retained it. No promised Hz outcome.

## Frozen candidates

Each starts independently from the complete live DC OFF program,875B/75packets.
Only the specified payloads are replaced by this same panel's native DC ON values.
The [manifest](manifest.json) gives exact byte offsets, full payloads and files.

| Candidate | Exact substitution | Changed bytes |
|---|---|---:|
| `thresholds.bin` |23:A9 and24:9D:0E→8E; adjacent AA/9E stay11. Threshold association is a hypothesis.|2|
| `page53.bin` |53:95:00 A0→44 50;53:A2 each10B block `10 10 10 10 48 10 10 10 4B 4B`→`10 10 10 10 48 10 10 74 7B B4`.|11|
| `page63.bin` |63:F2 data indices5–9:00→20;63:F3 indices5–9:20→00. Indices exclude opcode. Preserve53:F001…F000 and every intervening packet.|10|

No combined candidates, other values, changes to23:80,51/52,OD/init/timing tables,
power/reset/NVM commands, flashing, module/table replacement or persistence.
Five20 bytes are not asserted to mean five pulses; that remains an unproven idea.

## Bounded execution and return

One series: **stock→thresholds→stock→page53→stock→page63→stock**.
Each candidate at most once;7second holds. Same DBV3600/software120 and physical
camera720p/100µs/ISO6400/AE-AFoff/fixed focus. Record and compare the complete clip.
This authorizes only the listed three combinations, not a register sweep.

Reuse the [verified transport](../dsi_mode_trial_20261106/proposal.md): exact module
and panel guards, native pending counts/returns and per-packet comparison,
unchanged HS/batch/delay flags, chunks253/247/254/110/11 and final native flush
under panel_lock. No cached UI0 shortcut for return: send the full original OFF
program after each candidate. Stop the series on a failed guard, native error,
unexpected payload/pending state or lost trace; do not proceed to the next block.
If transfer/buffer state is uncertain, ordinary reboot instead of blind flushing.
If ADB is lost, stop remote writes; physical restart is the remaining return path.
A temporarily black display remains possible with an unverified combination.

Restore target policy/logger/tracing and remove generated device files. Camera
stays ready between tests as requested. Optical differences do not certify Hz,
fundamental frequency, calibrated depth or usability. No Android preset is
implemented until a useful panel-specific profile is actually established.
