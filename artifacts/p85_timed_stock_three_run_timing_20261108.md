# Timed stock: три same-version runs и admission

## Вывод

Все три actual G укладываются в 37 s host active window; **текущий консервативный all-phase-max admission не проходит**. Unknown 14 остаётся disabled. Ни быстрые whole-run samples, ни optical success не отменяют timing/remote-lifecycle ограничения.

Scope: factory 15 surrogate, middle diagnostic C1 явно omitted; baseline/return C1 и все holds сохранены. Source всех runs: `1785d32fd011314df3f1c5c55a5d3cbe0ee6b8a2`. Источники: [01](p85_timed_stock_a001_20261108_01/run.json), [02](p85_timed_stock_a001_20261108_02/run.json), [03](p85_timed_stock_a001_20261108_03/run.json). Все прочитаны после finished_at_utc. Это timing review; независимые raw/optical audits отдельны. Устройства/видео не читались; изменён только этот новый документ.

## Все измеренные samples

В секундах, порядок 01 / 02 / 03:

- G: 31.039259346 / 31.636799846 / 31.614684608.
- Arm: 1.153986164 / 1.142998159 / 1.146698690.
- Disarm: 0.569183115 / 0.576029312 / 0.564788891.
- Sham writer: 3.909918340 / 3.909900575 / 4.665815774.
- Return writer: 3.746445523 / 3.756704774 / 3.592032133.
- Baseline Q / P85 / C1 / H:
  - 01: 4.987156081 / 3.067384529 / 2.742324623 / 7.844881786.
  - 02: 5.291200367 / 2.909065336 / 2.689161911 / 7.897624836.
  - 03: 4.990482904 / 3.301206142 / 3.157491202 / 7.949891425.
- Middle Q / P85 / H:
  - 01: 4.007247219 / 2.171097471 / 7.133610926.
  - 02: 4.166770479 / 2.242448384 / 7.236150098.
  - 03: 4.550057033 / 2.005851925 / 7.087529564.
- Return Q / P85 / C1 / H:
  - 01: 4.050174318 / 2.167537386 / 2.125264986 / 7.370236538.
  - 02: 4.118540771 / 2.272698154 / 2.209665539 / 7.493519438.
  - 03: 3.963813603 / 2.010464238 / 2.023403452 / 7.823038853.

Worst observed G = 31.636799846 s; range 0.597540500 s. Margin to 37 s = 5.363200154 s. With recovery reserve 8 s and proposed positive engineering floor J = 2 s, observed worst total = 41.636799846 s, margin to 45 s = 3.363200154 s. Три runs не доказывают tail bound, особенно для неизвестного register value.

## All-phase-max: точная консервативная арифметика

Сохранены все baseline samples и медленный sham writer 03. Maxima не являются статистически доказанными upper bounds, но это текущая консервативная модель:

    Amax = 1.153986164019
    Wsham,max = 4.665815774002
    Wreturn,max = 3.756704773987
    Qmax = 5.291200367035
    R85max = 3.301206141943
    RC1max = 3.157491202001
    Hmax = 7.949891424971
    Dmax = 0.576029311982

Role-specific writer model, без исключения каких-либо samples:

    B = Amax + Wsham,max + Wreturn,max + 2*Qmax + 2*R85max + RC1max + Hmax + Dmax
      = 38.444731668918 s

Если объединять оба writer roles под один максимальный W, как в прежней более грубой модели:

    Bpooled = Amax + 2*Wmax + 2*Qmax + 2*R85max + RC1max + Hmax + Dmax
            = 39.353842668934 s

Полный G минус сумму собственных arm/writes/middle phase values/return Q-P85-C1/disarm даёт residual S: 0.004793898 / 0.004893601 / 0.004229305 s. Берём observed Smax = 0.004893601057 s; будущие непокрытые costs не считать ограниченными этой величиной автоматически.

- Role-specific B + Smax = **38.449625269976 s**. Уже превышает host active 37 s на **1.449625269976 s** без J. С 8 s + J = 2 s total **48.449625269976 s**: дефицит до 45 s **3.449625269976 s**.
- Pooled B + Smax = **39.358736269991 s**. С 8 s + J = 2 s total **49.358736269991 s**, дефицит **4.358736269991 s**.

Не выбирать только быстрые active-phase samples вместо baseline. Saved native trace review первых runs локализовал значительную часть baseline slowdown вне read trace span; timestamps отдельных envelope sections отсутствуют. Specific warm-up/preparation cause **unknown**. Корреляция с ранней стадией не разрешает conditional bound. Новые быстрые samples не стирают прежние медленные.

## Вложенность, overlap и suffix-модель

Return-prequiet overlap: 4.095831027 / 4.283644643 / 4.025438453 s; overshoot во всех трёх 0. Остаточный wait: 0.399348818 / 0.210609447 / 0.469345965 s. PRE_GUARD: sham 0.16 / 0.20 / 0.21 s, return 0.16 / 0.18 / 0.16 s. Device uptime timing имеет ограниченную точность.

PRE_GUARD уже внутри writer envelope, dispatch-gap внутри writer elapsed, overlap/prequiet внутри middle H. Не прибавлять их второй раз и не вычитать overlap из уже измеренного G. Return final H остаётся вне G только после qualified 15/C1/native/DBV/ESD и disarm; он не отменяется.

Для будущего reviewed pre-action admission нужна suffix-dependent модель, а не нынешний constant baseline Q+P85+C1 estimate:

- Перед arm: весь B + S + J должен помещаться в 37 s.
- Перед middle writer: writer + middle Q/P85/H + return writer + return Q/P85/C1 + disarm + S/J.
- Перед camera_start/overlap: start-metadata + max(4.5 s, complete prequiet with offsets) + end-metadata/final-hold validation + return path. При overshoot использовать actual time, не укоротить hold.
- Перед return writer: fresh-gap + unchanged writer/validators + return Q/P85/C1 + disarm + S/J.
- Перед return P85: P85 + C1 + disarm + S/J; перед C1: C1 + disarm + S/J; перед disarm: disarm + S/J.

Observed maximum retrospective suffix до disarm по трём runs: перед return dispatch-gap 12.933676519 s; writer transport launch 11.848804327 s; P85 launch 5.050991329 s; C1 launch 2.779411922 s; disarm launch 0.574985619 s. Это измерения, не prospective guarantees. Writer transport suffix исключает уже выполненный host gap; не смешивать границы при подстановке bounds.

Launch только при `elapsed + B_remaining + S + J < 37`. Timeout текущего шага должен резервировать downstream bound, а не потреблять весь remaining clock. После каждого результата повторить check; failure/uncertainty допускает только existing same-bound reboot recovery, не следующий DSI/retry/blind return. J не сокращать для прохождения; увеличение при variability допустимо. Три samples уже выполнены: бесконечные повторы ради выбора быстрых результатов не обоснованы.

## Самый маленький transport-only следующий вариант

Один readonly envelope: **prestate → BEGIN → sleep 2 → END/kernel → poststate**, затем все прежние host validators; до следующего child никаких DSI. Все state/native/DBV/boot/owner predicates и marker windows остаются. Изменение: host узнаёт неверный prestate после завершения только readonly/marker sequence, а не до него. Нужен explicit equivalence/fault review: ни скрытого child, ни маскирования nonzero, ни permissive poststate, ни иной cleanup.

В active critical path это устраняет две roundtrip boundaries для middle и return observation quiet. Первый writer prequiet уже до arm, его ускорение не сокращает G. Return-prequiet уже целиком перекрыт hold и имеет zero overshoot; его ускорение преимущественно увеличит wait, а не уменьшит G. Нельзя приписывать четыре full state savings активному пути.

Исходный state snapshot всё равно исполняется и проверяется: экономится transport/envelope overhead, не вся state duration. Даже чрезмерно оптимистичное удаление двух полных наиболее медленных baseline prestate calls (2 × 1.314067721 s), чего реально делать нельзя, не закрыло бы role-specific deficit 3.449625270 s с J = 2 s: осталось бы около 0.821489828 s. Это чувствительность по текущим measured costs, не future bound. Следовательно, вариант мал и разумен для отдельного измерения, но **не обещает admission**. Нужны новая source version и полная stock/optical qualification; unchanged child scripts/guards.

## Более крупный вариант: device-local validated sequencer

Не просто объединить несколько children в один shell. Сейчас host validator является обязательной границей перед каждой следующей DSI. Sequencer потребовал бы перенести **эквивалентные fail-closed validators** для trace/profile/queue/wire/native/DBV/ESD/ownership/identity/cleanup на устройство, прежде чем оно вправе вызвать следующий неизменный child. Нельзя отложить проверки до конца и назвать это batching. Camera metadata/optical holds требуют отдельного последовательного handshake. При потере host нельзя автоматически продолжать неизвестные профили или объявлять optical success. Возможный автономный возврат factory 15 должен быть отдельно проверенным recovery scope с полной локальной qualification; неизвестный outcome child, timeout или потеря evidence по-прежнему допускают только reboot, не blind 15.

Это новый safety-critical coordinator, намного больше scope/risk, чем readonly quiet envelope. Нужны bounded outputs, explicit per-child and absolute device deadline, no-renew watchdog, exit/signal/transport-loss faults, точный механизм remote stop/recovery, сравнение всех отрицательных fixtures с host validators и независимый review. Иные device-local processing costs и firmware state требуют нового stock timing/optical evidence. Никакой readiness или разрешения реализации здесь нет.

## Неподвижные границы

45 s host budget, включая 8 s recovery reserve; active host deadline 37 s; independent immutable device watchdog 60 s без renewal. Host timeout/alarm не гарантирует прекращение remote child: remote continuation и kill/reboot grace отдельно требуют доказанного lifecycle design. Успех трёх factory-15 runs этого не проверяет. J = 2 s — proposed engineering floor, не tail guarantee и не замена remote cancellation.

Итог: measured repeatability улучшила знание actual G, но all-phase conservative deficit увеличился из-за сохранённых медленных samples. Следующий шаг — отдельный review изменения transport/scheduling либо существенно более крупного coordinator design, не ослабление guards или постфактум conditional exclusion.
