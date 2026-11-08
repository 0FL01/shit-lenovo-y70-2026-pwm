# Goal: Интеграция Ghidra 12.1.4 (headless) как стандарта code-level RE в тулкит проекта

Status: complete
Source: инструкция владельца 2026-11-07 («Вноси правки в текущий тулкит… кратно усовершенствовать тулкит, чтобы сузить уровень ошибок и увеличить эффективность; инструкции исправить; скрипты старые заархивировать, если они не нужны при использовании гидры»); явный апрув trial «Да, Ghidra 12.1.4»; ревью Review-Sol-Global от 2026-11-07 (без блокеров, поправки включены ниже).
Last updated: 2026-11-07

## Objective
Ghidra 12.1.4 (пин URL+SHA256, headless-only, внешний каталог проектов) установлена и встроена в тулкит как стандарт бинарного code-level анализа через единый вход `06-tools/ghidra_decompile.py`; работоспособность доказана known-answer валидацией на двух решённых кейсах; инструкции проекта обновлены; supersession-реестр старых ad-hoc экстракторов создан. Действий на устройстве нет; замороженные evidence-артефакты не трогаются.

## Execution Directive
Выполни замороженные Required Outcomes по Change Envelope и Primary Evidence. Работай от наименьшего незакрытого исхода. Не добавляй требований из ревью, тестов, инструментов или спекулятивных рисков. Закончи, когда все исходы закрыты и затронутые ограничения соблюдены.

## Frozen Contract

### Required Outcomes
- R1: Ghidra 12.1.4 установлена headless-only с пином.
  - Source: апрув trial; ревью (версия/JDK подтверждены).
  - Acceptance: каталог `~/tools/ghidra-12.1.4` из официального ZIP `Ghidra_12.1.4_build`; SHA256 записан; offline-virtuenv PyGhidra 3.1.0 из `Ghidra/Features/PyGhidra/pypkg/dist` работает (`pyghidra` import, версия печатается); системных установок нет; GUI не запускался.
  - Primary evidence: лог установки + `python -c "import pyghidra; …"` в venv; запись пина в отчёт `artifacts/ghidra_toolkit_20261107/`.
  - Status: verified
  - Evidence: artifacts/ghidra_toolkit_20261107/install_pin.json, install.log:10–20; SHA256 OK, offline PyGhidra3.1.0/JPype1.5.2, Temurin21.0.12, установка завершена20:10:02UTC.
- R2: Единый инструмент `06-tools/ghidra_decompile.py`.
  - Source: инструкция владельца «кратно усовершенствовать тулкит, сузить уровень ошибок».
  - Acceptance: подкоманды `functions` / `decompile` / `xrefs` / `symbols` для ELF ARM64 (ET_REL .ko и ET_DYN); ВСЕ Ghidra-проекты и JVM temp — только в `/home/stfu/.cache/opencode-tmp/opencode/ghidra-toolkit-20261107/` (никогда рядом с ELF — дефолт PyGhidra запрещён флагом/обёрткой); вывод детерминирован; JSON-manifest + выгрузки .c несут provenance (путь бинарника, SHA256, версия Ghidra); адреса Ghidra документированы как section+offset, не live VA; unittest `06-tools/test_ghidra_toolkit.py` зелёный (тяжёлые кейсы — за флагом/переменной окружения, чтобы не ломать быстрый цикл).
  - Primary evidence: `python 06-tools/test_ghidra_toolkit.py` (unit-часть) + один прогон полного цикла на fixture.
  - Status: verified
  - Evidence: 06-tools/ghidra_decompile.py, test_ghidra_toolkit.py; artifacts/ghidra_toolkit_20261107/unit-tests.log (5PASS/2SKIP), known-answer-tests.log (последняя версия7PASS/97.237s); полный symbols/functions/decompile/xrefs цикл на B, побайтно равные повторные manifest/C, внешний cache/JVM temp/cleanup.
- R3: Known-answer валидация на решённых кейсах.
  - Source: утверждённый trial шаг 2 с поправкой ревью.
  - Acceptance: (a) `msm_drm.ko` → декомпилят `dsi_display_set_backlight` воспроизводит ДОКАЗАННЫЙ ручной результат: LUT→DBV clamp dataflow (153 инструкции, модель 65536 clamp-входов); выбор DCS-вместо-Linux-PWM в критерии этой функции НЕ входит (он живёт в `dsi_panel_set_backlight`/parser-функциях); (b) `motorola.hardware.sensorext-service` → threshold-потребитель воспроизводит сравнение `pwmToDcDbv=3601` (ALS-компенсация); (c) демонстрация авторазворота `.gnu_debugdata` (12.1.4 умеет: ElfProgramBuilder.java:1565–1655) — число восстановленных символов > dynsym-only у стрипнутого бинарника. Все три — в `artifacts/ghidra_toolkit_20261107/` (result.md + сырьё).
  - Primary evidence: known-answer сравнение декомпилята с `artifacts/brightness_policy_recon_20261107/result.md:20–31,216–230` и `artifacts/current_display_path/als/threshold_path.{json,disasm.txt}`.
  - Status: verified
  - Evidence: artifacts/ghidra_toolkit_20261107/result.md, known_answer_validation.json, module_backlight/ и als_threshold/ C/JSON:153instructions/65536clampcases/mismatches0; ALS this+f0 threshold3601 из сохранённого XML; debugdata_comparison.json + als_symbols/manifest.json + als_dynsym.txt:467>164, IMPORTED calculate absent from dynsym. Выбор DCS-vs-PWM в A не включался; только offline static/model claims.
- R4: Инструкции обновлены; supersession-реестр вместо перемещения evidence.
  - Source: инструкция владельца «инструкции исправить и скрипты старые заархивировать»; правило проекта о неприкосновенности evidence.
  - Acceptance: AGENTS.md — один пункт в Operating procedure (code-level RE → `06-tools/ghidra_decompile.py`; data-level остаётся на Python; Ghidra НЕ закрывает семантику DDIC); `03-investigation/code-search.md:60` и `03-investigation/firmware.md:63` — «кандидат Ghidra» заменён на установленную версию + как использовать; `06-tools/archive/README.md` — реестр superseded ad-hoc экстракторов (runtime_pwm/brightness/calibration/ddic_marker per-recon analyze.py) с указанием: исторические файлы остаются на месте в artifacts как замороженные evidence, для новых работ не копировать, использовать 06-tools; WORKSTATE.md — checkpoint сверху по конвенции.
  - Primary evidence: diff этих файлов + ссылочная целостность.
  - Status: verified
  - Evidence: один новый пункт AGENTS.md:20, точечные замены code-search.md/firmware.md, 06-tools/archive/README.md (6local links PASS), верхний checkpoint WORKSTATE.md; historical files не перемещены/не изменены. Отсутствующие brightness/calibration analyze.py и data-level ddic marker классифицированы честно.
- R5: Итоговый отчёт владельцу.
  - Source: роль оркестратора.
  - Acceptance: что изменилось, точные команды и результаты проверок, вердикт «принят как вспомогательный стандарт для ARM64 code-level», явное «не закрывает DDIC-семантику», остаточные риски, факт «соседний агент может продолжать».
  - Primary evidence: сообщение оркестратору + заполненный checkpoint.
  - Status: verified
  - Evidence: artifacts/ghidra_toolkit_20261107/result.md (команды/результаты/границы/вердикт), review.md (актуальный Sol PASS, session ses_e4850cb38ffe0PrfnK0RB0vUf4), WORKSTATE.md и финальная передача оркестратору. Основной агент может продолжать; основной OLED/PWM R3 не закрыт.

### Constraints
- C1: Никаких действий на устройстве (ADB/fastboot/DSI/sensor/reboot) — только офлайн-тулкит и доки.
- C2: Замороженные evidence не трогать: не редактировать и не перемещать существующие файлы в `artifacts/*/` (включая исторические analyze.py); supersession — только реестром.
- C3: Ничего Ghidra-сгенерированного внутри worktree, кроме намеренных артефактов `artifacts/ghidra_toolkit_20261107/`; проекты/JVM temp — в approved cache `/home/stfu/.cache/opencode-tmp/opencode/`.
- C4: Пин: официальный ZIP Ghidra 12.1.4 + опубликованный SHA256; существующий JDK 21 (sdkman Temurin 21.0.12); никаких system-wide установок; PyGhidra только offline из дистрибутива.
- C5: Никаких секретов/private-логов (OTA prefs, ADB-логи с идентификаторами) в новых артефактах.
- C6: Один timebox на всю сборку (учёт setup+analysis+ручной проверки); незавершённый анализ помечается явно, не замалчивается.

### Non-goals
- Исследовательский проход по mot_tcmd (это работа возобновляемого основного агента новым тулкитом).
- Hexagon DSP (остаётся на существующем LLVM-декодере), DEX/Java (androguard), data-пайплайны DTBO/DSI/оптика.
- Архивирование/изменение data-скриптов 06-tools (ни один не superseded Ghidra'ой — все 25 data/build/test).
- Любые обещания закрыть семантику регистров DDIC или заменить независимую проверку выводов.

## Change Envelope
- Target: тулкит бинарного RE и инструкции.
- Expected paths: `~/tools/ghidra-12.1.4/` (новый), отдельный venv PyGhidra (например `~/tools/ghidra-12.1.4-pyvenv/`), `06-tools/ghidra_decompile.py`, `06-tools/test_ghidra_toolkit.py`, `06-tools/archive/README.md`, `AGENTS.md` (один пункт), `03-investigation/code-search.md`, `03-investigation/firmware.md`, `WORKSTATE.md` (checkpoint сверху), `artifacts/ghidra_toolkit_20261107/` (результаты). Опционально: `+pyelftools` в `.venv`.
- Allowed: перечисленное; чтение любых файлов репо; работа в approved cache.
- Forbidden: device-действия; правки/перемещения существующих `artifacts/` и data-скриптов; GUI; system-install; новые зависимости сверх названных; commits (репо не git).
- Budget: один timebox сессии сборки; тяжёлый анализ (6 MB .ko) — с явным таймаутом и статусом.

## Current Checkpoint
- Closes: R1–R5, complete.
- Smallest next action: нет; передать результат основному агенту и остановиться.
- Expected evidence: artifacts/ghidra_toolkit_20261107/{result.md,review.md,known-answer-tests.log,known_answer_validation.json}.
- Stop or replan if: новые исследования/переносимость/аппаратные действия требуют отдельного scope; этот контракт не переоткрывать как общий backlog.

## Current State
- Resolved: R1–R5 verified; Ghidra принят как вспомогательный ARM64 code-level стандарт, не DDIC/physical-PWM proof.
- Last relevant evidence: полный gate7PASS/97.237s; ручная C/static/model сверка; актуальный Review-Sol-Global PASS без замечаний (review.md).
- Blocker: нет.
- Next: основной агент продолжает своей задачей; toolkit execution завершён.

## Material Decisions
- 2026-11-07: ProjectLocator12.1.4 отвергает hidden path element `.cache`; legacy open_program дополнительно canonicalizes pathlib.Path через converters.py:21–23, теряя FD-alias. Используется современный public PyGhidra open_project(str)/program_loader/program_context/analyze из bundled README:293–309; project path `/proc/self/fd/<directory-fd>` проходит realpath-проверку и указывает на per-run directory внутри утверждённого cache. Физическое расположение/JVM temp не меняются, persistent alias/новый state не создаётся.
- 2026-11-07: «заархивировать старые скрипты» исполнено как supersession-реестр `06-tools/archive/README.md` без перемещения файлов: ни один скрипт 06-tools не заменяется Ghidra (все data/build/test), а per-recon экстракторы в artifacts — замороженные evidence со ссылками из отчётов. Физическое перемещение — отдельным решением владельца.
- 2026-11-07: «кратное улучшение тулкита» = единая точка входа + provenance + known-answer тесты + реестр; data-пайплайны не рефакторятся (валидированы, риск регрессий).

## Checkpoint History
- 2026-11-07: контракт заморожен, статус active, передача General-Sol-Global.
- 2026-11-07: R1 verified (20:10UTC), пин/import в install.log; R2/R3 следующий checkpoint, initial ProjectLocator path validation failure диагностирован до импорта fixtures.
- 2026-11-07: R2/R3 verified после исправления SDK path/overload и PIE import-address mapping; последний полный gate7PASS/97.237s,153instructions/65536clampcases/mismatches0, debugdata467>164. Сохранён matching imported entry до demangler для functions→decompile workflow.
- 2026-11-07: актуальное foreground Sol review фактического кода/выгрузок PASS без замечаний; затем завершены R4/R5, финальные status/checkpoint/report edits только документационные. Runtime после ревью не менялся.

## Completion
- Resolved outcomes: R1–R5 verified; finish line достигнут.
- Commands and artifacts: artifacts/ghidra_toolkit_20261107/result.md содержит установку и точные gates; install_pin.json/install.log,7PASS known-answer-tests.log, raw C/JSON/refs/symbols, known_answer_validation.json и review.md. Быстрый gate5PASS/2SKIP; тяжёлый .ko лимит480s, B120s, timeout не потребовался.
- Constraint and diff-scope check: только approved tools/docs/новый каталог evidence и запрошенные статусы этого документа; существующие artifacts/*/ и data-скрипты не менялись/не перемещались. Проекты/JVM temp фактически только approved cache, per-run dirs очищены; GUI/device/system-install/commits/private-log publication отсутствуют. Всё внутри единого75-minute session timebox20:00:40–21:15:40UTC. Основной R3/аппаратные approvals не затронуты.
- Final status: complete; принят как вспомогательный ARM64 code-level стандарт. Соседний агент может продолжать; DDIC-семантика и физическая OLED PWM не закрыты.
