# Новый путь: заводская диагностика и отдельный flicker-сенсор

2026-11-07, завершён узкий реверс factory-пути и штатного flicker-режима.
Цель Lenovo OLED≥2000Hz не достигнута.
Проверяемая гипотеза: factory-компоненты содержат либо именованный PWM setter,
либо независимый оптический канал, способный отделить camera aliasing от света.
Новые DSI/flash, запуск CQA, калибровок или подписки на сенсор **не выполнялись**.
ADB использован только для чтения inventory/config и бинарников, не тестов.

## Подтверждено на текущем XT2611-1

`confirmed-on-target`, buildW3WWS36.65-64-4-1, `ro.vendor.hw.device=avr`,
`ro.vendor.hw.revision=pvt`:

- SensorService объявляет **stk_stk6a2x Alternate_Flicker Sensor**, Sensortek,
  vendor type **65588 /0x10034**, handles0x1020b(non-wakeup)/0x1020c(wakeup).
  Reporting mode on-change, minDelay/maxDelay0. Это частота Android reporting,
  **не внутренний ADC sample rate или диапазон измеряемого flicker**.
- Текущий `/vendor/etc/motorola/12m/fac_test_config.xml` содержит
  `FLICKER_ITEM=2`, `FLICKER_IGNORED=CCT`, `LuxCctFlickerSensor` в меню.
- Текущий `/vendor/lib64/sensors.qsh.so` **побайтно идентичен** RETCN reference
  W3WWL36.65-11-18, SHA256:
  `68c5c74056cf98204ed8ffdf18772695f980e243af1cc1cd2fea67abaeeaeffa`.
  Это конкретный binary-comparison, не допущение эквивалентности всей прошивки.
- ADSP`b21/b27/mdt`, наоборот, **не совпали** сRETCN. Их текущие копии получены
  root-read с проверкой SHA256. Последующий sensor reverse выполнен по currenttarget,
  а не путём переноса CNадресов/констант без проверки.

В прочитанном inventory Nothing flicker-named sensor не найден; это не утверждение
об отсутствии любого оптического железа или скрытого vendorинтерфейса.

## Прочитанный CQA-путь (CN reference APK)

Источник: `extracted/XT2611-1/W3WWL36.65-11-18/filesystems/system_ext_a/priv-app/CQATest/CQATest.apk`,
`classes.dex`, `com.motorola.motocit.sensor.LuxCctFlickerSensor`.
Сам APK сcurrentGLOBAL ещё не сопоставлен.

- `onResume`0x3d8ebc–0x3d8efc запрашивает sensors65578(lux),65589(CCT),65588(flicker).
- `getFlickerItemConfigFromXml`0x3d8630 читает`FLICKER_ITEM`, default8.
- `onSensorChanged`0x3d92e6–0x3d93a6 логирует13values и выбирает заданныйindex.
  **Индекс0 → values[0] напрямую; ненулевойиндекс → values[index]/1000.0f.**
  Поэтому config2 означает **values[2]/1000**, затем округление до2знаков.
  Доказательство: `if-nez`0x3d9372 переходит к0x3d9386, float1000 в0x3d938e,
  division0x3d9392. Parent независимо перепроверил этот branch: первая трактовка
  subagent была обратной и исправлена до публикации окончательного callgraph.
- GET_READING отдаётFLICKER; help называет его environmental light flicker frequency.
  Pass-проверка лишь«не ноль», не тест точности/диапазона≥2000.

В идентичном target/CN`sensors.qsh.so`:
`alternate_flicker::handle_sns_std_sensor_event`,VA0x644e4,size1140,
проверяетstatus3 и копирует до16float из decoded standard event в Android event
(0x6465c–0x64748); в loop0x64734–0x64740 нет единичного масштабирования.
Семантика элементов пока зависит от producer вDSP.
GNUobjdump неверно подписал24-byte PLT; constructor-call0x91910 независимо
разрешён черезGOT0x98138 иR_AARCH64_JUMP_SLOT как`qsh_sensorC2`, не`calibration`.
Случайные ближайшие PLT-labels не используются как callgraph evidence.

## Что уже отвергнуто в factory-поиске

- CQA`BlackPattern SET_DISPLAY_SETTINGS FLICKER` меняет`mInvalidateViewOn`
  и вызывает`View.invalidate()` (DEX0x346622–0x346654,0x345d80–0x345da4).
  Это redraw тестовой картинки, не physicalOLEDHz setter.
- DisplayPanelId читаетpanelId/panelCellId; GoodixPWM_EXPO относится к fingerprint
  exposure, cameraSCENE_FLICKER — кcamera metadata. Не переносим их на OLED.
- В CN`vendor_a/bin/mot_tcmd` строка«Config pwm line successfully» ведёт к
  helper0x7f95c…0x7fb08: gates`ro.vendor.hw.device`=`obakem`/`falcon`, revisiongate,
  команда`/vendor/bin/disp_util -lp -sh 51 00` поVA0x2a767. Это legacyDCSbrightness
  payload, не найденныйfrequency setting дляavr. Target`mot_tcmd` имеет другой
  SHA256, но после root-read **сам диапазон helper0x7f95c…0x7fb0c побайтно совпал**,
  адреса указанных строк также совпали. Наtargetro.vendor.hw.device=avr эта
  ветвь не достигает legacycommand. Команда/helper не запускались.
- ALS`pwmToDcDbv=3601` — **уже известный** compensation threshold, не новыйsetter;
  прежний анализ `dc_transition_recon_2026-11-06.md` не повторялся как открытие.

## Новый источник: DSP FFT

Офлайн из сохранённогоRETCN ZIP извлеченыdspso.bin иradio.img; ZIPCRC проверяется
при чтении. radio container`SINGLE_N_LONELY` разобран с256-byte entries,
4096-byte paddedpayload и footer`LONELY_N_SINGLE`; извлечён толькоNON-HLOS,
**FSG не извлекался, flash/erase recipes не выполнялись**. simg2img+read-onlydebugfs
далиADSPsegments. dspsoраздел не содержал отдельногоstkдрайвера, ноADSPсодержит его.

В CNADSPb21/b27 найдены именованные логиFIFO, sampling_rate, FFT block/padding,
**fre1/fre2/fre3**, magnitude иaverage/max/min. Статический проходCNFFTядра
показал масштабированиеbin×sampling_rate/N, а не простую выдачу номераFFTбина;
реальные единицы иsample-rate ещё не установлены.

Currenttargetкопии для завершённого перехода:
- `adsp.b21`: VA0xb2200000,3760276bytes,
  SHA256`48f5fd8e5ea8f1c04a12646037c03cb3d1fc99dcbbdba00b6f3a53fe1f351f4e`.
- `adsp.b27`: VA0xb201c000,498212bytes,
  SHA256`0e6034f26edbd299558cd4e6c7748940ad5fbb5e5951e9096a9e27f760994b4d`.
- `adsp.b22`: VA0xb2597000,2457604bytes,
  SHA256`463d156bdc64cb4fc0f6a43825e4493f128fa3ff9724b86f9c75b855ab14e29c`.
- `adsp.mdt`: ELF32Hexagon,flags0x79, program headers задают указанныеVA/размеры;
  SHA256`b6d0901c0e5fe46236f6ce3b208e0092fe45a1426fbcc6c5cecc18dd6fc46901`.

УстановленныеAndroidllvm-objdump не включаютHexagon. Рабочий decoder получен
без установки dependencies: `/usr/lib64/libLLVM.so.23.1` CAPI из`/usr/bin/python3`,
API signatures проверены по имеющемуся`llvm-c/Disassembler.h`. CondaPython дал
libstdc++ABIошибку, системныйPython её устранил. Linear sweep явно помечает
недекодируемые слова; участкиданных не объявляются кодом. Для выводов нужны
function boundaries иHexagonpacket-aware проверка, а не линейнаяCсемантика.

## Target event mapping: закрытый ранее неизвестный hop

`b27:0xb2034870` → FFT`0xb2034a8c` → message703/0x2bf,
descriptor0xb20d6278 → `b21:0xb2319030…0xb23190b4` decode вstate+1844 →
`stk6a2x_flicker_notify`,0xb231f0e0 → standardevent1025/status3/count25
(вызов0xb20ea2bc по0xb231f22c). HALкопирует первые≤16float.

| Android values | Семантика по target-коду |
|---|---|
|0,1|1.0,1.0|
|**2**|**1000×fre1**, наиболее сильный из сохранённых FFT-пиков|
|3|спектральная величина первого пика|
|4|1000×fre2|
|5|величина второго пика|
|**6**|вычисленный sampling_rate|

Точная запись: **`values[2] = 1000 * fre1`**, не обратное масштабирование.
CQA`values[2]/1000` возвращаетfre1. Это частотная координата пика, не обязательно
fundamentalPWM и не доказательство отсутствия низкой огибающей. Parent просмотрел
float1000 по0xb231f118 и stores по0xb231f148/0xb231f180. Полные поля сообщения и
порядок Hexagonпакетов независимо проверены subagent.

Изproducer0x2be в`b21:0xb231e944…0xb231ea58` восстановлена формула:

```
X = ((reg03 & 0x3f) << 8) | reg04
Y = reg0e & 0x3f
A = 26660 * (X + 1)
B = 833 * Y
D = floor((A + B + 130000) / 1000)
sampling_rate = floor(1000000 / D)
```

Это регистры **оптического сенсора**, не панели. D вычисляется черезhigh32
произведения с274877907 иshift6; parent проверил точное равенствоfloor/1000
на **1,048,576** комбинациях полей. Fs передаётсяFFT вstate+2472.
FFTconfig:128реальныхsamples,5пиков,padding512,detrendON. Zero-padding не повышает
ни частоту выборки, ни физическое разрешение. Формула peak coordinate:
`floor(k * floor(sampling_rate*128/512) / 128)`, k от1 до255; Nyquistбин исключён.

## Существенный предел штатного режима — не использовать CQA как прибор≥2kHz

Недостающий ранееtarget`b22` получен и сопоставлен сmdt; это не внешнийblocker.
Таблица mode2 поVA0xb259de00 /fileoffset0x6e00:

```
register value mask
03       00    3f
04       1e    ff
0e       17    37
00       10    10
```

Callsiteflicker enable0xb231f314…0xb231f330 → writer0xb231d63c…0xb231d690 →
maskedwrite0xb231d0e0, `new=(value&mask)|(old&~mask)`.
При успешном применении и отсутствии последующей перезаписи:

| X | Y | D | sampling_rate | Максимальная выдаваемая FFTкоордината |
|---:|---:|---:|---:|---:|
|30|23|975|**1025**|510|
|30|31|982|**1018**|506|

Два вариантаY обусловлены сохранённымmask0x37 старымбитом0x08. Parent перебрал
все256 предыдущих значенийreg0e и получил только эти две ветви. Независимый
packet-aware разбор подтвердил порядок(address,value,mask), формулу и вызовы.

**Если внутренние временные единицы реализованы какns/µs/Hz, это около1kS/s**, не
4–6kS/s. Тогда штатный канал не различает2160Hz и низкийalias. Синтетическая
проверка128samples показала точное до2.8e−13 совпадениеcos2160Hz сcos110Hz при
Fs1025 иcos124Hz приFs1018. Это математическая демонстрация aliasing, **не снятые
показания сенсора**. Нельзя объявить эти110/124Hz истиннымPWM эталона.

Оговорки: сырыеI2Cрегистры не читались; runtime-подписки не было; FsвфизическихHz
не калибрована. Если сохранённыйmode уже2, запись пропускается; watchdog/ALSmode1
может переигрывать таблицы. Кэшstate+80/+84 перечитывается лишь когда одно слово0;
полная инвалидация во всех ветвях не доказана. Поэтому1025/1018 — **условный
статический результат штатнойтаблицы**, не заявление«liveADC сейчас точно такой».
Но даже при исправном следовании найденномукоду этот factorymode не является
пригодным подтверждением≥2000Hz. Ручная переделкаADCтаблиц здесь не выполнялась.

## Итог и граница

Factory-route дал новое подтверждённое устройство/схему данных и выявил опасный
низкочастотный alias-путь, **но не PWMsetter**. Закрыта гипотеза«штатныйCQAflicker
можно прямо использовать как независимый измеритель≥2kHz». Сам sensorhardware
не объявлен неспособным к более быстрой выборке; для неё нет проверенного режима.
Фотокамерные сравнительные опыты остаются доступны безосциллографа по прежней
методике. Цель не закрыта, A9baseline сохранён; следующий подготовленный DSIтест
A0D1C1 всё ещё требует собственной точной авторизации, которой этот реверс не даёт.

Evidence: approvedprivatecache
`/home/stfu/.cache/opencode-tmp/opencode/factory-native-recon-20261107/` и
`/home/stfu/.cache/opencode-tmp/opencode/cqa-display-recon-20261107/`.
Сырыеsensorservice dumps не публикуются; вrepo только относящиеся к гипотезе факты.
Ключевые новые evidence: `target-adsp/b22-tables.json`,
`mode2-offline-validation.json`, `timing-parameter-bounds.json`,
`target-adsp-b21-disassembly.txt`, `target-adsp-b27-disassembly.txt`,
`cqa-flicker-parent-selected.txt`. Проверки были только source/binary/model и
read-onlyinventory; успешного оптического измерения этой веткой не заявляется.
