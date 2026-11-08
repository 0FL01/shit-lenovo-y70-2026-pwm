# FD byte probe01: остановка, проверка остатков и точная очистка

Статус: **confirmed-on-target STOP; independent saved-evidence replay PASS для
сохранённой остановки, inspection и cleanup**, не PASS самой FD-пробы.
[Исходный result.json](result.json) и [source](acquire.py) сохранены неизменными.
Завершение 2026-11-08T23:22:43.226735 UTC: wrapper rc90, stdout0, stderr48 B:
`cat: /proc/self/fd/8: No such file or directory` с конечным LF.
9 acquisition events /342 accepted B. Cause CLOEXEC не доказана.

[Последующая read-only inspection](inspection.json): 22 events /568 B,
закончена 23:25:45.233318 UTC. Ровно пять файлов: owner и owner.ref по38 B,
expected-lf1 B, expected-both2 B, lf0 B; both отсутствует. Это локализует отказ
первого cat. Directory UID2000/mode700; все пять файлов UID2000/mode600,
nlink1, regular/non-symlink; exact owner bytes проверены, boot unchanged.

[Отдельная cleanup](cleanup.json) заново проверила guards, ownership и содержимое:
24 events /568 B, завершена 23:27:21.906322 UTC. Удалены только проверенные
точные имена, owner последним, затем rmdir; отсутствие exact owned directory
проверено независимо. Никакого broad deletion/adoption; original failed result
не превращён в успешную пробу. Saved-evidence replay обоих этапов PASS.

## Граница вывода

В [старом capture wrapper](../../06-tools/offline_local_validator_spike/validate_capture.sh)
audit_fd=/proc/self/fd/8 используется только shell builtin -f/-s checks
(lines31,45,50,54,67,97), не external cat. Ошибка этой пробы **не доказывает**
несовместимость wrapper или необходимость его правки. Следующий
[owner-shell FD опыт02](../android_fd_byte_microprobe_20261108_02/result.md)
использует отдельные новые frozen sources, а не переписывает evidence01.

Raw command/event/stream и actual nonce/boot values остаются приватными.
Preflight/binding records не являются отдельно сохранённым raw host preflight
transcript. Никаких DSI/settings/trace/reboot; camera только identity.
Brightness/current restore не измерены. Полный batch/root lifecycle не доказан;
unknown14 disabled, ограничения37/45/8/60/600 сохранены, PWM>=2000 Hz не доказаны.
