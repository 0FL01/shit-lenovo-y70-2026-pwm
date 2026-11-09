# Offline CN binary policy query — 2026-11-09

## Результат

**confirmed offline, CN reference:** libsepol успешно разобрала явно переданный
сохранённый precompiled_sepolicy. Для входных предположений
`u:r:shell:s0` → `u:object_r:system_data_file:s0`, class `dir`:

- `write`: allowed=false; denial audit bit отсутствует; reason mask=1 (TE).
- `search`: allowed=true; reason mask=0.
- Процесс завершился rc=0, stderr пуст. Значение allowed AV=268435472,
  auditdeny AV=4294967291. Write bit=4, search bit=268435456.

Это подтверждает совместимость compiled CN policy с ранее найденными CIL
правилами отказа write и подавления его аудита. Это **не** доказательство
текущего GLOBAL runtime decision или причины конкретного `work_w=false`.
Контексты заданы явно для reference query, а не получены с устройства.
Permissive-domain status и live policy modifications не проверялись.

## Вход и ABI

Вход: `extracted/XT2611-1/W3WWL36.65-11-18/filesystems/odm_a/etc/selinux/precompiled_sepolicy`.
Размер 2698714 bytes. SHA256:
`1fd26f42d8e0467932e41ff22e237d8dc61fbf40136e29d723fc837f845d1b97`.
Это CN W3WWL36.65-11-18 reference; provenance/authenticity limits остаются
описанными в `receipt_access_policy_reference_20261109.md`.

Использована `/lib/x86_64-linux-gnu/libsepol.so.2`, package libsepol2 3.8.1-1.
Публичные version API возвращают supported policy range 15–34; это не
утверждение, что данный input имеет какой-либо конкретный номер версии.

Официальные источники tag 3.8.1:

- [sepol.h](https://github.com/SELinuxProject/selinux/blob/3.8.1/libsepol/include/sepol/sepol.h),
  `int sepol_set_policydb_from_file(FILE *)`.
- [services.h](https://github.com/SELinuxProject/selinux/blob/3.8.1/libsepol/include/sepol/policydb/services.h),
  context-to-SID, class/permission lookup, compute-av-reason.
- [flask_types.h](https://github.com/SELinuxProject/selinux/blob/3.8.1/libsepol/include/sepol/policydb/flask_types.h),
  SID/AV uint32_t, class uint16_t; decision состоит из пяти uint32_t
  allowed/decided/auditallow/auditdeny/seqno.
- [policydb.h](https://github.com/SELinuxProject/selinux/blob/3.8.1/libsepol/include/sepol/policydb.h),
  публичные min/max policy version API.
- [services.c:133–152](https://github.com/SELinuxProject/selinux/blob/3.8.1/libsepol/src/services.c#L133-L152),
  process-local loader; никакого kernel load.

`sepol_load_policy` не экспортирован установленной shared library и не используется.
Внутренние структуры policydb не воспроизводились; нового policy parser нет.

## Изоляция и проверки

Новый `06-tools/query_saved_selinux_policy.py` использует exact typed ctypes.
Проверяет integer return codes, ABI sizes/offsets, ASCII bounds и не более
8 permissions; читает только явно указанный non-symlink regular file ≤16MiB.
Весь снимок читается до parse, SHA относится к тем же bytes, которые переданы
через read-only fmemopen в process-local libsepol. Buffer жив до fclose.
Контроль UID/eUID запрещает root. CPU limit 10 s, address-space 512MiB,
core size 0; внешний subprocess timeout 20 s на query.
Никаких libselinux calls, ADB, kernel policy loads, установок, security changes,
повторного protected write или альтернативного device path не выполнялось.

Независимый source reviewer `review_corrected_portability` проверил frozen
source, ABI и loader до первого CN query и дал scoped READY. Frozen hashes:

- query script: `c8a3fc9c048756309d64605392d244c216a4e22fa64834739b2805e13d6f6960`
- focused tests: `b8a4b1892f834b10cc0f1b6781fd01e6c09e77870beafbd674809e0f0e70eb5c`

`06-tools/test_query_saved_selinux_policy.py`: **6/6 PASS normal**, **6/6 PASS
optimized**, включая write/search, invalid policy/context/class/permission,
ASCII bound. Optimized запуск использовал `PYTHONOPTIMIZE=1`, унаследованный
реальными subprocess query, а не только внешним unittest процессом.
До CN query также прошли synthetic invalid-policy/ASCII tests и compile()
без записи pycache. Полные command/rc/stdout/stderr, идентификаторы input,
assumptions и результаты обеих suites — в
`receipt_policy_query_20261109.json`.

## Граница вывода

Для current GLOBAL вывода по-прежнему отсутствуют фактический context
отказавшего plain shell и effective loaded policy того же boot, включая
runtime modifications. Сохранённая CN binary теперь непосредственно
подтверждает reference AV, но не заменяет эти данные. Для доказательства
именно причины syscall rc1 остаются дополнительные ограничения credentials,
mount view и фактической реализации test, описанные в reference report.
Protected write/trial admission остаются остановленными; этот результат их
не разрешает и не предлагает обход.
