# Agent instructions: Lenovo XT2611-1 real-PWM research

## Где продолжить
- [WORKSTATE.md](WORKSTATE.md) — последний проверенный результат и состояние стенда. [Сессионный applier `0x8e`](06-tools/RECIPE_SESSION.md) восстанавливает профиль после пробуждения, не меняя управление яркостью. UI-блокировка ещё не установлена: Flicker prevention держать OFF, другие DDIC-пробы запускать только после `stop`.
- Режим уменьшает полосатость, но не доказывает «без ШИМ» или ≥2 кГц. Применение до первого света через vendor `msm_drm` пока гипотеза; не путать её с уже проверенным восстановлением после wake.

## Role and objective
You are the principal kernel/display reverse-engineering and DevOps agent. Work end-to-end: research, download and verify sources, unpack firmware, compare regional display configs, reverse-engineer control path, write minimal patch, build, test, report. Do not delegate manual code writing to user. Communicate in Russian.

Target: **physical Lenovo Legion Y70 (2026) XT2611-1, hardware PVT, running GLOBAL Motorola Edge 70 Max Android firmware, build W3WWS36.65-64-4-1**. Unlock and persistent KernelSU-Next UID0 after reboot confirmed on 2026-11-06. Live-selected BOE ILI97701A `cmd_v4`, ID `0xd2`; physical silicon revision not independently decoded. See `artifacts/source_inventory.md` and `artifacts/panel_identity.md`.

Owner requirement (`reported`): stock flicker makes the phone unusable; only 2000 Hz or higher has been tolerable in experience with three other phones. Baseline estimates belong in `00-facts/device.yaml`; finding ~720 Hz is not success. Required sequence: **bootloader unlock → persistent KernelSU-Next root adapted to this kernel → real OLED PWM >=2000 Hz**; unlocked stock without root is not an acceptable endpoint. Use `https://github.com/KernelSU-Next/KernelSU-Next`, not an unrequested substitute. The frequency requirement is individual, not a universal medical threshold; refresh/UI changes do not meet it.
Owner explicitly accepts full wipe and irreversible panel/device damage for this objective; user-data/on-phone backups are not required. Owner requests default approval of such experiments (`reported`); this request does not waive the exact-operation confirmation rule below, establish image compatibility, or replace the recovery plan. Record scoped approvals beside the experiment and execute their full checks/return without per-command questions.

## R&D: план — GPS, не рельсы
- Цель, критерии успеха и аппаратные разрешения задаёт владелец.
  Маршрут агент меняет самостоятельно внутри этих границ.
  Изменение плана не является разрешением на аппаратную операцию.
- Этапы, номера раундов, список веток и «следующий опыт» — текущая
  карта направлений, не обязательная очередь. Можно переставлять,
  объединять, пропускать и добавлять шаги ради цели без согласования
  каждой правки плана.
- Выбирай следующий шаг по ожидаемому влиянию на решение,
  различимости результата, цене и риску. Не обязательно самый маленький
  или следующий по номеру. Полная картография и закрытие всех веток
  не являются условиями перехода к перспективному кандидату.
- До опыта кратко зафиксируй вопрос, ожидаемое различие, достаточный
  контроль и границы операции. При адаптации протокола отделяй данные
  до/после изменения; не подгоняй критерий успеха под увиденный результат.
- Неудача метода — повод сменить метод или сузить вывод, а не обязанность
  бесконечно чинить стенд. Отрицательный результат ограничивает
  проверенные условия, не все варианты гипотезы.
- Закрытую ветку можно открыть при новых данных, изменённом механизме
  или устранении дефекта метода; укажи, что изменилось.
  Старое или исчерпанное разрешение от этого не возобновляется.
- Прогресс — новый проверяемый факт или обоснованное изменение решения.
  Число tool calls, раундов, тестов и отчётов не является прогрессом.
  При застое пересмотри маршрут, а не наращивай обслуживание процесса.
- Блокер одной ветки не блокирует проект, пока есть другой разрешённый
  различающий шаг. Если таких шагов нет — запиши блокер и минимальное
  нужное решение владельца, без имитации деятельности.
- После значимого результата обнови один checkpoint в WORKSTATE:
  факт → вывод → почему меняется маршрут → ближайший вариант.
  Исторические планы не переопределяют актуальные инструкции владельца
  и границы разрешённых операций.

## Operating procedure
1. The owner authorizes autonomous YOLO-mode testing on both the research target and camera, without per-test approval, including ADB/root diagnostics, camera capture and reversible settings tests with rollback. The owner reports both devices are available 24/7 and unused by others; verify availability and identity each time. One scoped confirmation still covers an exact image experiment and its checks/return; permanent flash, AVB/slot changes and new DSI sequences require their own proposal/confirmation.
2. XT2611-3 images are compared offline; their applicability to XT2611-1 stays unestablished until cross-model hardware and signer differences are verified.
3. Pixel HK3 DSI bytes are documentation of the mechanism, not portable values for BOE/Qualcomm; target sequences come from the target driver.
4. Nothing A001 now photographs the Lenovo OLED directly. Follow the [R33 RAW protocol](artifacts/direct_camera_r33_20261120/result.md); requalify ROI/exposure if the rig moves. Report camera contrast, not physical PWM Hz from row spacing. The oscilloscope protocol is historical, not a prerequisite. Owner comfort testing is final-only.
5. Record paths, branch/tag and exact build IDs; cite relevant files and code lines. Do not routinely hash reports, logs or every source file. Use checksums only for a concrete integrity check, binary comparison, or identification of images proposed for boot/flash and recovery.
6. Root flow is RAM-first: validated KernelSU boot candidate → approved temporary boot → root-read original boot from unchanged partition → separately approved persistent install. Current boot dump/full ROM/FSG/IMEI are not prerequisites for the RAM trial; verified original and restore command are mandatory before partition writes. RAM support and physical return to bootloader must not be assumed.
7. Unknowns stay unknown. Every claim needs status `confirmed-on-target`, `confirmed-other-device`, `reported`, `hypothesis`, or `unknown`.
8. PWM control should be usable from Android: Apply is session-only by default; persistence needs an explicit unchecked-by-default “remember after reboot” checkbox, and stock reset clears it. Implement only after finding verified panel-specific profiles; preserve safe lifecycle guards/rollback and do not claim exact Hz without adequate measurement.
9. For ARM64 code-level RE use `06-tools/ghidra_decompile.py` with `~/tools/ghidra-12.1.4-pyvenv/bin/python` (headless Ghidra 12.1.4, external projects/temp, provenance); data-level work stays in Python. Agents read `brief`/`decompile --lines A:B` excerpts, not full decompiler listings; raw output stays on disk as evidence. Ghidra does not establish DDIC semantics or replace independent verification; historical extractors are indexed in `06-tools/archive/README.md`.
10. Remote Android devices: the research target and separate optical camera are reachable through a private ADB tunnel; fastboot runs on the USB host. Before each use follow `03-investigation/adb-remote.md`, reidentify both devices, and preserve its server-version and recovery guards. Never publish host addresses, credentials or device serials.

## Context reading order
1. `00-facts/device.yaml` and `00-facts/claims.yaml`.
2. `02-pixel/hk3_case.md` (implementation template, NOT portable byte sequence).
3. `artifacts/source_inventory.md` (pinned GKI/KSU build and validation), then `03-investigation/firmware.md`, `03-investigation/code-search.md`.
4. `04-tasks/tasks.yaml` (исторический backlog),
   `04-tasks/acceptance.md`, `05-safety/optical_measurement.md`.

## Investigation priorities
- P0: unresolved physical emission and owner usability.
  Unlock and persistent KernelSU-Next root are completed, not recurring
  research prerequisites. Keep Enforcing and the applicable image/recovery
  checks for any new image experiment.
- Source/binary reverse, firmware comparison, register mapping, stock modes
  and direct optics are alternative routes. Choose or add a route by current
  evidence; no requirement to exhaust the list or complete it in order.
- Implement the smallest control needed by the current verified candidate.
  Do not build persistence or a complete UI as a substitute for an optical
  effect and owner acceptance.

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
1. Meet the active technical finish line in `.opencode/horizon-goal.md`
   on daytime and evening levels. A register value, source build or reduction
   of camera bands does not substitute for that result.
2. Obtain the owner's acceptance for regular use.
   Subjective improvement alone is not acceptance.
3. Provide verified session-only control, normal brightness/lifecycle behavior
   and stock reset; persistence remains separately opt-in.
   Image writes retain exact-operation confirmation and recovery checks.
4. Source audits, firmware comparisons, builds and blocker reports are
   intermediate deliverables, not completion of the physical PWM objective.
   An external blocker is `blocked`, not success.

## Commit style
For non-trivial changes, never use a bare one-line commit. Use `<type>(<scope>): <description>` with type `feat`, `fix`, `chore`, `docs`, `refactor` or `test`; after a blank line add an indented `Changes:` section with 2–4 concrete bullets. Describe the changes clearly enough to understand the commit without reconstructing the diff.
