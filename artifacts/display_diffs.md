# CN / GLOBAL: дисплейное сравнение двух архивов

## Addendum2026-11-07 — bootloader/UEFI, отдельный источник init

`reported`, [новая офлайн-проверка](uefi_panel_recon_20261107/result.md): извлечены
девять ILI97 XML из LZMA FV уже скачанных CN11/GLOBAL64 bootloader.img.
GLOBALv4:95initpackets равны actual selected timing@0 по типу/порядку/payload
и численным delay values. CNv2/v3/v4 отличаются только прежним блоком2D;
нового boot-specific PWM profile здесь нет. DisplayDxe/BacklightDxe между этими
двумя references равны вне11байт CodeView workspace каждый. Current bootloader,
DDIC NVM, whole-ROM равенство и flash-совместимость не проверялись.

## Addendum2026-11-07 — более поздний CN48-7

Дополнительно CN48 `msm_drm.ko` изCRC-verifiedvendor_boot побайтно равен модулю
сохранённогоGLOBALreferenceW3WW36.65-64-4. CurrentOTAfile отличается лишь
BuildID/localUNIQUE_IDsymbolnames; всеcode/datasections и103589resolvedRELAentries
равны. Это не основание перепрошивать модуль: инойPWMbranch не появился,
полныйROM/userspace/hardware и source-reproducibility не объявлены одинаковыми.

Новая [проверка actual CNW3WWL36.65-48-7 DTBO](cn_48_7_recon_20261107/result.md):
BOEILI97701Av4 имеет **все53 `-command` properties равными current selected DT**
(52serializedarrays+1TEu32),412общихpropertiesравны.12v4init/timing changes против
старогоCN11-18 уже находятся в currentGLOBAL. Отличаются10generatednames и3
referencefields; полный image/hardware/policy match и flash compatibility не
утверждаются. Это ослабляет региональную гипотезу именно о готовых иных v4DSI
командах, не закрывает PWM-цель. Историческое сравнение ниже сохраняет свои buildIDs.

Дата: 2026-10-28. Офлайн-результаты — **reported**; область — display stack, не весь ROM.
CN — XT2611-1 RETCN W3WWL36.65-11-18,
`extracted/XT2611-1/W3WWL36.65-11-18/filesystems/vendor_a/`.
GLOBAL reference — XT2611-3 RETEU `W3WW36.65-64-4`,
`extracted/XT2611-3/W3WW36.65-64-4/filesystems/`.
Ниже сохранено первое сравнение CN с 11 T01 observations телефона **до OTA**:
[device_inventory.json](device_inventory.json), `target_files.files`, 17:43–17:49 UTC.
Сам GLOBAL reference теперь совпал с ними **11/11**, включая FOSS.
Текущая OTA уже `W3WWS36.65-64-4-1`, kernel `g09eda8c8505a-ab15950084`, `_b`:
[post_ota_display_observation.json](post_ota_display_observation.json), read-only 20:03 UTC.
Этот ZIP не доказывает текущие driver bytes. Разные SKU и даты сборки также не
позволяют изолировать причинность региона. Суммы использованы только для binary comparison.

Пути относительно `/vendor/`:

| Файл | CN / GLOBAL байт | Результат |
|---|---:|---|
| etc/init/com.motorola.hardware.display.panel-service.rc | 133 / 133 | идентичен |
| etc/vintf/manifest/com.motorola.hardware.display.panel-service.xml | 351 / 351 | идентичен |
| etc/init/vendor.qti.hardware.display.composer-service.rc | 324 / 324 | идентичен |
| etc/vintf/manifest/vendor.qti.hardware.display.composer-service3_v4.xml | 940 / 940 | идентичен |
| etc/init/init.qti.display_boot.rc | 1741 / 1741 | идентичен |
| etc/display/qdcm_calib_data_mipi_mot_cmd_boe_1440p_dsc_682.json | 1058416 / 1058416 | идентичен |
| etc/display/panel_mipi_mot_cmd_boe_1440p_dsc_682_C3D_cali_p3.txt | 143565 / 143565 | идентичен |
| etc/display/panel_mipi_mot_cmd_boe_1440p_dsc_682_C3D_cali_pcc.txt | 164 / 164 | идентичен |
| etc/display/panel_mipi_mot_cmd_boe_1440p_dsc_682_C3D_cali_srgb.txt | 144726 / 144726 | идентичен |
| etc/display/FOSSConfig.xml | 5053 / 5053 | **отличается** |
| lib64/libqservice.so | 85416 / 85416 | идентичен |

Итого **10/11 идентичны**. Совпадение QDCM/C3D ослабляет объяснение регионального
PWM разницей в этих цветовых калибровках, но не исключает отличий DSI/driver/HAL/policy
или физической panel revision. libqservice не представляет весь display stack.

## DTBO: DC одинаков, init/timing-switch различается

Сопоставлены basename девяти BOE panel nodes и relative paths всех descendants:
**3330 properties**. `phandle` definitions исключены из сравнения значений.
Результат: **18/18 DC ON/OFF arrays идентичны**, включая все ILI97701A v0–v4.

Реальные command changes — только у **ILI97701A v2, v3, v4**:
по **12 properties**, всего **36**. У ILI97680A v1–v4 и ILI97701A v0/v1
command differences в проверенных subtrees нет.

| Timing | Режим | `on-command`, CN → GLOBAL | `timing-switch-command`, CN → GLOBAL |
|---|---|---:|---:|
| `@0` | 120 Hz | +31 bytes, +3 packets | 109/11 → 140/14 bytes/packets |
| `@1`, `@2` | 144 / 90 Hz | идентично | идентично |
| `@3` | 60 Hz | +31 bytes, +3 packets | 109/11 → 140/14 |
| `@4`, `@5` | 30 / 24 Hz | +31 bytes, +3 packets | 109/11 → 300/30 |
| `@6`, `@7` | special idle 10 / 1 groups, nominal 120 Hz | +31 bytes, +3 packets | 109/11 → 140/14 |

Для v2/v4 ON 1145/92 → 1176/95 bytes/packets; для v3 1751/133 → 1782/136.
В этих таблицах GLOBAL расширяет page **0x2d**, payload `83 xx` → `83 xx 00`,
добавляет `98 .. ..`, `99 .. ..`, `a0 .. ..`. В 30/24 Hz timing-switch дополнительно
появляются page **0x08** и **0x4f** записи с временными значениями и восстановлением.
Это сырые различия штатных последовательностей, **не расшифрованный PWM multiplier**.

Примеры абсолютных decimal offsets в соответствующем `images/dtbo.img`, v4:

| Property / relative node | CN offset | GLOBAL offset |
|---|---:|---:|
| `on-command`, `.../timing@0` | 562924 | 515520 |
| `timing-switch-command`, `.../timing@0` | 564084 | 516708 |
| `on-command`, `.../timing@4` | 570960 | 523668 |
| `timing-switch-command`, `.../timing@4` | 572120 | 524856 |

Все **36 pairs offsets/raw bytes/packet edits** с точными node paths:
[regional_dtbo_diff.json](regional_dtbo_diff.json).
Packet alignment использует точные `(page, header, payload)` tuples.

Ещё девять raw differences — `qcom,panel-supply-entries`: `0x1dd` → `0xec`.
Оба phandle разрешены в `dsi_panel_pwr_supply_urus`; все четыре nodes его subtree
равны после исключения phandle definitions. Это **перенумерация reference**,
не найденная смена питания. Других property changes в этих BOE subtrees нет;
это не утверждение о всём SoC DTBO.

## Userspace и точный FOSS delta

Семь файлов относительно `filesystems/vendor_a/` целиком побайтово одинаковы:

| Файл | Размер, байт |
|---|---:|
| `bin/hw/com.motorola.hardware.display.panel-service` | 52528 |
| `lib64/hw/displaypanel.default.so` | 52080 |
| `lib64/com.motorola.hardware.display.panel-V2-ndk.so` | 85408 |
| `bin/hw/vendor.qti.hardware.display.composer-service` | 393456 |
| `lib64/libsdmcore.so` | 964040 |
| `lib64/libsdmextension.so` | 2590928 |
| `lib64/libqservice.so` | 85416 |

Размеры/build IDs и T01 comparison: [native_display_diff.json](native_display_diff.json).
`vendor_a/etc/display/FOSSConfig.xml:27` имеет единственный text delta:

```diff
- <LutUpdateSpeedOutput units='uint'>8 8 8 8</LutUpdateSpeedOutput>
+ <LutUpdateSpeedOutput units='uint'>3 3 3 3</LutUpdateSpeedOutput>
```

Связь параметра LUT update с OLED PWM Hz **не установлена**.
`bin/init.qti.display_boot.sh`, `bin/init.mmi.display.sh`, `etc/sensors/als_comp_config.xml`
идентичны. В 96/97 выбранных display/SF build properties три delta:
`persist.sys.sf.specified_feature_enabled` enabled → disabled,
`persist.sys.sf.specified_feature_id` 30022 → 30040,
добавлен `debug.sf.danmaku_weight_threshold=20`. Их PWM-семантика **unknown**;
точные файлы/строки — в native JSON. Display-named файлов в ODM не найдено;
это не exhaustive content audit каждого ODM binary.

Проверенные Java handlers `DisplayDCMode`, Motorola Global cache, `PanelsService`
и его DC lifecycle имеют одинаковые symbolically resolved instruction flows в CN/GLOBAL.
Обе vendor RRO разрешают `config_moto_display_dc_supported`; base framework bool false.
APK/JAR целиком **не** объявляются идентичными. JNI мост разобран на GLOBAL;
его сравнение с CN system ELF не выполнено. См. [driver_callgraph.md](driver_callgraph.md).

## Модуль, source match и boot chain

| Параметр | CN | GLOBAL reference |
|---|---|---|
| Kernel release suffix | `g18b507169406-ab14630870` | `gb0a9599c6c01-ab14987696` |
| msm_drm.ko bytes | 6075488 | 6071656 |
| ELF build ID | `13232a6fe74b761626ed9c14ee2f59b68ca46504` | `8c58ca326e99f7c98644d723230b40a7686dee81` |

Внутри каждого ROM vendor_boot и vendor_dlkm copies равны. Между ROM модуль разный,
несмотря на одинаковый `6.12.58-android16-6-maybe-dirty-4k` vermagic.
У восьми functions равны **relocatable instruction bytes**: `panelDC_show`,
`dsi_panel_send_param_cmd`, `dsi_display_set_param`, `dsi_panel_set_param`,
`msm_ioctl_set_panel_feature`, `dsi_host_transfer_sub`, `dsi_panel_enable`,
`sde_connector_atomic_set_property`. Это отдельно не доказывает равенства relocation
targets, referenced data или всего поведения.
`sde_kms_set_panel_feature` — 488 → 588 bytes: дополнительная GLOBAL cache-ветка
для `param_idx=0` при выключенном command path. DC по-прежнему может только
кэшировать `param_idx=3`/ненулевой value без DSI. VA/file offsets — в native JSON.

Десять ILI97701A DC arrays совпадают с pinned CN DTS; это ограниченный source/data match.
Exact `MMI-W3WW36.65-64-4` GitHub tag-prefix queries дали HTTP 200 / `[]` в
display-devicetree и techpack-display; это не исключает других tags/branches.
Полного build/KMI/source match нет, особенно для новой OTA.

`avbtool info_image`: в обоих ROM top/system `SHA256_RSA4096`, embedded public key bytes
равны; tool key ID `27bcbab040b154eecdce885d6c0e6283cee9c227` — идентификатор,
не проверка подписей. Rollback indices **CN 0 / GLOBAL 2**, flags 0;
chained vbmeta_system location 2. HAB metadata: **CID 11 / 50**, security version **0 / 2**.
На аппарате ранее fastboot сообщил CID 11. Target fuse/rollback counters,
все firmware signers и cross-SKU compatibility — **unknown**.

## Ранжирование

1. **Highest-confidence byte finding:** init/timing-switch v2–v4 различаются при равном DC.
   **Hypothesis:** возможен эффект на waveform/переходы. Нужны live revision, datasheet
   или оптика; это может быть build-age fix, не региональная policy. Наугад не переносить.
2. **Secondary:** FOSS LUT update delta; оптическая причинность не измерена.
3. **Unattributed:** SF feature properties и остальные module/kernel differences
   не доказаны PWM-регуляторами.
4. **Ослаблены:** разные DC arrays, QDCM/C3D или семь проверенных vendor ELFs
   как причина различия между этими двумя архивами — они одинаковы.

Нет доказанного соответствия register value → optical Hz. XT2611-3 — только offline
reference, не flash-compatible image и не проверенный backup XT2611-1.
DSI-записей, переключения настроек и перепрошивки этим сравнением не выполнялось.
