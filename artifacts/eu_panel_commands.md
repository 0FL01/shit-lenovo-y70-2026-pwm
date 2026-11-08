# GLOBAL reference: XT2611-3 / RETEU W3WW36.65-64-4

Дата: 2026-10-28. Выводы об архиве — **reported**, не наблюдение live-панели.
Это **до-OTA reference**, не текущая прошивка владельца и не разрешённый backup для XT2611-1.
В 20:03 UTC read-only ADB подтвердил `W3WWS36.65-64-4-1`, kernel
`g09eda8c8505a-ab15950084`, слот `_b`:
[post_ota_display_observation.json](post_ota_display_observation.json).

## Вход и извлечение

- ZIP: `downloads/XT2611-3_AVR_RETEU_16_W3WW36.65-64-4_subsidy-DEFAULT_regulatory-DEFAULT_cid50_CFC.xml.zip`.
- **13 483 677 726 байт**, 56 entries, 16 662 381 049 bytes uncompressed.
- `.info.txt`: `motorola/avr_g/avr:16/W3WW36.65-64-4/74ded8-48cd7:user/release-keys`,
  дата `Wed Aug 5 08:52:43 CDT 2026`, MBM `avr_g-0d80517c428a-dirty-260805`.
- Kernel в `boot.img`: `6.12.58-android16-6-gb0a9599c6c01-ab14987696-4k`.
  Fingerprint/kernel совпадают с **историческим T01-снимком**, не с новой OTA.
- 7-Zip извлёк **44 выбранных entries с проверкой CRC**; весь ZIP отдельно не тестировался.
  34 sparsechunks переданы native `simg2img` в числовом порядке, не склеены как raw.
- `super.raw.img`: **21 474 836 480 logical bytes**; liblp v10.2, три metadata slots,
  `virtual_ab_device`. `AB Update Enabled: False` из `.info.txt` не описывает эту layout.
- Root: `extracted/XT2611-3/W3WW36.65-64-4/`.
  `vendor_a`, `vendor_dlkm_a`, `odm_a`, `system_ext_a`, `system_a` извлечены через
  `lpunpack` и локальный `fsck.erofs 1.7.1 --no-preserve`, без mount/root.
  Для framework-сравнения дополнительно извлечён CN `system_a` в собственном CN root.
- Пять выбранных файлов GLOBAL vendor_boot CPIO находятся в `vendor_boot_ramdisk/`;
  legacy-LZ4 ramdisk после декомпрессии — 31 759 104 байта.
  Его `msm_drm.ko` побайтово равен GLOBAL vendor_dlkm copy, но **отличается от CN**.

Происхождение, список архива и размеры разделов:
[firmware_manifest.json](firmware_manifest.json), поле `global_reference`.
Гостевые executables и flash XML не исполнялись. Product, system_b и unrelated firmware
не распаковывались. Оригинальные ZIP/chunks/raw images не удалялись.

## DTBO и штатные DC arrays

`dtbo.img`: 75 497 472 bytes с padding; DT table total **617 174**,
один DTB offset **64**, size **617 110**. Root model `avr`, compatibles
`qcom,alor-qrd`, `qcom,alor`, `qcom,qrd`; msm-id `<685 0x10000>`,
board-id `<0x46 0x9000>`. Это данные архива, не отдельное чтение hardware IDs владельца.

Все **18 DC ON/OFF arrays девяти BOE-вариантов равны CN**. Значит, и десять ILI97701A
arrays равны ранее проверенному публичному CN DTS commit
`f088523dfba85c95c15f43726fcf972c0c7a957a`.
Это не равенство всего DTBO: init/timing-switch отличаются, см. [display_diffs.md](display_diffs.md).

Offsets ниже — десятичные, абсолютные внутри GLOBAL `dtbo.img`:

| Панель | ON bytes / packets / offset | OFF bytes / packets / offset |
|---|---:|---:|
| ILI97680A 1264×2780 v1 | 534 / 50 / 342444 | 556 / 52 / 343016 |
| ILI97680A 1264×2780 v2 | 534 / 50 / 358532 | 556 / 52 / 359104 |
| ILI97680A 1264×2780 v3 | 426 / 41 / 377888 | 426 / 41 / 378352 |
| ILI97680A 1264×2780 v4 | 426 / 41 / 421488 | 426 / 41 / 421952 |
| ILI97701A 1440×3168 v0 | 426 / 41 / 460084 | 426 / 41 / 460548 |
| ILI97701A 1440×3168 v1 | 426 / 41 / 464188 | 426 / 41 / 464652 |
| ILI97701A 1440×3168 v2 | 578 / 48 / 467900 | 578 / 48 / 468516 |
| ILI97701A 1440×3168 v3 | 578 / 48 / 487712 | 578 / 48 / 488328 |
| ILI97701A 1440×3168 v4 | 875 / 75 / 512388 | 875 / 75 / 513300 |

Raw bytes, HS transfer states и ON/OFF packet differences:
[eu_panel_commands.json](eu_panel_commands.json).
Переиспользован `read_fdt`/`packets`/`inspect` из `06-tools/inspect_cn_dtbo.py`;
историческое CN-описание `scope` заменено на GLOBAL-описание в этом JSON.
Парсер не отправляет команды и не доказывает выбор варианта на телефоне.

## Совпадение с телефоном и границы

**11/11** доступных vendor-файлов GLOBAL reference совпали с сохранёнными T01
size/SHA256 observations, включая `FOSSConfig.xml`. Это конкретное binary comparison,
не новое тотальное хеширование. Core vendor ELFs нельзя было прочитать на телефоне;
их равенство с live copies не установлено. После OTA этот 11-file снимок не обновлялся.

Точные live panel ID/revision по-прежнему **unknown**; повторное чтение `panelName`,
`panelSupplier`, `panelId`, `panelVer`, `panelDC` после OTA снова дало Permission denied.
Наличие v4 и одинаковое имя калибровки не выбирают v4.

В AVB top/system одинаковые embedded public keys, но CN/GLOBAL rollback indices **0/2**,
а `signing-info.txt` сообщает HAB CID **11/50**, security version **0/2**.
Подписи и фактические rollback counters аппарата не верифицированы;
совпадение AVB key не доказывает совместимость всей boot chain или возможность downgrade.

**PWM Hz и оптический эффект таблиц — unknown.** Read-only ADB дополнительно
подтвердил Motorola Global `display_dc_mode_enabled=1`, но это не подтверждение
успешного ioctl/DSI и не оптическое измерение.
