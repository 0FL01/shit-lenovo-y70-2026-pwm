# План сокращения P85 roundtrips без ослабления guards

Статус: offline design, не реализация и не допуск candidate. Устройства не опрашивались. Никакие executable files не изменялись. Численная выполнимость 45s пока **unknown**. Успешные unbatched writer timings теперь измерены в clean stock04; timings будущего batching ещё неизвестны. Не менять admission gate до успешной stock-only квалификации той же версии будущего batching и независимого review. Лимиты host45s / independent watchdog60s остаются прежними.

## Источники и воспроизводимые измерения

- [failed01 run.json](p85_stock_a001_20261108_01/run.json): единственный qualified baseline в неуспешном run; сам run не является stock qualification.
- [Trial](../06-tools/run_p85_guarded_trial.py): `_observe_stage`, `write_stage`, `arm_candidate`, `disarm_short`, `shell`, `cam`, `qualification`.
- [Sweep](../06-tools/stock_c1_sweep.py): `state`, `quiet`, `mark`, `identity`, `shell`, `esd_read_script`.
- [Child builders/validators](../06-tools/p85_guarded_trial.py): `long3_reader`, `bounded_c1_reader`, `write_script`, `validate_long3`, `validate_write_capture`, `validate_write_wire`.
- [Протокол runner](p85_guarded_runner_20261108.md), [оптическая квалификация](p85_optical_qualification_20261108.md).

Measured: baseline34.388664625s; P85 phase7.404454478s; C1 phase6.976984354s; hold+metadata10.459349764s. Остаток quiet/state9.547876029s вычислен вычитанием суммы `phase_seconds` из `elapsed_seconds`. Hold4.5s сохраняется.

Для воспроизведения transport-related оценки: из `events` взять разность `at_utc` следующего и текущего события для текущих номеров0082–0099, исключив текущие labels `baseline-p85` и `baseline-c1`. Получаются min0.619984s, median0.673679s, max1.027935s. Это интервалы между **стартами** вызовов: transport + execution + host validation/save, не чистая RTT. Для самих child старт→следующий marker: P85≈1.668s, C1≈1.519s; это также не чистое DSI time. Writer failed01 на gate0; его время до recovery нельзя использовать как оценку успешной записи. Ниже приведены новые успешные измерения04.

## Новые измерения clean stock04

[run04](p85_stock_a001_20261108_04/run.json), source commit `86ffbfd76aed81b95ca0e990362dd55aacca99a8`: `awaiting_optical_review`, все три stages qualified, camera stop/settings restoration/watchdog disarm/mutex release true, candidate_attempts0. Это завершённая software/cleanup серия, **не завершённая optical qualification**.

- Successful sham15 writer17.211483s, return15 writer16.694181s; каждый включает собственный pre-quiet и все post-write checks, три callbacks и exact wire подтверждены.
- Baseline32.639854s: P85 6.500035, C1 6.481270, hold/metadata10.270622, quiet остаток9.387926s.
- Sham32.738288s: P85 6.652067, C1 6.624222, hold/metadata10.438224, quiet остаток9.023775s.
- Return30.712932s: P85 6.120809, C1 5.828138, hold/metadata10.078440, quiet остаток8.685545s.
- Child-call start→следующий event для writers: sham1.809585s, return1.764669s; для P85 reads1.452508/1.548783/1.397143s; для C1 reads1.373407/1.450237/1.289679s. Это event-start gaps, включающие host overhead, не чистое device execution. Остальная большая часть write_stage приходится на quiet и распределённые проверки.

Воспроизведение: читать `writes[*].elapsed_seconds`, `stages[*].phase_seconds`, `stages[*].elapsed_seconds`; quiet вычислить вычитанием суммы phase_seconds. Child gaps вычислить как разность `at_utc` соседних events после labels `sham15-write`, `return15-write`, `{baseline,sham15,return15}-{p85,c1}`. Не читать приватные raw logs для этих расчётов.

## Предлагаемые envelopes

Сохранить все identity, native, DBV, ESD, queue, wire, profile и cleanup checks. Compound snapshot не атомарен и не заменяет compositor lock. Каждый компонент должен иметь проверенный exit status и однозначную ограниченную секцию результата. Отказ при oversize/truncation, без усечения evidence. Не передавать большие trace/dmesg через argv. Сырые секции остаются private; публично только timing и результаты validators.

1. `Sweep.state`: четыре host calls → один compound snapshot: brightness/bl_power/DC/Enforcing; dumpsys display; boot; owner. Сохранить исходные проверки и privilege context каждого компонента.
2. `Sweep.quiet`: сейчас11 calls + sleep2. Консервативный вариант: отдельный batched pre-state с host validation, затем envelope begin marker→sleep2→end marker→dmesg→post-state. Host проверяет прежние quiet/native/state predicates до любого следующего child. Одно-envelope вариант pre-state→markers/sleep/log→post-state допустим только после review эквивалентности: он откладывает pre-state host rejection до завершения readonly/marker envelope, но никогда не запускает DSI до всех validators. Не объединять quiet с последующим child.
3. `Trial._observe_stage`, каждая P85/C1 фаза: сейчас9 calls (begin, child, end, dmesg, state×4, ESD). Один envelope: begin→**неизменный child отдельным subprocess**→end→dmesg→state→ESD. Не inline-ить тело child, не менять его traps, timeout, packet sequences, callbacks или lifetime probes. Все прежние host capture/wire/state/ESD validators должны успешно завершиться перед следующим child. Ошибка child немедленно завершает envelope; postprocessing не должен маскировать status.
4. `Trial.write_stage`: сохранить отдельный qualified quiet и host collision check до writer. Затем envelope begin→неизменный writer subprocess→end→dmesg→state→ESD. Не добавлять reader/return15 до host validators. Collision preflight можно включить в предшествующий readonly snapshot, но его host rejection должен предшествовать writer.
5. Hold: отдельный begin перед camera_start; исходные camera_start→sleep4.5→camera_end неизменны, ≥120 advancing sensor frames сохраняются. После camera_end объединить end marker→dmesg→state. Не распараллеливать camera/target ради предполагаемой экономии; сохранить timestamp bounds и ≥60 central encoded frames review.
6. Identity/root/panel/module также можно пакетировать без удаления проверок, но это pre-arm работа и не основная экономия активного окна.

`esd_read_script` сохраняет собственный readonly debugfs mount namespace, timeout и unmount cleanup. Child cleanup не заменяет эту независимую проверку. Не считать одно успешное последнее действие доказательством успеха envelope. Framing должен различать payload и transport metadata, отклонять отсутствующие/повторные/неупорядоченные секции и неполный вывод.

## Консервативный active-window budget

Начало учёта: host monotonic непосредственно перед arm, как в текущем runner; watchdog обязательно arm до неизвестной записи и без renewal. Конец: подтверждённый disarm после exact15 TX + qualified15 readback + C1=60 + native/DBV/ESD. Финальный optical hold/review и полный cleanup остаются обязательными, но находятся после подтверждённого возврата.

Условие допуска:

    A + 2*W + O_candidate + V_return + D + J + 8 < 45 seconds

A — arm transport/verification; W — полный write_stage включая собственный pre-quiet; O_candidate — quiet+P85+C1+полный hold/metadata/post-state; V_return — quiet+P85+C1/native/DBV/ESD без финального optical hold; D — disarm; J — явный положительный запас variability/host processing, не учтённый другими измерениями; 8s — неизменный recovery reserve. Вместо 2*W можно суммировать отдельные upper bounds двух writes.

Эквивалентная детализация для сопоставимых envelopes:

    A + 4*Q + 2*W_body + 2*R85 + 2*RC1 + H + D + J + 8 < 45

Q включает все pre/post-state quiet checks; W_body включает collision/writer/post checks вне Q; R85/RC1 включают все проверки своей read фазы; H — полный candidate hold/metadata/post-state. Не дублировать компоненты и не вычитать их без измерения.

Даже удаление только final hold не спасает старый код: O≈34.389s и V≈23.929s дают58.318s **без** двух writers/arm/disarm. Экономия десятков calls делает batching правдоподобным, но это hypothesis, не измеренная upper bound.

Будущий admission использует phase maxima успешных same-version stock runs и свежего baseline/sham, плюс согласованный jitter margin. Среднее/median не являются upper bound. Проверять remaining-path budget перед каждым следующим шагом, сохраняя существующий8s reserve. При недостатке времени или любой uncertainty — только same-bound-target ordinary reboot; не blind15/page0 append и не retry DSI. Нельзя увеличивать45/60s или убирать проверки ради прохождения.

## Уточнённая оценка feasibility по04

Stock surrogate последовательности write→candidate observation→return write→return evidence: sham writer17.211483 + sham observation32.738288 + return writer16.694181 + return observation30.712932 − return hold10.078440 = **87.278444s** без A/D/J/8. Это surrogate, не физический candidate timing.

Более консервативная сумма phase maxima внутри04:

    Wmax = 17.211483
    Qmax = 9.387926
    R85max = 6.652067
    RC1max = 6.624222
    Hmax = 10.438224
    2*Wmax + 2*Qmax + 2*R85max + 2*RC1max + Hmax = 90.189619s

Здесь Wmax уже включает два writer quiet, поэтому добавлены только два observation quiet. Maxima одного run — наблюдённые максимумы, не доказанная future worst-case bound. Не подставлять их в новый gate как гарантированные bounds.

При консервативном two-envelope quiet уменьшаются36 calls (4×(11−2)); два writer bodies дают16 (2×(10−2), сохраняя отдельный collision preflight); четыре read phases дают32 (4×(9−1)); hold tail даёт5 (6−1). Всего **89 меньше host calls** при сохранении последовательности проверок. Это static call accounting успешного пути, не измеренная экономия времени. Все команды и их execution/output costs остаются.

Чтобы достичь45s с резервом8s, batching должен убрать **более53.189619s плюс A+D+J** из этой исходной суммы. Деление53.189619/89 даёт≈0.598s требуемой средней чистой экономии на удалённую границу, ещё без A/D/J. Исторический median gap≈0.674s включает полезное execution/validation, поэтому нельзя считать его полностью устранимым. Feasibility правдоподобна, но **запас узкий и не доказан**; two-envelope вариант может не пройти. Одно-envelope quiet экономит дополнительно4 calls только после review эквивалентности и не гарантирует успеха. При недостаточном measured budget остановиться, не расширять лимиты/не убирать guards.

## Handoff implementer: отдельная будущая задача

1. Сначала добавить isolated envelope builder/parser и unit fixtures: строгие bounded секции, per-component status, исходные privilege contexts и child subprocess без изменения generated child text. Не модифицировать shared DSI builders ради скорости.
2. Добавить batched state и консервативный two-envelope quiet в Trial-specific слой; существующие shared callers не менять без необходимости. Сохранить host gate между pre-state и quiet envelope и между quiet и child.
3. Подключить read/write envelopes и hold-tail batching; сохранить все существующие validators, pending_read/panel_uncertain transitions, exception recovery и final cleanup. Не объединять соседние child operations через host gate.
4. Добавить monotonic phase accounting и remaining-path budget model, покрыть fake-clock tests. Не ослаблять действующий candidate admission во время разработки. Если нужно включить новый admission позднее, отдельный review и только same-version successful stock timing/optics; старый record не должен молча проходить новую схему.
5. Выполнить offline regression/fault suite; передать coordinator diff, результаты и список потенциальных semantic differences. Только coordinator решает stock-only live run. После новых измерений повторно рассчитать feasibility и получить отдельное решение по candidate. Этот документ не является разрешением выполнения.

## Обязательные проверки до candidate

1. Offline framing/fault injection: missing/duplicate/reordered/embedded delimiters; truncation/oversize/invalid encoding; stderr и nonzero любого компонента; transport loss после каждого компонента; сохранение partial evidence private.
2. Доказать неизменность каждого child subprocess и его shell/traps/timeout/packets/gates. Выполнить существующие regression/fault suites, включая `python3 -O`. Native errors, pending/flags, wrong wire, lost trace, probe misses, prefix corruption, ESD/owner/boot/state mismatch должны по-прежнему запрещать следующую DSI.
3. Mock ordering: failed host validator запрещает следующий reader/return15; disarm запрещён до полного exact15/C1/native/DBV/ESD либо проверенного recovery boot. Камера/cleanup failures не превращаются в completion.
4. Timeout: envelope не создаёт unbounded/background child; исходные child timeouts и cleanup сохраняются. Host timeout/loss не считается доказательством остановки device command. Fixed60s watchdog остаётся независимым и не возобновляется. При неизвестном результате — recovery, не повтор операции.
5. Новая stock-only серия same-source version и независимый optical review. Нужны successful sham15/return15 writer timings, read envelopes, quiet, arm/disarm protocol accounting. Failed01–03 не квалифицируют новый код; clean04 ожидает optical review и тоже не квалифицирует будущую изменённую transport/version.
6. Записывать monotonic start/end каждого envelope и host validation/save, плюс arm→return evidence→disarm. Не подменять эти измерения прежними event-start gaps. Unbatched successful writer latency измерен в04. Неизвестны batched writer/read/quiet latency, стоимость крупных snapshots, tail jitter, timeout/cancellation timing и влияние batching на validators.

Не выполнять candidate до выполнения этих пунктов и отдельного решения координатора. Не расширять значения85, не писатьC1, не добавлять reset/sleep/latch/boot/security changes. Readback и camera banding не доказывают PWM Hz или физическое восстановление DDIC.
