# Loaded-policy snapshot и последующий offline query

Статус snapshot: **confirmed-on-target read-only capture; independent saved-evidence
replay PASS**. [Frozen acquisition result](result.json) оставлен как
SNAPSHOT_CAPTURED_PENDING_OFFLINE_PARSE: это точный исторический статус до parser.
Последующие [query.md](query.md) и [query.json](query.json) — отдельное evidence,
не переписывание executed source/result. Preparation README также сохранён.

Snapshot 2026-11-09T00:29:57.885279–00:30:09.166881 UTC: 16 events,
3,311,634 accepted B. Binary 3,311,175 B, header version 30, SHA256:
ddf7b9e756bd9aed0b8c10d620bdf53baa298b3eacb45be13408b492b23f824c.
Root independent source hash и positive stat before/after совпали. Fresh context
u:r:shell:s0 с ровно одним terminal NUL; same boot с предыдущим AVC проверен
приватно. Exact command/order/rc/caps/events/streams совпали в independent replay.
Acquisition SHA256: e6db4f251f142832b48a2ede6b16ee9fe5cb97f1a51178d9f7c98469bc257f82.
Policy read host elapsed 1.145222942 s, не remote timing bound.

## Current-policy query

Full parse завершился с rc 0 и пустым stderr. Independent query replay PASS: отдельный reviewer
process на сохранённом snapshot вернул rc 0 с пустым stderr; parsed JSON точно совпал
с privately retained 1432 B stdout, public sanitized fields/links совпали. Для fresh shell context → **ранее сохранённого**
u:object_r:system_data_file:s0, class dir: write AV denied, audit suppressed,
reason 1 (TE); search allowed. Harness c8a3fc9c048756309d64605392d244c216a4e22fa64834739b2805e13d6f6960
и libsepol2 3.8.1-1. Lead повторил 17 acquisition и 6 query tests в normal/-O: PASS.
Это policy-level AV вывод по captured current policy, уже не только
[CN reference](../receipt_policy_query_20261109.md). Target label не перечитан;
его актуальность в момент snapshot остаётся предположением.

Не доказаны exclusive historical syscall cause, historical process context,
отсутствие intervening policy changes, domain-permissive behavior или другие
DAC/mount/LSM причины. Fresh context не восстанавливает context прошлого процесса.
Нет clearance отказавшего write, retry, alternate-path execution или labels/
permissions/security changes. Protected write и split implementation STOP.

Последняя device action — только read-only snapshot; binary/private streams,
boot/device identifiers не публикуются. Brightness/current restore неизвестны.
Последний experimental DSI — timedstock03 8 ноября в 19:07:07.888880 UTC.
Native 828 был восстановлен тогда. Все 13 runtime blobs неизменны. Значение 14 отключено; ограничения 37/45/8/60/600 сохранены. Android validators,
clock/lifecycle integration и готовность factory 15 не доказаны; PWM >=2000 Hz
не доказаны. Этот диагноз не является разрешением следующего эксперимента.
