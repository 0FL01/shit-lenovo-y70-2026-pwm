# Независимый timeout microprobe (только offline)
Статус: host-only validated; Android behavior UNKNOWN. Ничего на Android не запускалось.

## Замороженный контракт
Точный 359-byte Android command хранится в android_command.txt (без конечного LF).
SHA256: a823fc4f4768534fc2a0e498262ecd542da2e8cf5b330c263e6b7e1a9cf3e306.
probe.py SHA256: 58eb6b22ef24fd69d9f12129145a94ef89354626105dfc62c5a73fcadd2381de.
test_probe.py SHA256: 9e49b0d975379f04dca70a713b1cfd17d0b187681a0342930a02599eab924c94.
Это pin исполняемого предложения и его parser, не checksum каждого отчёта.

Команда: /system/bin/timeout -k 1s 1s вокруг собственного /system/bin/sh,
который печатает PID и единственную строку /proc/$$/stat, затем exec
/system/bin/sleep 2s. Дочерний shell не оставляет дополнительный shell-потомок.
Внешний shell отдельно печатает фактический timeout_rc, END, завершается 0.
Есть ровно один конечный sleep, без loops, файлов, services и recovery.
Identity/stat остаются приватными; в публичный результат идут только verdict/rc.
Не запускать файл shell-ом на host: это Android-команда, не host-команда.

## Admission принадлежит lead
Lead единолично выполняет server/version preflight, свежую immutable binding
target/camera, identity/root/Enforcing/module/panel guards, read-only mutex absence,
проверку exact source/command pins и byte caps. Здесь нет ADB, runner imports
или автоматического запуска. До независимого review и принятия lead всё offline.

stdout и stderr должны быть ограничены host transport до накопления, stdout <=4096,
stderr пуст, transport завершён, wrapper_rc строго int0. Parser cap не является
device-side output/termination guarantee. Только exact 4 records принимаются.
124 означает только observed-timeout-124. rc0/125/137/любое другое остаётся UNKNOWN.
Ни один результат не разрешает следующий тест или return sequence.
Отсутствующая/дублированная/обрезанная строка и сомнительный transport: UNKNOWN,
не повторять оригинальную команду, не считать host deadline cancellation.
Внешний deadline для транспорта выбирает lead; 8s в tests лишь host acceptance bound.

## Отдельное наблюдение
Только после полного rc124 parse reconciliation_command(observation) предлагает
read-only /proc/<numeric PID>/stat command. Оно не выполняется автоматически.
parse_reconciliation различает ORIGINAL_IDENTITY_PRESENT,
PID_REUSED_OBSERVATION_ONLY, NOT_VISIBLE_OBSERVATION_ONLY, UNKNOWN_READ_FAILED.
PID/starttime сравниваются, PID канонический numeric; произвольного command API нет.
ORIGINAL_IDENTITY_PRESENT включает zombie, не утверждает выполнение CPU.
NOT_VISIBLE не доказывает universal process termination: proc visibility/races остаются.
READ_FAILED или неполный transport остаются UNKNOWN.
При неполном probe даже частичный PID нельзя использовать как подтверждённую identity.
Минимальный следующий шаг: lead изучает уже полученный приватный transcript/transport
без повторного запуска; при отсутствии полной identity ownership остаётся UNKNOWN.
Нельзя сканировать/убивать чужие процессы, автоматически recovery/reboot.
При полном124 самый малый следующий device шаг именно отдельный proc-read выше.

## Host verification 2026-11-08
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v test_probe: 5/5 PASS.
PYTHONDONTWRITEBYTECODE=1 python3 -O -m unittest -v test_probe: 5/5 PASS.
В каждом запуске реальный собственный finite host sleep был прерван timeout,
rc124 принят отдельно от wrapper0, read-only reconciliation: absence/reuse accepted.
Tests не печатают PID/starttime. Mapping host-only явно ограничен
/system/bin/{sh,timeout,sleep} -> /bin/sh,/usr/bin/timeout,/usr/bin/sleep.
Эта mapping не меняет Android command artifact. No bare asserts.
Fault coverage: malformed PID/stat, status aliases, mismatch PID/start generation,
missing/duplicate/truncated transcript, stderr, transport и wrapper failure.
Host GNU timeout не квалифицирует Android Toybox0.8.12.
Inventory и сохранённый help подтверждают лишь наличие/синтаксис; help rc125 не test.

## Остаточные ограничения
Нет математического wall-clock bound при произвольном scheduler/kernel stall.
Нет универсальной process-tree гарантии; наблюдается только одна собственная identity.
Exec failure тоже не считается successful timeout, а stderr/неполный transcript отвергается.
Точность timing, suspend clocks, Android поведение kill grace пока UNKNOWN.
Ни generic57 portability batch, ни DSI sequencer, ни 37/45/8/60/overall600 admission
этим примитивом не заменяются и не разрешаются.


## Завершённое ограниченное target observation

2026-11-08 один fixed primitive и отдельный known-PID proc-read выполнены:
[результат и независимый saved-evidence replay](../../artifacts/android_timeout_microprobe_20261108_01/result.md).
Это последующее limited target observation, уточняющее исходный host-only статус
выше: timeout124 / NOT_VISIBLE_OBSERVATION_ONLY. Не universal termination,
не batch admission, не brightness/restore/PWM proof. Frozen command/parser/tests
не изменены; полный batch остаётся HOLD.
