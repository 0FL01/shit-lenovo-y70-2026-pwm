# RECON: финальный unlock → постоянный KernelSU-Next root → PWM >=2000 Гц

Исторический RECON от 2026-11-06; наблюдения ниже относятся к моменту их записи.
Текущее состояние/упрощённый RAM-first маршрут — в Execution contract в конце файла.

## Цель и разрешения владельца

- `reported`: нынешние примерно 170 Гц делают аппарат непригодным для владельца;
  2000 Гц переносимы по опыту трёх других телефонов. Это индивидуальное требование,
  не измеренный baseline этого экземпляра и не медицинская гарантия.
- Приоритет: завершить bootloader unlock, получить постоянный KernelSU-Next root,
  затем добиться реального OLED PWM >=2000 Гц. Владелец требует root для повседневного
  использования; unlocked stock без root и только временный исследовательский доступ
  не являются приемлемым итогом. Выбран именно [KernelSU-Next](https://github.com/KernelSU-Next/KernelSU-Next)
  с адаптацией под наше ядро; не заменять другим root-проектом без согласования.
  720 Гц, смена refresh rate и программное затемнение не считаются выполнением цели.
- Владелец принимает полный wipe и рискованные эксперименты ради цели; бекапы
  пользовательских данных/на телефоне не требуются. Это не доказывает совместимость
  образов; точная следующая изменяющая операция и путь восстановления согласуются отдельно.

## Свежие наблюдения телефона

`confirmed-on-target`: 2026-11-06, 06:53:09–06:53:38 UTC. Единственный авторизованный
ADB transport; `fastboot devices` — пусто. Идентификаторы транспорта не сохранены.
Каждая команда ниже завершилась с exit code 0; пустой ответ не приравнивается к false.

| Read-only команда | Ответ |
|---|---|
| `adb shell getprop ro.boot.hardware.sku` | `XT2611-1` |
| `adb shell getprop ro.boot.hardware.revision` | `pvt` |
| `adb shell getprop ro.build.display.id` | `W3WWS36.65-64-4-1` |
| `adb shell getprop ro.build.fingerprint` | `motorola/avr_g/avr:16/W3WWS36.65-64-4-1/c9a7f-8fbf58:user/release-keys` |
| `adb shell getprop ro.build.version.incremental` | `c9a7f-8fbf58` |
| `adb shell uname -r` | `6.12.58-android16-6-g09eda8c8505a-ab15950084-4k` |
| `adb shell getprop ro.boot.slot_suffix` | `_b` |
| `adb shell getprop ro.boot.flash.locked` | `1` |
| `adb shell getprop ro.boot.vbmeta.device_state` | `locked` |
| `adb shell getprop ro.boot.verifiedbootstate` | `green` |
| `adb shell getprop ro.oem_unlock_supported` | пусто |
| `adb shell getprop sys.oem_unlock_allowed` | пусто |
| `adb shell settings get global oem_unlock_allowed` | `null` |
| `adb shell dumpsys oem_lock` | пусто |
| `adb shell id` | UID/GID 2000 shell, SELinux `u:r:shell:s0` (остальные группы опущены) |

Вывод: **Android сообщает locked/green, финальный unlock не завершён**.
`reported`: по уточнению владельца включено только OEM unlocking в системе.
`unknown`: fastboot securestate/unlock ability, eligibility XT2611-1, точная команда
и необходимость ключа. Пустые Android OEM-запросы не подтверждают и не опровергают
положение переключателя. Старое сообщение «уже unlocked» отозвано, не является фактом.

## Что уже есть для PWM, без повторного исследования с нуля

- `reported`, offline reference: CN и GLOBAL распакованы и сравнены;
  [display_diffs.md:36–77](display_diffs.md) — 18/18 BOE DC ON/OFF arrays равны,
  но 36 init/timing-switch properties ILI97701A v2–v4 различаются. Это кандидаты
  для анализа, не доказанные PWM-регистры и не готовая инструкция переноса.
- `reported`, reference/source: цепочка Motorola Global provider → PanelsService →
  JNI/AIDL → HAL → DRM → `dsi_panel_set_dc` → DSI установлена статически:
  [driver_callgraph.md:13–30,155–202](driver_callgraph.md). Owner инварианта —
  panel command sets/driver lifecycle, а не Android UI; `panelDC` read-only.
- `hypothesis`: live panel — BOE ILI97701A / `mipi_mot_cmd_boe_1440p_dsc_682`.
  `unknown`: exact panel/revision, register → Hz и наличие режима >=2000 Гц;
  [panel_identity.md:10–12,62–89](panel_identity.md). Обычный shell раньше не смог
  читать panel attributes/DT/dmesg. Сам unlock не предоставляет root и не снимает SELinux.
- `confirmed-on-target`: текущий kernel отличается от скачанного GLOBAL reference;
  [00-facts/claims.yaml:55–58](../00-facts/claims.yaml). Нет проверенных оригиналов
  текущего OTA/полного source/KMI match. Архив XT2611-3 — offline reference, не backup;
  старый CN того же SKU тоже не является проверенным downgrade/recovery.
- `reported`, archive analysis: AVB embedded keys равны, но rollback CN/GLOBAL 0/2,
  CID metadata 11/50; это не проверка подписей/совместимости:
  [display_diffs.md:140–145](display_diffs.md).
- `reported`, уточнение владельца: осциллографа нет; доступны оценка глазами/по
  переносимости и камера другого смартфона, а также два телефона с заявленными
  владельцем ~2000 Гц для сравнения. Мигрень/сухость глаз при низкочастотном PWM —
  его наблюдения, не измеритель частоты. `unknown`: baseline, точные Hz и допустимый
  профиль. Отсутствие осциллографа не блокирует сравнительные пробы; протокол:
  [optical_measurement.md](../05-safety/optical_measurement.md).

## План: три зависимых этапа

### 1. Завершить bootloader unlock

1. После согласования перехода — `adb reboot bootloader`, затем read-only
   `fastboot getvar product`, `sku`, `hwrev`, `securestate`, `unlocked`,
   `current-slot`, `is-userspace` и, если поддерживается,
   `fastboot flashing get_unlock_ability`. Проверить именно bootloader fastboot,
   не fastbootd; unsupported/пусто сохранять как unknown. Не использовать `getvar all`.
2. По target-supported OEM flow выяснить eligibility и необходимость ключа.
   `fastboot oem get_unlock_data` — только кандидат на чтение в Motorola flow;
   его вывод и ключ приватны. Отправка Device ID на официальный портал/запрос ключа
   согласуются отдельно; в этом RECON ничего не отправлялось.
3. Представить одну точную подтверждённую процедуру и последствия, затем выполнить
   после подтверждения владельца. `fastboot oem unlock <key>` встречается у других
   Motorola; AOSP документирует `fastboot flashing unlock`. **Ни одна из этих команд
   ещё не доказана правильной для XT2611-1**; не пробовать их по очереди наугад.
   `unlock_critical`, relock, AVB changes, manual erase и slot changes не нужны этому плану.
4. Предусмотреть физическое подтверждение владельцем и полный wipe. Затем повторно
   прочитать fastboot state и Android boot properties и проверить загрузку stock Android.
   Критерий: фактический flashing-unlocked state, не включённый toggle и не один факт wipe.

Путь выхода для штатного unlock: отмена до подтверждения оставляет locked stock;
после завершённого unlock — штатная перезагрузка/stock boot, повторная настройка и ADB
после wipe. Наличие доступного stock recovery и способ входа ещё проверить на аппарате.
**Полное восстановление после произвольного повреждения разделов не проверено**;
если процедура потребует flash, остановиться и подготовить отдельный image/recovery plan.
Не прошивать имеющиеся старые/cross-SKU образы и не relock в попытке «починить» unlock.

### 2. Сразу после unlock получить постоянный KernelSU-Next root

1. **RAM bootstrap:** из уже собранного pinned r59 + KernelSU-Next33355 подготовить
   один boot-кандидат, проверить упаковку/хэш. Одно подтверждение охватывает точный
   `fastboot boot`, Manager/root/Enforcing/vendor-loading проверки, чтение оригинального
   boot и возврат. Физический вход в bootloader и stock reboot должны быть проверены;
   поддержку RAM boot не предполагаем. Не писать разделы, не менять AVB/слот/DSI.
   FSG/IMEI/full ROM и файл текущего boot не требуются перед RAM-пробой. Совместимость
   реальных vendor modules остаётся экспериментальной до успешной загрузки.
2. **Постоянный root:** при успешном RAM root снять/идентифицировать оригинальный
   активный boot с неизменённого раздела, собрать сохраняющий его layout постоянный
   вариант. Отдельно согласовать точный flash с этим оригиналом для отката; проверить
   UID0 после reboot, Enforcing и stock display. При unsupported/rejected RAM boot
   вернуться в stock и остановиться, не переходить к flash автоматически.
3. **PWM evidence:** прочитать live panel/DT/msm_drm, затем продолжить этап3 ниже.
   Без panelCellId/персональных данных; остаточные denials не обходить global Permissive.

Критерий root-этапа (`T00R`): постоянный KernelSU-Next root с UID 0 после reboot,
нормальная загрузка и stock display behavior, SELinux Enforcing, проверенный restore path.
Совместимость нужных владельцу приложений/Play Integrity этим не доказана и автоматически
не обещается. Панельные данные (`T06`) — следующий результат для PWM либо точный блокер.
Пользовательские бекапы не требуются; подходящие исходные образы для отката — требуются.
Повторять полное сравнение уже разобранных архивов без новой причины не нужно.

### 3. Повышать PWM к цели >=2000 Гц и оценивать доступными средствами

Сначала качественный baseline камерой и краткая оценка владельца, со сравнением
двух его телефонов с заявленными ~2000 Гц; осциллограф для этих проб не требуется.
Затем расшифровать
панельные init/timing/DC sequences и найти подтверждённый профиль/документацию для
высокой частоты; наличие 720 Гц в обзоре не доказывает возможность 2000 Гц.
Если профиль найден — минимальный target-specific driver/DT override, stock по умолчанию,
bounded verified values, сборка и ABI/header/offline проверки, отдельный подтверждённый
тест с возвратом в stock. Новые BOE DSI bytes не брать из Pixel HK3 и не перебирать наугад.

Практический критерий: владелец сообщает о пригодной переносимости в проверенных
условиях, сохранены сравнения камерой при одинаковых настройках до/после,
не обнаружены display-регрессии и работает откат. Прямое наблюдение — краткое,
добровольное, до первого дискомфорта; не провоцировать мигрень/сухость ради проверки.
Точные carrier Hz, amplitude/duty и низкочастотная огибающая остаются `unknown` без
подходящей аппаратуры: ни сходство с reference, ни комфорт не доказывают >=2000 Гц.
Численная цель сохраняется; её инструментальная проверка — отдельный, сейчас
недоступный уровень доказательств, не блокер сравнительных проб. Если аппаратного
режима нет или документация недоступна — точно назвать блокер, а не обещать частоту
или выдавать pseudo-DC за native PWM результат.

## Первичные источники unlock, проверены 2026-11-06

- [Motorola: поддержка bootloader unlock](https://en-us.support.motorola.com/app/answers/detail/a_id/87215):
  участие конкретного аппарата проверяется по Device ID после входа в аккаунт;
  есть ограничения моделей/операторов. Это не доказательство eligibility XT2611-1.
- [AOSP locking/unlocking](https://source.android.com/docs/core/architecture/bootloader/locking_unlocking):
  OEM unlocking permission ≠ unlocked state; `flashing unlock`, confirmation и wipe —
  общая спецификация, не подтверждённая реализация конкретной Motorola.

## KernelSU-Next: проверенный upstream и границы применимости, 2026-11-06

- `reported`, upstream: [release v3.4.2](https://github.com/KernelSU-Next/KernelSU-Next/releases/tag/v3.4.2)
  опубликован 2026-10-13; Git ref указывает на commit
  `4c706b5938665866ebe16944a481a7b91e3396af`. В assets есть
  `aarch64_android16-6.12_kernelsu.ko`: поддержка upstream-семейства существует,
  **но совместимость этого готового модуля с Motorola не установлена**.
- [docs/README.md:49–57](https://github.com/KernelSU-Next/KernelSU-Next/blob/4c706b5938665866ebe16944a481a7b91e3396af/docs/README.md#L49-L57)
  заявляет поддержку 4.4–6.18 и GKI/LKM/KMI для 5.10+;
  [kernel/Kconfig:3–13](https://github.com/KernelSU-Next/KernelSU-Next/blob/4c706b5938665866ebe16944a481a7b91e3396af/kernel/Kconfig#L3-L13)
  определяет KSU как tristate с зависимостями. Это исходники возможностей, не target boot test.
- `unknown`: source-to-current-stock/config/KMI match, пригодный root build и root после
  reboot на нашем XT2611-1. Кастом ещё не написан/собран; install-скрипты и код upstream
  не запускались. KernelSU-Next — обязательный выбранный путь, не уже достигнутый результат.

Валидация этого этапа: чтение источников и узкий ADB-срез; изменены только документы
контекста/плана. Kernel build, boot/flash/unlock и оптический тест не выполнялись.

## Execution contract — 2026-11-06

Status: active (R1/R2 verified; A9 isolated causally; spatial-v2 integration and
offline2D audit completed. Stock120/144/120/90/120 capture completed2026-11-07
07:33UTC; native/optical validation passed, no proportional refresh→PWM proof.
Large coupled-block S0C1 candidate is offline-validated and awaits exact approval.
Early-source follow-up completed without a count/period map. Supported exposure
control completed08:22UTC with an integration minimum/rebound and verified cleanup;
physicalHz and>=2000 remain unproven. No justified>=2000Hz profile yet).
Source: owner instructions to finish unlock, require persistent
KernelSU-Next root, pursue PWM >=2000 Hz, and commence work with a work journal.

- R1 — final bootloader unlock and normal stock boot; **`verified`**.
  Unlock verified: one approved OEM invocation at 07:37, independent fastboot
  `flashing_unlocked:SDP` at 07:38; Android at 07:45 reports boot_completed=1,
  flash.locked=0/unlocked/orange, same build/kernel/slot and Enforcing.
  Primary evidence: target unlocked state plus post-unlock boot observation, not the toggle.
- R2 — persistent target-adapted KernelSU-Next root; **`verified`** at12:19 UTC.
  One separately approved boot_b flash after successful RAM/original-readback trial;
  authorized UID0 after ordinary reboot, same build/_b, Enforcing and msm_drm loaded:
  [primary evidence](kernel/gki_r59/kernelsu_next/persistent/install.json).
- R3 — pursue real PWM >=2000 Hz and owner-usable display; `in_progress`. The
  approved A9/9D experiment completed and localized the fine-suppression effect
  toA9 in this condition, but supplied no>=2000Hz fix. Primary evidence
  currently available: controlled camera comparison and owner assessment under the
  stated evidence limits; exact numerical Hz remain unverified without adequate metrology.
- Change envelope: existing facts/tasks/reports/journal; matched firmware/source/build
  artifacts and minimal root/display changes for R1–R3. No unrelated firmware conversion,
  blanket AVB/SELinux weakening, raw DSI fuzzing or unrequested root substitutes.
- Owner direction,2026-11-07, after the stock base-rate capture: **increase proposed
  frequency-change steps approximately2–3×; no small incremental increases**.
  Owner explicitly accepts destruction of the panel as an experimental risk and
  requests immediate substantive work/live tests rather than small placebo-like
  changes (`reported`: the placebo assessment is the owner's, not a measurement).
  The target remains actual PWM>=2000Hz, not a changed register or refresh value.
  Use large, falsifiable period/count hypotheses; do not call a raw-byte multiplier
  a frequency multiplier. This supersedes incremental frequency-trial planning,
  not the mandatory exact-operation proposal/confirmation for new DSI sequences,
  nor identity/cleanup/provenance checks. No panel damage has been observed or
  deliberately caused by recording this instruction. Finish analysing the already
  completed stock control; do not repeat it as a small-step solution.
- Execution directive: work on the smallest unresolved outcome, record completed
  checkpoints, do not add scope from discoveries, and stop at a proven external blocker
  or a required operation-specific confirmation. Never mark the objective complete
  while a required outcome remains pending/blocked or evidence is missing.
- Completed checkpoint: R1 pre-unlock observation at 07:24–07:25 UTC: agreed reboot,
  target fastboot locked:SDP/slot b/is-userspace no, OEM portal flow explicitly requested
  by bootloader, unlock-data saved privately. No external ID submission or destructive command.
- Current checkpoint: R1/R2 done, no custom recovery. Current boot original verified;
  known-good root-only boot and stock rollback identified in [proposal/result](flash_proposal.md).
  Live BOE ILI97701A cmd_v4 and actual stock DC traffic established;52 real command
  arrays distinguished from the53-property historical comparison including one scalar.
  [Field analysis](em_field_recon_20261106.md) links candidate0E11 words to ALS3601
  threshold evidence without assigning undocumented register semantics.
  At16:30 the agent recorded/retrieved/analysed Pacman video at fixed100µs/ISO6400,
  AE OFF: stock52/DBV3584 repeatedly gives dense banding,53/3646 sparse broad banding.
  [Primary optical evidence](pacman_boundary_analysis_20261106.json). Both phones
  restored. Owner authorizes autonomous camera capture; no pending manual handoff.
  Exact standard3600/3601 native dispatch subsequently verified at17:01:
  [payloads/returns/restoration](exact_dbv_dispatch_20261106.json). Pacman returned17:17;
  [exact optical capture](pacman_exact_analysis_20261106.json) confirms the dense/sparse
  transition between3600/3601 in both directions. Native packets and fixed camera
  settings verified; broad band remains, no frequency claim. Target restored;
  camera intentionally remains prepared/awake during the autonomous series.
  720p/4K/720p did not change recording skew. Subsequent fixed-exposure integration
  favors~720Hz for the fine component (`hypothesis`), consistent with the owner's
  revised baseline estimate, not success. Manual-camera DC0/1/0 retains a broad
  band; native minimumDBV460 retains the~93px spacing. See the latest
  [field checkpoint](em_field_recon_20261106.md). Exact/fundamental Hz, register
  causality and a >=2000Hz profile remain unknown; exact3600/3601 optical crossing
  itself is established. The approved [one-byte DSI experiment](dsi_mode_trial_20261106/proposal.md)
  completed once:225packets verified, stock OFF→isolated23:80=90→stock OFF.
  [Analysis](dsi_mode_trial_20261106/analysis.json) shows lower video signal but
  retained~93px fine train and a broad band; exact/fundamental Hz remain unknown.
  Native return/target cleanup passed, not an exact photometric calibration.
  The [three independent native blocks](dsi_block_trials_20261106/analysis.json)
  completed once each. Full stock ON raw controls, including same-DBV replay,
  did not reproduce the previous UI ON effect; see
  [method control](dsi_stock_on_control_20261106/with_dbv_replay/analysis.json).
  [Current native UI reference](current_ui_dc_reference_analysis_20261106.json)
  reproduced ON suppression with the same logged packets and no PCD invocation.
   [Runtime tracing](dsi_runtime_flags_analysis_20261106.json) matched raw/UI message
   and controller fields, DMA accumulation and qwait=0. The decisive changed-method
   [stock control](dsi_stock_on_control_20261106/with_redraw/analysis.json) then
   reproduced ON suppression after opening/cancelling a stock settings chooser:
   normalized image q93 changed1.004→0.385 without another logged DSI command;
   OFF plus redraw restored it. Internal frame-latch/CMDQ semantics remain unknown.
    Prior isolated negatives lacked this application step. The approved
    [corrected-method series](dsi_block_trials_20261106/with_redraw/result.md) is now
    complete: only the two-byte A9/9D pair suppresses fine structure, broad band remains.
    The source followup found no EM count/period encoding. No justified high-frequency
    profile is available; the exact next-evidence boundary is recorded in that result.
    No arbitrary values, combined candidates, flash or permanent preset were added.
  On2026-11-07 the new dump audit and bounded stock/readback tests established
  `4F:81`10→06→06→10 across120→30→120→DC cycle, without the claimed count-based
  optical scaling: [current findings](ddic_regdump_20261107/readback_findings.md).
  ESD protection was recovered; broad incomplete census was not resumed. Targeted
  source/history work is complete without a field map. The exact next operation is
  the [two independent high-byte variants](dsi_selector_split_20261107/proposal.md),
  completed once each with actual readback/optical evidence in the
   [selector result](dsi_selector_split_20261107/result.md). Spatial-v2 integration
   and2D method audit completed: current geometry is poorly conditioned, Hz unknown.
   Subsequent [stock base-rate control](stock_base_rates_20261107/result.md) verified
   native120/144/90 modes but did not establish a frequency multiplier. The owner's
   subsequent large-step direction is recorded above. A [full coupled-block S0C1
   control](dsi_coupled_on_20261107/proposal.md) is compiled/validated offline only;
   exact operation/recovery approval is pending while EM-field research continues.
   No further byte combination or repeat is implicitly
  approved; no hardware impossibility is claimed. The historical
  night-plan closure below remains evaluated, superseded only as the current status.
  Short meaningful checkpoints only; R3 unresolved, overall objective **not complete**.
- Journal: [bootloader_worklog_2026-11-06.md](bootloader_worklog_2026-11-06.md)
  and [WORKSTATE.md](../WORKSTATE.md). Initial preflight: one authorized XT2611-1,
  current build, locked, slot b at 07:23 UTC; last bootloader state is unlocked/slot b,
  normal Android/ADB boot verified 07:45. Evidence:
   [post_unlock_observation_2026-11-06.json](post_unlock_observation_2026-11-06.json).

## Night execution plan — 2026-11-07 local

Status: evaluated; stages1–5 completed, overall R3 blocked and not achieved.
Copied into this existing goal at the owner's explicit instruction;
execution starts2026-11-06 22:22UTC. R1/R2 remain verified, R3 unresolved. Owner said:
«Делай копию плана в цель и приступай к работе», with autonomous YOLO permission.
The scoped [authorization](dsi_block_trials_20261106/with_redraw/authorization.json)
covers this finite series; it is not an inferred permission for arbitrary DSI values.

### Finish line and present evidence

- Final objective: persistent KernelSU-Next, useful real OLED PWM>=2000Hz, Android
  session-only Apply by default, explicit unchecked persistence option and stock reset.
  No verified high-frequency profile exists yet; ~720Hz fine-component hypothesis is
  not success. Numeric frequency and absence of the broad component remain unknown.
- Night checkpoint: evaluate the four existing isolated blocks using the corrected
  application method, classify optical effects and derive one evidence-backed next
  change or an exact blocker. Negative research is not completion of R3.
- Raw factory ON now reproduces its UI optical effect only after the tested redraw;
  normalized image component1.004→0.385, return0.998. Pixel quantities are not Hz/depth.
  Prior isolated negatives lacked this step. Driver bug/internal CMDQ semantics are
  not proven; the immediate owner of the protocol correction is apply_program().

### Ordered work and budgets

1. First30–45min: extend only `06-tools/run_dsi_mode_trial.py` with fixed
   `--blocks-redraw`. Reuse existing transport, parser, camera, repaint_settings() and
   observe_stage(). Every candidate AND stock return follows native table verification
   → DBV3600 → redraw → state check →7s hold. Keep packet flags, locks, error/cleanup
   checks and one-shot counters. Dedicated output under
   `artifacts/dsi_block_trials_20261106/with_redraw/`; never overwrite prior evidence.
2. Aim to finish capture/analysis within the next hour: stock → mode90 → stock →
   thresholds → stock → page53 → stock → page63 → stock. Mode90 changes packet12
   23:80 50→90 (1byte); thresholds packets6/9 A9/9D0E→8E (2bytes); page53 packets16/17
   95/A2 nativeON payloads (11bytes); page63 packets27/28 F2/F3 nativeON (10bytes).
   All are existing875B/75packet programs, no combinations or new values. DBV3600,
   verified software120Hz, Pacman720p/100µs/ISO6400/AE-AF OFF/fixed verified focus,
   stabilization OFF. Select actual transports and verify Camera2 before recording.
3. Analyze original video against adjacent stock intervals: exact outgoing packets,
   redraw, fine structure, broad band, mean image signal and stock return. Same DBV
   need not mean equal luminance. No success from darkening, one suppressed image
   harmonic or reproducing the already-known stock DC ON alone. Save analysis.json
   and comparison frames in the dedicated evidence paths.
4. Remaining time is evidence-directed offline work. If one block changes relevant
   behavior, inspect that block against live tables, pinned history and actual module.
   Otherwise compare with complete nativeON and remaining51/52 changes. No automatic
   combinations or repeats: lack of an isolated effect proves neither irrelevance nor
   coupling. Stop substantive work if no next falsifiable in-scope action remains;
   identify the exact missing evidence, not fill the night with repeated captures.
5. One short WORKSTATE/goal checkpoint: attempted variants, optical effects, exclusions
   and limits, useful-profile status, concrete next evidence. Do not update every
   report per command. Time budgets guide effort, not a promised solution deadline.

### Verification and preserved boundaries

- Run Python compilation and existing packet parser checks:875B/75packets, exact
  differences1/2/11/10, unchanged headers/chunk boundaries/final flush; verify the
  nine-stage schedule includes DBV and redraw at every application.
- Execute the fixed runner once; check native error/trace-loss guards, actual camera
  settings, video/stage association, stock return, target policy/logger/Enforcing
  and cleanup. Closest vendor dsi_display_test.c only checks modes/display enable,
  not this contract; no broad kernel rebuild/test framework is needed.
- No repeated root/unlock, recovery install, LMSA/FSG, region change, image flash,
  module/DTBO replacement, arbitrary register sweep or persistent PWM setting.
- On uncertain partial transmission/applied state stop and use the existing ordinary
  reboot recovery; do not blindly append/flush. Camera remains ready between approved
  trials, with original-camera restoration still tracked separately.
- Android profile UI/persistence is deferred until a useful verified hardware profile
  and lifecycle handling exist. Settings-dialog redraw is a research application step,
  not the design of daily-use control. No success claim or new profile from missing Hz.

### Night checkpoint — 22:24–22:27UTC

The corrected nine-state run completed with all four candidates once and every
DBV/redraw/hold verified. [Results](dsi_block_trials_20261106/with_redraw/result.md)
and [analysis](dsi_block_trials_20261106/with_redraw/analysis.json): only the paired
23:A9/24:9D high-byte changes suppress the fine train (image ratio0.392), broad band
retained. Other three isolated blocks retain fine structure. This establishes pair
sufficiency in the tested condition, not independent register necessity or EM Hz.
Target restored/no image writes; camera stays ready. Stage4 is also complete: pinned
community history associates the pair with low-light/DC but does not decode the
high bit or identify an EM count/period field. The simple unsigned-threshold model
does not explain the observed reversal under its stated assumptions; actual encoding
remains unknown. No useful>=2000Hz profile or Android persistence implementation.

Final checkpoint: [result and blocker](dsi_block_trials_20261106/with_redraw/result.md).
All four candidates were used once; no experiment/research job remains running.
Missing target-specific timing semantics or a known high-frequency sequence prevents
deriving a justified frequency-setting change from this evidence. A new causal
experiment needs its own exact scope; the completed series does not authorize
automatic combinations, low-byte shifts or sweeps. This is not proof of a hardware
limit or impossibility, and not completion of the owner's PWM objective.
