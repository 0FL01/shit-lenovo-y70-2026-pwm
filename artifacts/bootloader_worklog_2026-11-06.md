# Журнал исполнения: unlock → KernelSU-Next → PWM

Дата: 2026-11-06. Общая цель и ограничения:
[execution contract](unlock_pwm_recon_2026-11-06.md#execution-contract--2026-11-06).
В журнале нет serial/IMEI/Device ID/unlock key. Пользовательские бекапы не требуются,
wipe принят; точные разрушительные операции согласуются отдельно.

## 07:23:26 UTC — старт R1/T00, preflight

- Основание: владелец поручил приступить к согласованному плану и вести журнал.
- Действия: read-only `adb devices`, `fastboot devices` и пять точечных `getprop`.
- `confirmed-on-target`: один авторизованный ADB аппарат, SKU `XT2611-1`, build
  `W3WWS36.65-64-4-1`, `ro.boot.flash.locked=1`, `ro.boot.vbmeta.device_state=locked`,
  `ro.boot.slot_suffix=_b`. Все запросы успешны; fastboot transport отсутствует.
- Следующий checkpoint: `adb reboot bootloader`, scoped read-only fastboot queries.
  Unlock/erase/flash/slot/AVB/root/DSI операции ещё не выполнялись.

## 07:24:44–07:24:57 UTC — bootloader transition и read-only state

- Разрешённое действие: `adb -s <omitted> reboot bootloader` → exit 0. Fastboot
  появился примерно через 12 секунд, единственный transport совпал с выбранным аппаратом.
- `confirmed-on-target`, чтение `fastboot -s <omitted> getvar <key>`:

| Key | Ответ загрузчика |
|---|---|
| `product` | `avr` |
| `sku` | `XT2611-1` |
| `hwrev` | `PVT` |
| `securestate` | `flashing_locked:SDP` |
| `current-slot` | `b` |
| `is-userspace` | `no` — это bootloader, не fastbootd |
| `version-bootloader` | `MBM-3.0-avr_g-0d80517c428a-260927-WW` + `WS36V.65-64-ST9.5-c9a7f` |
| `unlocked` | `not found`, remote `FAILED` |
| `battery-soc-ok` | `not found`, remote `FAILED` |

- У всех host exit code 0, включая remote FAILED; учитывается ответ протокола,
  а не один exit code. Отсутствующие переменные не трактуются как false/true.
- `fastboot -s <omitted> flashing get_unlock_ability` → protocol OKAY, но вместо
  численного флага загрузчик пишет: `use "oem get_unlock_data" and web portal`,
  `http://motorola.com/unlockbootloader`. Это target-specific подтверждение OEM flow,
  не доказательство eligibility или уже выполненного unlock.

## 07:25:35 UTC — unlock-data прочитаны, внешних запросов с ID нет

- Команда: `fastboot -s <omitted> oem get_unlock_data`; перед ней повторно подтверждены
  product/SKU/locked state/is-userspace. Protocol OKAY, без FAILED; пять hex/# chunks.
- Приватные файлы вне репозитория:
  `/home/stfu/.cache/opencode-tmp/opencode/xt2611-unlock-private-20261106/`:
  `get_unlock_data_response.txt` и `motorola_unlock_data.txt` (нормализованная строка).
  Каталог 0700, файлы 0600; значения не выводились в чат, журнал или repo artifacts.
- Официальному порталу Device ID не отправлен, ключ не запрошен и не получен.
  Unlock/erase/flash/AVB/slot/root/DSI операций нет. Телефон остаётся locked в bootloader.
- R1/T00: **blocked на owner-account/official-key шаге**. Нужны участие владельца
  в официальном portal flow либо уже полученный приватный ключ, затем отдельное
  подтверждение точной разрушительной unlock-команды. Не пробовать unlock без ключа
  или альтернативные команды наугад.
- Путь выхода без unlock: штатный `fastboot reboot` для возврата в Android;
  в этом checkpoint возврат ещё не выполнялся. Rescue после произвольного повреждения
  разделов не проверен; имеющиеся старые/cross-SKU образы не прошиваются.
- Пока ожидается внешний шаг R1, запущен независимый read-only аудит источников
  текущей OTA для R2/T03. Он не использует устройство и не меняет firmware.

## Следующее уточнение владельца — ключ уже получен

- `reported`: владелец выбрал «Ключ уже получен». Не запрашивать новый ключ и не
  отправлять Device ID на портал повторно. Существующий ключ ещё не прочитан:
  нужен путь к приватному локальному файлу; в закрытом каталоге пока только два
  ранее созданных unlock-data файла. В чужих каталогах секреты не искались.
- Точная destructive unlock-команда по-прежнему не выполнена и требует отдельного
  подтверждения после проверки исходных условий/ключа.

## 07:31 UTC — независимый source checkpoint для R2/T03

- Найден и проверен по первичным Google sources GKI r59:
  `android16-6.12-2025-12_r59`, commit
  `09eda8c8505ac19be9c4e063afa1d351c1ca9fe2`, kernel build `15950084`.
  Совпадают SHA-prefix и build ID из target uname; это не binary/config/KMI proof.
- Проверены Gitiles tag и реальные BUILD.bazel target/defconfig/ABI paths.
  Результат и пределы: [source_inventory.md](source_inventory.md).
- Checkout/сборки/kernel boot нет. Следующий root checkpoint: pinned build manifest,
  конечный config, текущие originals и vendor KMI; следующий unlock checkpoint:
  приватный key-file path от владельца, затем точная операция и подтверждение.

## 07:34 UTC — ключ предоставлен, предложение точной операции

- Владелец указал `artifacts/key`. Файл прочитан без вывода значения; формальный
  `KEY=<literal>` разобран без shell/source/eval. 20 ASCII alphanumeric characters,
  не placeholder; права ограничены до 0600. Совпадение ключа с аппаратом этой
  синтаксической проверкой не доказано; его проверит загрузчик. Ключ не копируется
  в журнал/отчёты/аргументы shell-команд в чат.
- Повторная read-only проверка 07:34:30 UTC: product avr, SKU XT2611-1, locked:SDP,
  slot b, is-userspace no. `battery-voltage=4325`; `battery-soc` unsupported/FAILED
  при host exit 0, процент заряда не установлен.
- Официальный последний portal instruction step требует авторизации (401);
  авторизация не обходилась. Target явно направляет на Motorola flow, владелец
  предоставил существующий ключ. Планируемый стандартный key-based Motorola вызов:
  `fastboot -s <выбранный transport> oem unlock <KEY из artifacts/key>`.
- Область подтверждения: только OEM unlock данного XT2611-1 с ожидаемым полным wipe
  и физическим подтверждением на телефоне при запросе. Перед вызовом вновь проверить
  SKU/securestate/mode. Ключ передавать напрямую argv subprocess, не shell; stdout/stderr
  санитизировать до публикации. При remote error/неожиданном запросе остановиться,
  не пробовать flashing unlock, critical-unlock или другие варианты вслепую.
- Не выполнять flash, AVB changes, slot changes, manual erase или relock. После
  успешного перехода прочитать securestate; штатно загрузить неизменённый Android,
  пройти первоначальную настройку после wipe и восстановить ADB с участием владельца.
- Выход до подтверждения: ничего не менять либо штатный `fastboot reboot`.
  Восстановление после повреждения разделов не проверено, matching current-build
  originals ещё отсутствуют; в этом OEM шаге образы не прошиваются. Доступ к stock
  recovery пока не проверен. Полной recovery-гарантии нет; root будет отдельной стадией.
- Состояние: **ожидается явное подтверждение этой операции**. Unlock ещё не выполнялся.

## Подтверждение владельца перед исполнением

- На конкретный запрос с `oem unlock`, ключом из `artifacts/key`, полным wipe,
  проверкой состояния и последующей штатной загрузкой владелец выбрал:
  **«Да, выполнить unlock»**. Образов/AVB/слотов это подтверждение не касается.
- Следующее действие: повторная проверка target identity/mode/locked state, один
  согласованный OEM unlock вызов; затем разбор санитизированного ответа, без blind retry.

## 07:37:09–07:37:24 UTC — OEM unlock выполнен успешно

- Повторно проверены product avr, SKU XT2611-1, locked:SDP, slot b, is-userspace no.
  Ровно один согласованный `fastboot -s <omitted> oem unlock <key>` вызов.
- Санитизированный ответ, host exit 0, продолжительность 14.796 s:

```text
(bootloader) Bootloader is unlocked!
OKAY [ 14.796s]
Finished. Total time: 14.796s
```

- Unlock key/transport identifiers удалялись из output до публикации. Других unlock
  команд, manual erase, flash, AVB/slot changes, root/DSI действий не было.
- Полный wipe был согласован и ожидается по OEM процедуре; фактический UI/data outcome
  ещё не наблюдался и не объявляется проверенным по одному сообщению unlock.

## 07:38:02–07:39:15 UTC — проверка состояния и normal stock reboot

- Независимый `getvar securestate` → **`flashing_unlocked:SDP`**; product avr,
  SKU XT2611-1, current-slot b, is-userspace no. Это проверка итогового unlock state,
  а не вывод из host exit 0/включённого Android toggle.
- Первый защитный reboot-check ожидал точную строку без `:SDP` и остановился **до
  reboot**. Ошибка была в ожидаемом формате проверки, не в OEM unlock. Повторного
  unlock не было; guard скорректирован на фактически прочитанный Motorola state.
- После повторной identity/state/mode проверки согласованный `fastboot reboot`
  принят 07:38:30 UTC: `Rebooting OKAY`, host exit 0. Ни один образ не прошивался.
- Один foreground `adb -s <omitted> wait-for-device` ограничен 45s и завершился
  timeout в 07:39:15 UTC. Это не диагноз bootloop: после wipe может потребоваться
  первоначальная настройка, включение USB debugging и новое RSA-подтверждение владельцем.
- **Финальный unlock verified; T00/R1 в целом пока blocked на post-wipe stock boot
  observation/ADB.** Не повторять unlock и не пробовать recovery/flash без причины.
  Следующий аппаратный шаг — наблюдение владельца и восстановление разрешённого ADB.

## 07:45 UTC — stock Android/ADB проверены, R1 завершён

- Владелец сообщил, что прошёл первоначальный экран и включил ADB debugging.
- `confirmed-on-target`: один авторизованный ADB target; `sys.boot_completed=1`,
  SKU XT2611-1, build W3WWS36.65-64-4-1, kernel g09eda8c8505a/ab15950084,
  `flash.locked=0`, `vbmeta.device_state=unlocked`, `verifiedbootstate=orange`,
  slot `_b`, UID 2000 shell и SELinux Enforcing. Все точечные запросы exit 0.
- **R1 verified / T00 done.** Root ещё не установлен; unlock не повторять.
- Evidence: [post_unlock_observation_2026-11-06.json](post_unlock_observation_2026-11-06.json).

## 07:46 UTC — подготовка root и пауза на recovery research

- Read-only `/proc/config.gz` доступен обычному shell; gzip проверен/распакован,
  сохранены 8085 строк фактической config и KSU-relevant flags (см. source inventory).
  GLOBAL mirror index всё ещё не содержит текущий post-OTA factory ZIP.
- Host `fastboot --help` подтверждает наличие команды `fetch PARTITION OUT_FILE`;
  **device-side fetch и temporary boot не проверялись**. Никаких fetch/reboot/flash
  экспериментов после Android boot не выполнялось.
- Владелец остановил дальнейшие действия для исследования TWRP/OrangeFox и явно
  попросил `@general`. Агенту переданы target/boot/root/source/config facts, запрет
  device/file changes и чтения ключа; запущен read-only research. Новые действия
  с телефоном на паузе, root/recovery не устанавливаются без отдельного proposal.
- Проверка артефактов пройдена: YAML/JSON, статусы/зависимости задач, boot facts,
  8085 config lines/сохранённые flags, локальные ссылки и отсутствие ключа в публичных
  документах. Ключ остаётся 0600; валидация к телефону не обращалась.

## Recovery research decision — основная работа возобновлена

- @general завершил read-only исследование: community AVR ports есть, но применимость
  к текущему build не установлена; некоторые releases явно неработоспособны.
  Для root custom recovery не обязательна и не даёт независимого от boot-kernel rescue.
- Владелец: «обойдёмся без кастом рекавери, продолжай работать по плану».
  Recovery не устанавливается/не портируется. Следующий checkpoint R2 — read-only
  bootloader fetch/readback с возвратом в Android, не новая прошивка.

## 07:55:47–07:58:53 UTC — bootloader fetch не поддерживается, Android возвращён

- После проверки Android identity/build/unlocked state выполнен согласованный reboot
  в bootloader. Проверены avr/XT2611-1, flashing_unlocked:SDP, slot b, is-userspace no.
- `max-fetch-size` → not found/remote FAILED. Partition sizes: boot_b/vendor_boot_b
  `0x6000000` (96 MiB), recovery_b `0x8000000` (128 MiB).
- Один `fastboot fetch boot_b` → exit 1: `Unable to get max-fetch-size. Device does
  not support fetch command.` 0 bytes, пустой output удалён; оригинал не получен.
  Никаких других OEM/readback/recovery протоколов наугад не пробовали.
- Обычный `fastboot reboot` принят; ADB вернулся. В 07:58:53 UTC boot_completed=1,
  прежняя сборка, flash.locked=0 и слот `_b`. Без flash/erase/AVB/slot/root/DSI изменений.
- Машиночитаемая запись: [boot_readback_2026-11-06.json](boot_readback_2026-11-06.json).

## 08:00–08:03 UTC — Google GKI config match и точный manifest

- Скачан официальный r59 certified ZIP (16 829 063 bytes), проверен CRC member
  `boot-6.12.img`. Извлечён IKCONFIG; все 8085 строк побайтово равны target config.
  Google boot — header v4/ramdisk 0/64 MiB; не Motorola boot_b original и не flash candidate.
- Получен CI `manifest_15950084.xml` (8185 bytes, 50 pinned project SHA), включая
  exact common/kernel-build/Clang pins. Эфемерный signed download URL не сохранялся.
- Начат background checkout только kernel/common и kernel/build для baseline.
  Это получение исходников, не сборка и не патч. Итог checkout ещё не известен;
  успех не заявляется до уведомления процесса. Подробности: [source_inventory.md](source_inventory.md).

## 08:06–08:16 UTC — source checkout verified, toolchain preparation начата

- Core source job завершился успешно: common HEAD 09eda8c8505ac19be9c4e063afa1d351c1ca9fe2,
  build/kernel HEAD a71b075c1d43d226779d2e834433e7a1d1885beb. Деревья перенесены в
  `sources/gki-15950084/{common,build/kernel}` для корректного Kleaf workspace path.
- Исходники подтверждают Clang r536225/Rust 1.82.0.p1/KMI generation 6; legacy
  build.config.gki.aarch64 не является текущим GKI build entrypoint.
- Начата фоновая подготовка только зависимостей native Kleaf/Bzlmod из exact manifest,
  с двумя Git jobs и sparse Clang checkout без ненужной r547379. Никакого build пока нет;
  ожидается уведомление, polling не выполняется. Результат — workspace_prepare.json.
- Получен официальный CI Module.symvers, 633144 bytes/10210 symbols, как будущий
  CRC reference. Никаких выводов об уже совместимом root kernel не делалось.
- С телефоном после подтверждённого normal Android return больше не взаимодействовали.

## 08:26–08:37 UTC — baseline build запущен, pinned KSU проверен офлайн

- Подготовка workspace завершилась: 29 exact project HEADs verified, без ошибок.
  Clang 19.0.1/r536225, Rust 1.82.0-dev/linux-15123656, Bazel 8.0.0 доступны.
- Создан `06-tools/build_gki_baseline.sh` (unmodified kernel target only, no device calls).
  Первый build attempt завершился за 6s до компиляции: workspace stamp попытался
  проверить нескачанный external/dtc из полного CI manifest. Error log сохранён.
- Script переведён на документированный native-Git stamping via extra_git_project;
  KMI/config checks и источники ядра не изменены. Следующий build job запущен;
  результат неизвестен, polling не выполняется. Нет пока baseline pass/root image.
- Pinned KernelSU-Next v3.4.2 source HEAD verified; setup.sh не запускался. Для его
  Kbuild/Manager compatibility получены pinned ancestry metadata: 3355 commits,
  upstream code33355/tagv3.4.2. Default authorization сохраняется в плане; root source
  не интегрирован до baseline success. Всё это офлайн, без новых действий с телефоном.

## 08:40–09:38 UTC — baseline/root build pass, Manager подготовлен; внешний blocker

- В 08:40:22 native-Git baseline build завершился exit0. В 08:44 проверены все
  8085 config lines (byte-equal target) и 10210 exports/CRC (равны official reference).
  Kernel Image того же размера/полной version string, но 1116 bytes отличаются.
- В 08:51 доказано, что все отличия — built-in public signing certificate и ELF notes.
  Target MODULE_SIG_PROTECT/TRIM_UNUSED_KSYMS нельзя отключать ради загрузки GKI modules.
  Извлечён только публичный Google reference certificate, не private key/handset secret.
- Минимальная built-in KSU integration: driver entries/symlink, existing fallback
  version variables33355/v3.4.2 и native trusted-keys path с Google public certificate.
  Local generated build certificate остаётся; actual live Motorola trust ещё unknown.
  Зафиксирован `artifacts/kernelsu_next_patch.diff`, display/DTS не менялись.
- `bash 06-tools/build_gki_kernelsu_next.sh` в 09:08:30 завершился exit0. В 09:18
  offline validation passed: CONFIG_KSU=y, debug/disable-manager/disable-policy=n,
  только ожидаемые config deltas; все 10210 exports/CRC retained; Google certificate,
  builtin init/hook symbols и compiled33355/v3.4.2 присутствуют. Raw Image 41638400 bytes,
  hash и полный dirty release — в `artifacts/kernel/gki_r59/kernelsu_next_validation.json`.
  Ни boot packaging, ни deployment approval этим не получены.
- В 09:29 скачан обычный, **не spoofed**, официальный Manager33355; release asset
  digest совпал. V2 signer certificate998 bytes/SHA256 совпал с Kbuild authorization pin.
  APK не установлен. Host full signature verification не запускалась; native Android
  PM verification остаётся обязательной. Никаких новых host dependencies не установлено.
- Public firmware-client docs описывают authenticated LMSA catalogue/Lenovo browser
  login; alternate OTA example требует unique IDs. Только прочитана документация:
  client/installer/login/Rescue/запросы с идентификаторами **не запускались**.
- R2 deployment blocked: current Motorola boot/header/restore и actual vendor module
  signing/ABI не получены. Запрашивается отдельное consent на read-only catalogue и
  owner login, без Rescue/flash и пока без serial/IMEI. Exact package availability unknown.
  С телефоном после 07:58 больше не взаимодействовали; root/UID0/PWM не подтверждены.

## После 09:51 UTC — LMSA consent, client audit и login handoff

- Владелец выбрал «Каталог LMSA»: только authenticated search/download, без Rescue,
  прошивки и пока без IMEI/serial. Это не расширяет разрешения на телефон.
- Закреплён/изучен MFD1.3.4, commit b5ea93abf5bc02ee56f5f7a9601320b9d80e3396.
  Временный source/state — private approved cache. Node22 уже установлен; installer,
  GUI, CLI wizard, `imei` command и новые dependencies не запускались.
- Для ссылки использован native HTTPS request по проверенному getLoginUrl protocol:
  официальный lsa.lenovo.com, HTTP200/code0000; validated passport-glb.lenovo.com
  authorize URL и официальный redirect. GUID/clientUUID — random session markers,
  не идентификаторы телефона. Никаких account credentials агент не отправлял.
- Login URL и пустой token input — вне repo, directory0700/files0600; публичный
  `artifacts/lmsa_catalog_2026-11-06.json` содержит только scope/provenance/status.
  Ожидается личный browser login владельца и запись token в приватный файл, не чат.
  Ни успешная авторизация каталога, ни наличие exact firmware ещё не подтверждены.

## Owner token ready — authenticated catalogue и недостающий FSG

- Callback JSON code0000/content URI принят структурно; две локальные preflight
  проверки обёртки не отправляли запросов/секрета. Один native CLI login --token-file
  завершился exit0, session saved0600 в private HOME; stdout/stderr не опубликованы.
- Model-only запросы успешны: XT2611-1/Legion Phone Y70 New Generation/Qcom и XT2611-3/
  motorola edge 70 max есть среди 1117 catalogue models. Требуются fingerPrint,
  fsgVersion.qcom, roCarrier. readSupport flag не объявляется partition readback.
- Source-backed manual getResource вернул null code/content для -1: результат отвергнут.
  Изучен отдельный readSupport getNewResource caller с optional IMEI/SN, без GUI/Rescue.
- В 10:29 выполнены только allowlisted read-only getprop: identity/build guard пройден,
  текущий fingerprint/teleu прежние; ro.boot.fsg-id пуст, baseband M8845_DE90_31.179.01.104.17R.
  Транспортный ID только для выбора единственного ADB target, не опубликован/не передан API.
- getNewResource/matchType1 для двух моделей с actual fingerprint/carrier, empty unknown
  FSG и без IMEI/SN → HTTP200/code0001/Parameters lack/null. Не «firmware отсутствует».
  Radio version вместо FSG не подставляли, другие значения не придумывали.
- Предлагается отдельный metadata-only bootloader roundtrip за version-baseband/fsg-id,
  затем штатный Android return. Пока не согласован/не выполнен. Никаких новых reboot,
  unlock/boot-image/flash/erase/AVB/slot/DSI изменений не было; root/PWM не установлены.

## 10:54:45–11:04:35 — согласованное чтение FSG и безопасный возврат

- Owner selected «Да, только чтение»: metadata-only bootloader roundtrip, no image permission.
- Android SKU/build/_b/boot_completed guard passed; adb reboot bootloader accepted.
  Fastboot productavr/skuXT2611-1/slotb/is-userspaceno verified. Only agreed version-baseband
  and fsg-id queried: first literal Done, second remote not-found/FAILED despite host0.
  No FSG label, no blind alternate OEM calls, no radio-version substitution.
- fastboot reboot accepted; at10:55:28 boot_completed1/currentW3WWS36.65-64-4-1/XT2611-1/_b
  confirmed. No raw partition/image writes, erase, AVB/slot change or new DSI sequence.
- Bounded fallback: Android property filter only three dev.mnt.*.vendor.fsg keys;
  getResource GLOBAL -3 returned HTTP200/null code/null content. /vendor/fsg exists0755,
  ls listing denied. No modem/NV file contents read, no permissions/policy changed.
- Result: FSG unresolved; no trusted current Motorola boot/header/restore or vendor proof,
  R2/root still blocked, R3 untouched. Next proposed supported catalogue path uses IMEI:
  official Lenovo only, separate owner consent/private file required, not sent/permitted yet.

## RAM-first simplification and first packaged image

- Owner requested simpler AGENTS/plan and continued work. RAM bootstrap separated from
  persistent writes; no FSG/IMEI/full-ROM prerequisite, no per-command read-only approvals.
- Native pinned mkbootimg packaged validated KSU33355 kernel as v4 RAM-only boot image,
  41644032B; payload identity/header/padding checks passed. Exact SHA/proof/command in
  `artifacts/flash_proposal.md`; no old/cross-SKU payload or copied signature.
- Fresh11:32 read-only preflight confirms unchanged stock r59/current build/_b/unlocked/
  orange/Enforcing. No images applied. Await physical bootloader entry and one RAM-trial
  approval covering Manager/research-root/original-boot readback/stock return, never flash.

## 11:43–12:08 — RAM root passed, current original obtained, permanent image prepared

- One approved fastboot boot accepted; exact r59-dirty/build/_b/Enforcing booted.
  msm_drm/current vendor modules loaded. Native PM verified/installed normal Manager;
  Manager reports Working/BUILT-IN/33355. Granted only com.android.shell through its UI;
  su returnedUID0. UI initially asleep; waking/displaying within one command resolved capture.
- Read unchanged boot_b96MiB to host; kernel byte-equals Google r59, native AVB hash valid.
  Actual current msm_drm.ko also acquired. Primary proof: `kernel/gki_r59/kernelsu_next/ram_trial.json`.
- Shell-level reboot denied; corrected to host adb reboot, stock/no-dirty/_b/Enforcing and
  boot_completed verified11:54. No partition image writes in RAM trial.
- Native AVB packaged permanent image with same tested payload and actual stock metadata,
  both original/candidate hash-verified. Exact write/rollback in flash_proposal experiment2.
- Owner requests permanent kernel and Android PWM controls: session default, separate
  opt-in persistence checkbox, stock rollback. Hardware lever still unknown; no speculative UI.

## 12:18–12:26 UTC — permanent root DONE, live panel identified

- Separate owner-approved experiment2 wrote boot_b exactly once. First guard rejected
  zero-padded size formatting before any write; numeric hex parsing fixed it, stock
  return verified before continuing. UID0/Enforcing/build/_b/msm_drm verified after
  flash boot and again after ordinary adb reboot at12:19. Primary proof:
  [persistent/install.json](kernel/gki_r59/kernelsu_next/persistent/install.json).
- Original boot_b96MiB, identity/restore command and known-good root-only baseline
  retained in [flash_proposal.md](flash_proposal.md). No other partition/AVB/slot change.
- Read-only root identified BOE ILI97701A cmd_v4/ID0xd2/Ver0 in sysfs/boot selector/live DT.
  Saved425 properties; all53 compared command arrays match GLOBAL reference, DC875B
  ON/OFF also equal CN. Physical silicon revision and actual optical Hz remain unknown.
  ScreenOFF/panelDC0/provider null after wipe; historical key1 is not current.

## Owner research hint — primary-source and byte checks

- Verified ITH IL97701A product card and BOE CN119811288A text: ILI97680a example,
  EM1/18, gamma/duty/CMDQ, not target register map. Checked candidate bytes against
  actual live v4 and ordered archive DC arrays; short switches shared across families,
  A2/F0/F2/F3 organization already in97701A v2/v3. No field given an invented meaning.
- Saved [DC transition analysis](dc_transition_recon_2026-11-06.md) and bounded next
  stock observation/camera plan. No new device writes/toggles/logging/DSI trials here.
  R1/R2 verified, R3 active; PWM unchanged. No oscilloscope required for qualitative trials.

## 13:14–13:21 UTC — stock trace preflight, no setting writes

- Fresh read-only root/build/slot/Enforcing verified; logger0, screenOFF/DC0, saved
  brightness78/auto1/min-peak absent. Kprobe events supported; function tracer absent
  by actual config, not a new kernel-build blocker. No probes/logger enabled yet.
- Read actual vendor DC service/HAL/V2 ELF files: all byte-equal available CN copies.
  Historical GLOBAL extraction absent; changed comparison to available concrete CN
  reference, preserving distinction from prior CN/GLOBAL equivalence evidence.
- Primary-source follow-up found no target register map. BOE/Honor strengthen low-DBV
  DC OFF/high-pulse hypothesis; real named Qualcomm emsync path is not configured here.
  Prepared one stock UI A/B/diagnostic proposal with cleanup, no image/new register writes.

## 13:49:24–13:49:52 UTC — approved stock A/B and cleanup passed

- Owner selected «Да, запускай». OEM inline Flicker prevention UI, manual78/40 and
  requested120Hz used; preparation tap unexpectedly toggled inline ON, explicitly
  recorded, then OFF restored within experiment. No guessed binder/raw ioctl/DSI values.
- Six phase states verified;579 MIPI writes include six exact75-packet ON/OFF sets.
  Actual settled DBV5197/2839; software active mode120.00001Hz. Native return/probe
  evidence and initial-wake marker caveat: [trace analysis](stock_dc_trace_analysis_20261106.json).
- No negative native return/known transfer failure log/missed own probes, buffer590/590.
  Cleanup verified DC0/logger0/auto1/min-peak absent/own probes+instance gone. Original
  null custom key becomes explicit0, effective OFF restored. No image/new profile writes.
- `python3 -m py_compile 06-tools/trace_stock_dc.py` and actual collector run passed;
  [execution record](stock_dc_trial_20261106.json). No camera/optical result fabricated;
  next needs camera/brief voluntary owner comparison, stop at discomfort.

## 14:09:21–14:10:42 UTC — separate camera presentation completed

- Owner selected «Готов снимать сейчас». Four conditions78-OFF/78-ON/40-OFF/40-ON
  held12s each after UI/native-state/brightness checks; requested120Hz. No tracing,
  image write or new DSI profile. Cleanup DC0/auto1/min-peak absent/logger0 verified.
- Owner reports ~90s video/five states ending with broad-stripe return after reset.
  [Baseline](optical_baseline.md) keeps exact observations and provisional mapping;
  no-bands in state4 is not a higher-frequency measurement. Clip not yet received.
- Next input is recording/path, not another unobserved device change. Host ffmpeg and
  ffprobe are available for inspection without installing dependencies.

## Supplied video inspected offline — no device actions

- Owner supplied `/home/stfu/Torrents/Android/VID_20261106_170959931_rotated_180.mp4`.
  ffprobe:87.810585s,HEVC1080×1920,359/12fps. Switch~10/25.8/41/56.6s matches four
  native taps, offset spread0.287s. Full/sequence frames inspected; audio untouched.
- Actual scene is light theme, not prior dark-theme assumption. Low-OFF fine bands
  visible before USB overlay; low-ON less visibly banded. Handheld motion/moiré/scrim
  prevent treating picture codes/stripe speed as physical Hz/duty. Fixed edge-ROI
  metric discarded after motion crossed the screen border; no claim based on it.
- [Analysis](video_analysis_20261106.json), [baseline](optical_baseline.md) updated;
  original file unmodified. Candidate mode4 needs reference/voluntary usefulness
  comparison; no numerical PWM success or medical-safety claim.
