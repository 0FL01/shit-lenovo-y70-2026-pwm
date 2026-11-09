# Offline query загруженной policy текущего target

2026-11-09. Снимок получен отдельным read-only acquisition; этот этап работал
только с сохранённым файлом на nc-lab. Результаты acquisition: [result.json](result.json).
Результаты query: [query.json](query.json).

## Подтверждённый результат

Полный parse **успешен**, process rc=0, stderr=0 bytes. Для `dir`:

- `write`: **запрещён** в вычисленном AV, write-bit отсутствует в auditdeny,
  то есть аудит этого отказа policy подавляет; reason=1 (TE).
- `search`: **разрешён**, reason=0.

AV allowed=268435472, auditdeny=4294967291; write bit=4, search bit=268435456.
Это уже query снимка loaded policy текущего target, а не только CN reference.

## Происхождение входных данных

- Policy snapshot SHA256:
  `ddf7b9e756bd9aed0b8c10d620bdf53baa298b3eacb45be13408b492b23f824c`.
- Размер **3311175 bytes**. Хеш и размер проверены до query и совпали с
  самим прочитанным harness input. Snapshot result указывает policy version30,
  verified loaded-policy source и identity guards.
- Source context `u:r:shell:s0` взят из **свежего** plain-shell context capture
  данного snapshot. Это не сохранённый context исторически отказавшего процесса.
- Target context `u:object_r:system_data_file:s0` взят из **ранее сохранённой**
  метки work directory. Его актуальность в момент snapshot остаётся явно
  указанным предположением; повторного чтения target label не было.
- Применён неизменённый independently reviewed harness
  `06-tools/query_saved_selinux_policy.py`, SHA256
  `c8a3fc9c048756309d64605392d244c216a4e22fa64834739b2805e13d6f6960`.
- Native libsepol2 **3.8.1-1**; supported policy version range15–34. Публичные
  ABI declarations pinned на [SELinuxProject 3.8.1](https://github.com/SELinuxProject/selinux/tree/3.8.1/libsepol/include/sepol).
  Существующие independent review и focused normal/optimized tests описаны
  в [CN query report](../receipt_policy_query_20261109.md); здесь они не выдаются
  за новые тесты текущего snapshot.

## Выполнение и пределы вывода

Один отдельный непривилегированный process; supplied regular non-symlink
bounded file, private in-memory libsepol policy, CPU10s/address-space512MiB,
external wall timeout20s. Exact raw stdout (1432 bytes) и stderr (0 bytes)
сохранены приватно; binary и private paths не публикуются в этих результатах.
Новых device calls, policy changes, permissions/labels/settings changes,
protected-write retries либо alternate execution path не было.

Результат подтверждает policy-level deny и подавление аудита для указанных
contexts на момент снимка. Он **не доказывает исключительную причину**
исторического syscall rc1, фактический historical shell context, неизменность
runtime policy до snapshot, актуальность старого target label либо отсутствие
других DAC/mount/LSM причин. Harness также не проверяет domain-permissive
status. Protected write и trial admission остаются остановленными; query
не даёт разрешения на повтор или обход отказа.
