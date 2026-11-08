# PWM-исследование: региональное сравнение и текущий no-go

## Текущий addendum2026-11-07 — R3 active

Постоянный root и softwarepanel identity давно подтверждены; A9-only остаётся
экспериментальным улучшением fine-компоненты, **не PWM≥2000Hz**.
[Current brightness/LTPO reverse](brightness_policy_recon_20261107/result.md)
закрыл userspaceDolby→APLgate иSurfaceFlingeridlepolicy, выявилотброшеннуюDBVLUT;
generic dimming/refresh нельзя выдавать за частоту OLED. Read-onlyсверка5ELF и
policy не меняла настройки. Независимые code/model ревью прошли.

[Новый CN48-7 DTBO](cn_48_7_recon_20261107/result.md), ранее не сравнивавшийся:
все52BOEv4serializedcommandarrays+TEscalar равны currentselectedDT,412properties
равны. Не найден готовый иной regionalv4profile; не доказана невозможность DDIC.
Нет новыхDSI/flash/reboot, A0D1C1unapproved/unrun. Исторический no-go ниже не
превращается в завершение цели и не восстанавливает уже устранённые access blockers.

Актуализация2026-11-06: **постоянный KernelSU-Next root подтверждён**, live BOE
ILI97701A cmd_v4/ID0xd2 и выбранный DT получены. Прежние root/panel-access blockers
ниже исторические; неизвестны register→Hz и optical effect. Проверенная наводка
BOE CN119811288A, ordered DC/revision comparison и следующий stock опыт — в
[DC/EM analysis](dc_transition_recon_2026-11-06.md); root/rollback proof — в
[source inventory](source_inventory.md). PWM пока не изменён, цель не закрыта.

Исторический отчёт от 2026-10-28. Область: CN XT2611-1 `W3WWL36.65-11-18` и GLOBAL XT2611-3
`W3WW36.65-64-4`. GLOBAL уже **до-OTA reference**: current read-only snapshot в
20:03 UTC подтверждает `W3WWS36.65-64-4-1`, `g09eda8c8505a-ab15950084`, `_b`.
Это не завершение всей PWM-задачи и не разрешение device writes.

## Доказательства и пределы

- **reported**: CN ROM содержит ILI97701A 1440×3168 v0–v4 и разные DC profiles;
  все десять ON/OFF массивов побайтово равны опубликованному CN DTS.
- **reported**: найден точный CN-tagged native display driver в отдельном
  kernel-msm-5.4-techpack-display, commit fa008c43c070ff20faa33853649f5dfd4c427e99.
  Название 5.4 не определяет kernel version: CN boot содержит Linux 6.12.58.
- **reported**: все 18 BOE DC ON/OFF arrays одинаковы между архивами, но 36 init/timing
  properties у ILI97701A v2/v3/v4 различаются: page 0x2d и low-refresh записи.
  Это реальный кандидат для проверки, **не найденная частота PWM**. Регион, дату сборки
  и ревизию панели пока нельзя разделить причинно.
- **reported**: семь ключевых vendor ELFs побайтово одинаковы; Java DC handlers и
  lifecycle совпадают символически. Единственный FOSS XML delta — `LutUpdateSpeedOutput`
  8 → 3. Сам msm_drm/kernel различается; восемь равных instruction bodies не доказывают ABI/KMI.
- **reported**: static GLOBAL reference chain закрыта: Motorola Global key → provider
  notification → PanelsService → JNI → system AIDL V1 → vendor V2 → legacy HAL
  → DRM DC ioctl → panel command table. Штатное значение 0/1 не инвертируется.
  Java/JNI кэшируют запрос, но native ошибки не становятся подтверждённым результатом UI.
- **reported**: GLOBAL fingerprint/kernel и 11 доступных vendor-файлов совпали с T01
  **до OTA**, не автоматически с текущим образом. Подробности в `display_diffs.md`.
- **confirmed-on-target**, post-OTA read-only: настоящий Motorola Global key
  `display_dc_mode_enabled=1`; все пять `panelName/Supplier/Id/Ver/DC` reads снова
  permission-denied. Сохранённая настройка не доказывает успешный ioctl/DSI или PWM effect.

## Отсечённые ложные выводы

panelDC — read-only software state, не setter и не register readback; source допускает
кэширование DC без DSI. Наличие v4, pvt и QDCM не выбирает live revision; default-panel
CN указывает на dummy. Generic PMIC PWM helper не применим автоматически к BOE
bl_ctrl_dcs; ALS pwmToDcDbv=3601 не задаёт PWM Hz. Отличающиеся DC packets и refresh
metadata не устанавливают оптические 720/167 Гц. Совпадение калибровок не доказывает
равенство boot/DTBO/driver/signers/policy.
Отсутствие AOSP settings key не доказывало placebo: используется другой provider,
`com.motorola.android.providers.settings`. Разные supply phandle numbers здесь
также не означают новое питание — разрешённые subtrees равны.

## Почему PWM-патча пока нет

| Требуемое доказательство | Состояние |
|---|---|
| Exact live IC/revision | **unknown**; повторные panel sysfs reads после OTA запрещены |
| BOE register/profile → optical Hz | **unknown**; page 0x2d/0x4f не расшифрованы по datasheet/оптике |
| Optical baseline и эффект stock profiles | **unknown**; измерений на этом экземпляре нет |
| Source-to-current-stock, config/KMI/ABI | GKI r59 baseline/root config+reference CRC pass; current Motorola image/vendor modules/signing не сопоставлены |
| Trusted originals / recovery | Cross-SKU ZIP не backup; target rollback counters и temporary boot не установлены |
| Разрешение kernel/display experiment | Отдельного approval нет |

Причина no-go — **не отсутствие native implementation**, а отсутствие panel-specific
оптического доказательства и безопасного source/recovery match. Есть место выбора profile,
но нет доказанного альтернативного профиля с нужным эффектом. Придумывать bytes,
делать пустой override или выдавать CN module за GLOBAL patch нельзя.

Из Pixel переносима только идея **inactive-by-default known-profile selection**:
exact panel guard, stock default, lock/initialized state, корректное восстановление при
enable/resume/refresh/HBM/FOD/AOD. Owner инварианта здесь — выбранные kernel panel
command sets, не UI и не read-only panelDC. Учитывать нужно **init/timing-switch,
а не только DC arrays**, с panel_lock/initialized checks и штатной обработкой ошибок.
Это target-specific design hypothesis, не готовый безопасный patch.

После root-этапа следующий PWM шаг — exact panel evidence и source/образы текущей OTA либо сохранение этого
блокера. Затем документированный read-only UI A/B с намеренным ручным переключением
владельцем и оптический baseline при одинаковых brightness/refresh/content/thermal условиях.
Осциллографа нет: доступное сравнение — камера/ощущения по `05-safety/optical_measurement.md`;
точные waveform, Hz, modulation и огибающая без достаточной metrology остаются unknown.
XT2611-3 остаётся только offline reference; одинаковые AVB keys не разрешают cross-flash
(CID/security-version и rollback metadata различаются).

Материалы: [CN разбор](cn_panel_commands.md), [GLOBAL inventory](eu_panel_commands.md),
[byte diff](regional_dtbo_diff.json), [current read-only snapshot](post_ota_display_observation.json),
[manifest](firmware_manifest.json), [callgraph](driver_callgraph.md), [сравнение](display_diffs.md).
В этапе регионального анализа 2026-10-28 выполнялись offline analysis и узкий read-only ADB. Настройки не менялись;
kernel build, optical test, flash, reboot и device writes в этой задаче **не выполнялись**.
Историческое уточнение 2026-11-06 06:53: прежнее сообщение об unlock было отозвано,
тогда ADB ещё показывал locked/green. **Позже** согласованный unlock завершён и normal
stock boot подтверждён: [актуальное состояние](bootloader_state.md),
[журнал](bootloader_worklog_2026-11-06.md). Unlock не повторять.

## 2026-11-06 09:38 — root-only component готов, deployment заблокирован

- `reported`, offline verified: pinned GKI r59 baseline собран, все 8085 config lines
  совпали с target и все 10210 exports/CRC — с official reference. Различия Image
  ограничены generated signing certificate/ELF notes; это не live Motorola byte-match.
- Root-only KernelSU-Next v3.4.2/code33355 compiled/offline pass: exports/CRC те же,
  CFI/SELinux/module protection не ослаблялись, Google public certificate реально
  сохранён через native trusted keys. Display/DTS не менялись. Скрипты/patch/проверки:
  [source_inventory.md](source_inventory.md),
  [root validation](kernel/gki_r59/kernelsu_next_validation.json).
- Обычный официальный Manager скачан, release digest и KSU certificate pin совпали;
  не установлен. Host full APK signature verification не запускалась; native PM
  verification обязательна. **Ни root на телефоне, ни PWM effect не подтверждены**.
- Blocker R2: отсутствует текущий Motorola boot original/header/restore, стандартный
  fetch не получил данных, реальные vendor modules/signers не прочитаны. Raw Image
  не подставляется в старый/cross-SKU boot. Image gates не пройдены, boot/flash не разрешены.
- Следующий узкий путь — authenticated LMSA catalogue/download точной прошивки:
  [auth docs](https://github.com/JoshRob297/moto-firmware-downloader/blob/main/docs/AUTHENTICATION.md).
  Нужны owner consent/login; client/Rescue/внешний ID query не запускались. Наличие
  exact post-OTA GLOBAL package пока unknown. Это пауза на внешнем входе, не отказ
  от обязательного постоянного root/PWM >=2000 и не завершение [контракта](unlock_pwm_recon_2026-11-06.md).
