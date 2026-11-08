
# HORIZON — реальный PWM XT2611-1

## Актуальное возобновление 2026-11-08

Владелец новой миссией явно возобновил автономные эксперименты на Lenovo и A001, включая ADB/root, DSI, настройки, обычные reboot и съёмку. Исторические пауза/consumed approvals ниже не описывают действующий scope. Safeguards и проверки bootchain/flash сохраняются. Текущий краткий checkpoint: [pwm_resume_20261108.md](../artifacts/pwm_resume_20261108.md). R3 и физические>=2000Гц остаются нерешёнными.

## Цель и критерий завершения

Получить управляемый реальный OLED PWM на физическом Lenovo XT2611-1/PVT с
выбранным software-профилем BOE ILI97701A cmd_v4/ID `0xd2`; целевое значение —
не ниже **2000 Гц**, с приемлемым для владельца экраном. Постоянный
KernelSU-Next уже установлен и UID0 после reboot подтверждался. R1/R2 завершены;
R3 активна и не решена. Ни предполагаемые 720 Гц, ни отсутствие камерных полос
не являются выполнением численной цели.

## Операционное обновление 2026-11-08 — A0D1C1 возвращён в stock

Первое [разрешение](../artifacts/dsi_coupled_9d_20261107/authorization.json)
на одну серию `stock → A0D1C1 → stock` владелец затем уточнил отдельной
[командой для ручного просмотра](../artifacts/dsi_coupled_9d_20261107/owner_view/authorization.json):
включить **один раз** и **не возвращать stock автоматически перед паузой**.
[Фактический отчёт](../artifacts/dsi_coupled_9d_20261107/owner_view/run.json)
фиксирует stock→A0D1C1 и проверки, `owner_view_active=true`,
`stock_return_verified=false`, `pending_bytes_may_exist=false` **на момент ручного
просмотра**. Позднее владелец прямо попросил вернуть stock для live-проверки.
[Отдельный return](../artifacts/dsi_coupled_9d_20261107/owner_view/return/run.json)
завершён08:12:31 UTC: 75 заводских пакетов, A9/9D `0E/0E`,
`stock_return_verified=true`, `target_restored=true`, `owner_view_active=false`,
ESD `reg_read`, cleanup без ошибок; Android manual52/requested120/timeout30min
и native DBV3584 проверены при завершении. Следующий read-only DBV был3356
при Android52/power0/DC0; причина дрейфа **неизвестна**, дополнительных записей
во время live-проверки не делать. Повтор A0D1C1 не разрешён, flash/persistence
не выполнялись. Физические PWM≥2000Гц и комфорт не доказаны.

Вместо старой G54 владелец подключил Nothing A001/Galaga. Open Camera1.56.2
настроена rear Camera2: H264 720p без звука, 100µs/ISO6400, AE/AF/OIS/EIS OFF,
ручной фокус2.03874850, crop4080×3072. [Офлайн-сравнение сохранённой съёмки
A0D1C1 со stock](../artifacts/dsi_coupled_9d_20261107/owner_view/optical_compare.md)
не выявило крупного подавления fine-полосы, но stock A001 записан при DBV3584,
кандидат при3600 и позднее; это не равноусловный причинный контроль и не PWM Hz.
Владелец попросил зафиксировать результат и **остановиться**;
[актуальный handoff](../artifacts/dsi_coupled_9d_20261107/owner_view/plan.md)
содержит оба run-отчёта и ограничение на новые операции. Без нового решения
владельца не запускать DSI/return/reapply; панели уже возвращён stock.
Остальной текст ниже — история до ручного разрешения и фактического запуска;
его фразы «NOT AUTHORIZED/только offline/нет run» более не описывают текущий
статус. Актуальный checkpoint — [WORKSTATE.md](../WORKSTATE.md), R3 активна.

Done требует доказанного поведения физической панели и пригодного профиля,
оптического подтверждения в пределах реально доступных методов, сохранённого
безопасного возврата и правдивого статуса неизвестных. Не объявлять ровно 2000 Гц
доказанными на основании кода регистра, refresh, DBV, камеры или комфорта.

## Обязательная baseline-методика

**Подтверждённое улучшение фиксируется как новый экспериментальный baseline;
последующие кандидаты сравниваются с лучшим сохранённым baseline и stock-контролем.**
Не сбрасывать учтённое улучшение к исходному состоянию при каждой итерации.
Сохранять профили, точные условия, исходные данные и процедуру возврата; не
оставлять новые DSI-профили включёнными постоянно без отдельного решения.

Уменьшение полос/их амплитуды либо иное воспроизводимое улучшение — **валидный
промежуточный успех**, который надо документировать и использовать для следующего
шага. Оно само по себе не доказывает частоту и не отменяет цель ≥2000 Гц.
Измерительный эффект, созданный только экспозицией/геометрией камеры, записывается
как улучшение метода измерения, а не панели.

## Приоритеты владельца

- Предпочитать крупные, различимые, проверяемые изменения. Для предложения
  повысить частоту владелец просит шаг примерно в2–3 раза и запретил мелкие
  инкрементальные прибавки как не дающие видимого результата.
- Владелец сообщил о принятии риска повреждения панели, даже необратимого.
  Это разрешает рассматривать рискованные гипотезы, но не превращает неизвестное
  кодирование байтов в множитель частоты и не заменяет точное подтверждение новой
  составленной DSI-последовательности.
- После отрицательного результата отвергается или сужается конкретная гипотеза,
  не цель. Менять метод при застое: offline source/binary reverse, сигнал/данные,
  независимый оптический метод. Не повторять тот же опыт без новой переменной.
- Не останавливаться на HORIZON-переформулировках: продолжать до следующего
  falsifiable разрешённого шага или точного operation-specific confirmation gate.

## Зафиксированный лучший panel baseline (экспериментальный, не persistent)

**A9-only улучшает оптическую fine-компоненту в проверенном режиме.** В завершённой
серии `stock → A9-only → stock → 9D-only → stock` при DBV3600,120 Гц, DC OFF:

| Условие | q93 total image-component / adjacent stock |
|---|---:|
| Stock reference | 1.000 relative |
| A9-only (`23:A9=8E`, `24:9D=0E`) | **0.2264067** |
| 9D-only (`23:A9=0E`, `24:9D=8E`) | 1.0214238 |

Статус: `confirmed-on-target` для этих условий и камерной компоненты. Это лучший
зафиксированный panel experimental baseline: A9-only уменьшает измеренную q93
компоненту примерно на77.4%, широкая полоса остаётся. Это промежуточный успех,
не доказанная PWM depth/Hz, не профиль ≥2000 Гц и не включённая постоянно настройка.
Первичные данные, readback, методические оговорки и v2 correction:
`artifacts/dsi_selector_split_20261107/result.md` и
`artifacts/dsi_selector_split_20261107/analysis_spatial_v2.json`.
Разрешение на эти две одиночные пробы использовано; **не повторять**.

Измерительный baseline: stock-экспозиционный sweep при ISO1600 дал нормированные
q93 ratios `100/500/1000/1428.571/2000/100 us = 0.9766/0.8891/0.3403/0.0328/0.1725/1.0234`.
Это минимум с rebound при изменённой экспозиции; телефон/панель не изменялись.
Использовать как camera-response/integration evidence, не как панельное улучшение
или подтверждение 720/1440/2160 Гц. Детали: `artifacts/exposure_notch_20261107/supported/result.md`.

## Завершённый S0C1 и следующий offline candidate

`artifacts/dsi_coupled_on_20261107/proposal.md`: S0C1 — полный native ON с двумя
селекторными high-bytes, оставленными OFF. 875 байт/75 пакетов, 32 пакета/83 байта
от OFF. Candidate independently byte-validated, но это совокупный interaction
test, **не** source-backed ×2–3 frequency setter. Владелец отдельно подтвердил
конечный опыт stock→S0C1→stock и emergency ordinary reboot при неопределённой
очереди: `artifacts/dsi_coupled_on_20261107/authorization.json`,2026-11-07 09:41UTC.
Это разрешение на одну серию и её возврат, не на другие комбинации/повторы/flash.
Просьба об approval by default и принятие необратимого риска записаны в AGENTS.md
как позиция владельца; обязательные operation-specific gates сохранены.

Исполнитель и анализатор уже подготовлены в существующих
`06-tools/run_dsi_mode_trial.py` / `analyze_dsi_redraw.py` (`--coupled-on`).
Проверены14 тестов, синтаксис, отказ до device calls без точной авторизации и при
Python `-O`, байты кандидата и синтетические guards/decoder. Evidence:
`artifacts/dsi_coupled_on_20261107/runner_offline_validation.json`.
Серия завершена09:44UTC:1671frames,225packets/37callbacks/9reads, total q93
ratio0.936347949, прежний fine-train сохранился. По отдельному запросу владельца
профиль включался для ручного просмотра; владелец отклонил его как неприемлемый.
Возврат stock завершён09:58:08UTC: `owner_view/return/run.json` и `validation.json`
в том же каталоге. Исторический `owner_view/run.json` описывает handoff, не текущее
active-состояние. Обе операции завершены, разрешения использованы; не повторять.
Сравнение с A9 baseline — по сохранённым данным с оговоркой о разных съёмках,
не разрешение повторить A9 и не автоматическая замена лучшего baseline на stock.

Новая конкретная гипотеза: 9D может выбирать иной режим только с C1, когда A9
оставлен OFF. Подготовлен `artifacts/dsi_coupled_9d_20261107/proposal.md` —
**A0D1C1**, native ON с единственным OFF-A9.875bytes/75packets проверены двумя
парсерами, новая комбинация не совпадает с7 прежними кандидатами. Это не scalar
frequency increment и не доказанный ×2–3 setter. На момент подготовки
**не согласован/не отправлен**; старое разрешение не использовалось. Нынешнее
однократное согласие и предзапусковый блокер записаны в обновлении выше;
всякая *иная* новая DSI-серия требует отдельного точного подтверждения.

## Восстановление после перезапуска

Текущий checkpoint 2026-11-08: [WORKSTATE.md](../WORKSTATE.md) и
`artifacts/uefi_panel_recon_20261107/selection_followup.md` (ABL→`/chosen`
addendum). Эталонный MotoBootModule читает UEFI `DisplayPanelVer` и пишет
big-endian `mmi,panel_ver`; current Linux показывает это свойство, а не новый
DSI-read. Имя переменной само не доказывает её producer, значение `DC` или
физическую silicon revision: current bootloader/boot trace не проверялись.
Численная PWM≥2000Hz не доказана, A9-only baseline сохранён. Исторический
checkpoint предшествует отдельному согласию на A0D1C1: он ещё не запускался;
текущий предзапусковый блокер описан в операционном обновлении выше.

Новая проверяемая офлайн-ветка: [CN48 bootloader](../artifacts/cn_48_7_recon_20261107/result.md)
из того же публичного XT2611-1 ZIP range-извлечён с CRC; все9 BOE XML равны
GLOBAL64 эталону, DisplayDxe/BacklightDxe отличаются только CodeView path.
Отличающийся `MotoBootModule` проверен Ghidra excerpt: его узкий путь
`DisplayPanelVer`→`/chosen/mmi,panel_ver` совпадает с GLOBAL64, но другие
изменения и actual current boot execution не исключены. Нового готового BOE
high-PWM init нет; physical Hz и variable producer неизвестны, R3 active.
Следующий [bounded literal scan](../artifacts/uefi_panel_recon_20261107/selection_followup.md)
проверил116 UEFI `.efi` и1 ABL `.efi` CN48: имя `DisplayPanelVer` есть также
в `MotSolDxe`/`BacklightDxe`, но direct Ghidra xrefs к нему и соседнему
`DisplayPanelName` пусты. Это не доказательство producer/его отсутствия;
variable value, UEFI read и PWM Hz остаются unknown. Новых device действий нет.
Новый ограниченный [CN48 GetVariable error-path reverse](../artifacts/uefi_panel_recon_20261107/selection_followup.md):
после ошибочного чтения один helper возвращается, следующий диагностический
путь может как завершиться без возврата, так и вернуться в зависимости от
непроверенного состояния диагностики/форматирования (внутренняя переменная
переиспользуется; исходная маска не определяет финальную ветку сама по себе).
`panelVer=0` не доказан ни fallback, ни физическим DC-read;
R3 active, ничего не посылалось панели.
Новый [офлайн backlight trace](../artifacts/uefi_panel_recon_20261107/backlight_followup.md):
CN48 reference `BacklightDxe` вызывает Display Power Ctrl brightness method;
точная статическая привязка BOE v4 descriptor→config5 callback `0xbd74`
подтверждена, первоначально близкий `0xbbbc` ошибочно считался кандидатом
для v4 и исключён. `0xbd74` при type3 посылает DCS `0x51` brightness, BOE v4
XML type3/14bit без PMIC PWM-frequency. Это не обнаруженный OLED frequency
setter; фактическое UEFI исполнение/current target bootloader/PWM Hz unknown.
A0D1C1 exact confirmation прежняя, панели ничего не посылалось.

Новый [офлайн target-module check](../artifacts/cellid_serialization_20261108.md):
штатный `panelCellId_show` при вызове может отправить page1D, прочитать cell-ID
и вернуть page0; prefix/suffix в текущем `msm_drm.ko` находятся вне того же
panel mutex, который охватывает DC-команды. В прежних S0C1 logs page1D не
наблюдалась; фактическое конкурентное чтение, общий transport-lock и влияние
на PWM unknown. Cell-ID content не читался, аппаратных действий не было;
это не новый frequency setter и не разрешение A0D1C1.
Дополнительный [offline camera-timebase контроль](../artifacts/optical_readout_ambiguity_20261108.md):
у прежнего Pacman stock video720 строк, q93.43 и Camera2 skew15.047630ms;
неизвестный mapping activeArray4080×3072→encoded rows даёт в идеализированной
модели условные512/686/2185Hz при трёх разных span. Ни одно из этих чисел не
измеренная частота панели; прежняя exposure-notch гипотеза о~720 fine
component сохраняется, но не доказанный фундаментал. Независимое offline
review подтвердило арифметику и оговорки, телефоны не трогали.

Следующий [offline temporal-alias test](../artifacts/temporal_alias_20261108/result.md)
на двух сохранённых stock100-мкс окнах установил межкадровое движение q93.43
с alias~1.3 цикла/с, но при почти ровных30fps гипотетические частоты,
различающиеся на30 Гц, имеют одинаковую фазовую согласованность. Небольшой
encoded-PTS jitter второго окна не подтверждён как sensor timestamp, потому
не служит калибровкой физического Hz. R3 active, A9-only baseline прежний;
A0D1C1 остаётся без отдельной авторизации/запуска, hardware не трогали.
На [прежней panel-серии](../artifacts/temporal_alias_20261108/selector_followup.md)
тот же офлайн phase-test установил: A9-only подавляет q93 амплитуду, а
остаточная фаза плохо описывается одним наклоном всего окна; 9D-only наклон
сохраняется после stock-возврата.
Это уточняет пределы optical метода, не опровергает улучшение A9 и не
устанавливает Hz. Новых DSI-последовательностей не отправляли.
Новый [HEVC GOP-контроль](../artifacts/selector_codec_gop_20261108/result.md)
на тех же архивных пяти окнах: I-кадр каждые24 кадра; у moving broad
component I-frame discontinuity имеет ранг1/20/16/23/19 среди24 возможных
GOP-позиций. Строго воспроизводимая привязка broad к I-frame не обнаружена,
но P-frame кодирование, camera/ISP и физическая low-frequency envelope этим
не исключены. Нет нового panel improvement или измерения PWM Hz; A9 baseline и
точная граница согласия A0D1C1 прежние, устройств не касались.

Предыдущий DDIC checkpoint: `artifacts/ddic_response_framing_20261107/result.md`.
Новый для той ветки офлайн-анализ
38 912 сохранённых DDIC чтений проверил CRC и полный условный repeated-40 путь
через Ghidra brief/excerpts. У EC/C1 CRC-boundary не найден; предыдущие CRC
перекрываются при многопроходном чтении, а успешная длина 40 не доказывает
длину ответа панели. Статический setup привязан к helper для index0, actual
runtime index остаётся unknown; проверка другого индекса не стала PWM setter.
Legacy broad reader не запускать: условный короткий long-response может привести
к записи за запрошенный allocation extent, без доказательства live corruption.
Воспроизводитель/тест и независимые проверки указаны в отчёте.

Следующий офлайн методический контроль завершён:
`artifacts/exposure_notch_20261107/supported/envelope_check.md`. На тех же
6×75 stock кадрах при1428.571us fine spatial band остаётся~0.040 baseline,
broad~0.42–0.46, но его физическая природа/Hz не идентифицированы. Выдержка
лишь близка к общей кратной нулевой точке720/1440/2160Hz; одна камера-полоса
или её исчезновение не квалифицирует численную PWM. Независимое ревью и
поправка методического вывода завершены, A9 baseline не менялся; новые выдержки
не были включены в несогласованный A0D1C1 scope.
Дополнительный контроль сохранённого stock120→144→120→90→120 показал, что broad
spatial peak меняет период230.76→364.09→240.94px между тремя120 stages при
неизменном fine классе~93px. Это ограничение метода, а не вывод об отсутствии
физической low-frequency envelope или причине изменения пика.

Следующий офлайн target-specific source check —
`artifacts/uefi_panel_recon_20261107/result.md` (раздел follow-up 2026-11-08):
CN bootloader XML v2/v3/v4 совпадают с публичным DT для своих вариантов, GLOBAL
v4 с сохранённым выбранным DT. v3-only 41 bootstrap пакетов включают 24-строчную
page2F таблицу и page63:F1–F4, последние равны selected v4 native DC OFF.
Вариант v3 не равен выбранному v4; ни переносимого high-PWM профиля, ни
физических Hz из этой сверки нет. Reproducer и compact JSON в том же каталоге;
устройств офлайн-проверка не касалась.
Новый BOE UEFI selection reverse в
`artifacts/uefi_panel_recon_20261107/selection_followup.md`: reference PE
каталог BOE group0 содержит ID config `DA/D2`, version config `DC` и
условную карту version-byte0→v1,1→v2,2→v3,3…254→v4. Это **не** доказательство
boot-time выбора на текущем target: Android panelVer0 не отождествлён с UEFI
second-read байтом, текущий bootloader/UEFI trace не сняты. Отдельный
`selection_validate.py`/JSON воспроизводит каталог; Ghidra PE вход поддержан
узко, scoped29 unit tests/2 known-answer skipped и два независимых ревью PASS.
Следующая проверяемая offline гипотеза — Linux source для `panelVer`, без DSI.
Она проверена в том же selection follow-up: target `dsi_panel_parse_panel_cfg`
читает `/chosen/mmi,panel_ver(_s)` в 64-bit cached field (default all-ones),
`panelVer_show` только форматирует поле. Значение Android0 не равно fallback,
но не доказывает UEFI DC version0 или executed boot XML: текущая `/chosen`
property/boot-time trace не сохранены. Независимое code-level review прошло;
реальный PWM Hz не установлен.

Предыдущие brightness/LTPO и CN48 source/module проверки завершены в
`artifacts/brightness_policy_recon_20261107/result.md` и
`artifacts/cn_48_7_recon_20261107/result.md`; новые поиски тех же таблиц не
засчитывать как переход. **R3 active**: нужен новый причинный оптический эффект
или panel-specific emission mapping; A9-only остаётся лучшим промежуточным
baseline, не ≥2000 Hz. Следующий подготовленный hardware-тест — одна
stock→A0D1C1→stock серия; отдельное точное согласие и run отсутствуют, HORIZON
и общая доступность двух телефонов его не заменяют. Без такого согласия —
только offline работа, не выполнять составленные DSI-последовательности.

1. Прочитать `AGENTS.md`, `WORKSTATE.md`, этот файл и только ближайшие артефакты
   ниже. Не начинать заново уже выполненные/запрещённые эксперименты.
2. Последняя проверенная рабочая точка: 2026-11-07 09:58 UTC. R1/R2 done,
   R3 active. Последний target cleanup: UID0, Enforcing, DC0, logger0, ESD
   `reg_read`, native DBV828 (фактическое начальное значение той сессии), manual52,
   requested120, timeout30min, stay-on7. Pacman restored100us/ISO6400, manual focus
   9.11752701, AE/AF/OIS/EIS off, prepared/awake. Это состояние не равно исходной
   политике проекта: auto/no refresh override/5min/stay-on0 и исходное состояние
   Pacman ещё подлежат возврату при окончательной уборке всей сессии. Повторно
   проверить transports/identity до любого device action.
3. Последние substantive results:
   - `artifacts/stock_base_rates_20261107/result.md`: stock120/144/90 optical test;
     нет PWM Hz conversion.
   - `artifacts/exposure_notch_20261107/supported/result.md`: camera integration
     minimum/rebound; это camera-only.
   - `artifacts/em_field_recon_20261106.md`: offline ILI97701A v0/v1 selector
     evolution; понятного EM count/period multiplier не найдено.
   - `artifacts/dsi_coupled_on_20261107/result.md`: S0C1 executed/rejected/stock returned;
     optical/phase + conditional A9 threshold model checks, no physical-Hz claim.
4. Последние проверки: `OPENBLAS_NUM_THREADS=2 python3 -m unittest discover -s
   06-tools -p 'test_*.py' -v` —16 tests passed (14 before the hardware trials;
   added saved-native-DBV and separate A0D1C1 scope validation); py_compile relevant tools;
   5939-frame input-timebase re-decode is bit-identical to original profile cache;
   S0C1 native/optical/return validated; new A0D1C1 offline-only byte validation.
   No flash/reboot/persistent display change.
5. Продолжить новый falsifiable offline reverse или exact-approved experiment.
   При любом воспроизводимом panel improvement обновить experimental baseline в
   этом файле и WORKSTATE до выбора следующего шага; сохранять stock контроль.
   Сохранять full logs/raw video; не использовать отсутствие полос как exact-Hz
   proof. Не закрывать R3 после промежуточного успеха или отрицательного кандидата.

## Source of truth

Checkpoint после restart, 2026-11-07: OpenCode service PID1404379→1407592,
API healthy, та же сессия продолжена; телефон не перезагружался. Новый offline
разбор `artifacts/runtime_pwm_recon_20261107/result.md` доказал, что найденный
Linux PWM API обслуживает type0, а выбранная BOE использует DCS/type2. DC map0/1
не содержит множителя; DC2/3 clamp→1. Не повторять этот закрытый поиск как новую
гипотезу. A9-only baseline сохранён, R3 active; последующий S0C1 завершён выше.

Новый source lead: `artifacts/community_pwm_followup_20261107.md` — внешний
Android17 build **AI71WWH.15-43**,2.59GB, подтверждён просмотром опубликованного
скриншота (`reported`, не target install). В проверенных mirror indexes/точных
display tag prefixes пакета/source нет. Root-read существующего OTA-кэша цели
успешен, но таблицы версий/истории пусты; URL не найден. OTA polling/download/install
не запускались. Raw OTA XML/DB содержат credentials: оставлены только в private
cache0600, не публиковать. Next firmware diff требует самого пакета/source;
Это не аппаратная невозможность. Новый `artifacts/ota_metadata_protocol_20261107.md`
прослеживает CN reference APK: device-specific metadata check/resources path,
не найденный анонимный каталог по build ID. Host-only запрос технически возможен,
но applicability/auth/registration/server side effects не проверены. Никаких
идентификаторов или credentials не отправляли, OTA requests не делали.

Следующий offline шаг выполнен: `artifacts/init_payload_recon_20261107/result.md`.
Длинный07:81/FE блок во всех8 init-массивах побайтно сопоставлен с native DSC PPS;
page1E и общий2D хвост совпали с source-labelled LHBM и1Hz transition/DBV dimming.
Готового EM count/period ×2–3 в этих блоках не найдено; это не общий no-go.
Этот init-разбор сам не отправлял команд; последующий S0C1 описан выше.

Подсказка владельца о полосах/биениях/выдержке сохранена в
`artifacts/owner_camera_hint_20261107.md` как методика, не target calibration.
Неподвижные полосы сохранены; дополнительно пересчитан старый native-ON cache
без temporal demeaning (`artifacts/optical_repair_20261107/native_on_cached_spatial_v2.json`):
361frame, after-redraw total ratio0.3849304, qualitative вывод прежний.

Текущий статус/датированные evidence — `WORKSTATE.md`; operation boundaries —
`AGENTS.md` и operation-specific proposal; panel/profile/firmware facts —
`artifacts/panel_identity.md`, `artifacts/source_inventory.md`,
`artifacts/em_field_recon_20261106.md`, selector/exposure/base-rate results.
Не хешировать рутинно отчёты.
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      
