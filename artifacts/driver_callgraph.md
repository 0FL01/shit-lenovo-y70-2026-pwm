# Flicker prevention: static GLOBAL chain и runtime-блокеры

## Addendum2026-11-07 — brightness policy, current userspace

[Проверенный разбор](brightness_policy_recon_20261107/result.md): target digital
dimming LUT не достигает panelDBV; ctrl/min_bl вызывают DRM event notification,
не DSI. Current `libsdmclient::CommitOrPrepare`0xa1258 вычисляет `dolby present`,
при смене bool →core0x8e534→DAL0x3c7d0→ioctl0x4008649b `{id=0,val}` →target
`msm_ioctl_set_moto_drm_command`0x1d6110→KMS0xd285c→display0x1a06fc→panel0x1c3ec4
→`dobly_enable`. APL ON требуетDBV>16000 иDolby0; overlappingHBMpayload неPWMmap.
Userspace ELF identities проверены отдельно; actual вызов/оптический эффект не наблюдались.

Current SurfaceFlinger0x2a5574 обновляетspecialIdleFlag; loadedthresholds0/9999999,
flag1 подтвержденыread-onlydump. Modefilter0x25d438 связываетflag1/2 сgroupbit3/4,
nominal120idle1/10 nodes ведут к настоящим targettimingcommandsets. Это не
измерение liveDDIC1Hz/PWM. Архивные5base+5selectorholds не содержатновыхDSIwrites;
A9baselineсохраняется. В этих ветках отдельный≥2000Hzsetter не найден.

## Addendum 2026-11-07 — actual target-module DC/PWM branches

`reported`, offline target-ELF verified: [annotated binary analysis](runtime_pwm_recon_20261107/result.md)
closes the narrower current-module question: `dsi_panel_set_param(index3)` →
`dsi_panel_send_param_cmd` → existing two-state OFF/ON map → `dsi_host_transfer_sub`.
Native positive DC values≥2 clamp to1, not frequency multiplication. Linux PWM
calls exist only in backlight type0; the selected live `bl_ctrl_dcs` becomes type2
and bypasses them. This is target-binary evidence, not a claim that the entire CN
source matches current OTA. Historical sections below retain their dated scope;
current root/panel/optical state is in WORKSTATE. A9-only remains an intermediate
optical baseline, and physical ≥2000Hz is not established.

Текущий checkpoint2026-11-06 13:49: **stock UI → provider0/1 → panelDC0/1 → полные
75-packet DC ON/OFF sets наблюдались на цели**. Native parameter returns0, real DBV
5197/2839 и software mode120Hz; [trace analysis](stock_dc_trace_analysis_20261106.json),
[scope/cleanup](stock_dc_trial_20261106.json). Предположение о недостижении DSI
отвергнуто для этого опыта; optical Hz/effect ещё unknown. Детализированный middle-hop
static code ниже остаётся reference evidence, не полный current framework source match.
Карта кандидатов и границы: [DC/EM analysis](dc_transition_recon_2026-11-06.md).

Исторический static analysis от 2026-10-28 — **reported**, GLOBAL reference
`XT2611-3/W3WW36.65-64-4`, root `extracted/XT2611-3/W3WW36.65-64-4/filesystems/`.
Закрыт AIDL-путь reference build, не доказано его выполнение на текущей OTA.
Исторические target observations: [device_inventory.json](device_inventory.json).
В 20:03 UTC read-only подтверждены новая `W3WWS36.65-64-4-1`, kernel
`g09eda8c8505a-ab15950084`, `_b` и сохранённый DC key = 1:
[post_ota_display_observation.json](post_ota_display_observation.json).

## Цепочка и границы доказательств

```text
CoreSettingsExt DisplayDCMode.onSwitchCheckedChanged(boolean)
  -> MotorolaSettings.Global.putInt("display_dc_mode_enabled", 0/1)
  -> MotorolaSettingsProvider PUT_global -> Global store -> notifyChange
  -> PanelsService observer -> updatePanelMode -> setDcMode_native(int)
  -> libandroid_servers.so -> system IDisplayPanel AIDL V1
  -> vendor IDisplayPanel AIDL V2 -> panel-service -> displaypanel.default.so
  -> setParam(PARAM_DC=3, value=0/1) -> DRM ioctl 0xc008649f
  -> msm_ioctl_set_panel_feature -> sde_kms_set_panel_feature
  -> dsi_display_set_param -> dsi_panel_set_param -> DC table -> DSI

current setting=1                      [confirmed-on-target, post-OTA]
runtime branch/module/success/DSI       [unknown; no controlled toggle/tracing]
exact live panel/revision, optical Hz  [unknown]
```

`panelDC` **не управляющий вход**: отдельный read-only индикатор panel->dc_state,
не setter и не чтение аппаратного регистра.

## UI → provider → system-server

Offsets здесь — **byte offsets внутри указанного DEX entry**, не APK/JAR offsets.
Invokes/fields проверены disassembly и разрешением DEX references. Проверенные
DC controller/consumer instruction flows CN/GLOBAL совпадают символически;
APK/JAR целиком не объявляются одинаковыми.

| GLOBAL файл / метод | Ключевое доказательство |
|---|---|
| `system_ext_a/priv-app/CoreSettingsExt/CoreSettingsExt.apk!classes.dex`, `DisplayDCMode.getKey` | code_item `0x262918`, tile key `display_dc_mode` |
| тот же DEX, `DisplayDCMode.onSwitchCheckedChanged(Z)` | code_item `0x262890` → Companion setter, затем true |
| `DisplayDCMode$Companion.setDisplayDCModeChecked(Context,Z)` | `0x262826` key `display_dc_mode_enabled`; `0x26282a` invoke MotorolaSettings.Global.putInt(...):Z, результат игнорируется |
| `system_a/system/framework/moto-settings.jar!classes.dex`, `Global.putInt` | code_item `0x4350`; `0x4368` → putString → NameValueCache |
| `Global.<clinit>` / `NameValueCache.putStringForUser` | `0x451c` URI `content://com.motorola.android.providers.settings/global`; `0x4546` PUT_global / `0x454e` GET_global; `0x47c6` IContentProvider.call |
| `system_ext_a/priv-app/MotorolaSettingsProvider/MotorolaSettingsProvider.apk!classes.dex`, `MotorolaSettingsProvider.call` | `0xcd24` PUT_global → r(...); `0xd18c` → a.l.i(...), Global/user 0 |
| тот же DEX, `a.l.i` → `a.l.m` → `a.l.n` / `a.j.handleMessage` | `0x9c78` изменение записи, `0x9ca6` notification; Global branch `0xa21a`; `0x7fca` ContentResolver.notifyChange |
| `system_a/system/framework/services.jar!classes3.dex`, `PanelsService.setUpObserver` | `0x2d0c26` registerContentObserver на Global URI/key, user 0 |
| `PanelsService$1.onChange` / `onDcModeEnabledChanged` | key comparison `0x2cecb6`; `0x2cecc8` → consumer; `0x2d0836` getInt(key,0); `0x2d08a4` enqueue при изменении |
| `PanelHandler.handleMessage` / `updatePanelMode` | what=1 → update; `0x2d1120` invoke-static setDcMode_native(I)V; `0x2d1126` запись software cache |

Это **не AOSP Settings.Global**, не property и не private preference.
Library `moto-settings` привязана к реальному JAR через
`system_a/system/etc/permissions/moto-settings.xml:17–19`.
`Global.getUriFor(key)` использует Uri.withAppendedPath (`0x4d70`).
Provider перед записью проверяет custom `com.motorola.permission.WRITE_SECURE_SETTINGS`;
permissions для исследования не менялись.

Controller metadata связывает `dc_mode_title` с **Flicker prevention**, CN локализация
`防屏闪模式`. Gate — `android:bool/config_moto_display_dc_supported`.
GLOBAL framework-res base resource `0x0111024f` false, vendor static RRO
`framework-res__avr_g__auto_generated_rro_vendor.apk` задаёт true (`0x7f020011`).
CN RRO также true. Этот же framework bool читает PanelsService (`0x2d009e–0x2d00ac`).
Эффективный runtime RRO владельца отдельно не измерен.

### DC gating / lifecycle reference Java

Штатный UI пишет 0/1, constants OFF=0 / ON=1; consumer нормализует через `>0`.
В updatePanelMode:

```text
dc = mCurrentDcModeSettings
fodPriority = (mFingerPrintHighBright || mFingerPrintHighBrightSettings)
              && mDisplayPowerMode == POWER_MODE_NORMAL(2)
if !fodPriority && primary STATE_OFF(1)
   && (!mSupportCli || CLI STATE_OFF(1)):
    dc = 0
if mDcModeSupport:
    setDcMode_native(dc)
    mCurrentDcMode = dc
```

DC source — `0x2d0d6a`, OFF branch — `0x2d0f16–0x2d0f48`, support check — `0x2d10e8`.
FOD priority означает, что OFF не безусловно выключает DC. Brightness threshold и
частота в Гц в этой DC-ветке отсутствуют; обычные HBM/video/doze затрагивают соседний
generic mode, но сами здесь не переназначают DC. CLI condition описывает код,
не утверждает наличие CLI на XT2611-1.

systemReady ставит observer и делает initial update (`0x2d0d20`); display-state changes
ставят новый update (`PanelsService$3`, `0x2ceefc`), не стирая requested setting.
`sendUpdatePanelMode(0)` — delay 0 ms, **не DC OFF**. Battery-saver callback также
инициирует пересчёт. Это не подтверждение downstream native success.

## JNI → AIDL → hardware module

Далее адреса — **ELF VA**, runtime требует load bias. Build IDs и bridge metadata:
[native_display_diff.json](native_display_diff.json).

| GLOBAL reference участок | Доказательство |
|---|---|
| `system_a/system/lib64/libandroid_servers.so` | SystemServer загружает android_servers; JNI_OnLoad `0xcf9b4` → register PanelsService `0xc72fc` через проверенный PLT/GOT |
| register function | FindClass `com/motorola/server/display/PanelsService`; RegisterNatives array `0xec580`, count 6 |
| JNI entry `0xec5e0` | name `0x2cf8e`=`setDcMode_native`, signature `0x3529d`=`(I)V`, function `0xc81e0` |
| native `0xc81e0` | `0xc81fc`: w2→w19; getPanelAidl; `0xc8248`: w19→w1; slot +0x48; `0xc8260` blr |
| system `com.motorola.hardware.display.panel-V1-ndk.so` | BpDisplayPanel vptr `0x10018`, slot `0x10060` resolves to setDcMode `0x8f60` |
| V1 setter | `0x8fb4–0x8fb8` AParcel_writeInt32 исходного enum; `0x9020` transaction 4; `0x9028` transact |
| vendor V2 `panel-V2-ndk.so` | onTransact `0x8578`, case 4: readInt32 `0x8710`, тот же int→w1 `0x8720`, slot +0x48 → handler |
| vendor `panel-service` | vptr `0x8048`, slot `0x8090` → impl::DisplayPanel::setDcMode `0x56fc`; main регистрирует /default (`0x4774`) |
| service constructor / setter | hw_get_module(displaypanel) `0x4f08`, open(primary_panel) `0x4f80`; device this+0x50; setter вызывает device function +0x88 (`0x5740`), enum без преобразования |
| `displaypanel.default.so` glue | open_panel `0x4020` сохраняет set_dc_mode=`0x419c` в device+0x88; `0x41cc` → stub/GOT → PanelMode::setDcMode `0x4760` |

**V1 client и V2 service — разные ABI libraries**: system setter `0x8f60`, vendor V2
client counterpart `0x900c`. Transaction 4 — static RE evidence, **не инструкция
вызвать её на телефоне**.

V1 vtable slot `0x10060` имеет raw QWORD **0**: `.rela.dyn` — Android **APS2 packed RELA**,
offset `0x3a68`, size `0x277`; запись offset `0x10060`, info `0x4000000101`,
R_AARCH64_ABS64, symbol 64 (setDcMode, value `0x8f60`), addend 0.
Packed поток из 115 записей разобран отдельно: обычный readelf listing его не показал.
Service slot `0x8090`, напротив, хранит raw `0x56fc` и покрыт RELR.
Raw slot bytes нельзя отождествлять с relocated runtime pointer.

getPanelAidl (`0xc6e54`) строит descriptor + /default, проверяет declaration,
вызывает waitForService/fromBinder и кэширует interface. Если получить AIDL не удалось,
есть резервная HIDL 1.1 ветка; её runtime-выбор не исследован. Ошибка уже выполненного
AIDL setter **не вызывает HIDL fallback**.

### Acknowledgement и ошибки

- UI игнорирует boolean putInt; provider acknowledgement не подтверждает panel operation.
- При отсутствии hardware device/function service возвращает service-specific -22.
  После HAL call он сохраняет int return и создаёт OK Binder status, даже если HAL int отрицателен.
- JNI после AIDL setter только удаляет AStatus (`0xc8268`): не проверяет AStatus_isOk,
  не читает int output и не возвращает результат Java (`void`).
- Поэтому mCurrentDcMode — **software cache запроса**, не подтверждение ioctl/DSI.

`confirmed-on-target`, компоненты существуют независимо от неизвестных стрелок:

| Компонент | Доказательство |
|---|---|
| Motorola panel HAL AIDL v2 | `service list`: `com.motorola.hardware.display.panel.IDisplayPanel/default`; `/vendor/etc/vintf/manifest/com.motorola.hardware.display.panel-service.xml`, строки 7–9 |
| panel init service | `/vendor/etc/init/com.motorola.hardware.display.panel-service.rc`, строки 1–4: `panel-aidl-service`, executable `/vendor/bin/hw/com.motorola.hardware.display.panel-service`, user/group `system`; `init.svc.panel-aidl-service=running` |
| Qualcomm Composer AIDL v4 | `/vendor/etc/vintf/manifest/vendor.qti.hardware.display.composer-service3_v4.xml`, строки 7–9; `android.hardware.graphics.composer3.IComposer/default` в `service list` |
| QTI config AIDL v13 | тот же manifest, строки 21–23; `vendor.qti.hardware.display.config.IDisplayConfig/default` в `service list` |
| composer init service | `/vendor/etc/init/vendor.qti.hardware.display.composer-service.rc`, строки 1–4: user `system`, group `graphics drmrpc` |
| kernel display module | `/proc/modules`: `msm_drm`; symlink `9800000.qcom,mdss_mdp/driver/module` → `/sys/module/msm_drm` |
| DRM panel metadata/DC endpoint names | `/sys/class/drm/card0-DSI-1/` перечисляет `panelName`, `panelSupplier`, `panelId`, `panelVer`, `panelDC`; значения недоступны shell |
| vendor module directory | `/vendor/lib/modules` → `/vendor_dlkm/lib/modules`; доступ к содержимому `msm_drm.ko` запрещён |

SHA256 и размеры исходных RC/XML и доступных display-конфигов сохранены в inventory.
Содержимое `panel-service`, `composer-service`, `libsdmcore.so`, `libsdmextension.so`
недоступно на аппарате. CN/GLOBAL reference copies доступны офлайн и семь проверенных
vendor ELFs равны, но не объявляются равными live copies после OTA.

## Native implementation — reported, CN source

Motorola kernel-msm-5.4-techpack-display, tag **MMI-W3WWL36.65-11-18**,
commit **fa008c43c070ff20faa33853649f5dfd4c427e99**.
[Annotated tag](https://api.github.com/repos/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/git/tags/f0357a11a2c3ca0c749ea2717a49d6989c9243dd)
проверен, unsigned, message «Avr push for Android 16».

```text
DRM connector property "DC"
 -> sde_connector_atomic_set_property -> _sde_connector_update_param
 -> dsi_display_set_param
либо DRM_IOCTL_SET_PANEL_FEATURE { PARAM_DC=3, value }
 -> msm_ioctl_set_panel_feature -> sde_kms_set_panel_feature -> dsi_display_set_param

-> dsi_panel_set_param(PARAM_DC_ID) -> dsi_panel_set_dc -> dsi_panel_send_param_cmd
-> param_cmds[PARAM_DC_ID].val_map[value].cmds
-> dsi_panel_tx_send_param_cmd -> dsi_host_transfer_sub -> DSI controller transfer
```

| Участок | Pinned source |
|---|---|
| Property DC / dispatch | [sde_connector.c:4077–4126](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/sde/sde_connector.c#L4077-L4126), [2773–2780](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/sde/sde_connector.c#L2773-L2780) |
| Ioctl handler | [msm_drv.c:1994–2024](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/msm_drv.c#L1994-L2024) |
| Display / panel setter | [dsi_display.c:338–357](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/dsi/dsi_display.c#L338-L357), [dsi_panel.c:1728–1795](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/dsi/dsi_panel.c#L1728-L1795) |
| Выбор / lock / отправка | [dsi_panel.c:1396–1507](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/dsi/dsi_panel.c#L1396-L1507) |
| 0=OFF, 1=ON / parser | [dsi_panel.c:123–130](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/dsi/dsi_panel.c#L123-L130), [6361–6448](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/dsi/dsi_panel.c#L6361-L6448) |

Побайтово одинаковый CN/GLOBAL displaypanel.default.so подтверждает ioctl branch:
setDcMode `0x4760` → setParam `0x428c` → ioctl `0xc008649f`, index 3, support flag check.
Mode table: arg 0 → entry `0x8108`, name OFF (`0x1238`), kernel value 0 (`0x8118`);
arg 1 → entry `0x8120`, name ON (`0x1552`), kernel value 1 (`0x8130`). Инверсии нет.
PLT labels objdump сдвинуты: проверены stub → GOT → relocation. SetParam stub
`0x5220` → GOT `0x8450`; ioctl stub `0x5370` → GOT `0x84c0`.
Исходный binary разбор: [cn_panel_commands.md](cn_panel_commands.md).

### State и lifecycle

- Sender использует panel_lock, требует initialized panel/command set, пропускает
  повторное значение, обновляет software state после успешного sender.
- [panelDC_show, dsi_display.c:7227–7247](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/dsi/dsi_display.c#L7227-L7247)
  печатает поле структуры; DEVICE_ATTR_RO(panelDC) на L7388.
- [sde_kms.c:4832–4868](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/sde/sde_kms.c#L4832-L4868)
  при !panel_send_cmd может кэшировать ненулевой DC **без DSI**: panelDC=1 не доказывал бы эффект.
- [dsi_panel.c:8960–8972](https://github.com/MotorolaMobilityLLC/kernel-msm-5.4-techpack-display/blob/fa008c43c070ff20faa33853649f5dfd4c427e99/msm/dsi/dsi_panel.c#L8960-L8972)
  повторно применяет OFF → ON при enable и сохранённом dc_state как sync workaround.
- В DC setter нет доказанного PWM multiplier по brightness/refresh; HBM имеет отдельный
  setter, FPS on/timing-switch — отдельные dimming-related записи, например
  [v4 DTS:880–907](https://github.com/MotorolaMobilityLLC/kernel-display-devicetree/blob/f088523dfba85c95c15f43726fcf972c0c7a957a/display/dsi-panel-mot-boe-ili97701A-682-1440x3168-dsc-cmd-common_v4.dtsi#L880-L907).

## Что пока нельзя заключать

- Поиск ключей `flicker`, `dimm`, `pwm`, low-light, anti и отдельного компонента `dc`
  в AOSP `settings list system/secure/global` не дал кандидатов: используется
  **другой Motorola provider**. Post-OTA GET_global вернул Bundle[{value=1}].
  Значение подтверждает storage, не native success или оптический эффект.
- Свойства `vendor.display.disable_stc_dimming=1`,
  `vendor.display.disable_sdr_dimming=0` и brightness-related boost не доказывают
  частоту PWM и не отождествлены с Flicker prevention.
- Узел `panelDC` не читался успешно и не изменялся. Наличие узла не доказывает,
  какие DSI-команды отправляются на этой сборке.
- DC arrays равны обоим архивам и pinned CN DTS, но init/timing-switch различаются.
  Их выбор на текущей OTA и точная panel revision — `unknown`.

Далее: сопоставить текущую OTA с source/stock, получить live panel proof, затем
read-only снимки до/после намеренного ручного переключения владельцем и оптика.
Переключатель не менялся, логи DSI не включались, оптический эффект не измерялся.
Закрытый reference AIDL callgraph не заменяет эти доказательства.
