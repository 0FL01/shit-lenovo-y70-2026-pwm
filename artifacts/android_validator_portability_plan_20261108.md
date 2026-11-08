# План минимальной Android portability qualification

Статус: **план, ни один Android probe здесь не выполнялся**. Только synthetic
userspace qualification перед возможным переносом offline validators; это не
local controller, не live admission и не новый factory15 experiment.
P85=14 disabled; физические PWM >=2000 Hz не доказаны. Пределы37/45/8,
SHORT60 и inherited OVERALL600 не изменяются.

## Основание и матрица

[Три qualified runs](p85_timed_stock_qualification_20261108.md#что-установлено)
(lines6–29) используют runtime `1785d32fd011314df3f1c5c55a5d3cbe0ee6b8a2`.
[Список13 runtime blobs](../06-tools/offline_local_snapshot_spike/runtime-source-blobs.json)
фиксирует точные источники. Наличие команды в исходнике само по себе не доказывает
её failure paths: ниже prior qualification означает успешные исполненные пути.

| Возможность | Уже exercised на Android | Новый обязательный probe |
|---|---|---|
| Shell и контексты | `/system/bin/sh`, set-eu, функции, substitutions, integer counters, traps, redirection; envelope UID2000 и selective su | Явный выбранный sh; noclobber/-C, >\|, FD8, read-r/EOF; отдельно нужные UID2000/UID0 contexts |
| Utility/files | mkdir-m700, umask077, cat/wc, rm/rmdir, id-u, stat %u/%a, owned chmod600 | stat %h; exact metadata stdout/rc/stderr; cmp-s, tr octal whitelist, tail-c1, od-An-v-tu1; cleanup faults |
| AWK | Regex/index, BEGIN/END/variables/exit PRE_GUARD predicate | arrays/delete, split/sub/match/RLENGTH, ENVIRON/ARGV/FILENAME, getline/close, %c byte preservation, actual frozen fragments |
| Числа/время | cut /proc/uptime; host Python GUARD_TIMING delta0..8 | Android floating-point boundary parity, microseconds, decimal/overflow rejection; clock/rate/suspend остаются отдельными unknown |
| Timeout | Успешные команды внутри timeout-k | Failure/kill/descendant behavior не доказаны; только отдельный own-sleep fixture, не реальный child |
| Ownership/publication | Existing root mutex и shell envelope workspace | Sealed immutable handoff, same-UID races, ambiguous publication, durable ledger не установлены |

Источники: [envelope](../06-tools/p85_batched_envelope.py) lines97–142,186–195;
[guard/caller](../06-tools/run_p85_timed_stock_trial.py) lines29–48,232–243;
[mutex](../06-tools/a9_reproduction.py) lines18–31.
Новые зависимости: [interval wrapper](../06-tools/offline_local_interval_spike/validate.sh)
lines27–68; [interval arithmetic](../06-tools/offline_local_interval_spike/interval.awk)
lines9–14,64–72; [envelope wrapper](../06-tools/offline_local_envelope_spike/decode.sh)
lines14–58; [byte decoder](../06-tools/offline_local_envelope_spike/decode.awk)
lines3–41; [snapshot wrapper](../06-tools/offline_local_snapshot_spike/validate_snapshot.sh)
lines28–68; [snapshot numeric predicates](../06-tools/offline_local_snapshot_spike/snapshot.awk)
lines3–32.

Corrective [capture wrapper](../06-tools/offline_local_validator_spike/validate_capture.sh)
frozen Git blob `b264e3be3be28a618614c3a58c231a98a37a0b4e`:
bootstrap/audit/cleanup lines14–45, metadata46–80, ASCII81–86,
final cleanup/verdict87–94. **Independent review pending at this assessment**;
freeze и host tests не означают readiness. Его /proc-FD capability на Android
**unqualified**. Он требует input regular/non-symlink/one-link/currentUID/0600,
capture<=262144B, actual producer rc0/empty stderr и final invocation rc0/empty
stderr плюс ожидаемый verdict. Verdict отдельно не receipt.

## Условия будущего запуска

Lead один координирует physical access. Сначала reviewed host-side synthetic
fixture bundle, expected results и source manifest; затем bounded userspace probe,
не запуск существующего trial/setup runner.

Сохранить [ADB preflight](../03-investigation/adb-remote.md) lines20–75,
existing [target identity](../06-tools/stock_c1_sweep.py) lines243–250 и
[mutex ownership](../06-tools/a9_reproduction.py) lines18–31. Не угадывать transport,
serial, address или paths; не присваивать чужой/stale lock. Идентификационные
read-only prerequisites отделены от synthetic тестов; никакого camera capture/UI.

`$Q` ниже — уникальная directory из проверенного manifest внутри явно выбранного
trusted temporary parent, не literal guessed path. Создать atomically0700 с
umask077; refuse existing/symlink path. Не предполагать наличие Android /tmp:
передать explicit absolute TMPDIR. Отдельные owned dirs для UID2000 и UID0;
не исполнять все старые envelopes как root. Root boundary не расширять и новых
grants не создавать.

Первый проход: <=1MiB суммарных synthetic inputs, фиксированный manifest случаев,
отдельные rc/stdout/stderr каждой команды; предзаданный короткий deadline
(предлагается10s на batch, подлежит review до запуска). По истечении — прекратить
новые dispatch, сверить состояние собственного процесса, не повторять вслепую.
Host timeout не remote cancellation. Эта цифра не новый successful-path bound
для sequencer и не изменение37/45/8/60/600.

## Минимальные synthetic тесты

### 1. Без записи на устройство

`id -u`; `command -v awk od tr cmp tail wc stat mkdir rm rmdir timeout cut`;
`printf '%s\n' "$((16777216 + 25165824))"`.
Existence не доказывает flags/semantics. Через выбранный sh/AWK выполнить:

```sh
awk 'BEGIN {
  x=999999999*1000000+999999;
  if(sprintf("%.0f",x)!="999999999999999")exit 1;
  if(split("12.34",a,".")!=2 || a[1]!="12" || a[2]!="34")exit 1
}'
```

### 2. Owned temporary file bytes/utilities

Следующие фрагменты — входы будущего reviewed harness, не готовый launch script.
Harness обязан проверить каждый rc и каждый stderr отдельно; ожидаемые bytes
сравниваются с host-built fixture, не с непроверенным выводом той же утилиты.

```sh
printf '\000\011\012\015\037\040\101\176\177\200' > "$Q/bytes"
wc -c < "$Q/bytes"
od -An -v -tu1 < "$Q/bytes"
tr -cd '\011\012\040-\176' < "$Q/bytes" > "$Q/ascii"
printf '\011\012\040\101\176' > "$Q/expected"
cmp -s "$Q/ascii" "$Q/expected"
tail -c 1 < "$Q/bytes"
stat -c %u "$Q/bytes"
stat -c %a "$Q/bytes"
stat -c %h "$Q/bytes"
```

Ожидаются10 bytes, od tokens0/9/10/13/31/32/65/126/127/128,
exact five-byte filtered output, tail128 и metadata currentUID/600/1.
Добавить empty input, finalLF/noLF, CR/NUL/nonASCII и32768/32769-byte lines.
Данные не помещать в shell variables/substitutions.

### 3. Noclobber и live unlinked FD

Проверить fresh `(set -C; : > "$Q/exclusive")`, затем отказ того же вызова
без изменения файла, затем owned-only `>| ` override. Для FD повторить отдельно
empty, LF-only и NUL-only случаи в fresh subshell:

```sh
(
  umask 077
  set -C
  : > "$Q/audit"
  exec 8>>"$Q/audit"
  rm "$Q/audit"
  test -f /proc/self/fd/8
  test ! -s /proc/self/fd/8
  printf '\000' >&8
  test -s /proc/self/fd/8
  wc -c < /proc/self/fd/8
  od -An -v -tu1 < /proc/self/fd/8
  exec 8>&-
)
```

Для NUL ожидаются count1/token0, для LF count1/token10. **Builtin -f/-s
после unlink — именно byte-diagnostic decision frozen wrapper**; stat/wc
дополнительны. Проверить также FD inheritance выбранными внешними utilities и
exact frozen cleanup sequence. Unlinked audit FD не делает inputs immutable.

### 4. Frozen validator subset и failure propagation

Для каждого компонента: valid fixture, semantic rejection, malformed/truncated
bytes, producer rc7, producer stderr LF/NUL; bounded trusted local utility stubs
для valid-output+rc7 и valid-output+LF/NUL diagnostics, cleanup failure.
Stubs только в отдельном private fixture PATH, без изменения системных файлов.

- Capture: currentUID/0600/one-link gates, metadata canonical decimal+LF<=10digits;
  no final success при final AWK diagnostics/nonzero даже после verdict.
- Interval: quiet2s boundary, protected-origin/collision/tail synthetic cases,
  timestamp microseconds и nearby floating-point cases.
- Envelope: byte1..127, noLF payload, framing/chunk boundary, exact published
  sections/SUCCESS; reject NUL/nonASCII/partial publication/unknown invocation.
- Snapshot: STATE_ONLY отдельно от GUARD_TIMING, supplied OWNER empty не owner
  proof; ESD не фабриковать. Guard0/8 и nearby decimal values,120±.03 thresholds.
  Его [documented limitation](../06-tools/offline_local_snapshot_spike/README.md)
  line16 сохраняется: bootstrap/final-cleanup diagnostics trusted NUL-free text,
  не новый byte-exact guarantee.
- `ulimit -f` units **unknown before test**. В отдельном subshell set-f1 и
  finite producer максимум2048 bytes в owned file; сохранить actual rc/size.
  Не предполагать512-byte units и не использовать unbounded fill-disk writer.
- Не копировать на Android Python test runners как dependency. Host заранее
  экспортирует нужные synthetic fixtures и oracle expectations.

Cleanup: удалять только фиксированные имена реально созданного instance,
затем rmdir; сверить отсутствие. При uncertain mkdir/rename/cleanup сохранить
receipt и quarantined remnants, не rm-rf/glob и не объявлять success. Не очищать
чужой mutex или root-owned files из UID2000.

## Что этот проход не докажет

- Immutable acquisition: stat/chmod/noclobber и FD audit не защищают от shared-UID
  races, existing writable FD или root. Нужен отдельный sealed handoff design.
- Durable ledger: обычный rename/TERM/KILL тест не доказывает power-loss durability,
  fsync/order или atomic multi-file receipt; missing/torn result остаётся unknown.
- Clocks: optional короткие read-only uptime samples с own sleep дают только
  observations. Не доказывают suspend/rate/origin equivalence; suspend не инициировать.
- Cost: маленький probe не ограничивает max-cap latency/storage. Отдельный будущий
  review нужен для capture256KiB, interval16MiB, snapshot display4MiB и envelope
  raw24MiB с od expansion~4.25x, одновременно raw+expanded+decoded+diagnostics.
  Не выполнять maximum-size stress автоматически.
- Никаких DSI/panel register операций, settings, reboot, camera capture/UI,
  kernel tracing, SELinux/mount/security-policy изменений, установки ПО,
  persistent access или автозапуска.0700/0600 относятся только к owned fixtures.

[Integration design](p85_local_sequencer_integration_design_20261108.md)
lines43–61,175–216,218–226 оставляет staging, clock/budget и durability открытыми.
Рекомендуемый итог первого прохода: **Android portability prerequisites observed**,
не NORMAL_RESERVED admission. Factory15 controller ещё не реализован.
