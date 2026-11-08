# STK6A2X: достижимость быстрого ADC через client request

2026-11-07. **R3 active; физический OLED PWM ≥2000 Гц не установлен.**
Новый вопрос после [заводского flicker-разбора](../flicker_sensor_recon_20261107.md):
можно ли получить ADC sampling >4 kS/s штатным запросом клиента, не меняя firmware
или I2C-таблицы? Это поиск измерительного канала, **не PWM setter панели**.
Новых ADB, подписки на сенсор, calibration/self-test, DSI, reboot или flash нет.

## Android HAL: on-change не передаёт желаемую частоту ADC

Использована `sensors.qsh.so` из сохранённого CN extraction: её побайтовое равенство
current target уже установлено read-only сверкой; SHA256
`68c5c74056cf98204ed8ffdf18772695f980e243af1cc1cd2fea67abaeeaeffa` перепроверен.
Далее адреса HAL — ELF VA этой библиотеки.

- Встроенный `.gnu_debugdata` независимо задаёт имя и границы
  `get_available_alternate_flicker_sensors()` **0x63abc**, size1748.
  [Factory](hal-flicker-factory.txt),0x63c74–0x63c7c: создаются только sensors
  с `get_stream_type()==1`. Вызовы alternate_flicker constructor —0x63c98/0x63d48.
- Constructor0x64208 устанавливает type65588 и vtable через GOT0x97900 →
  `_ZTV17alternate_flicker=0x94f70`. Слот vptr+0x60 (`0x94fe0`) разрешён через
  Android packed relocation в **`qsh_sensor::create_sensor_config_request`0x4f1f4**,
  не специальный flicker frequency setter: [relocations](hal-vtable-relocations.txt).
- [Create request](hal-create-config.txt): stream type получается по0x4f27c.
  `cbz x21`0x4f2b8 оставляет continuous-ветку только type0. При nonzero
  записывается **message ID514** по0x4f310; payload очищается через protobuf
  `ClearToEmpty` по0x4f390. Соответствующая log string прямо называет
  `SNS_STD_SENSOR_MSGID_SNS_STD_ON_CHANGE_CONFIG`.
- Только continuous-ветка вычисляет `1e9/period_ns` по0x4f3cc–0x4f3e0,
  формирует `sns_std_sensor_config.sample_rate` и ID513 по0x4f4d8.
  Это не ветка объявленного alternate_flicker sensor.
- [Outer sender](hal-send-config.txt) вызывает указанный virtual slot+0x60
  по0x50490–0x5049c. Batching/reporting metadata не следует путать с ADC integration.

**Уточнение прежнего диагностического файла:** cached
`factory-native-recon-20261107/alternate-flicker-registration.txt` начинается
с0x64958. `.gnu_debugdata` показывает, что это factory **alternate_rgb**,
несмотря на ближайшую подпись objdump. Для нового вывода использован реальный
flicker factory0x63abc. Ранее установленные flicker constructor, event handler,
mode2 table и alias-модель этим не изменены.

## DSP: direct standard rate меняет обслуживание, не mode-2 timing

Происхождение current ADSP b21/b22 и SHA256 — в исходном sensor-отчёте.
Адреса ниже — target DSP VA; CN offsets не переносились. Пять диапазонов заново
декодированы существующим LLVM Hexagon helper; записи совпали с сохранённым
target listing. Учитывались параллельные packets, а не обычный ARM-порядок строк.

1. `stk6a2x_set_client_request` **0xb23198b8** записан в обе API-таблицы b22
   `0xb259ddc0/0xb259ddd8`; flicker initialization задаёт sensor type8.
2. [Client handler](client.txt),0xb2319cf4–0xb2319d68: IDs513/518 декодируют rate.
   Для проверенных конечных положительных чисел проходит только unsigned truncate
   в **1…15** (`[1,16)` для этих float inputs), а не тысячи samples/s.
   Ошибку обозначает log `invalid sample rate`. NaN/overflow не квалифицированы.
3. [Aggregator](get_config.txt),0xb23197bc–0xb23197d4: ID514 отмечает активный
   запрос без sample-rate payload;513/518 агрегируют rate через sfmax.
   Внутренний instance-config ID513 не означает, что Android-клиент послал ADC rate.
4. [Instance handler](instance.txt),0xb2318b84–0xb2318bd4 сохраняет float+2780;
  0xb2318c8c–0xb2318cd0 использует `1e9/rate` для timer-config0xb231d7ec.
   Отдельная zero-rate ветка содержит fallback66666666. Это период обслуживания,
   не вычисление сенсорных registers03/04/0e.
5. Flicker enable выбирается по маске0x0c и передаётся как boolean по
  0xb2318d28–0xb2318d34 в [enable0xb231f288](flicker_enable.txt).
   По0xb231f320–0xb231f330 в [writer0xb231d63c](mode_writer.txt) идут
   **фиксированный table pointer0xb259de00 и mode ID2**, а не request-rate.
   Writer применяет четыре `(register,value,mask)` triples.

Фиксированная таблица и условные sampling parameters1025/1018 уже доказаны прежним
разбором; повторного аппаратного опыта здесь нет. Теоретический максимум6410
из формулы при иных X/Y **не стал достижимой настройкой** от изменения client ODR.
Физические единицы ADC и оптический спектр по-прежнему не квалифицированы.

## Message700: инициализация FFT, не найденный ADC setter

`reported`, статический анализ сохранённых target bytes; точное enum-имя700
остаётся `unknown`. Ветка не запускалась.

- [Client handler](client.txt),0xb2319d6c–0xb2319d90 сравнивает ID700 и вызывает
  **0xb231fd6c с instance в r0**; payload в специализированный handler не передаёт.
  Log descriptor0xb240afd0 указывает на0xb240af80:
  `stk6a2x_set_client_request: get reqest from fft lib`.
- [Handler](message700-handler.txt),0xb231fd6c–0xb231fe1c формирует локальную
  константную структуру: block128, peaks5, padding512, включённые flags и шесть
  коэффициентов. Он отправляет event701, затем через0xb231fe20 — event705
  при наличии FFT stream. Нет client-selected register/value или ADC timing args.
- [Consumer](fft-consumer.txt),0xb20343d4–0xb203450c распознаёт701 как512+189,
  декодирует данные и вызывает [stk_fft_init](fft-init.txt) по0xb2034d90.
  **Фактический указатель descriptor в producer и consumer —0xb20d635c**
  (`-1307745444`), не0xb20d6340 из предварительной заметки. Содержимое descriptor
  вне сохранённых target segments; его схема здесь независимо не декодирована.
  Init записывает FFT state, а не I2C timing registers03/04/0e.
- Event705 идёт в0xb2034d70, log descriptor0xb206a288→строка0xb206a248
  `stk_fft_version: Version:: %03X`.
- Имя `SNS_STK6A2XFFT_MSGID_SNS_STK6A2XFFT_CONNECT_ALGO` связано с **706**:
  [отдельная проверка](fft-connect706.txt),0xb2034784–0xb203479c;
  descriptor0xb2069f10→строка0xb2069e98. Называть700 CONNECT_ALGO/self-test нельзя.

[Message700 validation](message700_validation.json): четыре диапазона,220 записей,
без undecoded, с точным совпадением сохранённому target listing. Успешный handler
не декодировался повторно; остальные три завершены. Первая consumer-выборка
обрезала следующую после immext инструкцию: end0xb2034508 исправлен на0xb203450c,
старый diagnostic сохранён отдельно. Это ошибка границы extraction, не firmware
mismatch; проверки не ослаблялись.
Независимое узкое ревью повторно подтвердило все220 записей, caller/consumer,
сырые log pointers и граничную ошибку. MDT относит descriptor0xb20d635c к b29,
не сохранённому среди этих target segments. Замечаний в проверенной области нет.

## Сохранённые ограничения

- Если cached mode уже2, table-write пропускается. Watchdog проверяет initial
  table и может повторно применить сохранённый mode, но это не readback четырёх
  timing registers в любой момент.
- FFT использует cached timing words+80/+84; полная инвалидация во всех переходах
  не доказана. Выданный rate нельзя безоговорочно объявить live ADC rate.
- Registry/vendor-интерфейсы целиком не исключены. Нельзя обобщать проверку
  стандартного client path до «железо никогда не работает выше1kS/s».
- Общий request сохраняется через instance vtable до700-specific вызова;
  пустота wire-payload700 не доказана. Общий хвост0xb2319e10–0xb2319e6c при
  instance+2747 может выполнять registry/calibration updates. Отсутствие ADC
  setter в разобранном700 handler не исключает все vendor/registry-пути.

[Validation](validation.json): target HAL identity, actual vtable relocations,
пять freshly decoded DSP ranges, 12 finite rate-guard cases. Это static/model
проверки, не исполнение прошивки и не оптическая калибровка. A9-only baseline
сохранён; обычный sensor request не объявлен способом изменить OLED PWM.
Независимое ревью обычного rate-пути подтвердило1825 raw ARM64 words,
1097 DSP records, APS2 relocations и12 float32 cases. Outer sender не заменяет514
и не добавляет flicker sample-rate payload. Этот результат не даёт основания
активировать сенсор как готовый измеритель≥2kHz.
