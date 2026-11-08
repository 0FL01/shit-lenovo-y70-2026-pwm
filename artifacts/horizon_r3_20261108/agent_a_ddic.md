# Agent A — DDIC / emission mechanism, bounded offline audit

Source checkout: `fffb0feeda534add90dfaf7056964d40adefc183`. 2026-11-08.
No device access, binary deployment, DSI program generation, or new capture.

## Executive result

**Нового декодированного PWM setter не найдено.** Существующий A0D1C1 остаётся
наиболее проверяемым неиспользованным DDIC-рычагом, но его подготовка — прежняя
работа, не открытие этого запуска. Новое здесь — привязанная к сохранённым binary
программам факторизация, которая показывает точно, какой независимый параметр
ответа измеряет этот опыт, и где прежние отрицательные результаты его не ограничивают.

Вторая новая проверка ограничивает достижимость «банков 4F»: среди всех 52
выбранных DT arrays только `4F:81` имеет готовые writers, причём всегда внутри
одного составного шаблона. Для остальных перечисленных 4F-пар, `07:EC` и `23:C1`
готовых writers нет. Это ограничение **этого статического DT**, не доказательство
read-only регистра или отсутствия runtime writer.

## 1. Факторизация существующих вмешательств

[Воспроизводитель](agent_a_factorization.py) и [результат](agent_a_factorization.json)
независимым parser проверили framing и байты семи сохранённых программ: 875 bytes,
75 packets, неизменные headers. A=изменение единственного payload byte `23:A9`
по offset `0x44`, D=`24:9D` по `0x61`, C=остальные **83 bytes в 32 packets**
native ON/OFF. A0D1C1 отличается от OFF на 84 bytes / 33 packets; полный ON на
85 / 34. Никакой новый кандидат не создан.

Сохранённые испытанные вершины ADC: `000,100,010,110,001,111`; `011` подготовлена,
но не запускалась, `101` тоже не измерена. Источники response labels:

- `dsi_selector_split_20261107/result.md:4–6,21–35,76–79`: A9-only подавляет fine,
  9D-only сохраняет; оба поля могут иметь отдельные readback values.
- `dsi_block_trials_20261106/with_redraw/result.md:3–7,35–45`: selector-pair
  подавляет fine при DBV3600 и redraw; отдельные page53/page63/mode90 не дают
  значимого эффекта в проверенном контексте.
- `dsi_coupled_on_20261107/result.md:8–12,22–33`: S0C1 fine сохраняет.
- `dsi_coupled_9d_20261107/proposal.md:11–34`: native ON после redraw подавляет
  fine; это не waveform identity и не измерение Hz.

В условной насыщенной двоичной модели `F(A,D,C)`, где 1 означает качественное
подавление fine-train, шесть наблюдений имеют **rank 6 из 8**. Это алгебраическое
свойство дизайна, не fitted физическая модель. Все четыре заполнения двух
недостающих вершин совместимы с прежними labels. Формула имеет вид:

`F = A + (v−1)·A·C + u·D·C + (1−v−u)·A·D·C`,

где `u=F(0,1,1)`, `v=F(1,0,1)` пока свободны (по 0/1).

Новая stock→A0D1C1→stock серия непосредственно измеряет **совокупный эффект
профиля**, отличающегося от stock в 33 packets (84 bytes). **D×C contrast**
`F011−F010−F001+F000` получается только при подключении исторических наблюдений
`010/001/000` и допущении сопоставимости динамического состояния панели, условий
и метрики между сериями. При этом допущении отрицательные D-only и S0C1 не
являются отрицательной проверкой interaction. Положительный полный ON тоже не
определяет его: A=1 уже даёт suppression в C0. Это условное основание проверки
взаимодействия, а не изоляция эффекта 9D или ×2–3 частотный множитель.

Под равномерным **иллюстративным**, не эмпирическим prior по четырём binary
completions каждая из двух недостающих вершин даёт один bit информации. Поэтому
заявлять, что `011` математически имеет больше информации, чем `101`, нельзя.
Приоритет `011` — инженерный: A=0 позволяет увидеть самостоятельную D×C ветвь
вместо модификации уже подавленной A9-ветви, и программа уже byte-validated.
Для реальной optical waveform и Hz такой prior не задан; численной вероятности
успеха в ≥2000 Гц из этой факторизации получить невозможно.

Ограничения: trials в разные моменты, совпадают nominal условия, но полное
динамическое состояние панели не доказано; C — совокупность 32 вмешательств;
качественная label скрывает остаточную амплитуду. Старое A9 q93 ratio0.2264067
не пересчитано и не изменено. Нельзя подставлять бинарный F в физический Hz.

## 2. Достижимость 4F и возможный commit/shadow механизм

В текущем выбранном DT **52 arrays / 1101 packets** найдены четыре writers `4F:81`:
два DC arrays с `81 10` и timing@4/@5 с `81 06`. Во всех четырёх порядок:

`08:98=02 → 4F:81={10|06} → 4F:88=78 → … → 08:98=A6 → 4F:8B=78`.

В timing@4/@5 дополнительно между ними стоит `4F:8A=78`. Сохранённые byte offsets:

- DC ON/OFF: `08:98=02` packet1/offset0x0B; `4F:81` packet3/0x1F;
  `4F:88` packet4/0x28; `08:98=A6` packet36/0x1B8; `4F:8B` packet40/0x1E0.
- timing@4/@5: первые три точки совпадают; `4F:8A` packet19/0xBD;
  `08:98=A6` packet24/0xF0; `4F:8B` packet28/0x118.

Все пути/полные payload и offset — `transaction_skeletons` в JSON. Это новая
явная factorization совместно меняемых transaction controls. Слова «commit»,
«shadow bank», «scan scheduler» здесь **hypothesis**, не register definitions.
Совпадение 78 с decimal120 и 06 с six pulses не используется как семантика.

Ни одного writer в этом корпусе для `4F:80,C0,C1,C8,C9,D0,D1,D8,D9`, `07:EC`,
`23:C1` нет. Исторический short-read audit показывает, что C1/C9/D1 остаются06,
D9 остаётся10 при переходе `81:06→10`; это не доказанные aliases
(`ddic_regdump_20261107/readback_findings.md:32–46`). Полный stock timing
переход возвращал81 в06, а native DC возвращал10; fine train в OFF сохранялся
при обоих значениях (`readback_findings.md:48–82`).

**Содержательный открытый механизм:** 81 может выбирать исполняемый слот/режим
составной update-системы, тогда как наблюдаемые C/D поля — другие слоты либо
status. Это совместимо с архивом, но не поддержано больше, чем альтернативные
status/config значения. Минимум, превращающий его в candidate: target supplier
field map либо точный same-revision native command trace с известным изменением
emission timing и этим selector/update шаблоном. Простое ещё одно readback06/10
не даёт нового знания. Из имеющихся байтов нельзя безопасно вывести command к
C1/D1 либо «увеличить count». Текущий likelihood meaningful PWM improvement:
**unknown/непригоден для ранжирования как готовый hardware trial**.

## 3. Динамическая state variable: redraw не является доказанной latch semantics

Новая сверка host-timestamp chronology в
`dsi_stock_on_control_20261106/with_redraw/run.json` даёт:

- native ON transmission verified `21:33:03.348524Z`;
- единственный same-DBV replay3600 зафиксирован `21:33:03.630454Z`;
- pre-redraw optical hold длится7.000523s и заканчивается через7.357898s после replay;
- post-redraw hold начинается через14.796735s после replay;
- новый table не отправлялся, logged control-write list во время redraw пуст.

Это связывается с **прежним**, не вновь вычисленным наблюдением q93 ratio
до/после redraw1.0058686/0.3849304 (`dsi_coupled_9d_20261107/proposal.md:29–34`).
Такой результат обосновывает исследование frame-data/update зависимого состояния:
одна фиксация selector readback недостаточна для предсказания optical output.

Но архив не содержит matched no-redraw sham с такой же задержкой. Поэтому
однозначно назвать событие именно frame latch нельзя: elapsed-time response,
transient image content, pipeline/ISP response остаются альтернативами. Пустой
контрольный DSI logger не означает отсутствие pixel-data transfer. Равенство
финальной картинки не квалифицирует предшествующий pixel/scan history.

Самая дешёвая **последующая** проверка этого механизма — fixed-content one-frame
resend vs no-redraw sham с одинаковым elapsed time/DBV, optical waveform в
синхронном независимом временном канале. Она имеет новую переменную и не является
повтором использованного S0C1; всё равно требует новой scoped authorization.
При отсутствии эффекта от frame event при matched elapsed time latch-гипотеза
сужается/отвергается для того контекста. Она может улучшить delivery semantics,
но сама по себе не обещает PWM≥2000.

## 4. Отбор рычагов и границы

1. **A=0, D=1, C=1 selector/background interaction** — существующая конкретная
   программа, высокий information gain для D×C ветви; вероятность ≥2000 неизвестна,
   уверенность в наличном intervention высокая, физическая семантика низкая.
   Риск смешанного vendor state, rollback полный native OFF+DBV replay+redraw,
   не просто A9/9D=0E. Следующий опыт — прежняя точная stock→A0D1C1→stock серия,
   с заранее отделёнными optical/Hz критериями и только после consent.
2. **Frame-data/update gated activation** — физически проверяемая гипотеза lifecycle,
   подтверждены разные сохранённые optical classes после event; новая chronology
   вскрывает elapsed-time confound. Новый matched sham/event опыт нужен для latch
   attribution; частотный эффект unknown. Низкая нагрузка на command discovery,
   но новый hardware/camera scope, discomfort stop и полный stock rollback.
3. **Native transaction/4F slot selection** — source-backed envelope существует,
   boot/refresh/DC history меняет81; остальные «банки» пока только readback pattern.
   Новая запись в неизвестные поля не обоснована. Сначала semantic evidence о
   selection/commit и physical timing; без него expected information gain blind
   write низкий и риск неквалифицированный. Не рекомендуем hardware trial сейчас.

EC/C1 как markers полезны только после protocol-qualified reads и отделения
checksum/content/config альтернатив; это не frequency control. Уже закрытые
unsigned threshold, 4F81 literal pulse count, isolated mode90/page53/page63,
S0C1, stock source ready-CN-profile не переоткрывались.

## Verification and reproduction

`python artifacts/horizon_r3_20261108/agent_a_factorization.py` печатает результат
без записи. С `--output NEW_PATH` использует exclusive create, не перезаписывает
старое. Полный повтор совпал с сохранённым JSON. Новый parser побайтно согласуется
с существующим `06-tools/audit_pwm_archive.py:11–35` на всех1101 packet по
offset/page/opcode/payload/header; это проверка реальных входов, не только тесты
собственных предположений. Rank вычислен exact rational elimination, четыре
полных binary interpolants перечислены и проверены для всех восьми вершин.
Независимая проверка root в [root_offline_audit.json](root_offline_audit.json)
(разделы `candidate_identity` и `qualitative_design`) уже подтвердила байты кандидата,
rank 6/8 и четыре допустимых binary completions. Это проверка байтов и алгебры;
она не устраняет допущение сопоставимости исторических labels и состояний.

Исходные ELF, private kernel traces и original video в checkout отсутствуют;
их повторная binary/video проверка **не заявляется**. Анализ не требует новых
устаревших DDIC readers. Device state после последней сохранённой записи неизвестен.
