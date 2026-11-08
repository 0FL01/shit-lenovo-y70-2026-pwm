# Предложение минимального launch contract, не реализация

Статус: HOST-ONLY HOLD. Ни одного Android probe, supervisor или cleanup API здесь
не реализовано и не запущено. Решение о следующем этапе принимает lead отдельно.
Источник: текущие manifest.json/source Git blobs; historical-aab0d6f7 сохраняет
отклонённую исходную версию, не является launch candidate.

## Stage zero: только inventory, отдельно от probe

После обычных lead identity/service-version/mutex prerequisites можно предложить
отдельный read-only inventory: текущий UID, выбранные shell/PATH и command-v для
уже существующих sh, timeout, sleep, id, sha256sum, mkdir, rm, rmdir, cat, cmp, tr,
od, tail, wc, stat, awk, mv; отдельно setsid, kill, ps, df и shell ulimit.
Для найденных trusted utilities нужны короткие help/version сведения только об
интересующих flags. Сохранять ограниченный ответ на host; не создавать target
files, fixtures, sleep children, process groups или supervisor. Сами read-only
utilities являются краткими процессами, не тестовым деревом. Никаких installs,
su, изменения permissions/security, настроек или DSI. Неизвестная/неограниченная
help-команда не запускается только ради inventory. Inventory не qualification.

## Что требуется установить до выбора конкретного launcher

- Какой именно source/version timeout, поддержка -k, действительно ли он
  ограничивает всё собственное дерево, TERM/KILL semantics и exit codes.
- Наличие isolated process-group/session primitive и возможность адресовать
  только собственную группу; leader PID, start-time, UID, PGID/SID и boot identity
  должны быть связаны с конкретным invocation. PID или kill-0 отдельно недостаточны.
- Read-only способ повторно сверить /proc identity, членов группы и отсутствие
  собственного дерева после wait/kill. Нельзя сигналить переиспользованный PID,
  чужой процесс или неизвестную группу. Неизвестность означает HOLD/quarantine.
- Точные hard/soft RLIMIT_FSIZE semantics выбранного shell: inheritance, unit,
  невозможность поднятия hard limit descendants. Наличие stat/df для bounded
  размера/свободных blocks/inodes. Не менять filesystem quotas/security.

Сначала review этих возможностей; затем отдельная конечная own-sleep fixture для
проверки конкретного timeout/group механизма. Наличие command-v/help не доказывает
его поведение. Не строить новый общий supervisor/framework по предположениям.

## Минимальный будущий fixed launch (только предложение)

Один source-pinned fixed probe, один newly owned context-specific workspace,
никакого arbitrary command API. UID2000 и UID0 раздельны, no su. Trusted source
manifest, выбранные shell/PATH, identity и mutex проверяются до launch снаружи.

Target-local deadline охватывает весь batch, включая prelude/publication;
предложенные 10 s плюс явно согласованный конечный kill grace не являются
доказанным successful-path bound. Source-pinned local supervisor/существующий
подходящий primitive выбирается лишь после inventory/review. На expiry прекращать
новые dispatch, завершать только доказанное собственное дерево, wait/reconcile
его identity и отсутствие descendants. rc124/137 отдельного case сейчас лишь
останавливает dispatch, НЕ доказывает отсутствие descendants. Host60s timeout
НЕ cancellation remote. Потеря связи не разрешает повторный dispatch.

При отсутствии доказанного механизма deadline/identity/reconciliation полный
probe не запускать. Missing/torn result, ambiguous termination, foreign/missing
ownership или неожиданные файлы => retain exact remnants, HOLD, без нового запуска
и broad deletion. Это userspace uncertainty, не DSI uncertainty.

## Storage: существующее и предлагаемое строго разделены

Сейчас enforced лишь per-case `ulimit -f 32768` с неизвестной Android unit;
initial synthetic fixtures 76509 B, expected baseline output 67016 B. Host
1 MiB/file и16 MiB aggregate проверки после исполнения НЕ disk quotas. У wrapper
interval собственный `ulimit -f 32768`: уменьшать его или исходники запрещено.

Первый finite own fixture читает максимум2048 B и устанавливает -f1; units нужно
наблюдать ДО применения derived limit. Наблюдение512/1024 B само по себе ещё не
доказывает hard-limit inheritance. Эта fixture требует отдельно reviewed bounded
launch, не является частью read-only stage zero.

Консервативный кандидат для отдельного review, не заявленный enforced bound:
57 fixed invocations, не более32 создаваемых regular-file inodes на invocation
(включая scratch/unlinked audit; decoder максимум16 sections +4 служебных файла,
capture audit/bootstrap+fixed scratch, snapshot9 scratch, interval7 scratch),
плюс171 rc/stdout/stderr и8 shared/marker/reserve slots. Это2003 slots, округление
до2048. При проверенном hard ceiling32768 units и максимальной unit1024 B:
2048 *32 MiB =64 GiB логических writable bytes. Bundle bytes отдельно <=1 MiB
требуют проверки ВСЕХ файлов, не только fixtures. Это намеренно грубая верхняя
оценка, НЕ разумное обещание67 KiB storage и НЕ действующая квота.

Чтобы такая оценка стала enforced contract, reviewer должен проверить точные
creation counts всех frozen paths (включая failure cleanup/unlinked descriptors),
запрет добавления files за manifest, hard+soft ceiling до первого writer, отсутствие
возможности повышения hard ceiling и bounds launcher diagnostics/receipts.
Проверить finite ownership/path lengths и один instance без retry. Preflight
free blocks/inodes должен покрывать верхнюю границу, allocation rounding,
filesystem metadata и согласованный reserve; конкурирующие writers требуют
отдельной exclusivity/resource assumption. Периодический du/stat лишь detection,
не quota и не доказательство сохранения свободного места.

Если такой большой reserve неприемлем, сначала отдельное review меньших batches
и меньших inherited limits ТОЛЬКО там, где frozen wrapper это допускает, плюс
bounded per-stage size checks перед следующим dispatch. Это новая архитектурная
правка, здесь не реализована. Не подменять bound ожидаемыми normal sizes.

## Retrieval/accounting и cleanup

После proven termination извлечь manifest-linked exact rc/stdout/stderr каждого
case, внутреннее INNER_TIMEOUT_RC отдельно, inventory всех owned files/directories
и размеры. Отсутствующий результат не PASS. OBSERVED не success receipt. Сверить
fixed expected names, ownership, inode/link/type/permissions, payload/marker и
отсутствие foreign objects перед любым удалением. Удалять только подтверждённые
собственные exact names, затем rmdir, и отдельно проверить отсутствие. Никаких
rm-rf/globs, cleanup по одному guessed PID или присвоения stale lock. Uncertain
ownership/termination/cleanup => оставить/quarantine, не удалять чужое.

Не доказаны immutable acquisition, root sealing, durable ledger, power-loss
ordering, clocks/rate/suspend, Android max-cap timing или sequencer readiness.
37/45/8/60/overall600 сохраняются как прежние protocol constraints; P85=14 disabled,
PWM>=2000 Hz не доказан. Никакие live dependencies не меняются.
