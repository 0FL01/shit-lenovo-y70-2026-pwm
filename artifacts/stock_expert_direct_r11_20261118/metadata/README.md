# Round11: независимая offline QA метаданных

Прочитаны четыре отдельных camera-service dump: short_drag, short2, short3, short4. Никаких обращений к устройствам, запусков acquisition-кода или изменений режима. JSON рядом содержит только выбранные поля, хеши исходников и ограничения; серийных номеров и путей в нём нет.

| Sample | Frame offset | Timestamp offset, ns |
|---|---:|---:|
| short_drag | 0 | 0 |
| short2 | 821 | 27365632000 |
| short3 | 1295 | 43165035000 |
| short4 | 1772 | 59064433000 |

Во всех четырёх открыто устройство **id2**, latest result: exposureTime **156000 ns =156 us**, sensitivity **6400**, frameDuration **33350000 ns**, rollingShutterSkew **31824000 ns**. AE OFF. Last request отдельно: **200000 ns =200 us (UI 1/5000)**, sensitivity **0**, frameDuration **33333333 ns**. Это НЕ один и тот же выдержанный интервал: reported actual на22% короче UI/request. ISO0 запроса не следует интерпретировать как реальный ISO0; result6400 имеет приоритет для описания результата. Между запросом и latest result нет доказанной пары по frame ID, и отсутствует однозначная привязка screenshot к результату.

Результаты vendor aeIsoSpeed=0, aeSensorGain=16384 и aeIspGain=16384 не являются независимо калиброванными ISO/выдержкой; их единицы/семантика здесь не установлены. postRawSensitivityBoost=100. Упоминание tag в availableKeys или реестре vendor tags НЕ означает наличие значения для текущего кадра. Не обнаружен отдельный current line-time/readout timestamp, удостоверяющий время каждой строки preview.

Из **static именно id2**, не другого устройства: activeArray/preCorrection/pixelArray **3264×2448**, orientation **90°**. Crop result/request и vendor crop:0,0,3264,2448. Stream0 preview **1440×1080**, CUSTOM operation mode36869; остальные output streams configured, но произведено0 кадров. OIS/video stabilization OFF. Эти данные сужают варианты, но не удостоверяют текущую физическую схему binning/skip, ISP resample/distortion correction, SurfaceTexture transform и соответствие осей сенсора screenshot. Из-за поворота90° сенсорная строка не обязана соответствовать горизонтальной строке портретного screenshot.

**Не вычисляется численное время строки preview и частота PWM.** Деление skew на2448 либо1080 без подтверждения sampling/геометрии создало бы неподтверждённую шкалу. Frame duration также нельзя автоматически делить на высоту: он включает иные интервалы. Для физической временной аттестации недостаёт известного независимого оптического времени/частоты, проверки режима считывания, полного преобразования sensor→stream→UI, привязки кадров и контроля возможного aliasing. Стабильные четыре HAL значения подтверждают только повторяемость зарегистрированных метаданных, не внешнюю точность.

QA не оценивает содержимое новых изображений, clipping, распознавание пространственного кода или возврат устройств; это отдельные проверки.

## Воспроизведение

`python3 replay.py PRIVATE_ARCHIVE` читает только четыре raw-файла. Аргумент каталога не сохраняется в outcome. Абсолютные clock/frame IDs заменены смещениями; id2 означает локальный Camera2 номер, а не идентификатор устройства. Никаких PNG в пакете нет.

`python3 test_replay.py PRIVATE_ARCHIVE` и тот же запуск с `-O`: 11/11 PASS в обоих режимах. Негативы: подмена actual запросом и наоборот, ISO, skew, frameDuration, повтор dump, отсутствующий dump, другой camera status, размер preview и отсутствующая правильная static-секция. Replay сохраняет различие request/result и не выдаёт численной физической шкалы.
