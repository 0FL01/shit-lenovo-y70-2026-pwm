# Limited Android timeout observation — 2026-11-08

Статус: **confirmed-on-target limited observation; independent saved-evidence
replay PASS**. [Санитизированный результат](result.json), [frozen acquisition](acquire.py)
и [контракт primitive](../../06-tools/android_timeout_microprobe/README.md).
Один запуск, exit0, завершён 2026-11-08T23:14:03.907659 UTC.
Acquisition SHA256: d201fd7658f4621b8dfbfe09ac074c79fb69a5cac96b175c8b4848d01157376c.

Fixed timeout -k1s /1s исполнил только свой конечный sleep2s: observed timeout124
при wrapper0. Отдельный read-only /proc/<known PID>/stat дал
NOT_VISIBLE_OBSERVATION_ONLY. Это наблюдение одной ранее разобранной identity,
не universal process-tree termination и не гарантия kill grace или clock timing.

Existing-server/version preflight, fresh distinct immutable target/camera bindings,
identity/root/module/BOE-v4/Enforcing guards прошли. Boot одинаков до/после;
mutex отсутствовал до/после. Camera: только три getprop. Device files, settings,
experimental DSI, traces и reboot не менялись; brightness/current restore не измерены.

## Timing and evidence

13 последовательных events, 708 accepted bytes; whole preflight/acquisition sequence
23:13:53.894114–23:14:03.907659 UTC = 10.013545 s, не «двухсекундный весь опыт».
Сам timeout transport event: 23:14:00.046851–23:14:01.621388 UTC,
reported elapsed 1.5742278120014817 s. Отдельный proc-read:
23:14:01.622340–23:14:02.190010 UTC, elapsed 0.5673554780660197 s.
Это host elapsed observations с transport overhead, не Android worst-case bounds.
Все exact per-event timings/caps/status находятся в result.json.

Independent replay проверил exact private command bytes/hashes, expected order,
wrapper rc0, caps, public/private event equality, timestamps, полные streams и
complete-frame partial streams; совпадений без расхождений 13/13. Frozen parser
повторно вывел timeout124 и NOT_VISIBLE_OBSERVATION_ONLY. Identity/root/module/
panel/UID/Enforcing/mutex и boot equality проверены без публикации private values.
Preflight/binding flags подтверждаются frozen acquisition source и lead execution
record, но отдельный raw host preflight transcript не сохранён.

## Host verification and limits

Независимые 8 acquisition transport fake-socket tests normal/-O PASS;
5 microprobe host tests normal/-O PASS. Acquisition исправляет host deadline:
проверяет каждое recv и exit, применяет byte cap до чтения payload, сохраняет
только complete-frame partial streams при failure. Incomplete current-frame bytes
не сохраняются. Host acceptance deadline никогда не означает remote cancellation.

Ни full57 batch, ни controller/DSI admission не разрешены. Whole batch lifetime,
process reconciliation, storage и exact owned cleanup остаются HOLD. Последний
experimental DSI по-прежнему timedstock03 (19:07:07.888880 UTC), native828 restored
тогда; этот опыт не обновляет restore claim. Unknown P85=14 disabled,
37/45/8/60/overall600 не ослаблены; физические PWM >=2000 Hz не доказаны.
