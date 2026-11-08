# Persist display calibration: кто потребляет файлы

2026-11-07. **R3 active, не решена.** Ветка проверяет, не хранится ли отдельная
панельная command table вне ROM DT. Уточнение владельца «сейчас только offline»
соблюдается после последней нижеописанной read-only инвентаризации; новых
обращений к устройству, DDIC, sensor/test активаций и settings writes нет.

## Что было прочитано на аппарате

`confirmed-on-target`: свежая идентификация transport2 — XT2611-1,
W3WWS36.65-64-4-1/avr; rootUID0, Enforcing, прежний KSU kernel.
Transport1 идентифицирован как PacmanPro; его настройки не менялись.
Идентификаторы USB/IMEI не публиковались.

Выполнены только `find -maxdepth 2 -type f`/`ls -ln` в четырёх конкретных
display-каталогах. **Содержимое файлов не читалось.** В persist/display найдены:

| Суффикс panel_mipi_mot_cmd_boe_1440p_dsc_682_C3D_cali_ | Target размер | CN reference размер |
|---|---:|---:|
|srgb.txt|144725|144726|
|p3.txt|143512|143565|
|pcc.txt|164|164|

`/data/vendor/display/qdcm_mode_merge_version.json` имеет500bytes.
`/data/vendor/display_config` и `/mnt/vendor/persist/demura` не наблюдались
в этом срезе. Нельзя приравнять содержимое target кCN: два размера уже различны,
равный размерPCC тоже не доказывает равенства. После уточнения offline scope
эти файлы не копировались и не сравнивались по содержимому.
Санитизированная сводка:[inventory.json](inventory.json); raw metadata private0600.

## Офлайн consumer по существующему CN reference

`reported`: `extracted/XT2611-1/W3WWL36.65-11-18/filesystems/vendor_a/lib64/libstcMotoColor.so`.
Это **не** установленное равенство текущей target библиотеки.

- `StcMotoColor::loadCalibratedParam`,VA0xad8c,size2516 конструирует paths под
  `/mnt/vendor/persist/display/` со строкой `_C3D_cali_`.
  Вызовы `read3DlutFromFile` видны по0xb454/0xb4d4/0xb558/0xb5d8;
  loader также вызывает `readPCCFromFile`, не parser DSI packets.
- `read3DlutFromFile`,0xf674,size1192: по0xf820–0xf84c читает **шесть integer
  columns** черезsscanf, по0xf85c–0xf88c кладёт24-byte records вlut3d_info;
  по0xf93c сравнивает число строк с **4913**. Это не поля DSI header/address.
- Оба reference файла независимо разобраны: по4913уникальных input triples,
  полная решётка **17×17×17**, осиfloor(4095*i/16), output triples в0…4095.
- `MotoColorRenderIntentCalibration`,0xcc60,size1096 выбирает именно
  **PostBlendGamut** (14-byte string compare0xcd8c–0xcdb4). По0xcfb4/0xcfe8
  копирует0x1cca8bytes =16-byte header+4913×24 из выбранной LUT в output
  hardware-config payload. Получатель в разобранном теле — gamut-config,
  не MIPI DDIC write.
- Reference PCC содержит3строки×11double coefficients; ненулевые диагональные
  коэффициенты0.994627594627595/0.999023199023199/1.0.
  `readPCCFromFile`,0xfb1c,size2340 — отдельный parser PCC config. Его наличие
  не является декодером emission count или разрешением менять калибровку.

Для четырёх перечисленных функций1786ARM64words свежего listing сверены с ELF.
Листинги в privatecache`ddic-ec-semantics-20261107/calibration/`.
[Validation](validation.json) сохраняет ranges и фактическую структуру таблиц.
Символические имена подкреплены dataflow/типизированными записями, не только strings.
Независимое офлайн ревью calibration/C1-выводов завершено без замечаний;
оно не устанавливает identity текущей target библиотеки и не является
аппаратной проверкой. Результат transport-проверки C1 отдельно описан в
[marker report](../ddic_state_marker_20261107/result.md).

## Ограниченный вывод

В проверенном reference пути эти calibration files — цветовые LUT/PCC, а не
найденная таблица OLED timing. Не включать digital dimming и не менять их ради
фиктивного PWM результата. Current contents/runtime applicability остаются
unknown; чтение metadata не заменяет binary identity. Весь persist/vendor
и все возможные firmware overrides этим не исключены. Частота≥2000Hz и
пригодный профиль по-прежнему отсутствуют; A9baseline и stock reference сохранены.
