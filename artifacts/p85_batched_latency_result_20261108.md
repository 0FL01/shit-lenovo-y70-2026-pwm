# P85 batching: измеренный budget и оставшийся критический путь

## Решение

**Candidate не готов.** Clean software/cleanup результат первого batched stock-only run не укладывает текущий последовательный active path в 45 s с неизменным 8 s recovery reserve. Optical review также ещё требуется. Watchdog 60 s не заменяет host 45 s и не может продлеваться.

Источник: [завершённый batch 01 run.json](p85_batch_stock_a001_20261108_01/run.json), source commit `881ffb7e501d95205ad3f9ac8ece89adb143387e`; `finished_at_utc` присутствует, status `awaiting_optical_review`, candidate_attempts 0, camera_stopped_verified/original_settings_dbv_logger_restored/watchdog_disarmed/mutex_released true. Чтение выполнено после завершения. Устройства и видео не читались; этот документ не изменяет executable/report.

Контекст: [исходный latency plan](p85_latency_plan_20261108.md), [batched runner](../06-tools/run_p85_batched_trial.py), [envelopes](../06-tools/p85_batched_envelope.py).

## Точные сохранённые измерения

В секундах; всё ниже measured elapsed, а не чистая RTT:

- Baseline stage 18.548828569: quiet 4.988472469, P85 3.331255446, C1 2.810262107, hold+metadata 7.417966624.
- Sham stage 16.668455343: quiet 4.229970849, P85 2.271186521, C1 2.125686755, hold+metadata 8.040516369.
- Return stage 15.953030156: quiet 4.261436596, P85 2.145590776, C1 2.078580925, hold+metadata 7.465821067.
- Sham writer 6.673705390; return writer 6.589433672. Каждый включает отдельный prequiet и все writer checks.
- Writer envelopes 2.435467950 и 2.420976504 по сохранённым envelope timings; для расчётов брать полную точность JSON, не округлённые значения здесь. Prequiet envelopes+prestate соответственно примерно 4.223944 и 4.148334 s, без небольшого host overhead.
- Stage elapsed minus sum(phase_seconds): baseline 0.000871923, sham 0.001094849, return 0.001600792 s. Эти остатки не исчезают из upper budget.

`transport_seconds` включает command construction/transport/device execution. `envelope_timings.elapsed_seconds` включает часть host overhead; `phase_timings` дополнительно фиксирует validation/save. Вложенные интервалы нельзя суммировать второй раз поверх elapsed parent phase. Сумма отдельных framing_validation/host_validation/host_save durations за **весь run** ≈ 0.142510 s. Python micro-optimization не даёт нужных нескольких секунд.

Воспроизведение без private raw: из JSON взять `writes[*].elapsed_seconds`; `stages[*].phase_seconds`; stage residual вычислить как elapsed минус сумму phase values. Для каждого вида phase взять максимум по трём qualified stages. Для envelopes отфильтровать labels `sham15-write`, `return15-write`, `quiet-sham15_PRE`, `quiet-return15_PRE` и непосредственно предшествующие state entries. Не считать timings одного run доказанными worst-case bounds.

## Текущий active path не проходит

Сохраняем исходную формулу:

    A + 2*W + 2*Q + 2*R85 + 2*RC1 + H + S + D + J + 8 < 45

A — arm и его проверка; W — полный writer с prequiet; Q — observation quiet (writer quiet уже в W); R85/RC1 — qualified read phases; H — candidate hold/metadata/последующие native/state checks; S — непокрытые межфазные save/control costs; D — disarm; J — явный запас variability. Финальный return optical hold вне active exposure только после exact 15 TX + qualified 15/C1 = 60/native/DBV/ESD и подтверждённого disarm, но остаётся обязательным.

Observed maxima одной и той же batched версии:

    W = 6.673705390072428
    Q = 4.988472468918189
    R85 = 3.331255445955321
    RC1 = 2.810262107057497
    H = 8.04051636904478
    2*W + 2*Q + 2*R85 + 2*RC1 + H = 43.64790719305165

Следовательно **51.647907193 s с 8 s reserve**, ещё без A/S/D/J. До допуска требуется сократить более 6.647907193 s плюс A/S/D/J. Нельзя исключать медленный baseline или использовать только более быстрый sham/return.

Даже optimistic actual stock surrogate sham writer + sham observation + return writer + return observation − return hold = **38.418803494 s**, то есть **46.418803494 s** с 8 s reserve, ещё без A/D/J. Это не live candidate measurement, и оно уже не проходит.

## Наименьшие guard-preserving следующие варианты

Ни один пункт не разрешён этим документом к выполнению. Требуется отдельный дизайн/review и новая same-version stock qualification. Изменения научного протокола нельзя скрывать как latency optimization.

1. **Подготовить первый writer до arm.** Выполнить существующий writer prequiet, nonce/collision preparation и host validators до независимого arm; затем arm и только после подтверждения вызвать неизменный child. Начало 45 s остаётся непосредственно перед arm,60 s начинается до unknown write и не renew. Все child queue/native/owner/wire gates остаются. Нельзя переносить arm после первого callback. Прежний arm identity/camera/quiet также сохраняется. Обязательны freshness review и проверка, что окно между prequiet и child не вводит непокрытую native смену; при необходимости readonly interval/child checks должны покрывать arm gap. Экономия примерно 4.2 s в этом stock run, но новая bound неизвестна. Одного этого недостаточно по 43.6479 s phase-max модели.

2. **Совместить return-prequiet с уже обязательным candidate optical hold.** После candidate P85/C1 host qualification: hold begin→camera start→полный return-prequiet (отдельно hostvalidated prestate, собственные markers, sleep 2, kernel+poststate validators)→при необходимости дождаться полных 4.5 s от конца camera_start→camera_end→hold-end/native/state validation→return writer. Оба набора evidence и validators сохраняются; ≥120 advancing sensor frames и ≥60 central encoded frames с прежними timestamp margins не сокращаются. Никакой параллельной DSI/камерной команды, никакого return writer до всех validators. Fresh collision gate должен использовать свежий final hold kernel snapshot; native quiet coverage должна включать промежуток до return child, а не предполагаться из старого snapshot. Это scientific-equivalence hypothesis: quiet/read-only activity во время съёмки надо проверить stock optics. Максимальная устранимая задержка ограничена overlap, не полной суммой elapsed; при долгом prequiet hold станет длиннее, а не будет обрезан. Нельзя просто удалить prequiet или сократить hold.

По наблюдённым ≈ 4.2 s prequiet каждый из двух вариантов отдельно не закрывает 6.65 s+overhead дефицит; вместе способны приблизить fit, но запас перед A/D/J остаётся узким. Экономию нельзя вычесть как доказанный future bound: нужен новый scheduling prototype, deterministic fake-clock accounting и свежие stock measurements. Значения candidate могут менять поведение/latency; robust gate обязан резервировать оставшийся return path.

3. Если этих двух изменений недостаточно, next-smallest transport вариант — одно-envelope quiet со всеми прежними pre/post snapshots и 2 s markers, без child до host validations. Это откладывает pre-state host rejection внутри readonly envelope, поэтому требует отдельного equivalence/fault review. Либо уменьшить чистый transport overhead, не меняя checks. Ни тот ни другой вариант не обещает нужную экономию заранее.

В рамках анализируемого неизменного протокола нельзя молча убрать candidate C1/native/ESD или return qualification, сократить 4.5 s/120sensor/60encoded thresholds, вырезать final optical hold, записать 15 вслепую, уменьшить 8 s reserve, поднять 45/60 s. Readback-only trial без оптической проверки не отвечает текущему PWM experiment objective и потребовал бы отдельного явно изменённого исследовательского вопроса; здесь он не предлагается как готовый обход. Отдельный вариант с явным изменением только candidate diagnostic scope и исключением candidate C1, при сохранении P85 readback, optics/state и полного возврата 15 + C1, находится вне данного анализа неизменного протокола. Это не утверждение о его универсальной научной непригодности: координатор отдельно запрашивает независимый review такого варианта. Данный документ не разрешает это изменение или его выполнение.

## Требования к будущему admission

- Batched runner сейчас намеренно stock-only: constructor/CLI/arm_candidate/write 14 запрещают candidate. Это сохранить до отдельного review, не включать через наследование base gate.
- `BatchedTrial.envelope` вызывает transport напрямую с `plan.seconds+5`, обходя inherited `Trial.shell` clipping. Для будущего candidate нужен самостоятельный remaining 45-minus 8 deadline на **каждый** envelope и camera call; launch допускается лишь когда измеренный remaining whole-return budget помещается. Device child timeout/kill grace также должны укладываться в политику, host timeout не доказывает остановку child.
- Unknown/timeout/lost evidence → same-bound reboot, не retry/append 15/page 0. Watchdog 60 остаётся независимым, не renew; disarm только после exact 15+qualified readback/C1/native/DBV/ESD или verified changed boot recovery. Cleanup и optical hold/review обязательны.
- Измерить A/D/S и обосновать J на безопасной stock-only protocol rehearsal; успешный optical review текущего stock run не измеряет эти неизвестные и не квалифицирует будущую изменённую версию.
- Tests должны покрыть pre-arm preparation ordering, arm failure before child, stale native/collision evidence, quiet/hold overlap и overshoot, unchanged 4.5 s timing/metadata bounds, каждый failed validator, deadline в любой фазе и запрет следующей DSI. Сохранить существующие child/framing/cleanup fault suites и `python3 -O`.

Итог: batching дал существенное измеренное ускорение, но текущий sequential active path остаётся недопустимым. Следующий полезный шаг — review минимального изменения расписания, а не ослабление admission gate.

## Дополнение: минимальная следующая stock-only rehearsal для reviewer

Предложение координатора, **только план**, не разрешение этого документа на live execution:

1. Сохранить baseline/sham optics и identity/camera/owner проверки. Для surrogate factory 15 подготовить writer nonce, collision evidence и полный stock prequiet **до arm**. Непосредственно перед arm свежо подтвердить необходимые identity/state, а gap до child записать и покрыть native evidence; стоимость этих дополнительных проверок нельзя считать нулевой. Если gap устарел/неполон, unknown child в будущем запрещён.
2. Arm **тот же** отдельный immutable 60 s watchdog и фиксировать host start до arm; unknown 14 по-прежнему жёстко disabled. Только после подтверждённого arm вызвать factory 15 writer, используя неизменный child и все callbacks/host validators. Любой отказ запрещает следующий DSI.
3. Сохранить candidate-surrogate observation prequiet и оба P85/C1 readers со всеми проверками. В минимальном изменении этот observation quiet **не удалять**: writer wire interval содержит намеренную DSI, а не прежний 2 s quiet. Qualified read intervals также содержат чтения и не являются заменой `qualify_quiet`. Два endpoint state snapshots сами по себе не доказывают непрерывную native stability. Заменить gate более поздним hold означало бы выполнить readers до прежнего prerequisite; это отдельное изменение safety ordering, не эквивалентное простому reuse. Если рассматривать позже, нужен новый доказанный invariant и fault review, а не вычитание 2 s из budget.
4. После readers: hold begin, camera_start; затем полный return-prequiet со своими 2 s markers и state/native checks. Дождаться минимум 4.5 s **после завершения camera_start**, если prequiet занял меньше. Затем camera_end, hold-end snapshot и все quiet/native/state/camera progress validators. Если prequiet/metadata/transport переросли ожидаемую длительность, использовать actual elapsed и remaining-path admission; не объявлять unchanged hold заранее и не обрезать его. Не начинать return writer при неполной qualification.
5. После свежего collision/native-gap validation выполнить explicit factory 15 return writer и полный return observation quiet/P85/C1/native/DBV/ESD. Только после доказанного возврата disarm тот же short watchdog, записать end. Final optical hold, video review и cleanup остаются обязательными.
6. Измерить A, D, gaps, каждый qualified phase, **полное arm-start→disarm-confirmed G** и запасы remaining-path перед каждым действием. Успех software rehearsal не означает optical equivalence. Требуются fresh video replay с unchanged profile/ROI/timestamp criteria и независимый review, затем same-version stock qualification. Никаких 14 в этой rehearsal.

### Запас и критерий feasibility

С текущими данными два scheduling savings оцениваются примерно 4.2+4.15 ≈ 8.35 s; phase-max surrogate 43.6479−8.35 ≈ 35.30 s до A/D/S/J. Это **projection**, не measured bound: overlap ограничен фактическим 4.5 s wait, новые freshness checks/gaps добавляют стоимость. С 8 s reserve остаётся всего ≈ 1.70 s для A/D/S/J. Поэтому перенос расписания не даёт автоматического допуска и может оказаться недостаточным.

После rehearsal использовать измеренный conservative same-version bound G для arm→disarm и требовать:

    G_bound + J + 8 < 45
    J_available = 37 - G_bound

Если J_available ≤ 0, отказ без обсуждения. Если положителен, это не разрешение выбрать J ≈ 0. Для независимого reviewer предлагается начальный **инженерный**, не статистически доказанный floor J = 2 s, отдельно от 8 s recovery reserve; тогда нужен G_bound < 35 s. Floor 2 s нельзя считать tail guarantee: несколько повторных успешных factory 15 rehearsals должны показать, что measured variability/overhead не требуют большего J. Если требуют, поднять J или отказаться, не лимиты 45/60. Подбирать J только ради прохождения нельзя. Прежние phase maxima уже учитывают observed variation внутри run; не суммировать те же интервалы дважды, но резервировать невиденные tails отдельно.

В текущих stock timings P85 разброс 3.3313−2.1456 ≈ 1.1857 s, C1 ≈ 0.7317 s, quiet ≈ 0.7585 s; это дополнительная причина не использовать несколько десятых секунды как убедительный запас. Нужны actual A/D, которых эта версия не измеряла. Ожидаемое ускорение transport не подменяет измерения.

Минимальные новые риски: pre-arm evidence может устареть во время arm; overlap может удлинить hold и съесть return reserve; read-only quiet activity может влиять на кадры; deadline может истечь внутри envelope; host timeout не гарантирует child stop. Mitigations: full gap/native coverage, conservative remaining whole-return admission, actual timestamps/full-length hold, fresh optical replay, неизменные subprocess gates, independent no-renew watchdog и reboot-only uncertainty. Все candidate guards остаются disabled до отдельного решения.
