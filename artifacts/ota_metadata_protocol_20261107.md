# Offline путь к OTA metadata — источник новых display tables

2026-11-07, `reported`: исследован **CN reference APK**, не установленный updater
цели. Цель этой ветки — получить новый источник таблиц, не обновить телефон.
Серверных запросов, передачи идентификаторов и действий на телефоне не было.

APK: `extracted/XT2611-1/W3WWL36.65-11-18/filesystems/system_ext_a/priv-app/3c_ota/3c_ota.apk`,
22,981,798bytes. Использован установленный
`/home/stfu/.cache/android-sdk/build-tools/36.0.0/dexdump -d <APK>`.

## Найденный путь

- `BotaUpgradeSource.checkForUpdate`: DEX calls `0x2742e0` → `BuildPropertyUtils.getId`,
  `0x2742f4` → `getIdentityInfoAsJsonObject`, `0x2742fc` → `serialNumber`,
  `0x274310` → URL constructor, `0x27433e` → JSON builder, `0x274390` → WebService.
- `CheckUrlConstructor.constructUrl` добавляет `/ctx/` и `/key/`; context key
  URL-encoded. По companion methods default check endpoint —
  `https://<server>/cds/upgrade/1/check/ctx/<context>/key/<context-key>`, POST.
  Production hosts в reference code включают `moto-cds.appspot.com` и
  `moto-cds.svcmot.cn`; runtime может их переопределять.
- Download descriptor запрашивается отдельно через
  `BotaUpgradeSource.checkForDownloadDescriptor`, используя metadata/tracking ID.
  Resources constructor добавляет `/t/` (`0x2b141c`), `getTrackingId` (`0x2b1426`),
  затем context/key. Wi-Fi/cellular URL берутся из ответа сервера, не вычисляются
  из строки `AI71WWH.15-43`.

Parent независимо извлёк и проверил четыре указанных метода,608 lines:
`/home/stfu/.cache/opencode-tmp/opencode/ota-offline-protocol-20261107/metadata-path-dex.txt`,
mode0600. Первое чтение всего dexdump как UTF-8 встретило невалидную последовательность;
повторный **byte-level** отбор не изменял данные, выбранные методы затем успешно
проверены как UTF-8 без replacement/ignore. Это исправление host parser, не OTA failure.

## Что это разрешило и чего не разрешило

В этом клиентском пути нет найденного анонимного поиска пакета только по build ID:
он device-specific и включает identity/current-build информацию. Host-only HTTPS
технически возможен без запуска updater, но server authentication/registration,
eligibility и side effects POST **не установлены**. Нельзя называть его проверенным
read-only каталогом или утверждать, что регистрация обязательно нужна.
Применимость CN APK к текущему GLOBAL updater также `unknown`.

Raw current-target prefs/DB с credentials не использовались; их значения не
читались для этого разбора и не отправлялись. Новый пакет Android17 всё ещё не
получен. Дальнейшее получение требует публичного download URL/публикации source
либо отдельно определённого и разрешённого device-specific metadata check —
не слепого запуска OTA на телефоне. Ни один вариант сам по себе не обещает PWM fix.
