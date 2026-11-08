# Изолированный OFFLINE interval spike

Статус: **offline feasibility**, не production validator и не разрешение следующего
child. Только сохранённые текстовые kernel snapshots. Нет ADB, DSI, acquisition,
controller CLI, установки зависимостей или изменений qualified runtime.

## Запуск

Из корня репозитория:

```sh
sh 06-tools/offline_local_interval_spike/validate.sh quiet PWM_TEST_BEGIN PWM_TEST_END 120 abcdef012345 /absolute/saved.log OFFLINE
PYTHONDONTWRITEBYTECODE=1 python3 06-tools/offline_local_interval_spike/test_interval.py
PYTHONDONTWRITEBYTECODE=1 python3 06-tools/offline_local_interval_spike/test_interval.py --corpus
PYTHONDONTWRITEBYTECODE=1 python3 -O 06-tools/offline_local_interval_spike/test_interval.py --corpus
```

Аргументы: `read|quiet|dispatch|guard BEGIN END|- 120|1 NONCE|- LOG OFFLINE`.
`120` означает actual=120/group=0x3, `1` означает actual=1/group=0x8;
оба требуют 1440x3168, peak120, clock1234000000. `dispatch` и `guard`
принимают только actual120 и обязательный 12-hex writer nonce. `-` отключает
writer-collision проверку только для ordinary read/quiet. `guard` использует
единственный protected BEGIN; аргумент END обязан быть `-`. Код возврата 0 означает
только успешную offline семантическую проверку, 1 отказ, 2 неверный вызов.

## Операции и точные источники oracle

- `read`: `stock_c1_sweep.verify_read_interval` + обязательный END→dump-tail
  guard из `TimedStockTrial.envelope`. Уникальные ordered BEGIN/END, pinned
  native state до BEGIN и в конце, никаких mode/failure внутри, никаких
  DSI/mode/failure/LOST после END. **Это не exact read-packet whitelist.**
  Передача внутри read допускается; её payload policy остаётся отдельным gate.
- `quiet`: `dsi_trial_transaction.qualify_quiet` BEGIN→весь dump, включая tail,
  плюс реальный `TimedStockTrial.quiet` timestamp check END−BEGIN>=2s.
  При заданном writer nonce проверяется отсутствие collision во всём retained log,
  как в `prepare_writer`. Используются точные микросекунды и дополнительный
  floating-point threshold Python: граница ровно 2s может округлиться ниже 2.
- `dispatch`: `qualify_quiet` protected-origin→fresh PRE_DISPATCH, collision
  во всём retained log и unchanged AWK predicate из `guard_command`.
  **Вторая 2s quiet не добавлена.** Для return15 origin обязан быть
  `SHAM15_HOLD_BEGIN`, а не более поздний return-prequiet BEGIN. Привязка origin
  к этапу остаётся обязанностью caller; тест corpus выбирает его по текущему run.
- `guard`: только unchanged embedded AWK log predicate из `guard_command`,
  со строгим локальным grammar. Любой новый malformed native event сбрасывает
  старую хорошую anchor; mode→120 после protected origin тоже запрещён.
  Это не реализация surrounding remote command и не проверка fresh acquisition.

Oracle imports только offline functions. Read tail-check AST компилируется из
текущего production метода; timed quiet вызывается с mocked base acquisition.
Guard oracle запускает **только извлечённый AWK**, никогда shell guard command.
State/root/panel/owner/boot/DBV/DC/power checks здесь не подменяются mock-проверками:
они явно находятся вне этого компонента. `GUARD_TIMING` не портирован; current
caller требует exact `GUARD_TIMING decimal decimal\n` и 0<=delta<=8.

## Принятый более узкий dialect

ASCII, LF-terminated, максимум16MiB, строка <=32768 bytes, без NUL/CR/control
bytes, кроме tab. Relevant events имеют ровно один timestamp
`[ *digits.ffffff] `, максимум9 integer digits, ровно6 fractional digits.
BEGIN/END должны занимать весь body строки; embedded/duplicate/reordered
markers и несколько relevant events на строке отклоняются. Все вхождения
`dsi_display_set_mode` и `dsi_ctrl_cmd_transfer` учитываются, а не выбирается
последний удачный regex match. Native grammar целиком anchored на сохранённый
`[drm:... [msm_drm]] [msm-dsi-info]: mdp_transfer_time=..., hactive=...`
формат с фиксированным порядком/пробелами. Transfer grammar целиком anchored
на `dsi-ctrl-N: dsi_ctrl_cmd_transfer len=N, type=0xHEX hs|lp cmds= XX ...`.
Len/type/byte semantic consistency и exact factory payload здесь не проверяются.

Любой malformed relevant historical event, LOST или Command transfer failed
отклоняется даже до BEGIN: сознательное ужесточение Python callers. Неизвестные
обычные строки допускаются, но не могут скрыть relevant token. Отсутствие
последнего LF выявляет только часть truncation; удаление целых строк/суффикса
невозможно надёжно отличить от короткого настоящего dump без trusted envelope.
Это не доказательство полноты acquisition, source identity или отсутствия
неизвестного firmware vocabulary. Валидный сохранённый старый dump не становится
fresh от успешного результата. Набор конечных тестов не доказывает universal
subset/equivalence на произвольном языке логов или всех AWK implementations.

## Зафиксированная база и результаты

Initial/base checkout HEAD: `0c9aad60122ab3a88eedad2efb18977dbf8b9c36`.
При исправлении review замечаний current main уже
`3bf33d60a33af3657bf278e00252f797a4d2c182` после независимого capture spike;
этот компонент не зависит от него.
Qualified runtime provenance: `1785d32fd011314df3f1c5c55a5d3cbe0ee6b8a2`.
Точные Git blobs текущих oracle источников:

- `06-tools/dsi_trial_transaction.py`: `64b85ce49f80cb10ca50e85da6cb581968954764`
- `06-tools/run_p85_timed_stock_trial.py`: `9c804b7f12c5a77768d2487c31703b66c540f62c`
- `06-tools/stock_c1_sweep.py`: `b37529b22da7991bc55cc8a73a387787c6926058`

`runtime-before.blobs` фиксирует исходные56 tracked `06-tools/*.py` из initial
checkout, без добавления новых файлов независимого spike; тест сверяет их
до и после запуска. Созданные файлы находятся только в этой новой директории.
Private corpus не копируется в Git, не выводится и не сохраняется в отчётах.
`saved_sections` является **только extraction helper существующих fixtures**,
не proposed production byte-envelope parser. Три corpus directories:
`~/.cache/legion-y70-p85-timed-stock/p85_timed_stock_a001_20261108_{01,02,03}`.

`results-normal.json` и `results-optimized.json`: одинаковые verdict counts
на обычном Python и `-O`; никаких assert-dependent gates в тестах:

- 312 synthetic cases:164 accepted,95 oracle rejections,53 strict rejections.
- 39 saved snapshots:39 accepted и39 combined-oracle accepted.
- 324 saved-corpus mutations:78 accepted; каждый accepted также oracle accepted.
- 6 дополнительных guard predicate rechecks dispatch snapshots. Это не сохранённые
  fresh remote guard-kernel acquisitions и не evidence их freshness.
- 0 unsafe acceptances в проверенном конечном наборе;56 frozen runtime files
  неизменны. Synthetic fixtures встроены в тест и работают без private corpus.
- 42 invalid-argument tests проверяют wrapper и прямой AWK invocation с2s timeout;
  BEGIN/END пустые, overlapping, malformed и остальные invalid параметры
  завершаются exit2 до чтения данных. AWK BEGIN больше не оставляет только bad flag.
- 24 producer-failure injections: wc (обе позиции),tail,od,tr,awk с valid output
  + exit7, valid output + stderr, missing output, truncated output. Все отклонены,
  все24 private scratch directories очищены; ACCEPT не выдаётся.

Wrapper не использует pipelines или command substitutions для byte checks.
Каждый producer отдельно пишет stdout/stderr в фиксированные owned scratch
files; ненулевой status или любой stderr запрещают продолжение. Numeric outputs
читаются builtin read с проверкой полного единственного LF record; окончательный
AWK verdict также проверяется и выдаётся только после cleanup. Scratch directory
создаётся atomically с0700, файлы0600, per-file ulimit16MiB, удаляются только
перечисленные имена и затем directory. Это ownership **временных файлов**, не
подтверждение ownership/freshness входного kernel evidence. Shell/platform tools
остаются доверенными: status checks не аутентифицируют скомпрометированный
executable, который подделывает результаты и возвращает success. Повторное чтение
изменяемого input по-прежнему требует внешнего immutable staging/TOCTOU gate.

Покрытие: отсутствующие/embedded/duplicate/reordered markers, multiple tuples
и transfers в строке, stale/malformed latest anchors, transient mode→120,
after-END activity, collision до/после interval, LOST/failure, partial final
record, NUL, numeric suffix/leading zeros, whitespace/order ambiguity,
ambiguous timestamps, quiet<2s и floating-point boundary, accepted mutations.

## Неперенесённые обязательные gates

Trusted fresh acquisition; byte-envelope/stdout boundary/nonce/source binding;
immutable owned staging и TOCTOU; exact factory payload policy; fresh state;
camera barriers; finite deadline/remaining-return budget; независимые watchdog
и recovery неизменны. Любой failure, unknown outcome или log loss запрещает
следующий child: reboot-only uncertainty, без blind15/page0/retry.
Unknown P85=14 остаётся disabled. Пределы37/45/8 и watchdog60s не ослаблены.
Host timeout не является remote cancellation. Никакого нового local controller.
