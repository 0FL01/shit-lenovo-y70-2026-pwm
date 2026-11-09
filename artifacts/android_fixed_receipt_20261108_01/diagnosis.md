# Read-only access и AVC diagnosis

Статус: **confirmed-on-target narrow observations; independent saved-evidence
replay PASS**. Frozen [access diagnosis](access_diagnosis.json) и
[AVC diagnosis](avc_diagnosis.json) не изменены.

Read-only access pass завершён2026-11-08T23:57:16.194507 UTC. Остальные семь
access predicates прошли; work_w=false для plain shell. Root stat: work UID2000,
GID0, mode700, label system_data_file. Эти DAC metadata сами по себе не доказывают
эффективный write access. MAC/SELinux причина остаётся гипотезой, не установленным
диагнозом. No permission/label workaround, retry/capture/seal или cleanup.

Последний read-only AVC query:2026-11-09T00:07:12.996050–00:07:22.425994 UTC,
14 events /432 B. Source inspect_own_avc.py SHA256:
1c1932bb81da400af9c413303c977220c6c21084d1403e29feeb5d4feaede678.
Independent replay подтвердил own device+inode quoting, command/order/caps,
exact dmesg rc0 marker, grep rc1/empty stdout и same boot. Zero matching AVC lines.
Комбинированный query event stderr21 B несёт status marker, не AVC match.

Ограничение: проверен только доступный dmesg и literal dev="name", стоящий перед
ino=value. Suppressed, rotated, reformatted AVC или AVC другого объекта не исключены.
Отсутствие matched lines **не доказывает** отсутствие MAC denial и не даёт разрешения
повторить trial или обойти gate другим путём. Saved-evidence replay PASS означает
согласованность этого узкого результата, не успех receipt/security/lifecycle.

Точный BASE остаётся spent. Split host-only implementation остановлена и никогда
не исполнялась на target; альтернативные paths после отказа запрещены. Дальнейшая
диагностика/переход требует отдельного решения, не автоматического workaround.
Никаких label/security changes; последнее experimental DSI по-прежнему timedstock03
19:07:07.888880 UTC Nov8 с native828 restore тогда. Current brightness неизвестно;
>=2000 Hz, full Android validators/clock/lifecycle и factory15 readiness не доказаны.

[Offline CN policy reference](../receipt_access_policy_reference_20261109.md)
содержит shell∈appdomain, dontaudit и neverallow для system_data_file directory
write. Это reference-only explanation, не effective current GLOBAL policy и не
доказательство фактической SELinux причины rc1. Требуемый context/loaded-policy
gap не закрыт; новых device действий или alternate-path разрешений нет.
