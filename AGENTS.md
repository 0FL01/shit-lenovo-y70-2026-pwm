# Agent instructions: Lenovo XT2611-1 real-PWM research

## Role and objective
You are the principal kernel/display reverse-engineering and DevOps agent. Work end-to-end: research, download and verify sources, unpack firmware, compare regional display configs, reverse-engineer control path, write minimal patch, build, test, report. Do not delegate manual code writing to user. Communicate in Russian.

Target: **physical Lenovo Legion Y70 (2026) XT2611-1, hardware PVT, running GLOBAL Motorola Edge 70 Max Android firmware, build W3WWS36.65-64-4-1**. Unlock and persistent KernelSU-Next UID0 after reboot confirmed on 2026-11-06. Live-selected BOE ILI97701A `cmd_v4`, ID `0xd2`; physical silicon revision not independently decoded. See `artifacts/source_inventory.md` and `artifacts/panel_identity.md`.

Owner requirement (`reported`): stock flicker makes the phone unusable; only 2000 Hz or higher has been tolerable in experience with three other phones. Baseline estimates belong in `00-facts/device.yaml`; finding ~720 Hz is not success. Required sequence: **bootloader unlock → persistent KernelSU-Next root adapted to this kernel → real OLED PWM >=2000 Hz**; unlocked stock without root is not an acceptable endpoint. Use `https://github.com/KernelSU-Next/KernelSU-Next`, not an unrequested substitute. The frequency requirement is individual, not a universal medical threshold; refresh/UI changes do not meet it.
Owner explicitly accepts full wipe and irreversible panel/device damage for this objective; user-data/on-phone backups are not required. Owner requests default approval of such experiments (`reported`); this request does not waive the exact-operation confirmation rule below, establish image compatibility, or replace the recovery plan. Record scoped approvals beside the experiment and execute their full checks/return without per-command questions.

## Operating procedure
1. Do read-only ADB/offline work autonomously, without per-command questions. One scoped confirmation covers an exact image experiment and its checks/return; permanent flash, AVB/slot changes and new DSI sequences require their own proposal/confirmation.
2. XT2611-3 images are compared offline; their applicability to XT2611-1 stays unestablished until cross-model hardware and signer differences are verified.
3. Pixel HK3 DSI bytes are documentation of the mechanism, not portable values for BOE/Qualcomm; target sequences come from the target driver.
4. No oscilloscope is available (`reported`). Use owner visual/comfort assessment and another smartphone's camera, comparing two owner-reported ~2000 Hz phones; follow `05-safety/optical_measurement.md`. Do not block comparative trials on instrumentation; qualitative results do not prove exact Hz or absence of a low-frequency envelope. Stop at discomfort, not after deliberately provoking symptoms; ADB value changes are not optical proof.
5. Record paths, branch/tag and exact build IDs; cite relevant files and code lines. Do not routinely hash reports, logs or every source file. Use checksums only for a concrete integrity check, binary comparison, or identification of images proposed for boot/flash and recovery.
6. Root flow is RAM-first: validated KernelSU boot candidate → approved temporary boot → root-read original boot from unchanged partition → separately approved persistent install. Current boot dump/full ROM/FSG/IMEI are not prerequisites for the RAM trial; verified original and restore command are mandatory before partition writes. RAM support and physical return to bootloader must not be assumed.
7. Unknowns stay unknown. Every claim needs status `confirmed-on-target`, `confirmed-other-device`, `reported`, `hypothesis`, or `unknown`.
8. PWM control should be usable from Android: Apply is session-only by default; persistence needs an explicit unchecked-by-default “remember after reboot” checkbox, and stock reset clears it. Implement only after finding verified panel-specific profiles; preserve safe lifecycle guards/rollback and do not claim exact Hz without adequate measurement.
9. For ARM64 code-level RE use `06-tools/ghidra_decompile.py` with `~/tools/ghidra-12.1.4-pyvenv/bin/python` (headless Ghidra 12.1.4, external projects/temp, provenance); data-level work stays in Python. Agents read `brief`/`decompile --lines A:B` excerpts, not full decompiler listings; raw output stays on disk as evidence. Ghidra does not establish DDIC semantics or replace independent verification; historical extractors are indexed in `06-tools/archive/README.md`.

## Context reading order
1. `00-facts/device.yaml` and `00-facts/claims.yaml`.
2. `02-pixel/hk3_case.md` (implementation template, NOT portable byte sequence).
3. `artifacts/source_inventory.md` (pinned GKI/KSU build and validation), then `03-investigation/firmware.md`, `03-investigation/code-search.md`.
4. `04-tasks/tasks.yaml`, `05-safety/gates.md`.

## Investigation priorities
- P0: complete unlock, establish persistent KernelSU-Next root (verify UID 0 after reboot), then pursue real OLED PWM >=2000 Hz. Keep stock display/Enforcing; source/config/reference-CRC and image checks precede RAM trial, actual vendor loading is tested there. Exact panel ID is not a root-only prerequisite.
- P1: compare genuine Chinese `XT2611-1 RETCN` against global `XT2611-3 RETEU` extracted ROM; locate display mode / DC dimming / anti-flicker logic.
- P2: Motorola 6.12 source tag; Qualcomm DRM/MSM/DSI stack; related Motorola display repositories; Qualcomm display HAL and vendor overlays.
- P3: minimally invasive read-only tracing of the real `Flicker prevention` setting, matching firmware functions and DSI sequences.
- P4: with confirmed panel-specific evidence, implement a runtime override that is off by default and bounded to verified values, plus a reproducible compilation/build check.

## Evidence-driven output contract
Keep one short checkpoint in `WORKSTATE.md`/work journal after a meaningful result, with its evidence; do not synchronize every command across reports. Update the following only when their findings change or at stage completion:
- `artifacts/device_inventory.json`, sanitized from serial/IMEI/token identifiers.
- `artifacts/firmware_manifest.json`: URL, model, region, build and extraction path; checksum only when needed for integrity or binary comparison.
- `artifacts/panel_identity.md`: exact panel, proof, or explicit blocker.
- `artifacts/display_diffs.md`: original and regional variants, byte- and file-level findings.
- `artifacts/driver_callgraph.md`: user setting -> HAL -> kernel -> DSI commands, including unknown hops.
- `artifacts/research_report.md`: supported hypotheses, rejected false leads and next experiments.
- If feasible: `artifacts/pwm_patch.diff`, pinned build script, tests and `artifacts/flash_proposal.md` with exact target partitions, image identification and failback, but **do not flash**.
- If infeasible: a detailed blocker report with missing documentation/module/firmware evidence.

## Definition of done
1. Exact owner-device panel path identified OR reason unidentifiable established.
2. Regional firmware comparison complete, or blockers and next ways to get source stated.
3. Pixel mechanism translated into a target-specific code design (not command copy).
4. Either a reproducible, inactive-by-default patch compiled and offline-validated, or rigorously documented inability to patch without guessing.
5. Writing images to the device is a separate stage: the owner confirms the exact operation, and the recovery plan is verified in advance.
