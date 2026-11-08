# Независимый review: только host

Статус: **HOST-ONLY PASS; полный Android batch HOLD**. Итог независимого reviewer
передан lead 2026-11-08; это summary review, не новый прогон или device qualification.
Manifest SHA256: d12695ad3e0701e50dac38c27fe7bbc8e03c021230619c932dd4cd4825417c67.

- Независимо повторены 57 shell cases + 20 checks normal/-O; exact rebuild 104 files.
  Все 13 qualified runtime blobs неизменны.
- Outer124/137 останавливают dispatch после 23 cases. Inner0/1/125/137/143/255
  сохраняют фактический stdout; fixture3 -> launcher4, без capture dispatch/OBSERVED.
- Fresh malformed envelope действительно доходит до decoder1 -> wrapper3;
  collision2 проверена отдельно, не подменяет malformed evidence.
- Baseline независимого прогона: 67024 B. Сохранённые author results содержат
  67016 B и independent_review=PENDING; их исторические bytes не переписаны.
  Сравнение retained baseline streams normal/-O локализовало ровно +8 B в
  noclobber.stderr (191 -> 199 B): diagnostic содержит более длинный путь
  independent checkout; остальные baseline rc/stdout/stderr bytes совпадают.
  Это path-dependent observation, не fixed size или изменение timeout payload.
  Этот review и review-snapshot.json фиксируют последующий статус. Manifest
  OFFLINE_UNREVIEWED также оставлен неизменным ради frozen identity.

Source Git blobs: build.py 18674261e07ca7a6d813454103769b3c0cc2410f;
test_host.py 1cc5ec394598406ffd335ce522d1a06ddd775629;
bundle/probe.sh 3d4c33fb7f24c0602bc28cef82b2e31a3758e7a7.

[Историческая aab0d6f7](historical-aab0d6f7/HISTORICAL-ONLY.md) и
[5707e9ce](historical-5707e9ce/STATUS.md) остаются superseded HOLD, bytes сохранены.
Бинарные synthetic NUL fixtures преднамеренны, не секреты и не corrupt text.

[Read-only inventory](../../artifacts/android_portability_inventory_20261108_01/result.md)
не запускает bundle и не доказывает behavior. Whole-lifetime deadline, process
reconciliation, aggregate storage и exact owned cleanup ещё HOLD. Далее только
отдельно reviewed finite primitives, начиная с fixed sleep2 / timeout1 / -k1.
Ни один из них не реализован этой doc-only правкой. Unknown P85=14 disabled;
>=2000 Hz не доказаны. [Launch proposal](launch-contract-proposal.md) не разрешение.

## Publication whitespace exceptions

Полный git diff --cached --check сообщает известные whitespace warnings для
преднамеренных byte fixtures ascii/envelope/envelope_bad/payload во всех трёх
snapshots и frozen trailing blank EOF в build/test и historical README.
Остальной изменённый текст проверен чисто по publication audit lead. Эти
исключения не означают PASS полного whitespace check; frozen evidence bytes
сохранены без исправления или unstaging.
