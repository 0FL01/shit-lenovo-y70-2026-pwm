# Timed factory-15 surrogate: timing review

## Результат

Measured G = **31.039259346 s**. Запас до host active deadline 37 s: **5.960740654 s**. С неизменным recovery reserve 8 s и предложенным J = 2 s: G + 8 + J = **41.039259346 s**, остаток до 45 s **3.960740654 s**.

Это один успешный sample, **не robust bound и не candidate admission**. Более консервативная сумма всех same-version phase maxima, включая медленный baseline, уже даёт **36.239293588 s** до межфазного overhead, или **46.239293588 s** с 8 s + J = 2 s. Поэтому положительный actual G нельзя превращать в readiness.

Источник: [завершённый timed stock 01 run.json](p85_timed_stock_a001_20261108_01/run.json), source `1785d32fd011314df3f1c5c55a5d3cbe0ee6b8a2`, finished `2026-11-08T18:50:21.169304+00:00`. Scope `p85-timed-stock-surrogate-v1`: только factory 15; middle diagnostic C1 явно не измеряется, baseline/return C1 обязательны. Все optical holds сохранены. Unknown 14 disabled. Независимый hardware/optical review отдельно; документ анализирует только timing. Устройства/видео не читались, источники/report не изменялись.

## Полный интервал и вложенность

- Active start monotonic 611555.711761743.
- Return qualified monotonic 611586.181837974: **30.470076231 s** после start.
- Disarmed monotonic 611586.751021089: разность со start точно согласуется с G.
- Arm 1.153986164 s; request-to-verified 1.153962398 s, почти тот же вложенный интервал, не суммировать оба.
- Disarm 0.569183115 s входит в G.
- Writer sham 3.909918340 s, return 3.746445523 s: уже включают fresh host dispatch-gap, writer envelope/PRE_GUARD и host validation. Предварительный первый quiet выполнен вне active clock.
- Middle observation 13.311972161 s: quiet 4.007247219, P85 2.171097471, hold/metadata 7.133610926 s; C1 отсутствует согласно scope.
- Return до disarm: quiet 4.050174318, P85 2.167537386, C1 2.125264986 s. Финальный return hold 7.370236538 s остаётся обязательным, но вне G после qualified return/disarm.

Сумма arm + оба writer elapsed + middle observation elapsed + return quiet/P85/C1 + disarm = **31.034481993 s**. Разница до полного G **0.004777353 s**: control/save/gaps, не ошибка и не бесплатное время. Для admission предпочтителен полный monotonic G и непрерывные remaining-path интервалы, а не сумма неполных phases.

20 active transport intervals суммарно **30.478143359 s**, остаток G **0.561115987 s** содержит explicit wait, host work и gaps. Эти transport intervals уже содержат device execution; не трактовать их как чистую RTT. Последний transport end предшествует disarmed на 0.002405616 s. Recorded remaining_active_seconds согласуются с 37 − (action start − active start) в пределах 0.000001724 s из-за соседних clock reads; противоречия таймеров не обнаружено.

## Overlap, freshness и PRE_GUARD

Camera-start call завершён в 611568.078142381; camera-end call начат в 611572.578314759. Разница **4.500172378 s**, hold не укорочен.

Полный return-prequiet: 611568.082962536 → 611572.178793563, **4.095831027 s**, полностью внутри hold. Записаны overlap 4.095831027 s, overshoot 0, wait 0.399348818 s. Начальный gap от завершения camera_start до prequiet ≈ 0.004820155 s; оставшиеся небольшие различия относятся к host scheduling. Marker interval на target kernel clock **2.155250 s**; это другой clock, его нельзя синхронизировать с camera/host timestamps вычитанием.

Return camera-end→dispatch **2.081810485 s** включает final hold validation и fresh host dispatch-gap. Host gap envelope: sham ≈ 1.010860 s, return ≈ 1.035812 s. Оба writer PRE_GUARD по device uptime **0.160 s**, с ограниченной точностью uptime; они уже включены в writer envelope (≈ 2.885488 / 2.697420 s), не прибавлять отдельно.

Quiet-age upper values 5.065212316 / 5.658878697 s измерены до validated return; это не точное время callback и не установленный допустимый возраст. Native/state/owner/collision coverage обеспечивается проверками, а не просто малым возрастом. PRE_GUARD прямо перед CHILD проверяет bounded dmesg от protected marker и state; post-child validation дополнительно проверяет весь protected wire interval. Это timing description, не доказательство атомарного exclusion или замена независимого safety review.

При следующем run overshoot допустимо только учитывать фактически: не сокращать hold, не объявлять completed hold заранее, при нехватке remaining path — uncertainty/reboot policy. Overlap уже находится внутри hold elapsed; его нельзя ещё раз вычитать из G.

## Почему provisional estimates не являются admission

Каждый active_action вычитает одинаковые baseline quiet + P85 + C1 = **10.796865233 s**, даже когда часть return уже выполнена. Поэтому partial_margin около return P85 +0.014609580 s, перед C1 −2.147797104 s, перед disarm −4.267775602 s. Это не нарушение реального 37 s deadline: значение явно имеет status `provisional_partial_not_a_bound`, не моделирует оставшийся путь и не включает writer/freshness/disarm/variability.

Actual remaining-to-disarm: перед return dispatch-gap 12.658357576 s; перед return writer 11.615575655 s; перед return P85 4.850743172 s; перед return C1 2.688334506 s; перед disarm 0.568354355 s. Это retrospective measurements, не prospective bounds. Текущие timeout caps также ограничены только оставшимся host clock, а не бюджетом всей suffix-последовательности.

## Консервативный same-version расчёт

Нельзя выбросить baseline как «разогрев» без заранее обоснованного state-conditioned протокола. По всем сохранённым stages этой версии:

    A = 1.153986164
    Wmax = 3.909918340
    Qmax = 4.987156081
    R85max = 3.067384529
    RC1max = 2.742324623
    Hmax = 7.844881786
    D = 0.569183115
    A + 2*Wmax + 2*Qmax + 2*R85max + RC1max + Hmax + D
      = 36.239293588 s

Middle C1 не включён, return C1 включён. Hmax берётся консервативно по доступным holds; overlap не вычитается повторно. Добавить непокрытый control/save overhead S и J, а не объявлять приведённое worst-case guarantee. С J = 2 s модель сейчас не проходит; без J запас всего 0.760706412 s до 37 s до S. Не уменьшать J для прохождения.

## Минимальная следующая квалификация и pre-action модель

Предложение для координатора/reviewer, не самостоятельное разрешение live:

1. Минимально два дополнительных **полных same-version factory-15** runs, то есть три total, с тем же scope, профилем, checks и immutable watchdog. Первый — fresh run после обычного восстановления; второй — отдельный повтор normal setup после завершения предыдущего, без искусственного warm-only отбора. Все failures/slow samples сохраняются. Три runs дают минимальную проверку повторяемости, не статистическую гарантию tail; текущий failing phase-max автоматически ими не отменяется.
2. Сопоставить whole G, A/D, writer gap/PRE_GUARD, middle Q/R/H-overlap, return Q/R85/RC1 и suffix bounds. Использовать максимум по всем подходящим samples плюс S и J ≥ 2 s как ранее предложенный инженерный floor; увеличить J при evidence большей variability. Никаких cold-baseline исключений post hoc. State-conditioned bounds допустимы только по отдельному review с проверяемыми preconditions, не ради сокрытия медленного sample.
3. Перед каждым действием вычислять **сумму оставшегося конкретного пути** B_suffix(action), не постоянный baseline пакет. Launch разрешать лишь когда elapsed + B_suffix + J + S < 37 s. Для отдельного action timeout дополнительно ограничивать временем, остающимся после зарезервированного downstream suffix/J; completion проверять фактическим clock. При violation не начинать следующую DSI и применять существующую reboot-only uncertainty policy.
4. Overlap-модель: camera-start cost + max(4.5 s, full return-prequiet duration плюс scheduling offsets) + camera-end + final hold validation. Prequiet/state/PRE_GUARD не сокращать. На передаче к return writer отдельно резервировать fresh gap + writer + return quiet/P85/C1 + disarm. Перед return C1 остаётся C1 + disarm + S/J, а не уже выполненные quiet/P85.
5. Admission для unknown 14 не следует из factory-15 timings: возможен иной device latency/effect. Unknown 14 остаётся disabled до независимых hardware/optical/timeout reviews и явного решения координатора.

## Host 37 s не останавливает remote child

37 s — host active alarm/transport deadline, оставляющий 8 s до host45. Истечение host timeout не доказывает, что remote envelope/child прекратил работу: код прямо сообщает remote child may still run. Device PRE_GUARD/child/envelope timeouts имеют собственные durations, не общий синхронизированный remaining clock. Independent 60 s watchdog не renew, запускается до writer, остаётся fallback; он не делает любой remote continuation до 60 s соблюдением host45.

Будущий pre-action budget обязан учитывать remote lifecycle/kill grace и правила recovery при возможном продолжающемся child. Нельзя после timeout дописывать 15/page0, повторять DSI или считать снятие host alarm отменой remote command. Timing этого successful sample не доказывает worst-case remote termination/reboot latency. Это отдельная нерешённая boundary для candidate, которую J или быстрый G не устраняют.

Итог: timing поля согласованы; обнаружены не арифметические ошибки, а намеренно неполные provisional estimates и недостаточность одного actual G для консервативного admission. Сохранить текущие запреты и продолжить только отдельно согласованную stock qualification.
