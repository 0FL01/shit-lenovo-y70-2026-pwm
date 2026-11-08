# Интеграция Ghidra 12.1.4 / PyGhidra: офлайн-валидация

Дата: 2026-11-07. Scope: установка, единый ARM64 code-level RE toolkit,
два известных fixture, инструкции и supersession-реестр. Никаких действий на
устройстве, GUI или новых исследований. Общий timebox: 20:00:40–21:15:40 UTC.

## Установка и воспроизведение

Пин официального ZIP, опубликованный SHA256, пути JDK/venv/cache:
[`install_pin.json`](install_pin.json). Установка: [`install.log`](install.log).
Установка **PASS**: SHA256 OK, CPython3.13.5, PyGhidra3.1.0, JPype1.5.2,
Temurin21.0.12; завершена20:10:02UTC. Архив скачан в approved cache и сверен до распаковки; системных установок
и изменений основной `.venv` нет. Offline pip использует только wheels,
включённые в дистрибутив (включая runtime-зависимости PyGhidra).

```sh
CACHE=/home/stfu/.cache/opencode-tmp/opencode/ghidra-toolkit-20261107
mkdir -p "$CACHE" /home/stfu/tools
curl --fail --location --max-time 600 --output "$CACHE/ghidra_12.1.4_PUBLIC_20260921.zip" \
  https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.4_build/ghidra_12.1.4_PUBLIC_20260921.zip
printf 'ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db  %s\n' \
  "$CACHE/ghidra_12.1.4_PUBLIC_20260921.zip" | sha256sum -c -
unzip -q "$CACHE/ghidra_12.1.4_PUBLIC_20260921.zip" -d /home/stfu/tools
mv /home/stfu/tools/ghidra_12.1.4_PUBLIC /home/stfu/tools/ghidra-12.1.4
python3 -m venv /home/stfu/tools/ghidra-12.1.4-pyvenv
/home/stfu/tools/ghidra-12.1.4-pyvenv/bin/python -m pip install --no-index \
  -f /home/stfu/tools/ghidra-12.1.4/Ghidra/Features/PyGhidra/pypkg/dist pyghidra
/home/stfu/tools/ghidra-12.1.4-pyvenv/bin/python -c \
  'import pyghidra; from importlib.metadata import version; print("PyGhidra", version("pyghidra")); print("JPype1", version("JPype1"))'
```

## Единый вход

Из корня проекта, Python **отдельного PyGhidra venv**:
`OUTPUT` — намеренный экспорт в `artifacts/ghidra_toolkit_20261107/CASE`
для этой интеграции либо внешний каталог; это не каталог проекта Ghidra.

```sh
PY=/home/stfu/tools/ghidra-12.1.4-pyvenv/bin/python
$PY 06-tools/ghidra_decompile.py functions BINARY --filter NAME --output OUTPUT --timebox 300
$PY 06-tools/ghidra_decompile.py symbols BINARY --output OUTPUT --timebox 300
$PY 06-tools/ghidra_decompile.py decompile BINARY --function NAME --output OUTPUT --timebox 300
$PY 06-tools/ghidra_decompile.py xrefs BINARY --address HEX_IMPORT_ADDRESS --output OUTPUT --timebox 300
```

`functions`/`symbols` показывают импорт без полного auto-analysis;
`decompile`/`xrefs` выполняют auto-analysis через public PyGhidra API.
Для последних двух команд допустимы `--function` (точное короткое или qualified
имя; неоднозначность — ошибка) либо `--address` (hex import address).
`decompile --address` выбирает содержащую функцию; xrefs — ссылки **на/из
точного адреса**, не транзитивный callgraph всего тела функции.

`manifest.json` детерминированно сортирован и содержит путь/SHA256 исходного ELF,
реальную версию Ghidra, режим анализа, адреса и выгрузку. `decompiled.c` несёт
такой же provenance в заголовке. Логи `analysis.log` диагностические, не обязаны
быть побайтно детерминированными. ET_REL `.ko`: адрес Ghidra + имя memory block
и offset относительно его начала; это **не live kernel VA**. У PIE import VA
также не учитывает runtime ASLR. Импортёр применяет ELF relocations; исходный
бинарник не исполняется и не изменяется.

Каждый запуск создаёт свежий временный проект с явным `project_location`
**только внутри** approved cache из пина; JVM/Python temp и рабочий каталог
worker также внешние. Python-parent ограничивает всю JVM/import/analysis/export/
закрытие через `--timebox`; при timeout — manifest `status=timeout`, exit 124,
TERM/KILL process group (включая native decompiler), затем удаление проекта.
Повторный output не сохраняет старый `.c` при неудаче нового анализа.

Первый startup (7.315s, до импорта обоих ELF) выявил особенность12.1.4:
`ProjectLocator` запрещает path element с начальной точкой, включая `.cache`.
[`startup-project-path-error.log`](startup-project-path-error.log) и
[`initial-startup-tests.log`](initial-startup-tests.log) сохранены как диагностика,
не PASS. Решение без переноса/нового persistent state: открыть directory-fd
на per-run project directory в том же approved cache и передать явный
`/proc/self/fd/<fd>` в PyGhidra, проверив realpath внутри разрешённого корня.
FD закрывается после проекта; JVM temp продолжает использовать исходный cache.
Legacy `open_program` для этого не подходит: bundled
`pyghidra/converters.py:21–23` вызывает `Path.resolve()` и теряет alias
([`legacy-path-conversion-error.log`](legacy-path-conversion-error.log)).
Поэтому используется современный public API **PyGhidra3.1.0**:
`open_project(str)` → `program_loader` → `program_context` → `analyze`,
как в bundled `Ghidra/Features/PyGhidra/pypkg/README.md:293–309`.
Это единственное необходимое отклонение от предложенного legacy-примера API;
не добавлены зависимости, persistent alias или новый каталог проектов.

## Проверки

- Быстрый gate: `PYTHONDONTWRITEBYTECODE=1 python3 06-tools/test_ghidra_toolkit.py`.
  Результат: **5 PASS, 2 SKIP** за env-флагом; [`unit-tests.log`](unit-tests.log).
  Проверены ELF validation, SHA256/stable JSON, внешний project root/запрет
  выхода через symlink, CLI selectors/timebox, завершение worker по timeout.
- Known-answer gate (только в PyGhidra venv):
  `GHIDRA_TOOLKIT_KNOWN_ANSWER=1 /home/stfu/tools/ghidra-12.1.4-pyvenv/bin/python 06-tools/test_ghidra_toolkit.py`.
  Точные fixture-команды печатаются самим тестом; `.ko` ограничен **480 s**,
  каждый малый ELF-запуск — **120 s**, плюс максимум 5 s аварийного cleanup.
  **Последняя версия: 7 PASS за97.237s**, без timeout/skip;
  [`known-answer-tests.log`](known-answer-tests.log). Покрыт также переход
  `functions` (mangled имя до анализа) → `decompile` (после demangler),
  сохранением matching entry; существующие имена не становятся недоступными.
- Ручная сверка C с замороженными known-answer и отдельный stdlib clamp-model:
  [`known_answer_validation.json`](known_answer_validation.json) с provenance
  обоих ELF: **153 instructions, 65 536 inputs, mismatches0**. Повторить
  вычислительную часть (прямая транскрипция `module_backlight/decompiled.c:58–67`):

  ```sh
  python3 - <<'PY'
  import json
  from pathlib import Path
  old = json.loads(Path('artifacts/brightness_policy_recon_20261107/validation.json').read_text())
  minimum = old['panel_properties']['qcom,mdss-dsi-bl-min-level']
  maximum = old['panel_properties']['qcom,mdss-dsi-bl-max-level']
  mismatches = 0
  for level in range(65536):
      value = maximum
      if level <= maximum:
          value = level
      if value == 0:
          value = 0
      elif value <= minimum:
          value = minimum
      expected = 0 if level == 0 else max(minimum, min(maximum, level))
      mismatches += value != expected
  if mismatches:
      raise SystemExit('known-answer mismatch')
  print('PASS: 65536 clamp inputs; mismatches=0')
  PY
  ```
- Ссылочный gate реестра: stdlib `Path.exists` для6 Markdown local links — PASS.
  Поиск `.gpr`/`.rep`/JVM crash logs внутри worktree не нашёл Ghidra-проектов;
  per-run `run-*` в approved cache после gate не осталось.

## Known-answer: ручная сверка

### A. `msm_drm.ko`: PASS, LUT не достигает отправляемого DBV

SHA256: `1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804`.
[`module_backlight/manifest.json`](module_backlight/manifest.json) содержит
**153 инструкции** `dsi_display_set_backlight` и block-relative offsets.
В [`decompiled.c`](module_backlight/decompiled.c):

- :45–56 scaling/LUT читается в аргумент `__drm_dev_dbg`, включая
  `puVar6[(ulong)uVar8 / 0xffff + 1]`; это не присваивание исходному `param_3`.
- :58–67 `uVar8` заново инициализируется max DBV, затем выбирает исходный
  `param_3` и min clamp. Offsets `puVar7+0xbb` = `+0x5d8` (max),
  `(long)puVar7+0x5d4` (min), что совпадает с исходным disassembly.
- :68–75 полученный DBV либо сохраняется по `param_1+0x1570`, либо передаётся
  вторым аргументом `dsi_panel_set_backlight(puVar7,uVar8)`. LUT не входит в него.

Сверено с `../brightness_policy_recon_20261107/result.md:20–31,216–230`,
`validation.json` и исходным annotated body. При сохранённых min460/max16180
это `level == 0 ? 0 : max(460, min(16180, level))`; модель охватывает65 536
uint16 входов. Это static/model comparison, **не эмуляция модуля и не panel trial**.
Выбор DCS-vs-Linux-PWM в критерий этой функции **не включался**.

### B. ALS threshold consumer: PASS, не display setter

SHA256: `b1a3bbb2dcb2fc975403c40df5a8404f62d3c95ac7239f5cdc2b0c05a7643f71`.
Автоимпорт восстановил `_ZN15AlsCompensation9calculateEfj`;
после анализа имя — `AlsCompensation::calculate`, ELF entry `0x147a8`,
Ghidra entry `0x1147a8` / `.text+0xc7a8`.
**PIE импортирован с image base0x100000**: сохранённое ELF сравнение `0x148e4`
соответствует Ghidra `0x1148e4` / `.text+0xc8e4`, не live ASLR VA.
Для CLI `--address` брать именно адрес из нового manifest/functions, а не
без пересчёта подставлять старый ELF VA.

В [`als_threshold/decompiled.c`](als_threshold/decompiled.c):69 `uVar6` —
`getDCmode`; :85–88 `uVar1=0`, но при
`uVar10 <= *(int *)(this+0xf0) - 1U` выбирается `uVar6`; :109–111 этот
`uVar1` поступает в `PanelLux::getPanelLux`. Это точно соответствует
`effective_dc_for_als = (dbv >= 3601) ? 0 : read_panel_dc` в достигнутой ветке.
**3601 — значение сохранённого XML, а не константа в декомпиляте**:
`../current_display_path/als/als_comp_config.xml:42–45`; связывание ключа
`pwmToDcDbv` с `this+0xf0` — из уже решённого
`threshold_path.json`/`threshold_path.disasm.txt` (load/init `0x13524`).
Опциональная DBV map отсутствовала в сохранённой конфигурации; runtime instance
не читался. Это ALS-компенсация, не display setter и не числовая PWM-частота.

### C. `.gnu_debugdata`: PASS без ручной распаковки

[`debugdata_comparison.json`](debugdata_comparison.json),
[`als_symbols/manifest.json`](als_symbols/manifest.json),
[`als_dynsym.txt`](als_dynsym.txt): **467 Ghidra import symbols > 164 dynsym
entries (включая NULL)**. Само увеличение count могло бы включать generated
labels, поэтому дополнительно проверено восстановленное `IMPORTED` имя
`_ZN15AlsCompensation9calculateEfj`, **отсутствующее в dynsym-only**.
Ручное извлечение `.gnu_debugdata` не применялось; это локальные символы,
не DWARF-типы.

Полный цикл `symbols → functions → decompile → xrefs` выполнен на B;
[`als_xrefs/manifest.json`](als_xrefs/manifest.json) содержит6 incoming refs,
из них3 `UNCONDITIONAL_CALL` (остальные data/unwind/entry, не вызовы).
Два независимых свежих проекта B дают побайтно одинаковые manifest/C:
`als_threshold` и `als_threshold_repeat`; diagnostic logs из сравнения исключены.

## Ограничения и передача

Гидра не даёт отсутствующие DWARF-типы и не доказывает DDIC-семантику,
оптическую PWM-частоту, живой runtime-путь или совместимость firmware.
Все выводы здесь офлайн; не заявляется whole-product/live READY.
Исторические evidence не менялись; различия code/data и отсутствующие отдельные
скрипты честно отражены в `../../06-tools/archive/README.md`.
FD-alias рассчитан на текущее Linux `/proc`; переносимость на другие ОС и
произвольные архитектуры/бинарники не проверялась. GUI/device/whole-repo gates
намеренно не запускались; Python data/build-инструменты не изменены.

## Независимое ревью и вердикт

**Review-Sol-Global: PASS**, блокирующих и доказанных неблокирующих in-scope
замечаний нет; [`review.md`](review.md). Прочитаны фактический runtime/test,
документационный diff и C/JSON; код после ревью не менялся. Reviewer не запускал
проверки вместо исполнителя. Startup path/JPype overload/PIE-address issues
исправлены до этого ревью, зелёный97.237s gate соответствует последней версии.

**Принят как вспомогательный стандарт для ARM64 code-level RE.**
**Не закрывает DDIC-семантику** и не заменяет независимую проверку.
Соседний/основной агент может продолжать новым инструментом; текущая работа
останавливается на закрытом toolkit-контракте. Основной OLED/PWM R3 не закрыт,
сохранённый A9 baseline и hardware approval gates не менялись.
