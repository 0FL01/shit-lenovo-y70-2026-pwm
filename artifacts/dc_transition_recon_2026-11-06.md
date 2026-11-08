# ILI97701A: DC-переход, EM-гипотеза и следующий опыт

Дата: 2026-11-06. Наводку передал владелец, указав внешнюю GPT 6 Pro как источник
поиска (`reported`). Первоисточники ниже проверены агентом; вывод модели сам по себе
не является доказательством для телефона. Новых DSI-записей при этом анализе нет.

## Что уже привязано к цели

- `confirmed-on-target`: live-профиль **BOE ILI97701A `cmd_v4`**, `panelId=0xd2`,
  `panelVer=0`; boot selector, sysfs и выбранный DT согласованы:
  [panel_identity.md](panel_identity.md), [снимок](panel_live_20261106.json).
  `0xd2` не адрес регистра DDIC и не selector отладочного `panel_para_by_id`.
  Физическая silicon revision независимо не декодирована.
- [Live DT](device_tree/selected_boe_v4_acquisition.json): DC ON/OFF по **875 B / 75 пакетов**,
  побайтно равны обоим архивным v4. Все 53 сопоставленных command arrays равны GLOBAL
  reference; 12 init/timing arrays отличаются от CN. Это свойства DT, **не трасса
  окончательно отправленных пакетов**: [сравнение](device_tree/selected_boe_v4_comparison.json).
  Повторный полный regional diff понижен в приоритете, но эти 12 различий не отброшены.
- `confirmed-on-target`: live overlay задаёт `bl_ctrl_dcs`, min **460**, max **16180**,
  default **7001**, присутствуют `bl-inverted-dbv` и `bl-is-exponent`.
  Базовые значения DTS не заменяют итоговый live overlay. Процент Android не равен
  переданному DBV; смысл преобразований проверять в фактическом driver path.

## Проверенные первоисточники — `reported`, не доказательство режима цели

1. [ITH Mobile](https://www.ilitekholding.com/en/product/Mobile): **IL97701A**,
   AMOLED DDIC, до 1440×3360, MIPI D-PHY/C-PHY, 30-bit, LTPO. Искать оба написания
   `IL97701A` и Motorola `ILI97701A`. Карточка не содержит register map/PWM-формулы
   и не удостоверяет физическую ревизию нашего экземпляра.
2. [BOE CN119811288A](https://patents.google.com/patent/CN119811288A/en), публикация
   **2025-04-11**, BOE Technology Group / Mianyang BOE; [оригинальный PDF](https://patentimages.storage.googleapis.com/53/5b/a0/f576ed749cb46e/CN119811288A.pdf).
   Описание рис. 2 прямо сопоставляет **1 и 18 EM pulses**, duty **97.36% и 52.5%**
   при одном DBV в примере. Описание рис. 4 прямо называет **ILI97680a** и CMDQ
   с покадровым переходом gamma через состояния 3/6/9/12/15 импульсов.
   Это свидетельство необходимости согласовать emission timing, DBV и gamma,
   **не register map ILI97701A**. DBV/nit/duty примера не калибровка нашего телефона.
3. Motorola display DT pin **`f088523dfba85c95c15f43726fcf972c0c7a957a`**, tag
   `MMI-W3WWL36.65-11-18`; ветка из наводки — `android-16-release-w3wwl36.65-11-18`.
   [v4 DC arrays, строки 74–230](https://github.com/MotorolaMobilityLLC/kernel-display-devicetree/blob/f088523dfba85c95c15f43726fcf972c0c7a957a/display/dsi-panel-mot-boe-ili97701A-682-1440x3168-dsc-cmd-common_v4.dtsi#L74-L230),
   [AVR overlay](https://github.com/MotorolaMobilityLLC/kernel-display-devicetree/blob/f088523dfba85c95c15f43726fcf972c0c7a957a/display/alor-sde-display-avr.dtsi).
   Родственные `ili97680A…common_vantage_v4.dtsi` — донор информации, **не прошивки**.

`hypothesis`: 18 равномерных импульсов на базовый цикл 120/s дали бы **2160/s**.
Ни базовый emission cycle, ни такое число импульсов на цели пока не установлены.
120 Hz refresh metadata не доказывает первый множитель; `0x12` не найденный setter.
Даже высокочастотные импульсы не исключают низкочастотную огибающую.

## Карта кандидатов v4 — наблюдаемые байты, назначение `unknown`

Данные ниже аналитические, **не последовательность для отправки**. Индекс пакета
нулевой, включает page-select packets; property — `qcom,mdss-dsi-dc-{off,on}-command`.
Страница — контекст после `FF 5A A5 xx`, не отдельное имя глобального регистра.

| Пакет | Page:opcode | DC OFF → ON, данные без opcode | Что доказано |
|---|---|---|---|
| 6 | `23:A9` | `0E → 8E` | Меняется бит `80`; назначение неизвестно |
| 9 | `24:9D` | `0E → 8E` | То же; устойчиво и в родственных профилях |
| 12 | `23:80` | `50 → 90` | Изменение старших битов, не доказанный делитель |
| 16 | `53:95` | `00 A0 → 44 50` | Короткая связанная настройка |
| 17 | `53:A2` | 3 × 10-byte блока, см. ниже | Структура, не установленное RGB/brightness назначение |
| 27/28 | `63:F2/F3` | Пять `20` переходят из F3 в F2 | Перестановка данных между командами |

`53:A2`, каждый из трёх одинаковых блоков:

```text
OFF: 10 10 10 10 48 10 10 10 4B 4B
 ON: 10 10 10 10 48 10 10 74 7B B4
```

Обрамление сохраняется полностью: пакет22 `53:F0 01`, затем page00/`00 00`,
page63/`F1,F2,F3,F4`, возврат page53/пакет31 `F0 00`. F1/F4 между OFF/ON равны.
F0 пока **не называем unlock/commit/CMDQ enable**. Связь page53/page63 с CMDQ —
`hypothesis`; CMDQ из патента нельзя автоматически отождествлять с Qualcomm TX batching.
Не сжимать поток до словаря «последнее значение»: потеряются повторы и обрамление.

### Проверка эволюции по уже извлечённым архивам

`reported`, offline [CN arrays](cn_panel_commands.json), parser
[`packets()`](../06-tools/inspect_cn_dtbo.py), с отдельным подтверждением v4 на цели:

- ILI97701A v0/v1: по **426 B** на OFF/ON, соответствующие массивы v0 и v1 равны.
- v2/v3: по **578 B**, соответствующие массивы v2 и v3 равны; **A9/A2/F0/F2/F3
  организация из наводки уже присутствует здесь**, не впервые появляется в v4.
- v4: по **875 B**; перечисленные короткие кандидаты и блоки сохранены, полный
  массив отличается от v2/v3. Дополнительные настройки нельзя выбрасывать как «лишние».
- `23:80 50→90`, `24:9D 0E→8E` общие для всех пяти 97701A и четырёх архивных 97680A.
  `24:91 01 27 34 56→11 77 44 66` есть у 97701A v0/v1 и 97680A v1–v4,
  но отсутствует в DC arrays 97701A v2–v4. Это корреляция, не разрешение переноса.

## Формат и точки наблюдения

Motorola driver pin **`fa008c43c070ff20faa33853649f5dfd4c427e99`**:
[dsi_panel_create_cmd_packets:3603–3640](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/dsi/dsi_panel.c#L3603-L3640).
В его 7-byte header: `[0] type`, `[1] >> 6 controller`, `[2] channel`, `[3] flags`,
`[4] post_wait_ms`, `[5:7] big-endian payload length`. `last_command` определяется
batch flag, **не обычным для других веток правилом «byte1 = last»**. Сохранять raw
header, source/property/index/offset, полный payload и LP/HS state. Имеющийся parser
сохраняет границы и raw header; семантику exact binary целиком ещё не удостоверили.

- DC owner: `dsi_panel_set_dc` → `dsi_panel_send_param_cmd`, `panel_lock`, initialized
  guard, штатные значения 0/1; [существующий callgraph](driver_callgraph.md).
- [mipi logging: dsi_ctrl.c:3711–3755](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/dsi/dsi_ctrl.c#L3711-L3755)
  видит outgoing write payload перед `dsi_message_tx`. Это полезнее DT для runtime
  DBV, но само сообщение **не подтверждает transfer rc/optical success**; результат
  передачи и последующие перезаписи учитывать отдельно. Полный source-to-module match
  ещё не доказан; отдельные symbols/calls сверены с сохранённым actual `msm_drm.ko`.
- `panel_para_by_id` выбирает диагностический вывод, не DC/PWM режим; у source есть
  unchecked indexing. `panel_parse_para` заменяет sets без достаточной синхронизации
  и надёжного error reporting. Для этой задачи через них ничего не записывали.
- `dimming disable` в v4, `2D:CE` low-refresh DBV dimming и `00:60` refresh selection
  не являются доказанными PWM frequency controls. PMIC `pwm_period` — другая ветка,
  не активный `bl_ctrl_dcs` данной панели.

## Следующий ограниченный опыт — ещё не выполнен

1. **Offline A:** использовать приведённую карту/ordered arrays для сопоставления
   устойчивых mode bits и меняющихся таблиц, не присваивая полям название PWM_FREQ.
2. **Stock B:** наблюдать только штатный DC OFF/ON: requested mode → выбранный set →
   post-mutation payload (включая DCS DBV) → transfer result → доступное optical evidence.
   Начать с фиксированного запрошенного 120 Hz и подтверждать фактическое состояние,
   одинаковые content/thermal/brightness/camera settings. Логирование ограничить по
   времени и вернуть исходный flag; яркость, refresh, screen off/on и HBM/FOD/AOD
   учитывать как отдельные возможные источники перезаписи, не форсировать HBM на старте.
3. **Camera C:** несколько согласованных DBV, короткое добровольное сравнение камерой
   и по комфорту с двумя reference phones; осциллографа нет. По
   [протоколу](../05-safety/optical_measurement.md) остановиться при дискомфорте.
   Exact Hz, pulse count/duty и отсутствие низкочастотной огибающей оставлять `unknown`,
   пока метод их не разрешает. Не требовать осциллограмму для самой сравнительной пробы.

Никаких новых power/NVM/OTP команд, переноса donor sets или слепого `panel_parse_para`.
Новый DSI-профиль потребует отдельного обоснования и согласованного опыта. Android UI
с временным Apply и opt-in Remember остаётся требованием **после нахождения рычага**,
а не способом выдать штатный DC boolean за найденную частоту >=2000 Hz.

## Follow-up 13:14–13:21 UTC: stock trial готов к согласованию

`confirmed-on-target`: [preflight](stock_dc_trace_preflight_20261106.json) сохраняет
r59-dirty/UID0/Enforcing/_b. MIPI logger исходно0, DC0, screenOFF, Android brightness78,
auto-brightness1, min/peak refresh keys отсутствуют. [Trace facilities](stock_dc_trace_facilities_20261106.json):
kprobe_events/dynamic_events доступны, CONFIG_KPROBE_EVENTS/KRETPROBES=y. Function
tracer отключён, поэтому отсутствие available_filter_functions ожидаемо и не повод
пересобирать ядро. Return-probe ещё **не создан/не проверен**; глобальные tracer и
существующий wifi instance не трогать, для нашего опыта отдельный instance/group.

Текущие vendor panel-service / displaypanel.default.so / panel-V2-ndk.so прочитаны:
[comparison.json](current_display_path/comparison.json), все три byte-equal доступному
CN reference. Их равенство GLOBAL — прежний recorded comparison, не повторная проверка
отсутствующей сейчас GLOBAL extraction. Это усиливает соответствие vendor-части DC
callgraph, но не закрывает весь текущий framework/module source match.

### Новые первичные зацепки — `reported`, не target frequency proof

- BOE [рис.2, PDF p11](https://patentimages.storage.googleapis.com/53/5b/a0/f576ed749cb46e/CN119811288A.pdf):
  EM counts1/3/6/9/12/15/18 соответствуют duty97.36/92.08/84.17/76.25/68.33/60.42/52.50%.
  Рис.4 не даёт кодов регистров или временной базы.
- Цитируемый [Honor CN118471139A](https://patents.google.com/patent/CN118471139A/en),
  описание рис.4–5/7A–8: DDIC может выбирать число EM pulses по DBV; низкая яркость
  многоимпульсная, высокая — одно-/малоимпульсная. Его32/16 pulses/~90nit не параметры
  ILI97701A. `hypothesis`: native DC OFF проверять обязательно и на низкой яркости;
  ON может означать globalDC, а не повышение carrier Hz. На цели полярность не доказана.
- Найден настоящий именованный `emsync_fps` — «EM pulse rate in Hz»:
  [msm_drv.h:996–1007](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/msm_drv.h#L996-L1007).
  Но parser требует `qcom,mdss-esync`, DRM property gated соответствующей capability,
  а выбранный live DT не содержит esync/em-pulse properties. Это **не готовая крутилка**;
  спекулятивно включать внешнюю EM-sync ветку нельзя. Новый register map не найден.

### Один ограниченный stock A/B — согласован и выполнен 13:49 UTC

Ниже первоначальный scope; фактический результат и cleanup — в следующем разделе.

- Без boot/partition/module/DTBO writes, нового профиля, panel_parse_para и raw ioctl.
- После отдельного согласования агент сам переключает **официальный Android UI**
  Flicker prevention OFF→ON→OFF; не заставляет владельца писать код или команды.
- Временно manual brightness78 и40 из255, requested min/peak120Hz; фиксировать
  фактические DBV bytes/показанный mode, не называть запрос доказанной scan frequency.
  На каждом уровне полный OFF→ON→OFF для обхода штатного same-value skip.
- Logger0→1 только на время сбора. Если native return-probe разрешится — снимать
  dsi_ctrl_cmd_transfer return code в отдельном pwm_dc trace instance, без очистки
  глобальных trace/kmsg и без вмешательства в wifi instance. Передача rc0 сама по себе
  не гарантирует optical success или завершение отложенного DMA.
- Всегда cleanup: logger0, удалить только собственные probes/instance, brightness78,
  auto1, вернуть отсутствующие min/peak keys удалением созданных AOSP keys. DC вернуть
  штатным UI в OFF: effective initial state0; если исходный provider key отсутствовал,
  UI может оставить явный0, что фиксируется, а не выдаётся за byte-exact restore.
- Не форсировать HBM/FOD; стоп при потере display/Root/Enforcing, ошибке передачи,
  неожиданном состоянии или дискомфорте. Без камеры это лишь transport/software
  evidence; сравнение камерой/краткая оценка владельца остаются отдельным результатом.

## Stock transport result — 13:49:24–13:49:52 UTC

`confirmed-on-target`: владелец отдельно выбрал «Да, запускай» для указанного stock
опыта. [Execution record](stock_dc_trial_20261106.json),
[decoded trace](stock_dc_trace_analysis_20261106.json),
[исполненный collector](../06-tools/trace_stock_dc.py). Raw kernel/UI/trace logs
остались private0600 вне repo; публичные данные не содержат serial/IMEI/token.

- Выполнены шесть фаз OFF→ON→OFF при двух Android brightness values78/40.
  Provider0/1 и panelDC0/1 следуют UI; screen remained ON, Enforcing retained.
- Захвачено **579 outgoing write messages** на наблюдаемом `dsi-ctrl-1`.
  **Шесть полных наборов по75 packets /875 исходных DT bytes**, три ON и три OFF,
  совпали с live DT по payload/type/order/HS. Часть начального ON — восстановление
  сохранённого при подготовке ON во время wake **до** первого UI OFF tap; marker
  обозначает следующий запрошенный этап, не мгновенное состояние. Это не маскируется
  под отдельный запланированный переход. Подготовительный inline UI tap был без трассы.
- Runtime DBV после ramp: Android78 → sysfs5197 → **`51 14 4D`**; Android40 →
  sysfs2839 → **`51 0B 17`**. Page context0 подтверждён. Всего34 DBV writes, видна
  промежуточная ramp; заданные UI-переходы ON/OFF в обоих диапазонах происходили
  уже при стабильном DBV. Начальный wake ON отдельно, до завершения ramp, и не
  выдаётся за такой переход. Проценты/slider value не заменяют эти байты.
- Software active mode/peak/vsync/render reports **120.00001Hz**, desired physical
  range120..120. Это software scan metadata, не optical PWM proof.
- Native probes: ctrl_return581 hits/0 misses, param_return9/0; buffer590/590,
  lost-events не заявлены. Все9 parameter returns0; controller returns579×0 и2×+1,
  отрицательных нет. Положительное read length допустимо в RX path; по одному
  return event без аргументов не приписываем его конкретному сообщению. Именованных
  TX/RX failure messages в окне нет. rc/полный набор не доказывают физический carrier
  или завершение отложенного DMA.
- **Cleanup проверен**: DC OFF/provider0, logger0, auto1, min/peak keys снова absent,
  собственные probes/instance удалены. Запрос brightness78 восстановлен перед auto1;
  последующие изменения яркости auto — штатный алгоритм. Начальный provider null
  заменён явным0 через UI, это effective-state restore, не побайтовое восстановление.
  Ни boot/DTBO/module writes, ни новых DSI sequences не было.

Вывод: гипотеза «переключатель вообще не доходит до kernel/DSI» для этого stock
опыта отвергнута. **Оптическое различие, EM count и >=2000Hz ещё unknown**.
Следующий требуемый результат — camera/brief-owner A/B при этих воспроизводимых
условиях, прежде чем менять неизвестные регистры или строить новую PWM UI.

## Camera presentation/owner report — 14:09–14:10 UTC

Отдельно согласованы/предъявлены четыре условия78-OFF/78-ON/40-OFF/40-ON по12s,
затем проверенный возврат DC0/auto1/обычного refresh policy. Владелец сообщил о
толстой медленной → толстой быстрой → множестве тонких → отсутствии полос →
возврате толстой полосы. [Qualitative baseline](optical_baseline.md) сохраняет
предварительное сопоставление, неизвестные camera settings и границы вывода.
Впоследствии получен/офлайн разобран87.81s ролик: switches~10/25.8/41/56.6s совпали
с native tap chronology; low-OFF полосы видны до USB popup, low-ON менее полосатый.
Актуальные условия/ограничения: [video analysis](video_analysis_20261106.json).
Отсутствие полос не доказательство >=2000Hz. Далее reference/краткая добровольная
оценка практической пользы режима4, не новый flash или перебор регистров.

## 15:31 UTC onward — actual ALS threshold consumer decoded

`confirmed-on-target`: root read-only acquisition of current ALS XML, sensor-extension
service and panel filter; [provenance](current_display_path/als/acquisition.json).
Config/filter equal the CN copies, **current service differs**, so analysis uses the
newly acquired current binary, not an assumed CN match. Embedded `.gnu_debugdata`
provides function names. [Narrow disassembly](current_display_path/als/threshold_path.disasm.txt)
and [result](current_display_path/als/threshold_path.json) preserve the evidence.

`reported` — offline semantics of the acquired target binary:

- `AlsCompensation::init`,0x134f0–0x13524: reads `pwmToDcDbv` through
  `Config::getValueInt`, stores the value at object+0xf0. Actual XML value is3601.
- `DisplayBuffer::getDCmode`,0xc5bc–0xc6bc, opens the configured DC node read-only,
  reads one byte and parses it. It does not set panelDC or a DSI register.
- `AlsCompensation::calculate`,0x147f0–0x1492c, gets brightness and DC; its threshold
  comparison0x148d0–0x148e8 is equivalent for the acquired config to:

  ```text
  effective_dc_for_als = (dbv >= 3601) ? 0 : read_panel_dc
  ```

- Optional `backLightCorrespondingArray` is checked at0x14160–0x141c0 and can remap
  brightness before this comparison; that key is **absent in actual acquired XML**.
  No live initialized service-memory state was inspected.
- `PanelLux::getPanelLux`, selected model-input4 path0xeedc–0xef08/0xf364–0xf38c,
  uses this effective DC value to choose the compensation inference path; the
  same selector also reaches calibration/filter consumers. No display setter or
  numerical PWM-Hz field is established in this path.

This supports a **brightness-dependent ALS model distinction**, not a proven DDIC
switch at3601 or a frequency regulator. Our tested DBV2839 is below and5197 above
this boundary. Editing sensor XML would alter compensation, not program EM pulses.
No frequencies can be assigned to these values, nor inferred by `120 × 18` without
the actual panel timebase/pulse count.

Owner reports remaining bands after the brief mode4 trial and requires further
frequency work. DC ON must not be treated as a tunable high-frequency baseline:
its lower band visibility can also reflect duty/depth. Next unresolved engineering
item is target-specific emission timing/count mapping in native DC/init command
sets (23/24/53/63 candidates above), not another GKI rebuild or ALS/XML tweak.
