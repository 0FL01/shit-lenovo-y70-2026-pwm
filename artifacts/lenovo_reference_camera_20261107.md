# Open Camera на Lenovo для съёмки эталонного Nothing

2026-11-07 15:38:59 UTC (host). По запросу владельца реверс приостановлен,
Open Camera установлена и настроена на Lenovo XT2611-1 / W3WWS36.65-64-4-1.
Статус установки и приведённых camera metadata: `confirmed-on-target`.
Nothing PacmanPro как экран-эталон **2160 Гц** — `reported`, прямое подтверждение
владельца; в этой подготовке частота заново не измерялась.

## Установка и настройки

Переиспользован исходный APK с Nothing, без модификации: Open Camera **1.56.2**,
versionCode96, 4,978,282 bytes. SHA256 установленного на Lenovo APK совпал:
`b4df7b6c724aa8e56babae9090b28da088148b95c6c413b4efdb2c3cc4a7c952`.
Выданы CAMERA/RECORD_AUDIO; location и root-доступ самому приложению не выдавались.
Исходные настройки Nothing экспортированы штатным Settings manager. На Lenovo
перенесены параметры съёмки, не чужие неподдерживаемые photo resolution/path.
Настройки экрана Nothing не менялись. APK/prefs и сырые dumps остаются private.

| Параметр | Nothing: фактический результат | Lenovo: запрос → результат HAL |
|---|---|---|
| API / камера | Camera2 / задняя0 | Camera2 / задняя0 |
| Выдержка |100000ns (1/10000s)|100000 → **99999ns**|
| ISO |6400|6400 → **6400**|
| AE / AF |OFF / OFF|OFF / OFF → **OFF / OFF**|
| Ручной фокус, диоптрии |9.11752701|9.11752701 → **9.17431259**|
| Баланс белого |AUTO|AUTO → AUTO|
| EIS / OIS |OFF / OFF|OFF / ON → **OFF / OFF**|
| Frame duration |33350000ns (~29.985fps)|33333333 → **33333333ns**|
| Rolling-shutter skew |15596307ns|**27011343ns**|

Два важных отличия от простого копирования preferences:
- Nothing сохранял FPS=24, но фактически работал около30fps. Копия24 на Lenovo
  действительно дала24fps. Поэтому Lenovo установлен30fps, чтобы совпадала
  фактическая кадровая частота. Видео —1280×720, HEVC/MP4.
- OIS в request Lenovo остаётсяON из шаблона HAL, однако static capabilities
  объявляют толькоOFF, а **полный result возвращаетOFF**. Обычный dumpsys latest
  frame содержит лишь часть metadata; недостающие поля проверены штатным
  `cmd media.camera watch`, scoped к net.sourceforge.opencamera. Подмена HAL,
  изменение APK или принудительный аппаратный override не потребовались.

Ручной фокус слегка квантуется драйвером Lenovo. При перезапуске первый кадр
отражал движение линзы, следующий — установившееся9.17431259; отдельный снимок
metadata после установления подтвердил это значение. Не выдаём запрос за result.
Режим фото также подготовлен с ручным фокусом вместо исходного Nothing photo-AF;
его отдельная JPEG-съёмка не проверялась. Для сравнения оставлен **видеорежим**.

## Реально выполненные проверки

- Версия, побайтовая SHA256-идентичность установленного APK, сохранение owner/mode/
  SELinux context файла preferences при настройке; SELinux остаётсяEnforcing.
- Camera2 request, capabilities и полные result metadata; параметры Nothing
  перечитаны и остались100us/ISO6400/manual focus/AE-AF-EIS-OIS OFF.
- Один технический ролик Lenovo: **61 кадр / 2.033056s**,1280×720 HEVC,
  avg_frame_rate219600/7319 (~30.004fps). ffprobe и полное ffmpeg decode — успешно.
  Это проверка записи, **не измерение экрана/PWM**. Тестовый файл удалён только
  с телефона; private host-копия сохранена.
- Перезапуск приложения (не телефона) сохранил настройки; финальный camera
  result проверен после установления фокуса. UI передан с кнопкой Start recording
  video: камера открыта, запись не идёт. Tag monitoring остановлен, собственные
  временные UI XML удалены с обоих телефонов.

Evidence: `/home/stfu/.cache/opencode-tmp/opencode/lenovo-reference-camera-20261107/`,
directory0700/files0600: `preflight.json`, `nothing-settings-export.xml`,
`lenovo-settings-requested.xml`, `lenovo-handoff-watch.txt`, `verification.json`,
`lenovo-test-ffprobe.json`, `lenovo-test-recording.mp4` и scoped dumps.

Короткий лог диагностики: пустой exit1 от `pm path` означал отсутствие пакета,
не потерюADB; результат подтверждён `pm list packages`. Export лежал в
Android/data/.../files/backups, что подтверждено методом APK getSettingsFolder.
Проверка всех startup focus-значений как steady-state была неверна: сохранён
переходf0→f1, затем отдельно проверен установившийся result. Во время одного
финального чтения foreground оказался в Display Settings, поэтому слепые taps
не выполнялись; повторно открыта только Open Camera, параметры подтверждены.

**Ограничение сравнения:** rolling shutter двух сенсоров различается (около27.01
и15.60ms по metadata); также различаются оптика/обработка. Даже при тех же ISO
и выдержке нельзя напрямую переводить отношение числа/ширины полос в PWM Hz.
Снимать нужно камерой Lenovo экран Nothing, а не системным скриншотом Nothing.
Новых DSI, flash, reboot и постоянных PWM-настроек не было; A0D1C1 не запускался.

## Снимок владельца перенесён

По следующему запросу скопирован **один** исходный JPEG с Lenovo:
`/sdcard/DCIM/OpenCamera/IMG_20261107_103657.jpg` →
`/home/stfu/Downloads/Nothing_PWM_Lenovo_20261107_103657.jpg` (995,569bytes).
SHA256 источника и копии совпали; оригинал на телефоне сохранён, обработки
изображения не было. Файл открыт и просмотрен: видны частые наклонные полосы
на снятом экране. Идентификация экрана как Nothing — по владельцу (`reported`);
новой частоты по этому изображению не присвоено. Это камерное фото, не системный
скриншот, что подходит к поставленной задаче.

Последующий [офлайн-анализ эталона](nothing_reference_20261107/result.md) прочитал
EXIF этого JPEG:99999ns, **ISO6592**,4096×3072. Таблица выше относится к
проверенному preview/video setup сISO6400, не к capture result этой фотографии.
