# Компактная Ghidra-дистилляция DDIC response framing

2026-11-08. Только offline static analysis; новых действий на устройстве нет.
`reported`: соседний провайдер остановил чтение полного Ghidra-экспорта флагом
`cyber_policy`. Поэтому агентам предназначены brief/excerpt, не полные листинги.
Это изменение способа представления evidence, не обход safety-проверок и не
новое доказательство DDIC semantics, runtime binding или физических PWM Hz.

## Вход и прежние экспорты

До удаления прочитаны все три исходных `manifest.json`; их структурная проекция
сохранена в [original_exports.json](original_exports.json) и точно сверена с
оригиналами (включая incoming/outgoing xrefs, без массива инструкций).

- Бинарник: `artifacts/kernel/gki_r59/target_vendor/msm_drm.ko`.
- SHA256: `1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804`.
- Ghidra `12.1.4`, язык `AARCH64:LE:64:v8A`, ET_REL, auto-analysis.
- Прежний корень: `/home/stfu/.cache/opencode-tmp/opencode/ghidra-toolkit-20261107/ddic-response-20261107/`.

| Каталог | Режим / обязательный selector | Entry `.text+offset` / import | Инструкций |
|---|---|---|---:|
| controller-transfer | decompile / `--function dsi_ctrl_cmd_transfer` | `0x1970c0` / `0033db30` | 515 |
| read-data | decompile / `--function dsi_ctrl_hw_cmn_get_cmd_read_data` | `0x19161c` / `0033808c` | 211 |
| read-data-xrefs | xrefs / `--function dsi_ctrl_hw_cmn_get_cmd_read_data` | `0x19161c` / `0033808c` | — |

Точный прежний `--timebox` **unknown**: успешные manifests его не содержат,
все три `analysis.log` пусты. Default инструмента был 300 s; приписывать его
исходным shell-командам нельзя. Ни shell argv, ни явный `--project-location`
не сохранены. Команды ниже воспроизводят selectors с новым явным лимитом 480 s.

## Формат brief и воспроизведение

Каждый `*/manifest.json` режима `brief` содержит provenance, имя/entry,
`size_bytes` распознанного Ghidra body (не ELF symbol size), число инструкций,
все xrefs на entry с содержащими функциями, уникальные разрешённые call-targets,
прямо адресуемые defined strings, scalar-операнды кроме 0/1 и `branch_count`.
Константы включают смещения и маски, не восстанавливают составные значения;
`branch_count` считает jump-инструкции, не calls/returns/CFG edges.
Строка возвращается целиком от начала defined data; поле `reference` отличает
ссылку внутрь неё. Косвенные вызовы, tail jumps и косвенные строки могут отсутствовать.
`callers` — название поля для xrefs, **не только CALL**.

Из корня проекта, новый output во внешнем approved cache (не перезапись evidence):

```sh
PY=/home/stfu/tools/ghidra-12.1.4-pyvenv/bin/python
BIN=artifacts/kernel/gki_r59/target_vendor/msm_drm.ko
CACHE=/home/stfu/.cache/opencode-tmp/opencode/ghidra-toolkit-20261107
REGEN=$(mktemp -d "$CACHE/ddic-response-regenerated-XXXXXX")
for CASE in controller-transfer read-data catalog-setup; do
    case "$CASE" in
        controller-transfer) FN=dsi_ctrl_cmd_transfer ;;
        read-data) FN=dsi_ctrl_hw_cmn_get_cmd_read_data ;;
        catalog-setup) FN=dsi_catalog_ctrl_setup ;;
    esac
    "$PY" 06-tools/ghidra_decompile.py brief "$BIN" --function "$FN" \
        --output "$REGEN/brief/$CASE" --timebox 480
done
```

Для регенерации прежнего сырья (читать агенту только `excerpt.c`/brief):

```sh
"$PY" 06-tools/ghidra_decompile.py decompile "$BIN" \
    --function dsi_ctrl_cmd_transfer --lines 10:16 \
    --output "$REGEN/raw/controller-transfer" --timebox 480
"$PY" 06-tools/ghidra_decompile.py decompile "$BIN" \
    --function dsi_ctrl_hw_cmn_get_cmd_read_data --lines 10:16 \
    --output "$REGEN/raw/read-data" --timebox 480
"$PY" 06-tools/ghidra_decompile.py xrefs "$BIN" \
    --function dsi_ctrl_hw_cmn_get_cmd_read_data \
    --output "$REGEN/raw/read-data-xrefs" --timebox 480
```

`decompiled.c` остаётся полным evidence на диске; `excerpt.c` добавляет свой
provenance и **только** физические строки 10..16 этого файла (его исходный
provenance занимает строку 1). Выход за границы — ошибка, не silent clipping;
полный evidence сохраняется, старый excerpt удаляется. Убрав `--lines`, получим
обычный прежний decompile без фрагмента. ET_REL import address/block+offset
никогда не приравниваются к live VA.

## Проверки

### Согласование с прежним результатом

Новые brief: [controller-transfer](controller-transfer/manifest.json),
[read-data](read-data/manifest.json), [catalog-setup](catalog-setup/manifest.json).
Последний добавлен как владелец DATA-xrefs на helper.

| Brief | Recognized body, bytes | Instructions | Jump-инструкций |
|---|---:|---:|---:|
| controller-transfer | 2060 | 515 | 86 |
| read-data | 844 | 211 | 36 |
| catalog-setup | 1712 | 428 | 22 |

Provenance, entries, instruction counts первых двух и **все три helper xrefs**
точно совпали с исходной проекцией. `.text+0x19bdbc/0x19c088` — `DATA` из
`dsi_catalog_ctrl_setup`, плюс `EXTERNAL Entry Point`; это не прямые вызовы.
Helper отсутствует среди разрешённых controller callees: это не опровержение
косвенного slot-call и не доказательство его runtime binding.

С [result.md:43–100](../result.md) структурных расхождений нет: controller body
содержит 515, **не 539** instructions; прежние 24 пропущенных words не восстановлены.
Среди controller scalar-операндов есть `0xa/0xe/0x10/0x28/0x258/0xdc0`, среди
helper — `0x6/0x10`; сами по себе они не доказывают MRPS/skip/dataflow.
Буквального `0x26` (38) в brief нет — отсутствие immediate не опровергает
вычисляемое значение итерации. Сохранённая `../analysis.json`/условная Python-модель
по-прежнему дают MRPS `10→24→38→40`, normalized counts `16/30/44/46`, offsets
`0/14/28/42`, skip `0/0/0/12`, copied `16/16/16/4`, allocation 48 и overrun-domain
P1..10. Таблица сверена с моделью, regression ниже зелёный; **brief не заменяет
независимую instruction-level проверку этой арифметики**. DDIC semantics,
live headers/WC/counts, фактическое повреждение памяти и PWM Hz не установлены.

После этой сверки удалён **ровно** прежний `ddic-response-20261107/` из cache,
по решению владельца после `reported cyber_policy`-инцидента соседнего провайдера.
`test ! -e /home/stfu/.cache/opencode-tmp/opencode/ghidra-toolkit-20261107/ddic-response-20261107/`
прошёл. Другие существовавшие cache/evidence не удалялись. Это регенерируемое
сырьё: команды выше создают полные C/manifest и excerpts в **новом** `$REGEN`.
Прежняя абсолютная ссылка в frozen `../result.md:18` теперь историческая;
исходный отчёт намеренно не редактировался.

### Гейты

Быстрый gate (Ghidra не запускается):

```sh
python3 06-tools/test_ghidra_toolkit.py
```

9 PASS / 2 SKIP, 0.530 s — [unit-tests.log](unit-tests.log).
Проверены обязательный selector brief, формат/границы диапазона, включительность,
provenance excerpt, сохранность полного C при ошибке и удаление старого excerpt.

Полный gate выполнен **один раз**:

```sh
env GHIDRA_TOOLKIT_KNOWN_ANSWER=1 /usr/bin/time -p \
  -o artifacts/ddic_response_framing_20261107/ghidra_distill/known-answer-time.txt \
  /home/stfu/tools/ghidra-12.1.4-pyvenv/bin/python 06-tools/test_ghidra_toolkit.py \
  > artifacts/ddic_response_framing_20261107/ghidra_distill/known-answer-tests.log 2>&1
```

11 PASS, unittest 161.978 s, elapsed **162.04 s** (user 541.64 s / sys 30.65 s):
[log](known-answer-tests.log), [time](known-answer-time.txt).
ET_REL brief/backlight 153 instructions, recognized size 612 bytes, caller/callee,
строки/константы/jumps; настоящий `decompile --lines 10:16`; прежние режимы,
debugdata и детерминированность C/JSON; ET_DYN brief по imported имени и адресу
дают одинаковый результат кроме selector. Test outputs временные во внешнем
cache и автоматически очищены; существующие toolkit artifacts не перезаписывались.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s 06-tools \
    -p test_ddic_transport.py -v
```

1 PASS / 0.002 s — [framing-tests.log](framing-tests.log). Это regression
условной FIFO/CRC-модели, не запуск target code и не live framing qualification.

Foreground `Review-Sol-Global`, session `ses_e48264b6effedMBXF0v3Stm240`: **PASS**
фактического кода/артефактов без замечаний. Reviewer сам тесты не запускал;
удалённые оригиналы повторно не сверял. После review добавлена только эта запись
и её отражение в WORKSTATE; runtime/tests не менялись.
