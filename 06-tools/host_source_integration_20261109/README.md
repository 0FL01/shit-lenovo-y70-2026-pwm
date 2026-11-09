# Source provenance и inactive host wiring, 2026-11-09

Статус: offline fixtures PASS, runtime не изменён, live admission отсутствует.
Запрещённые commit/stage/push/retry/branch-change не выполнялись.
Все новые материалы только в этой директории. WORKSTATE и pwm_resume не изменены.

## Точный существующий контракт

run_p85_timed_stock_trial.py:399 вызывает base.source_provenance(paths=SOURCE_FILES,
require_clean=args.execute) до mkdir выходных/private directories и до создания GuardedADB.
В offline режиме грязный набор разрешён только как отчёт с false; это не admission.
Исходная функция run_p85_guarded_trial.py:42–62:
1. Git HEAD должен быть 40–64 lowercase hex.
2. ls-tree HEAD по точному списку должен вернуть blob для каждого пути.
3. hash-object каждого текущего файла должен совпасть с соответствующим HEAD blob.
4. git diff --quiet HEAD -- paths должен завершиться 0; rc1 означает dirty, другой rc ошибку.
5. При require_clean=True любое нарушение clean отвергается.
Guard scoped, не global git-status; unrelated artifacts не запрещены автоматически.
Нельзя заменять HEAD manifest произвольным sha256 allowlist, разрешать untracked,
принимать staged-only blob или require_clean=False перед live I/O.

Точный набор 13 runner sources:
- 06-tools/run_p85_guarded_trial.py
- 06-tools/p85_guarded_trial.py
- 06-tools/stock_c1_sweep.py
- 06-tools/capture_ddic_c1.py
- 06-tools/p85_single_bit_plan.py
- 06-tools/dsi_trial_transaction.py
- 06-tools/a9_reproduction.py
- 06-tools/camera_capture_metadata.py
- 06-tools/run_dsi_mode_trial.py
- 06-tools/guarded_adb_socket.py
- 06-tools/p85_batched_envelope.py
- 06-tools/run_p85_batched_trial.py
- 06-tools/run_p85_timed_stock_trial.py

2026-11-09 read-only replay оригинальной AST-функции с настоящим subprocess/Git:
HEAD 0548cf6ba5916c40c6512ef0e2cca332f8e4a4e3, все 13 clean.
Добавление существующих offline_baseline_adb.py и linux_adb_probe_dependencies.py
к тем же paths корректно отвергается: они не являются tracked HEAD blobs.
Это новый runtime-source blocker, НЕ следствие unrelated pending 13 policy files.
Предыдущий отказ commit policy checkpoint не даёт права на повтор или обход.
Не делать отдельную task branch/temporary commit для прохождения guard.

## Минимальный changed/new executed set

Сохранить все 13 исходных путей, включая guarded_adb_socket.py, даже если его
transport более не создаётся. Не сужать исходный baseline contract.
Изменяемые existing sources:
- stock_c1_sweep.py: уже reviewed canonical UUID recovery predicate.
- run_p85_guarded_trial.py: already reviewed pull expected_size/byte_cap metadata;
  дополнительно отдельный reviewed video-validation split, если выбран.
- run_p85_timed_stock_trial.py: только явная dependency injection/expanded SOURCE_FILES;
  отдельно video-split lifecycle delta. Не смешивать непроверенные virtual snapshots.

Добавляемые executed sources, точные имеющиеся пути:
- 06-tools/host_adb_full_api_spike/offline_baseline_adb.py
- 06-tools/host_adb_full_api_spike/linux_adb_probe_dependencies.py
- 06-tools/host_private_sink_20261109/private_video_sink.py

Дополнительно нужны named reviewed launcher + construction module. Их production
пути ещё не согласованы; до этого expanded set НЕ закрыт. Не выдавать этот документ,
fixture.py, proposed patch или tests за future executed module.
offline_baseline_adb.py также потребует малого изменения callback metadata:
существующий callback получает только path/deadline, sink factory требует observed_size.
Точный inactive diff сохранён рядом. После него старый reviewed adapter hash уже
не описывает executed adapter; нужны новые fixtures, independent review и HEAD admission.

Для split анализа отдельно:
06-tools/video_validation_split_20261109/offline_acceptance.py и proposal.py плюс exact original
validator source run_p85_guarded_trial.py и reviewed transfer/receipt implementation.
Этот nc-lab analysis set регистрируется отдельно от USB-host executed set; он не
заменяет host provenance и не добавляется туда только потому, что существует.

## Inactive construction design

См. construction_design.py.txt. Это текст предложения, не importable implementation.
Все pins, serial pair, directory parent dev/inode/uid и capacity передаются явно из
independently approved PRIVATE configuration. Не выводить expected values из freshly
observed actual values. Не записывать их в public report/manifest/argv.
Создаются LinuxProcFS, LinuxAssociation(pin, limits, proc, monotonic),
make_socket_factory и one-shot create_sink callback. Никаких sockets/proc reads,
mkdir или device services во время default/offline import/construction.
Новые adapter operations сохраняют caller lifecycle, recovery, uncertain dispatch,
один best-effort reboot, 37/45/8/60/600, pull90 и camera/restore cleanup.
Caller после наблюдаемого camera stat передаёт expected_size=size, byte_cap=size.
Callback получает observed_size только из validated expected_size в sync и создаёт
PrivateSinkFactory с этим размером. One-shot spent latch находится снаружи factory:
повтор callback не получает нового права create/retry. Не использовать global mutable
observed-size, stack inspection, stat локального ещё не созданного capture или fake size.

Наличие factory не означает complete private-directory lifecycle: held parent pin,
creation/ownership of fresh runner directory, real capacity и syscall deadline limits
должны быть независимо согласованы/проверены. Host root/kernel/server остаются trusted.
Existing LinuxAssociation доказывает visible thread-group-leader FD tables only;
fixture PASS не расширяет это до all-task unique-holder claim.

## Launch-only execution-origin gap и минимальное hardening proposal

Baseline guard проверяет disk paths ПОСЛЕ обычных imports. Он не связывает actual
module origin/code с проверенными bytes: sys.path shadowing, preload/sys.modules,
stale pyc, изменение между read/import не покрыты. Это граница исходного guard,
не доказательство, что прошлые trials исполнили неверный код.

Предложение: один небольшой self-contained trusted launcher, отдельный review,
без изменения legacy module bodies для loader logic:
1. До project imports выполнить тот же scoped HEAD/tracked-blob/worktree-clean
   контракт для неизменённых исходных 13 плюс полный расширенный executed set.
2. Прочитать каждый exact approved regular source path один раз; проверять raw-byte
   Git blob identity против проверенного HEAD blob (учесть repository object format,
   git attributes/filters: hash-object alone не всегда raw-byte identity).
3. Для фиксированного project dependency DAG создать exact-name modules из этих
   проверенных bytes, compile/exec с expected __file__/__spec__; не читать .pyc.
   Не применять произвольный plugin loader/динамическое discovery.
   Отклонять preloaded project module или unexpected module origin, не молча заменять.
4. Только после загрузки вызвать существующий исходный source_provenance
   require_clean=True на расширенном наборе; сохранить его original semantics.
5. Только затем explicit approved runtime branch может создать dependencies.
   Default/inspection mode остаётся no socket/proc/sink/device I/O.

Это design, НЕ готовый launcher. Реальный fixed import DAG и exact origin checks
нужно проверить fixtures (shadow module, stale pyc, preloaded module, tampered bytes,
missing blob, late worktree change). run_dsi_mode_trial содержит runpy в неиспользуемом
coupled helper: будущий exercised call graph должен это исключить или включить
дополнительный executed source; нельзя заявлять all-code coverage по одним imports.
Stdlib/interpreter/Git и trusted host root не превращаются в adversarially authenticated
компоненты. Не строить общий security framework или обещание против malicious root.

## Что воспроизводят fixtures

source_binding.json сохраняет baseline SHA256 для integrity конкретного review,
не новый live authority. Reviewed adapter/Linux hashes сверены с existing freeze.
canonical_boot_guard и pull_metadata virtual replacement воспроизводят EXACT
existing unified patches и virtual hashes без записи в runtime.
15 source tests normal и -O: original guard clean/dirty/untracked/error/invalid commit,
exact scoped path list, virtual input/output hash mismatch, nonunique replacement,
reviewed dependency identity, неизменность 13 baseline files, отсутствие live admission.
Оригинальная source_provenance исполняется из AST с fake subprocess. Это тест её
неизменённого тела, не production execution bypass. Virtual proposed code только
компилируется, device methods не вызываются.

Команды из repository root:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s 06-tools/host_source_integration_20261109 -v
PYTHONDONTWRITEBYTECODE=1 python3 -O -m unittest discover -s 06-tools/host_source_integration_20261109 -v

## Admission checklist и точный blocker

- [done] Read-only original 13-file clean check at current HEAD.
- [done] Reviewed canonical/pull source bindings and 20 normal/-O outer tests (including 32 nested unchanged transport/caller tests).
- [pending] Final sink source freeze + independent review; no capacity defaults.
- [pending] Explicit observed-size callback adapter patch + normal/-O fault tests.
- [pending] Final video-split patch composition and receipt binding review.
- [pending] Small source-byte launcher/construction implementation and origin tests.
- [pending] Full exact executed module set, fixed DAG, new source freeze/review.
- [blocked] Live expanded source gate: new/modified runtime absent from clean tracked
  HEAD. Commit/stage/push retry is NOT authorized by this work; no Git write attempted.
  Previously denied exact policy-checkpoint commit remains stopped, separate from
  this new runtime admission. Parent must resolve actual authorized source checkpoint
  scope without assuming that policy checkpoint would admit these new sources.
- [pending] Privately approved actual pins, identity continuity, directory/capacity
  and host platform qualification; previous one self-test is not trial latency proof.
- [pending] Separate admitted host deployment/execution and stock-only rehearsal,
  whole lifecycle fault/recovery tests; ffprobe or reviewed split cannot be skipped.
- [pending] Report remains awaiting offline validation until actual immutable
  capture/receipt/source match and original validator succeed.

No live-ready claim. No device/ADB/USB-host/root/settings/security/producer action.
Protected producer/spent path remains stopped. Candidate14 disabled. No physical Hz claim.

## Callback bridge test addendum

20 outer tests normal/-O PASS, включая nested 32 unchanged reviewed transport/caller tests.
Virtual keyword bridge адаптирует только fixture callback, original fixture files неизменны.
Exact forwarding, undersize/oversize wire rejection, invalid cap before sink, fake capacity
rejection и existing failed-video cleanup covered. Capacity refusal здесь — throwing fake,
не test настоящего PrivateSinkFactory/free-space; outer spent latch и construction text
остаются design-only. См. sink_bridge_binding.json для exact virtual source identity.
Для non-code deployment closure см. RUNTIME_INPUTS.md.

## Inert loader implementation addendum (supersedes design-only loader status above)

По отдельному продолжению поручения добавлены inert_source_loader.py и
test_inert_source_loader.py. Это importable inert prototype, не live launcher.
Ни original runtime, ни sink/video files не изменены. Все36 outer tests normal/-O
PASS; один test прогоняет32 unchanged transport/caller tests как nested suite.

FixedSourceLoader constructor не делает I/O. Explicit load использует injected
git/read/registry, fixed16-module dependency order + собственный path (17 paths total).
Сохраняет baseline13 paths, проверяет HEAD tree/hash-object/diff; затем отдельно
hashes Git raw blob header+bytes по object format sha1/sha256, без filters.
Каждый source snapshot читается один раз и исполняется прямо через compile/exec,
не .pyc. Preloaded и late preloaded project names отвергаются до project exec.
Explicit project imports разрешены только в fixed order, остальные только stdlib
root names. Проверяются __file__, spec.origin и registry identity. Это не sandbox
для malicious reviewed source или trusted root и не generic import framework.

Tests применяют только synthetic source bytes/fake Git/fake file reader/registry:
missing tracked blob, dirty diff/hash/error, raw drift, wrong origin/registry,
unlisted import, forward dependency, preload race, stale-on-disk-after-snapshot,
one-shot load, inert constructor, no __main__, sha1/sha256. Реальный runtime через
loader НЕ импортировался и не запускался. Реальная совместимость16-module DAG
ещё требует separately reviewed bounded offline integration with no action entrypoint.

Оставшиеся обязательные launch steps:
- pin bootstrap source independently BEFORE executing it; its self path check is
  not retroactive authentication;
- provide admitted real Git/read wrappers and sys.modules registry, trusted stdlib;
- after verified-byte load call ORIGINAL base.source_provenance(root, paths=PATHS,
  require_clean=True) before dependency construction/I/O; loader does not call it yet;
- include any future concrete construction/receipt module in PATHS and review DAG;
- bind final canonical/pull/video/sink bridge composition, not mixed snapshots;
- no execution until new runtime source is clean tracked HEAD under authorized scope.
Current actual repository cannot pass expanded gate. No commit/stage/push attempted.

Reviewer found a construction error before production: acquire=association would
drop sticky process-trust invalidation in adapter facts. Corrected DESIGN to
acquire=association.acquire_process; AST bridge regression confirms adapter and
OperationFacts invalidation with zero sockets. No runtime bugfix was applied.

## Concrete actual-source import fixture, 2026-11-09

Теперь37 outer tests normal/-O PASS (+32 nested unchanged transport/caller tests).
check_actual_imports.py запускается тестом в отдельном Python -I -B процессе
(normal и -O). Все16 actual reviewed project sources исполняются из exact original
bytes, без virtual code replacement; полный SHA256 map в actual_import_binding.json.
Это HARDWARE IMPORT SLICE, не полный deployment closure и НЕ tracked-source admission.
Virtual Git возвращает fixture HEAD, не настоящий repository admission.

Предварительная AST inspection проверила imports, top-level assignments, class
decorators/defaults. Обнаружен один filesystem-metadata call:
run_dsi_mode_trial ROOT=Path(__file__).resolve(). В fixture ТОЛЬКО этот exact path
resolution заменён локальным deterministic fake; report перечисляет эту замену.
Остальные реальные project bytes не изменены. Используется настоящий fresh
sys.modules, необходимый @dataclass, а не toy registry={}.
Trusted stdlib preload выполняется до запрещённого-I/O интервала.
Во время project load monkeypatches и audit hook запрещают open/socket/process actions.
Caller/adapter/sink instances не создаются; ни main, ни trial methods не вызываются.
Проверены actual inheritance, shared SinkIdentity class, original13 SOURCE_FILES,
37s constant, candidate disabled и __file__ всех16 modules.

Прямой stdlib name allowlist loader НЕ проверяет происхождение stdlib или уже
импортированных standard modules. Trusted interpreter/stdlib/import environment —
явная предпосылка, не доказанная защита против malicious host/root/shadow stdlib.
Bootstrap loader самостоятельно уже исполняется до своего file check; требуется
external pin. Полный original source_provenance post-load guard остаётся обязательным
future integration step. Actual source gate сейчас всё ещё отвергает expanded set.

Первая попытка нового теста остановилась ДО project imports из-за ошибки сборки
fixture manifest: в expected map попал test helper, которого нет в fixed16.
Manifest фильтр исправлен; runtime source не менялся. Final37 tests PASS.

## Phase-specific executed closure (not closed by fixed16)

Fixed16 + loader self covers only this hardware import slice. Future concrete
construction code и ordinary host evidence code, если исполняются на USBhost,
обязаны войти в ЕГО expanded tracked-source gate до исполнения:
- 06-tools/video_validation_split_20261109/host_evidence.py
- его imports offline_acceptance.py и proposal.py в той же директории.

Для nc-lab post-validation role отдельно нужен complete tracked/source-bound set:
- host_evidence.py, offline_acceptance.py, proposal.py, analyzer_join.py;
- exact pinned 06-tools/analyze_p85_timed_surrogate.py и analyze_p85_optical.py,
  если их AST methods исполняются;
- original validator run_p85_guarded_trial.py и любые дальнейшие executed helpers.

Даже helper, использованный только для receipt creation, может исполнять imported
dependencies: нельзя переносить их provenance в другую фазу только по имени.
Никаких silent imports из dirty working tree. Эти evolving video helpers здесь
не импортировались и не hash-frozen как готовая deployment release.
check_synthetic_media.py не runtime module, пока остаётся только test utility.
Новый role manifest — prerequisite; текущее16-source PASS его не заменяет.

## Latest entrypoint slice

See ENTRYPOINT.md and runtime_audit_manifest.json for the current concrete inactive
entrypoint, exact source roles and86-test scope. Prior sections are retained phase
history; historical_84ccb4/ preserves exact earlier reviewed artifact bytes.
