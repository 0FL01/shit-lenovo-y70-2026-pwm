# Возобновление R3 — 2026-11-08

Checkpoint 2026-11-08, **FD byte observations:01 отказ локализован и owned remnants очищены;02 owner-shell путь ограниченно подтверждён.**

- [Probe01](android_fd_byte_microprobe_20261108_01/result.md): 23:22:43.226735 UTC STOP/rc90, stdout0/stderr48 B, external cat self-FD ENOENT. Independent replay9events/342 B. Read-only inspection22events/568 B выявила ровно пять owned files и первый cat failure; exact cleanup24events/568 B завершена23:27:21.906322 UTC, owner last+rmdir и независимое отсутствие. Failed result сохранён; CLOEXEC не доказан.
- [Probe02](android_fd_byte_microprobe_20261108_02/result.md): latest limited physical action завершён23:29:56.914565 UTC, independent replay13events/395 B PASS. Explicit owner /proc/$$/fd/8 сохраняет unlinked LF1/LF+NUL2; substitution теряет оба без diagnostics. Probe stdout54 B/rc0/stderr0; host elapsed0.769395562 s, whole guarded run9.028409 s, не bounds. Independent own absence/sameboot/mutexabsent/Enforcing; host7 и acquisition8 normal/-O PASS.
- Старый validate_capture.sh использует /proc/self/fd/8 только builtin -f/-s, не external cat.01 не доказывает его несовместимость или необходимость patch;02 не доказывает full wrapper/root lifecycle/all-failure cleanup/batch/clock/PWM. Qualified runtime13 unchanged. Camera только identity; без DSI/settings/traces/reboot; current brightness/restore не измерены.
- Следующий milestone: небольшой fixed non-DSI synthetic acquisition/receipt root↔shell probe под offline construction, не generic57 batch. Unknown14 disabled;37/45/8/60/overall600 сохранены. Последний experimental DSI timedstock03 19:07:07.888880 UTC, native828 restored тогда; PWM>=2000 Hz не доказаны. Предыдущий checkpoint опубликован и remote verified в2bb1f9013677e6ce305f5a858bd19c2cfaba463a; текущая запись не утверждает публикацию.


Checkpoint 2026-11-08, **portability bundle независимо проверен на host; read-only Android inventory завершён, полный batch HOLD.**

- [Независимый review](../06-tools/android_validator_portability/independent-review.md): 57 shell cases + 20 checks normal/-O, exact104-file rebuild, runtime13 unchanged; manifest d12695ad3e0701e50dac38c27fe7bbc8e03c021230619c932dd4cd4825417c67. Superseded historical fixtures/results сохранены, текущие executable/manifest/results bytes не изменены. Последний опубликованный checkpoint: 2db5ae1691c205903823b13c932fb0179aafe446; эта запись ещё не утверждает публикацию.
- **Последнее physical action теперь limited timeout, не DSI:** [результат](android_timeout_microprobe_20261108_01/result.md) завершён 23:14:03.907659 UTC, один запуск. Независимый saved-evidence replay PASS: 13 sequential events /708 B, timeout124 при wrapper0, отдельный own-PID proc-read NOT_VISIBLE_OBSERVATION_ONLY. Exact commands/events/streams сохранены приватно; preflight/binding flags опираются на frozen source + lead record, отдельный raw host preflight transcript отсутствует. Whole preflight sequence10.013545 s; timeout event1.5742278120014817 s, proc-read0.5673554780660197 s, не universal bounds.
- Acquisition8 и microprobe5 host tests normal/-O независимо PASS; deadline проверяется на каждом recv/exit, cap до payload; retained partials только complete frames. Host deadline не remote cancellation. Boot unchanged, mutex absent, identity/root/module/panel/Enforcing совпали; camera только3getprops. Нет device files/settings/DSI/traces/reboot; brightness/current restore не измерены. Full57 HOLD, P85=14 disabled, PWM>=2000 Hz не доказаны. Последний experimental DSI всё ещё timedstock03 19:07:07.888880 UTC с восстановлением native828 тогда.
- [Inventory](android_portability_inventory_20261108_01/result.md): 27 read-only calls / 4514 B, 22:35:54.674177–22:36:11.366415 UTC; fresh identity/root/module/BOE-v4/Enforcing, unchanged boot и absent mutex before/after. Device files/locks/settings/camera/traces/DSI/signals/reboot не менялись. UID2000 paths /system/bin; timeout --help rc125 unsupported-or-unknown, limits unlimited, units unknown. Raw consistency совпала; raw alone не доказывает command text/rc/order/guarded acquisition, полный inline script/log не сохранён.
- Последний experimental DSI: timedstock03, завершён 19:07:07.888880 UTC с восстановлением исходного native828 тогда. Новый inventory не измерял brightness/current restore. Full57 Android batch остаётся HOLD: whole lifetime, process reconciliation, storage и owned cleanup не квалифицированы. Продолжение: отдельно reviewed finite primitives, не full batch; первый fixed sleep2 / timeout1 / -k1 теперь завершён с ограниченным результатом выше.
- Unknown P85=14 disabled, 37/45/8/60 и overall600 не ослаблены; физические >=2000 Hz не доказаны. Никакого live-runtime изменения этим checkpoint нет.

## Предыдущий resume (исторический контекст)

Статус: **R3 активна; физические PWM >=2000 Гц не доказаны.**

Завершена [инертная модель stock-only sequence](../06-tools/offline_local_sequence_model/README.md)
по [согласованному design](p85_local_sequencer_integration_design_20261108.md):
normal/-O по 927 synthetic subcases, независимые 116 дополнительных проверок.
Модель не выполняет shell, ADB или children. Она разделяет normal/exploratory/degraded
исходы, camera ACK/hold, immutable receipts, incident-bound recovery/cleanup и два
watchdog lifecycle. Найденные late-ACK, pre-start quiet и stale-proof ошибки закрыты.

[Отдельные STATE_ONLY и GUARD_TIMING](../06-tools/offline_local_snapshot_spike/README.md)
прошли normal/-O по 646 случаев, повторены lead и reviewer. Это snapshot content,
не acquisition, ESD, ownership или clock proof. Bootstrap/final-cleanup utility
diagnostics пока имеют явно ограниченный trusted NUL-free text контракт.

Ранее опубликованные [interval](../06-tools/offline_local_interval_spike/README.md)
и [byte-envelope](../06-tools/offline_local_envelope_spike/README.md) компоненты
остаются bounded offline feasibility. Host decode max 0.706 с не является Android
bound. В старом [capture/state spike](../06-tools/offline_local_validator_spike/README.md)
новые tests нашли leading-zero FULL-state false accept, потерю metadata producer
status/diagnostics и escape decoding trusted arguments. Corrective revision теперь
прошла bounded independent review: targeted14 normal/-O, 283 дополнительных
identity/argument cases и binary-diagnostic/cleanup injections. Expected identity
поступает через raw ENVIRON; nonce/kind проверяются до AWK decoding. Metadata и
cleanup сохраняют rc и каждый stderr byte. Это не universal subset proof; новые
Linux/proc FD assumptions ещё не квалифицированы на Android. Ни одна версия
этих компонентов не запускалась на телефонах и не встроена в controller.

Следующий шаг: независимо проверить
[ограниченный Android userspace portability probe](android_validator_portability_plan_20261108.md)
на synthetic files. Затем отдельно нужны реальные source/ownership/sealing,
durable ledger, clock-origin/rate и max-cap cost gates. Новый физический тест пока
не объявлен готовым. Unknown14 выключен; ограничения 37/45/8/60 и overall600,
qualified runtime sources и устройства после timed03 не менялись.
[Joint alias/exposure design](joint_alias_exposure_design_20261108.md) объясняет,
почему неквалифицированный sensor alias и 2160-гармоника не доказывают PWM-фундаментал.

Последние физические опыты: [три timed factory-15 rehearsal](p85_timed_stock_qualification_20261108.md)
завершены с независимым hardware и ограниченным optical PASS, собственным
native 828/settings/ESD восстановлением и G около 31–32 с. Conservative
all-phase-max timing всё ещё не проходит 45 с с reserve/J. Unknown 14 выключен;
интеграция проверенных offline-компонент ещё предстоит, без расширения
временных ограничений или заявления о PWM Hz.

Предыдущий checkpoint: [batched stock-only 01](p85_batch_stock_a001_20261108_01/hardware_result.md)
завершён 18:18:28 UTC с независимым hardware replay PASS и восстановлением
собственного исходного native DBV 828. [Оптика](p85_batch_stock_a001_20261108_01/optical_result.md)
подтверждает fine/mean diagnostic pass, но не полную waveform equivalence.
[Timing audit](p85_batched_latency_result_20261108.md) всё ещё не допускает
неизвестный 14 в 45 с с резервом 8 с. После него были выполнены три timed
stock-only серии выше; ограничения 45/60 с сохраняются.

Владелец новым заданием «Dots Mission: Lenovo Legion Y70 — Hardware PWM Control»
возобновил работу и разрешил автономные ADB/root, DSI, настройки, обычные
перезагрузки и съёмку на обоих исследовательских устройствах. Историческая
пауза и использованные разовые разрешения не запрещают новые опыты в этом
обновлённом scope. Проверки совместимости/восстановления для bootchain/flash
сохраняются. В этом цикле bootchain и разделы не изменялись.

## Проверено на физических устройствах

- Приватный ADB tunnel: служба активна, host protocol 41, версии клиентов
  nc-lab и USB-хоста совпадают. Цель и камера идентифицированы независимо.
- Lenovo: XT2611-1/avr, W3WWS36.65-64-4-1, slot_b, UID0, Enforcing,
  boe_ili97701A_682_1440x3168_dsc_cmd_v4, panelDC0. В начале native DBV828
  при Android brightness98/manual; старые 3584/3600 не являются live значением.
- Nothing A001/Galaga: Open Camera, rear Camera2, 100us/ISO6400, focus
  2.03874850, AE/AF/OIS/EIS OFF. Одна короткая камера-only запись завершена.
  Два снимка метаданных во время записи показали продвижение на78 кадров и
  2.599969 секунды; preview skew15.596307ms отличается от recording15.047630ms.
  Это метаданные режима, не калибровка физической частоты панели.
- Краткая штатная запись brightness3600 для осмотра кадра вернула исходный
  native828. Никакого нового экспериментального DSI-профиля при ней не было.
- Обычная перезагрузка Lenovo 14:18:23–14:19:09 UTC прошла через текущий
  туннель: boot_completed1, прежние модель/build/slot, UID0, Enforcing и
  panelDC0 подтверждены. Boot/DTBO/AVB не записывались. Это проверяет обычный
  recovery-путь, но не гарантирует восстановление зависшего ядра/повреждённой панели.

## Исходный план цикла (первые два пункта завершены)

1. Уточнить framing трёхбайтового ответа23:C1 и сравнить stock90/120/144.
   Архивные 00 00 65 /00 00 55 допускают гипотезу internal-base emission count,
   но третий байт legacy40-byte read не квалифицирован. Новая проба должна
   захватить DSI header/WC/count; неизвестныйC1 не записывается.
2. Равноусловная stock→A9-only→stock серия на A001 с проверенным новым кадром,
   readback до/после оптического окна и общим непрерывным видео. Единственное
   различие кандидата: штатный23:A9 0E→8E. Это проверка поведения лучшего
   промежуточного baseline, не заранее объявленный high-PWM режим.
3. Подготовить camera exposure sweep вокруг ожидаемых integration notches,
   сохраняя реальные достигнутые выдержки и неизменные ISO/geometry. Не
   использовать preview metadata вместо recording и не выдавать q93 заHz.

Сырые camera/UI/kernel данные и идентификаторы остаются в приватном кеше.
Две выполнявшиеся пустые grep/glob проверки завершились ненулевым кодом;
это ошибки формата наблюдения, не потеря устройства. Новые исследовательские
утилиты тестируются офлайн и проходят независимый review перед DSI.

## Полученные результаты

### Равноусловная A9 серия

14:26–14:30 UTC: [stock → A9-only → stock](a9_a001_20261108_01/run.json),
по 75 точных пакетов, DBV3600/120 Гц. Новый кадр, отсутствие посторонних DSI
во время redraw/hold и селекторы/DBV до и после hold проверены. Stock,
настройки, native828 и ESD reg_read восстановлены, watchdog снят, камера
остановлена, собственный mutex освобождён; ошибок cleanup нет.

[Оптический результат](a9_a001_20261108_01/optical_result.md): у новой камеры
период stock fine-компоненты около 50.57 строк, а не исторические 93 строки.
Основное окно из 90 кадров даёт отношение A9/соседний stock **0.262658**
(снижение нормированной image-code компоненты на 73.7%); два соседних ROI
дают 0.262968/0.264988. Возврат stock отличается от начала на 0.158%.
Широкая структура остаётся; диагностическая broad-компонента в основном ROI
увеличилась примерно в 1.43 раза, с существенной зависимостью от ROI/окна.
Это воспроизведённое аппаратное изменение, но не доказательство улучшения
всего flicker-сигнала, более высокой частоты или >=2000 Гц.

### Первый квалифицированный C1 payload

[Свежие чтения](c1_live_20261108/stock_sweep.json) ограничены тремя байтами.
Во всех успешных пробах captured header `1c 03 00 16`, WC3/ECC, raw count9,
normalized count9, scratch16 и single receive подтверждены. При DBV3600:

- software90 → `00 00 80`;
- software144 → `00 00 50`;
- software120 → `00 00 60`, включая возврат;
- при DBV3646/software120 → `00 00 10`.

Старшие полубайты дают условные 8×90 = 5×144 = 6×120 = 720. Предсказание
восьмёрки при 90 подтвердилось и первоначально усилило emission-count гипотезу.
Последующая карта яркости ниже ограничила её: считать C1 общим счётчиком
импульсов/частоты нельзя. Назначение C1, его writable-статус и физические PWM Hz
остаются неизвестны. Ни одного C1 write не было. Исходные refresh120/native828
восстановлены; последующий опыт под A9 завершён и описан ниже.

### Исправленная проверка ESD

Первый C1 precheck остановился **до** register query: target debugfs writer
сравнивает токены с обязательным LF, а прежний helper отправлял bare token.
Новая проверка readback заметила молчаливый no-op. Состояние reg_read и
успешный page0 cleanup подтверждены независимо, собственные probes/mutex
убраны, brightness восстановлен. [Запись восстановления](c1_live_20261108/guard_failure_recovery.json).
Setter и restore теперь передают LF и проверяют фактические INITIAL/ACTIVE/RESTORED
режимы. Успешные C1 пробы уже выполнены с этим исправлением. Историческая
строка ESD_RESTORED не доказывает, что временная ESD isolation действительно
включалась; сегодня A9 trace/readback подтверждены, но старая isolation не заявляется.

### Остановленные A9+C1 серии

В сериях [02](a9_c1_a001_20261108_02/run.json) и
[03](a9_c1_a001_20261108_03/run.json) safeguards остановили выполнение до
первого A9 candidate (`candidate_attempts=0`). Обычный recovery reboot
в каждом случае подтвердил прежние build/root/Enforcing и stock; native DBV 828,
настройки, остановка камеры и освобождение собственного mutex проверены,
ошибок cleanup нет. Это не результаты A9+C1.

В 02 stock C1 вернул квалифицированные `00 00 60`, но main trace дополнительно
увидел штатный ESD status read после восстановления `reg_read`. Для этого
точного callsite/task/rc вне окна C1 добавлена отдельная классификация,
с отрицательными тестами для остальных событий. В 03 C1 не читался:
проверка точного stock packet stream заметила дополнительные native DSI
пакеты. Причина исследуется офлайн; guard не отключён.

### Ограничение гипотезы 23:85

Независимая проверка всех восьми selected-v4 init arrays нашла единственный
`23:85=15` на packet index 23, offset 310, до sleep-out/display-on. Stock DC
ON/OFF и timing-switch его не восстанавливают. Ни divider-семантика, ни
runtime-latching, ни безопасность альтернативного значения не установлены.
Предположение о low-nibble divider `(N+1)` остаётся спекулятивным.
Никакого write в 23:85 не выполнено. Даже совпавший readback и обычный reboot
не гарантируют восстановления повреждённого DDIC.

Одна новая проба при исходном DBV 828 / software 120 использовала maximum
request 3 и scratch 16, чтобы не применять опасный четырёхбайтовый scratch
request 1. Ожидавший short1 валидатор корректно отверг фактический long3.
[Отдельный offline-разбор сохранённого ответа](p85_live_20261108/stock828_long3_reanalysis.json)
подтвердил payload `15 00 00`, header `1c 03 00 16`, WC 3 / ECC,
raw и normalized count 9, единственный receive и точные return/cleanup.
Это валидный префикс 15, но не доказательство ширины регистра, значения нулей,
тождественности read/write planes или frequency semantics. Payload CRC не захвачен.
Исходная rejected-attempt запись сохранена; повторного read не было.
[Независимый postcheck](p85_live_20261108/stock828_postcheck.json) подтвердил
UID0, Enforcing, native 828, DC0 и отсутствие собственного mutex/trace/temp.

### Native timing и новая защита отправки

Trial03 содержал реальные native timing@2 (90 Hz) и timing@7
(peak 120 / actual 1 Hz) команды между deferred blocks. Это не stale prefix.
Следовательно, Android min/max 120 и software peak 120 не доказывают native
actual 120. Численная C1 закономерность относится к гипотезе внутренней базы,
а не измеренной scanout/PWM частоте.

Теперь те же пять блоков отправляются одним bounded device-shell с проверкой
реального pending/length/flags/returns после каждого блока. Перед опытом
квалифицируется тихий интервал и один из pinned native 120-family режимов:
timing@0 actual 120 или timing@7 actual 1; во всех фазах требуется тот же режим.
Это сокращает окно гонки, но не создаёт compositor mutex. Любое замеченное
вмешательство по-прежнему вызывает abort и штатное recovery; guard 75 пакетов
не ослаблен. Независимый review и 91 offline tests (2 skips) пройдены.
Серия 04 остановлена до любых таблиц: после setup logger включался слишком
поздно, и в retained log не было native anchor. Никаких candidate attempts;
stock/settings/native 828 и cleanup восстановлены без reboot.

[Отдельная stock-only квалификация](native_anchor_qualification_20261108.json)
затем проверила исправленный порядок: logger включён до обычных настроек
90 → 120. Свежие последние driver anchors показали actual 90/group 5,
затем actual 120/group 3. Ожидаемые переходные OEM состояния сохранены в отчёте,
а не выданы за стабильный режим. Исходные min/peak 120.0, native 828 и logger 0
восстановлены; mutex снят. Candidate table, C1 и camera при этой проверке
не использовались. Этот путь добавляется в setup до очередного A9+C1 опыта.


### Завершённая A9+C1 серия 06

[Новый причинный результат](a9_c1_a001_20261108_06/c1_result.md): при DBV 3600
и неизменном native actual 120/group 3 квалифицированный C1 payload проходит
`00 00 60 → 00 00 10 → 00 00 60` на stock → A9-only → stock.
Это обратимая связь register status с изменением изображения, не доказанные
one-count branch или повышение несущей. Физические Hz по-прежнему неизвестны.
Все три программы по 75 пакетов, selector/DBV
checks, holds и полный stock/settings/camera/watchdog/mutex cleanup пройдены.
Серия 05 до этого остановилась до таблиц из-за повторных markers в retained
dmesg. Теперь все markers привязаны к уникальному experiment ID; логи не очищались.

### Stock C1 map и поправка к интерпретации

[Завершённая stock-серия](stock_c1_20261108_01/run.json) при неизменном native
actual 120/group 3 дала DBV 828/460/2048/3000/3600/828 и соответственно C1
`00 02 B3 / 00 02 C0 / 00 02 26 / 00 01 30 / 00 00 60 / 00 02 B3`.
Все шесть framing/return gates прошли; повтор 828 совпал с началом.
Исходные настройки, native 828 и logger восстановлены до снятия watchdog
и mutex. Камера не использовалась, неизвестные значения регистров не писались.
460 — selected DT minimum; точки ниже него не выдаются за обычную stock-яркость.

Raw C1 сильно зависит от DBV, а младшие полубайты уже не всегда нулевые.
Универсальная расшифровка `C1 >> 4 = pulse count` не установлена. Возможные
duty/off-time/width/status модели также не доказаны. Специальная near-threshold
закономерность 96/128/80 остаётся фактом, но не даёт общего frequency counter.
Нельзя умножать новые числа на refresh и объявлять достижение >=2000 Гц.

[Старый короткий DBV828 ролик](qualification_dbv828_20261108/result.md) содержит
различимый fine-период около 50.6 camera rows, совпадающий по разрешению анализа
со stock3600. Это cross-session наблюдение без одновременного C1/DBV в ролике,
поэтому оно ограничивает простую raw-C1-proportional модель, а не доказывает
одинаковую физическую частоту. [Повторный анализ архива refresh sweep](stock_base_rates_20261107/reuse_index_20261108.md)
показывает, что 120/144/90 уже проверены при одной камере и записи; sampled
alias остаётся около 1.3 cycles/s. Это не универсальное различение fixed-count
и fixed-carrier: N, кратное пяти, и другие гармонические модели остаются
неразличимы при этих номинальных частотах. Лишнюю такую же съёмку не повторяем.

Новый stock reader проверяет реальные callback/controller returns перед каждой
следующей DSI-командой. Точный debugfs TX writer может вернуть user bytecount
при неуспешном native callback; одного shell rc недостаточно. Старые успешные
framed captures имеют правильные фактические returns и не аннулируются.

Следующая отдельная разработка — ограниченный runtime 23:85 `15 → 14 → 15`
с same-value sham 15, общей видеозаписью и коротким независимым watchdog.
До candidate нужна stock-only квалификация нового runner. Ни runtime-latching,
ни частотная семантика, ни безопасность альтернативного бита не установлены.
Unknown-value 85 write пока не выполнялся; Android-интерфейс для неизвестного
профиля не выдаётся за готовое решение.

### Первая P85 stock-only квалификация: отказ до writer packet

[Серия 01](p85_stock_a001_20261108_01/result.md) начала same-video baseline/sham15/
return15 протокол без неизвестного 14. Baseline при DBV 3600/native actual 120
прошёл с P85 `15 00 00` и C1 `00 00 60`. Первый writer gate затем передал слишком
большой retained dmesg как один argv внешнему Android printf. Отказ произошёл
до первой команды writer: trace пуст, все пять probe counters нулевые.
Таким образом, same-value85 write ещё не live-qualified, а 14 не отправлялся.

Guard выбрал один same-target reboot вместо дальнейшего DSI. Новая загрузка,
identity/root/Enforcing/DC0, исходные settings/native 828/logger, остановка камеры,
watchdog disarm и mutex release подтверждены. Исходная failed запись сохранена.
Raw video/screenshots не публикуются и не анализируются как завершённая
stock/sham/return серия.

Исправление [изолированного runner](p85_guarded_runner_20261108.md) использует
owned bounded files и прямые awk/cmp вместо неограниченных argv. Независимые
тесты воспроизводят legacy E2BIG настоящим external printf с 2 MiB журнала,
проверяют exact gates и fail-closed oversized/read-error paths. Логи не очищались.
Перед новым выполнением relevant executable sources должны быть committed/clean;
HEAD и десять Git blob IDs фиксируются в отчёте для воспроизводимости.

Measured baseline занял 34.389 с, поэтому нынешний conservative candidate timing
gate не проходит. Лимиты 45/60 с не увеличивались. Следующая новая квалификация
использует только заводской 15; неизвестный 14 требует отдельного успешного
stock video review и допустимого измеренного timing budget. Аппаратная frequency
семантика 85 и физические >=2000 Гц остаются unknown.

### P85 setup 02–03 и строгое ожидание камеры

[02](p85_stock_a001_20261108_02/result.md) остановилась до native anchor из-за
post-reboot keyguard. Штатный OS dismiss затем прошёл, две проверки показали
ON/AWAKE/unlocked; credentials и security settings не изменялись.
[03](p85_stock_a001_20261108_03/result.md) начала запись, но первый dump ещё
содержал PREVIEW result, старый skew и нулевые encoder frames. Guard остановил
выполнение до baseline/P85. В обеих попытках исходные settings/logger,
watchdog/mutex и, для03, остановка камеры проверены без reboot;85 writes нет.
Saved original native DBV был828 в02, но6438 в03 при том же Android98/manual.
В03 восстановлены именно6438; первоначальная ссылка на828 была ошибкой описания.
Причина изменения native уровня между попытками не установлена.

Новый startup helper сначала ждёт2с после единственного start-tap. Затем
допускает максимум5 read-only dumps в8с, две последовательные fully-valid
recording snapshots с progress и одним session. Только ID mismatch при уже
правильных остальных полях может дать retry. Состояние из03 остаётся fatal;
PREVIEW/old skew/zero encoder frames не принимаются и не скрываются ожиданием.
Startup-only alarm прерывает зависший transport, не меняя shared ADB или
candidate budget; handler/timer восстанавливаются до внешнего cleanup.
Нужны committed/clean source и новая stock-only квалификация, не повтор failed ID.

### P85 stock-only04: transport PASS, ограниченная optical проверка

[Hardware04](p85_stock_a001_20261108_04/hardware_result.md) завершён без ошибок
и reboot: baseline → sham15 → return15, две точные трёхпакетные записи и шесть
framed reads. При DBV3600/native actual120/group3 все P85=`15 00 00`, C1=`00 00 60`.
Независимый raw replay пройден. Это квалифицирует передачу same-value15,
но не устанавливает frequency semantics или read/write-plane identity.

На завершении восстановлены сохранённые исходные значения, включая native
DBV6438 при Android98/manual, а не828 из более ранних попыток. Все settings,
logger/ESD/root/Enforcing/DC0, camera stop и watchdog/mutex cleanup проверены.
Ошибочное описание828 для03–04 исправлено; данные run.json и фактическое
восстановление не менялись.

[Оптика04](p85_stock_a001_20261108_04/optical_result.md) повторно декодирована и
независимо проверена: main fixed fine ratio sham1.0000529, return1.0149156,
fine period около50.568 camera rows. Это воспроизводимый fine-контроль и
стабильная средняя яркость, но не полное waveform equivalence: return full-spectrum
L2 отличается около9.6–10%, broad оценка зависит от ROI/detrend. Поэтому
безусловный p85-stock-review-v1 и разрешение14 не создавались. PWM Hz unknown.

[Измеренные задержки и план](p85_latency_plan_20261108.md) требуют уменьшить
host roundtrips, сохранив все guards и неизменные child scripts. Новый batching
adapter сначала будет stock-only; его source/transport/timing/optical qualification
нельзя наследовать от04. Лимиты45с/60с не увеличены, неизвестных85 values не было.
