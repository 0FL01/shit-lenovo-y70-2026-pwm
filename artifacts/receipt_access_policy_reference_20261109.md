# Offline: отказ записи в synthetic receipt work

2026-11-09. Только сохранённые файлы nc-lab; без device calls, изменений
security settings, повторного producer/capture/seal или вариантов обхода.

## Вывод и статус

**hypothesis для current target:** SELinux объясняет сочетание успешного
traversal/read, отказа `test -w` при owner mode700 и отсутствия AVC.
**confirmed offline для CN reference:** сохранённая policy включает shell
в appdomain, запрещает разрешать этой группе запись в system_data_file
directories и подавляет аудит соответствующего отказа. CN reference не
равна активной GLOBAL OTA policy; точная причина target rc1 ещё unknown.

## Воспроизводимые источники

Все пути ниже относительно корня репозитория. Номера относятся к сохранённым
файлам; проверить отдельный диапазон можно `nl -ba FILE | sed -n 'A,Bp'`.

- [Target access evidence](android_fixed_receipt_20261108_01/access_diagnosis.json),
  строки 4–28: traversal/read проходят, work_w false; 503–509: owner UID2000,
  mode700, type system_data_file. Полные raw labels/идентификаторы здесь не копируются.
- [Диагностический код](android_fixed_receipt_20261108_01/diagnose_access.py),
  41–42: проверены current build, Enforcing и `id -u`; 48–62: точные predicates
  и metadata. SELinux domain процесса и real/effective/fs UID tuple не сохранены.
- [AVC query](android_fixed_receipt_20261108_01/inspect_own_avc.py), 47–62:
  фильтр только собственного device/inode в доступном dmesg; нулевой результат
  не доказывает отсутствие SELinux denial.
- [CN platform policy](../extracted/XT2611-1/W3WWL36.65-11-18/filesystems/system_a/system/etc/selinux/plat_sepolicy.cil):
  808: shell включён в appdomain; 9280: `dontaudit appdomain system_data_file
  (dir (write))`; 9644: neverallow appdomain записи и иных изменений directory
  этого типа; 14031: domain разрешён search. Neverallow является ограничением
  сборки policy, не отдельным runtime deny. Dontaudit объясняет возможную тишину AVC.
- [CN file contexts](../extracted/XT2611-1/W3WWL36.65-11-18/filesystems/system_a/system/etc/selinux/plat_file_contexts),
  472–473: тип корня data — system_data_root_file, общий тип потомков —
  system_data_file; это согласуется с сохранёнными target metadata.
- [Firmware provenance](firmware_manifest.json), 50–55 и 299–305: CN
  W3WWL36.65-11-18 ZIP, mirror provenance, выбранные извлечённые members прошли
  CRC; authenticity/signature chain не установлена. [Firmware scope](../03-investigation/firmware.md),
  21–28: прежний GLOBAL archive не является текущей OTA W3WWS36.65-64-4-1.
  Документированный GLOBAL extraction path на nc-lab сейчас отсутствует.
  CN compiled policy существует в
  `extracted/XT2611-1/W3WWL36.65-11-18/filesystems/odm_a/etc/selinux/precompiled_sepolicy`;
  sesearch/seinfo на PATH не найдены. Exact current active policy среди
  просмотренных artifacts/extracted не найдена.

## Что означает access check

- [Saved kernel namei.c](../sources/gki-15950084/common/fs/namei.c), 351–356:
  совпадающий mapped owner/fsUID проверяется по owner mode, раньше POSIX ACL.
  Поэтому обычный ACL не объясняет отказ owner write при действительно совпавших
  credentials и mode700. 510–543: immutable, mapping, filesystem и LSM checks
  существуют сверх DAC. Saved source не приравнивается целиком к running kernel.
- [Saved kernel open.c](../sources/gki-15950084/common/fs/open.c), 385–428:
  access без AT_EACCESS использует real credentials через fsUID override;
  510–525: проверяет permissions и read-only mount. Успешный root reserve
  доказывает writable root view в тот момент, не исключает отдельный shell
  mount namespace/read-only view. Mount/immutable metadata не сохранены.
- [Saved Toybox test.c](../sources/gki-15950084/external/toybox/toys/posix/test.c),
  114–117: `-w` вызывает access(W_OK), а не только сравнение mode bits.
  Однако target-команда была `test`, без принудительного Toybox:
  фактический shell builtin/utility и его реализация unknown.
- [Saved SELinux hooks.c](../sources/gki-15950084/common/security/selinux/hooks.c),
  3130–3152: access permission decision и audit decision разделены;
  применяется дополнительная access audit mask. Отсутствие AVC не классифицирует
  причину rc1, даже помимо найденного CN dontaudit.

## Минимальный недостающий read-only факт

Для active-policy вывода нужны **реальный SELinux context отказавшего plain
shell и effective loaded policy того же target boot**, включая runtime policy
изменения. Offline query этой policy должен установить, разрешён ли этому
domain `system_data_file:dir write`, и применимый dontaudit. Один CN source
или stock policy от другой версии этого не доказывает.

Для более сильного вывода «именно SELinux вызвал конкретный rc1» также нужны
семантика фактического test, соответствующие credentials/mount view либо
записанный syscall errno/permission decision. Новых проверок устройства этот
анализ не выполняет и изменения разрешений или alternate execution не предлагает.
