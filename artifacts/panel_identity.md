# Панель владельца: выбранный live-профиль и границы идентификации

## Текущий результат — 2026-11-06, 12:21–12:26 UTC

`confirmed-on-target`, после постоянного KernelSU-Next root:

| Наблюдение | Значение |
|---|---|
| sysfs panelName | `boe_ili97701A_682_1440x3168_dsc_cmd_v4` |
| panelSupplier / panelId / panelVer | `boe` / `0xd2` / `0` |
| msm_drm dsi_display0 | `qcom,mdss_dsi_mot_boe_ili97701A_682_1440x3168_dsc_cmd_v4:` |
| выбранный live DT | `/soc/qcom,mdss_mdp@9800000/qcom,mdss_dsi_mot_boe_ili97701A_682_1440x3168_dsc_cmd_v4` |

[Root-снимок](panel_live_20261106.json), [425 свойств выбранного subtree](device_tree/selected_boe_v4_acquisition.json),
[сравнение](device_tree/selected_boe_v4_comparison.json). Все 53 сопоставленных command arrays
равны GLOBAL reference; DC ON/OFF по875B равны также CN v4. Это идентификация
**активного программного профиля**, не измерение DDIC/PWM и не final DSI trace.
`v4` не объявляется независимо считанной silicon revision; `panelVer=0` оставлен
как software observation. ID `0xd2` не адрес DDIC-регистра. Exact physical revision
и частота свечения пока `unknown`; выбирать другую ревизию теперь не требуется.

Экран при чтении OFF: brightness0/bl_power4/panelDC0. Motorola GET_global вернул
`value=null` после wipe, поэтому историческое сохранённое значение1 не текущее.
PanelCellId/PCD/register nodes не читались, DSI-настройки не менялись.
Дальнейшая карта DC/EM-кандидатов: [dc_transition_recon_2026-11-06.md](dc_transition_recon_2026-11-06.md).

## Исторический unprivileged RECON — 2026-10-28

Сбор: **2026-10-28, 17:43–17:49 UTC**, повтор panel reads после OTA — **20:03 UTC**;
авторизованный ADB, обычный `shell`.
Машиночитаемые значения, команды и SHA256: [device_inventory.json](device_inventory.json).
Новый снимок: [post_ota_display_observation.json](post_ota_display_observation.json).

### Результат до root

**Точная установленная панель, IC и ревизия — `unknown`.**
**Кандидат — `hypothesis`: BOE ILI97701A / `mipi_mot_cmd_boe_1440p_dsc_682`.**
Нельзя выбирать конкретную таблицу `v0`–`v4` или DSI-профиль по имени калибровочного файла.

## Что прочитано на аппарате

Все пункты здесь имеют статус `confirmed-on-target` именно как программные наблюдения:

- `getprop ro.boot.hardware.sku` → `XT2611-1`;
  `getprop ro.boot.hardware.revision` → `pvt`.
- В исходном T01-снимке установлена глобальная `W3WW36.65-64-4`, модель Android `motorola edge 70 max`,
  `ro.product.name=avr_g`, `ro.carrier=teleu`.
- `dumpsys display` сообщает **1440×3168**, режимы примерно **24/30/60/90/120/144 Гц**.
  SurfaceFlinger сообщает command mode и `MaxBrightness:16180` в секции SDM.
  Во время display-dump экран был **OFF**; сохранённый active mode 120 Гц не доказывает
  физическую частоту сканирования выключенного экрана и тем более частоту PWM.
- В `/vendor/etc/display/` есть `qdcm_calib_data_mipi_mot_cmd_boe_1440p_dsc_682.json`
  и три одноимённых C3D-калибровки `p3`, `pcc`, `srgb`.
  JSON действительно прочитан и содержит ключ `mipi_mot_cmd_boe_1440p_dsc_682`;
  SHA256 всего файла — `bda2618a08c53244d90a913c167d40ba386e954f02737ef6423bf79e735ca1db`.
  Это подтверждает наличие конфигурации в ROM, **не её выбор для данного экземпляра**.
- `SurfaceFlinger --display-id` сообщает `pnpId=QCM`, пустое `displayName`.
  Эти generic-данные Qualcomm не идентифицируют OLED-контроллер.
- DRM-коннектор: `/sys/class/drm/card0-DSI-1` →
  `/sys/devices/platform/soc/9800000.qcom,mdss_mdp/drm/card0/card0-DSI-1`.
  Backlight: `/sys/class/backlight/panel0-backlight`.
  Ссылка `9800000.qcom,mdss_mdp/driver/module` разрешается в `/sys/module/msm_drm`;
  `/proc/modules` независимо показывает загруженный `msm_drm`.

## Почему появился кандидат ILI97701A

Статус следующего сопоставления — `reported`: публичные CN исходники.
Теперь доказано ограниченное равенство десяти DC-массивов с CN stock DTBO и
GLOBAL reference `W3WW36.65-64-4`. Это не выбирает live revision и не устанавливает
равенство с текущей после OTA `W3WWS36.65-64-4-1`.

Motorola `kernel-display-devicetree`, тег `MMI-W3WWL36.65-11-18`,
commit **`f088523dfba85c95c15f43726fcf972c0c7a957a`**:

- [`Kbuild:8`](https://github.com/MotorolaMobilityLLC/kernel-display-devicetree/blob/f088523dfba85c95c15f43726fcf972c0c7a957a/Kbuild#L8)
  связывает `CONFIG_AVR_DTB` с AVR display overlay.
- [`display/alor-sde-display-avr.dtsi:6–16`](https://github.com/MotorolaMobilityLLC/kernel-display-devicetree/blob/f088523dfba85c95c15f43726fcf972c0c7a957a/display/alor-sde-display-avr.dtsi#L6-L16)
  включает и ILI97680A 1264×2780, и ILI97701A 1440×3168, с несколькими ревизиями.
- [`display/dsi-panel-mot-boe-ili97701A-682-1440x3168-dsc-cmd-common_v4.dtsi:13–17`](https://github.com/MotorolaMobilityLLC/kernel-display-devicetree/blob/f088523dfba85c95c15f43726fcf972c0c7a957a/display/dsi-panel-mot-boe-ili97701A-682-1440x3168-dsc-cmd-common_v4.dtsi#L13-L17)
  содержит `mipi_mot_cmd_boe_1440p_dsc_682` и supplier `boe`.
  Там же [`строки 74–230`](https://github.com/MotorolaMobilityLLC/kernel-display-devicetree/blob/f088523dfba85c95c15f43726fcf972c0c7a957a/display/dsi-panel-mot-boe-ili97701A-682-1440x3168-dsc-cmd-common_v4.dtsi#L74-L230)
  содержат `dc-off-command` / `dc-on-command`.

Совпадение разрешения и имени конфигурации делает это направлением поиска,
но не доказывает ни `v4`, ни наличие программируемого множителя PWM на аппарате.
`pvt` — ревизия hardware из boot-свойства, не ревизия панели.

## Исторический блокер прямой идентификации — снят root-чтением выше

`confirmed-on-target`: каталог DSI перечисляет `panelName`, `panelSupplier`,
`panelId`, `panelVer`, `panelDC`, однако `cat` каждого возвращает **Permission denied**.
Чтение `dsi_display0/1`, содержимого Device Tree, `/proc/cmdline`, `/proc/bootconfig`
и `dmesg` также запрещено. Полный список попыток — в `access_limits` inventory.
Наличие имени узла не означает доступность его значения.

Штатный `dumpsys` Motorola `IDisplayPanel/default` вернул `FAILED_TRANSACTION`;
QTI `IDisplayConfig/default` — пустой ответ. Номера binder-транзакций не угадывались.
`panelCellId` намеренно не читался; panel register/PCD-узлы не использовались.

## Региональное сравнение и оставшийся блокер

Оба архива разобраны: присутствуют все пять ILI97701A v0–v4; все их DC arrays равны.
При этом init/timing-switch отличаются только у v2/v3/v4. Это **не доказывает,
что на телефоне выбран один из них**, и не позволяет выбрать профиль по разрешению.
См. [GLOBAL inventory](eu_panel_commands.md), [сравнение](display_diffs.md).

После OTA read-only снимок подтверждает `W3WWS36.65-64-4-1`, kernel
`g09eda8c8505a-ab15950084`, слот `_b`, Motorola Global DC key = 1.
Все пять `panelName/Supplier/Id/Ver/DC` reads снова возвращают **Permission denied**.
Настройка не раскрывает ID и не является hardware readback.

Требовавшиеся boot-selection/live DT данные теперь получены — см. текущий результат
выше. Это не разрешает перенос XT2611-3 DTBO или неизвестных DDIC команд.

**Оптическая частота PWM — `unknown`.** Изменений яркости, refresh, Flicker prevention,
SELinux, загрузчика, разделов и DSI-команд при сборе не выполнялось.
